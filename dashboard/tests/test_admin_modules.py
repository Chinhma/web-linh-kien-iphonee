"""Kiểm thử các module Admin Panel (SPEC_ADMIN_PANEL bước 7–11)."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from chatbot.models import ChatbotSetting
from core.models import FAQ, Banner, ContactMessage, StoreSetting
from core.tests.factories import make_admin, make_customer
from orders.views import enabled_payment_methods

User = get_user_model()
AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest', 'content_type': 'application/json'}


class ContentModuleTests(TestCase):
    def setUp(self):
        self.admin = make_admin('sa', superuser=True)
        self.client.force_login(self.admin)

    def test_reorder_banners_and_faq(self):
        b1, b2, b3 = (Banner.objects.create(title=f'B{i}', display_order=i) for i in range(3))
        res = self.client.post(reverse('dashboard:reorder', args=['banner']), json.dumps({'ids': [b3.pk, b1.pk, b2.pk]}), **AJAX)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(Banner.objects.order_by('display_order').values_list('pk', flat=True)), [b3.pk, b1.pk, b2.pk])
        f1, f2 = FAQ.objects.create(question='a', answer='a'), FAQ.objects.create(question='b', answer='b')
        self.client.post(reverse('dashboard:reorder', args=['faq']), json.dumps({'ids': [f2.pk, f1.pk]}), **AJAX)
        f2.refresh_from_db()
        self.assertEqual(f2.display_order, 1)
        self.assertEqual(self.client.post(reverse('dashboard:reorder', args=['product']), '{}', **AJAX).status_code, 404)

    def test_markdown_preview_escapes_html(self):
        res = self.client.post(reverse('dashboard:markdown_preview'), json.dumps({'text': '## Tiêu đề\n<script>x</script>'}), **AJAX)
        html = res.json()['data']['html']
        self.assertIn('<h3', html)
        self.assertNotIn('<script>', html)

    def test_contact_status_toggle(self):
        msg = ContactMessage.objects.create(name='A', email='a@example.com', message='Xin chào')
        self.assertContains(self.client.get(reverse('dashboard:contacts')), 'Xin chào')
        self.client.post(reverse('dashboard:contact_read', args=[msg.pk]))
        msg.refresh_from_db()
        self.assertTrue(msg.is_read)
        self.assertNotContains(self.client.get(reverse('dashboard:contacts')), 'Xin chào')
        self.assertContains(self.client.get(reverse('dashboard:contacts') + '?status=done'), 'Xin chào')

    def test_chatbot_settings_save_suggestions(self):
        res = self.client.post(reverse('dashboard:chatbot_settings'), {
            'is_enabled': 'on', 'greeting_message': 'Chào bạn', 'suggested_questions_text': 'Câu 1\nCâu 2\n\n',
            'extra_store_info': '', 'max_messages_per_hour_guest': 10, 'max_messages_per_hour_customer': 30})
        self.assertEqual(res.status_code, 302)
        self.assertEqual(ChatbotSetting.get_solo().suggested_questions, ['Câu 1', 'Câu 2'])

    def test_store_settings_tabs_open(self):
        for tab in ('info', 'shipping', 'contact', 'integrations'):
            self.assertEqual(self.client.get(reverse('dashboard:store_settings') + f'?tab={tab}').status_code, 200)

    def test_cod_toggle_affects_checkout_methods(self):
        store = StoreSetting.get_solo()
        store.enable_cod = False
        store.save()
        self.assertFalse(enabled_payment_methods()['cod'])


class AdminAccountTests(TestCase):
    def setUp(self):
        self.sa = make_admin('sa', superuser=True)
        self.client.force_login(self.sa)

    def test_random_temp_password_shown_once(self):
        res = self.client.post(reverse('dashboard:admin_accounts'), {'full_name': 'Nhân viên', 'email': 'nv@example.com', 'password': ''})
        self.assertEqual(res.status_code, 302)
        page = self.client.get(reverse('dashboard:admin_accounts'))
        self.assertContains(page, 'chỉ hiển thị một lần')
        password = page.context['new_credential']['password']
        self.assertTrue(User.objects.get(email='nv@example.com').check_password(password))
        self.assertIsNone(self.client.get(reverse('dashboard:admin_accounts')).context['new_credential'])

    def test_cannot_lock_or_revoke_self(self):
        for action in ('lock', 'revoke', 'superuser'):
            self.client.post(reverse('dashboard:admin_account_action', args=[self.sa.pk]), {'action': action})
        self.sa.refresh_from_db()
        self.assertTrue(self.sa.is_active and self.sa.is_staff and self.sa.is_superuser)

    def test_lock_and_unlock_other_superuser(self):
        other = make_admin('sa2', superuser=True)
        url = reverse('dashboard:admin_account_action', args=[other.pk])
        self.client.post(url, {'action': 'lock'})
        other.refresh_from_db()
        self.assertFalse(other.is_active)
        self.client.post(url, {'action': 'lock'})  # mở khóa lại được dù chỉ còn 1 superuser đang hoạt động
        other.refresh_from_db()
        self.assertTrue(other.is_active)


class CustomerAndReviewTests(TestCase):
    def setUp(self):
        self.client.force_login(make_admin('sa', superuser=True))
        self.customer = make_customer()

    def test_customer_pages(self):
        self.assertContains(self.client.get(reverse('dashboard:customer_list')), 'Mới trong 30 ngày')
        for tab in ('orders', 'addresses', 'reviews', 'chats'):
            url = reverse('dashboard:customer_detail', args=[self.customer.pk]) + f'?tab={tab}'
            self.assertEqual(self.client.get(url).status_code, 200)

    def test_review_tabs(self):
        for status in ('all', 'pending', 'approved', 'hidden'):
            self.assertEqual(self.client.get(reverse('dashboard:review_list') + f'?status={status}').status_code, 200)


class ProductImageUploadTests(TestCase):
    def test_upload_multiple_images(self):
        import io
        import shutil
        import tempfile

        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from PIL import Image

        from core.tests.factories import make_product
        from dashboard.forms import ProductImagesForm

        def png(name):
            buf = io.BytesIO()
            Image.new('RGB', (20, 20), 'red').save(buf, 'PNG')
            return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')

        from django.utils.datastructures import MultiValueDict
        form = ProductImagesForm({}, MultiValueDict({'images': [png('a.png'), png('b.png')]}))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(len(form.cleaned_data['images']), 2)
        self.assertTrue(ProductImagesForm({}, MultiValueDict()).is_valid())  # không chọn ảnh vẫn hợp lệ

        media = tempfile.mkdtemp()
        try:
            with override_settings(MEDIA_ROOT=media):
                product = make_product()
                from dashboard.views.catalog import _save_images
                from django.contrib.messages.storage.fallback import FallbackStorage
                from django.test import RequestFactory
                req = RequestFactory().post('/', {'images': [png('c.png'), png('d.png')]})
                req.session = {}
                req._messages = FallbackStorage(req)
                _save_images(req, product)
                self.assertEqual(product.images.count(), 2)
                self.assertEqual(product.images.filter(is_primary=True).count(), 1)
        finally:
            shutil.rmtree(media, ignore_errors=True)


class CategoryDeleteTests(TestCase):
    def setUp(self):
        from core.tests.factories import make_category, make_product

        self.client.force_login(make_admin('sa', superuser=True))
        self.old = make_category('Cáp và linh kiện khác', 'OTH')
        self.target = make_category('Pin', 'BAT')
        self.child = make_category('Cáp sạc', 'CBL')
        self.child.parent = self.old
        self.child.save()
        self.p1 = make_product('Cáp A', sku='S1', category=self.old)
        self.p2 = make_product('Cáp B', sku='S2', category=self.old)

    def test_delete_moves_products_and_children(self):
        url = reverse('dashboard:category_delete', args=[self.old.pk])
        self.assertContains(self.client.get(url), 'Chuyển 2 sản phẩm')
        # chưa chọn đích → không xóa
        self.client.post(url, {})
        self.assertTrue(type(self.old).objects.filter(pk=self.old.pk).exists())
        self.client.post(url, {'move_products_to': self.target.pk, 'move_children_to': ''})
        self.assertFalse(type(self.old).objects.filter(pk=self.old.pk).exists())
        self.p1.refresh_from_db()
        self.child.refresh_from_db()
        self.assertEqual(self.p1.category, self.target)
        self.assertIsNone(self.child.parent)
