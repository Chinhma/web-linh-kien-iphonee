"""Smoke test: mọi mục trong sidebar Admin Panel mở được (200) và phân quyền Admin theo SPEC_ADMIN_PANEL A5."""

import json

from django.test import TestCase
from django.urls import reverse

from core.tests.factories import make_admin, make_customer, make_model, make_product, verify
from dashboard.menu import MENU
from products.models import Product

AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest', 'content_type': 'application/json'}


from dashboard.menu import _url  # noqa: E402


def menu_urls():
    for _title, items in MENU:
        for item in items:
            for node in [item, *item.children]:
                if node.url_name:
                    yield _url(node)


class AdminPanelPagesTests(TestCase):
    def setUp(self):
        self.admin = make_admin('sa', superuser=True)
        self.product = make_product()
        verify(self.product, make_model())

    def test_every_menu_page_opens(self):
        self.client.force_login(self.admin)
        for url in set(menu_urls()):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_detail_pages_open(self):
        self.client.force_login(self.admin)
        for url in [reverse('dashboard:product_edit', args=[self.product.pk]), reverse('dashboard:category_edit', args=[self.product.category_id])]:
            self.assertEqual(self.client.get(url).status_code, 200)


class AdminPermissionTests(TestCase):
    """SPEC_ADMIN_PANEL A5."""

    def setUp(self):
        self.admin = make_admin('ad', superuser=False)
        self.product = make_product()

    def test_admin_cannot_purchase(self):
        self.client.force_login(self.admin)
        r = self.client.post('/api/cart/add/', json.dumps({'product_id': self.product.pk}), **AJAX)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['code'], 'ADMIN_CANNOT_PURCHASE')
        for url in ['/thanh-toan/', '/yeu-thich/', '/gio-hang/', '/tai-khoan/']:
            self.assertRedirects(self.client.get(url), '/', fetch_redirect_response=False, msg_prefix=url)

    def test_admin_sees_draft_customer_404(self):
        draft = make_product('Nháp', 'IP-BAT-DRAFT-001', status=Product.Status.DRAFT)
        self.client.force_login(self.admin)
        r = self.client.get(draft.get_absolute_url())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Công cụ quản trị')
        self.client.force_login(make_customer())
        self.assertEqual(self.client.get(draft.get_absolute_url()).status_code, 404)

    def test_customer_403_guest_redirect(self):
        self.assertTrue(self.client.get('/quan-tri/')['Location'].startswith('/quan-tri/dang-nhap/'))
        self.client.force_login(make_customer())
        self.assertEqual(self.client.get('/quan-tri/').status_code, 403)

    def test_regular_admin_cannot_manage_admins(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('dashboard:admin_accounts')).status_code, 403)
        self.assertEqual(self.client.get('/admin/').status_code, 302)  # Django admin chỉ Superuser

    def test_admin_header_and_login_stays_on_site(self):
        from core.tests.factories import PASSWORD

        r = self.client.post('/dang-nhap/', {'identifier': 'ad', 'password': PASSWORD})
        self.assertEqual(r['Location'], '/')
        home = self.client.get('/')
        self.assertContains(home, 'Vào trang quản trị')
        self.assertNotContains(home, 'aria-label="Giỏ hàng"')
