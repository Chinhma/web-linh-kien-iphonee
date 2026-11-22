"""Test phân quyền và xác thực (Phần 19.1)."""

import json

from django.core.cache import cache
from django.test import TestCase

from orders.models import Order

from .factories import PASSWORD, make_admin, make_customer, make_product

AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest', 'content_type': 'application/json'}


class PermissionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.customer = make_customer()
        self.product = make_product()

    def test_guest_cart_api_returns_401(self):
        r = self.client.post('/api/cart/add/', json.dumps({'product_id': self.product.pk}), **AJAX)
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()['code'], 'LOGIN_REQUIRED')

    def test_guest_checkout_redirects_with_next(self):
        r = self.client.get('/thanh-toan/')
        self.assertRedirects(r, '/dang-nhap/?next=/thanh-toan/', fetch_redirect_response=False)

    def test_customer_admin_area_403(self):
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get('/quan-tri/').status_code, 403)

    def test_guest_admin_area_redirects_to_admin_login(self):
        r = self.client.get('/quan-tri/')
        self.assertTrue(r['Location'].startswith('/quan-tri/dang-nhap/'))

    def test_customer_cannot_view_other_order(self):
        other = make_customer('khac')
        order = Order.objects.create(user=other, recipient_name='A', recipient_phone='0889400470', recipient_email='a@a.vn',
                                     province_code='01', province_name='Thành phố Hà Nội', ward_code='00166', ward_name='Phường Cầu Giấy', street_address='1', subtotal=1, total=1)
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(f'/tai-khoan/don-hang/{order.code}/').status_code, 404)

    def test_profile_form_ignores_is_staff(self):
        self.client.force_login(self.customer)
        self.client.post('/tai-khoan/thong-tin/', {'full_name': 'Tên Mới', 'phone': '0912345678', 'is_staff': 'on', 'is_superuser': 'on'})
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.full_name, 'Tên Mới')
        self.assertFalse(self.customer.is_staff)
        self.assertFalse(self.customer.is_superuser)

    def test_next_to_external_domain_ignored(self):
        r = self.client.post('/dang-nhap/?next=https://evil.com/', {'identifier': 'khach', 'password': PASSWORD})
        self.assertEqual(r['Location'], '/')

    def test_admin_cannot_buy(self):
        self.client.force_login(make_admin())
        r = self.client.post('/api/cart/add/', json.dumps({'product_id': self.product.pk}), **AJAX)
        self.assertEqual(r.status_code, 403)

    def test_google_user_never_staff(self):
        from allauth.socialaccount.models import SocialAccount, SocialLogin
        from django.test import RequestFactory

        from accounts.adapters import SocialAccountAdapter
        from accounts.models import User

        request = RequestFactory().get('/')
        sociallogin = SocialLogin(user=User(email='g@gmail.com', is_staff=True, is_superuser=True),
                                  account=SocialAccount(provider='google', uid='1', extra_data={'name': 'G User', 'email': 'g@gmail.com'}))
        user = SocialAccountAdapter().populate_user(request, sociallogin, {'email': 'g@gmail.com'})
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.auth_provider, 'google')


class GoogleStaffBlockTests(TestCase):
    """Email Google trùng tài khoản Admin -> bị từ chối, không liên kết, không đăng nhập vào Admin."""

    def test_google_cannot_login_staff(self):
        from allauth.core.exceptions import ImmediateHttpResponse
        from allauth.socialaccount.models import SocialAccount, SocialLogin
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory

        from accounts.adapters import SocialAccountAdapter
        from accounts.models import User

        make_admin()  # email quantri@example.com
        request = RequestFactory().get('/')
        request.session = self.client.session
        request._messages = FallbackStorage(request)
        sociallogin = SocialLogin(user=User(email='quantri@example.com'), account=SocialAccount(
            provider='google', uid='99', extra_data={'email': 'quantri@example.com', 'email_verified': True}))
        with self.assertRaises(ImmediateHttpResponse):
            SocialAccountAdapter().pre_social_login(request, sociallogin)
        self.assertFalse(SocialAccount.objects.exists())


class AuthTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_customer('nguoidung', 'NguoiDung@Example.com')

    def _register(self, email):
        return self.client.post('/dang-ky/', {'full_name': 'Trần Văn B', 'email': email, 'phone': '0912345678',
                                             'password1': 'Matkhau123', 'password2': 'Matkhau123', 'terms': 'on'})

    def test_register_duplicate_email_case_insensitive(self):
        r = self._register('NGUOIDUNG@example.com')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Email này đã được sử dụng')

    def test_register_logs_in(self):
        r = self._register('moi@example.com')
        self.assertEqual(r.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)

    def test_login_with_email_and_username(self):
        for identifier in ('nguoidung@example.com', 'nguoidung'):
            self.client.logout()
            r = self.client.post('/dang-nhap/', {'identifier': identifier, 'password': PASSWORD})
            self.assertEqual(r.status_code, 302, identifier)

    def test_lock_after_5_failures(self):
        for _ in range(5):
            self.client.post('/dang-nhap/', {'identifier': 'nguoidung', 'password': 'sai'})
        r = self.client.post('/dang-nhap/', {'identifier': 'nguoidung', 'password': PASSWORD})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'sai quá nhiều lần')

    def test_logout_get_has_no_effect(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/dang-xuat/').status_code, 405)
        self.assertIn('_auth_user_id', self.client.session)
        self.client.post('/dang-xuat/')
        self.assertNotIn('_auth_user_id', self.client.session)
