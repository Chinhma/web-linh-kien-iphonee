"""Adapter tùy biến cho django-allauth (đăng nhập Google).

Quy tắc bảo mật: đăng nhập Google KHÔNG BAO GIỜ cấp quyền Admin (is_staff / is_superuser luôn False).
"""

import logging

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

from core.permissions import safe_next_url

logger = logging.getLogger('iparts')


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        # Đăng ký bằng form của allauth bị tắt, chỉ dùng form /dang-ky/ của iParts (Google vẫn tạo tài khoản được)
        return False

    def get_login_redirect_url(self, request):
        return safe_next_url(request, '/')


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        return True

    def pre_social_login(self, request, sociallogin):
        """Liên kết với tài khoản KHÁCH HÀNG sẵn có khi email Google đã được xác minh.

        Tài khoản quản trị (is_staff) KHÔNG BAO GIỜ được đăng nhập/liên kết qua Google:
        Admin chỉ đăng nhập bằng tên đăng nhập + mật khẩu.
        """
        data = sociallogin.account.extra_data or {}
        email = (data.get('email') or '').lower()
        target = sociallogin.user if sociallogin.is_existing else (
            get_user_model().objects.filter(email__iexact=email).first() if email else None)
        if target is not None and target.pk and target.is_staff:
            self._reject_staff(request)
        if sociallogin.is_existing:
            return
        if target is not None and data.get('email_verified', False):
            sociallogin.connect(request, target)

    @staticmethod
    def _reject_staff(request):
        from allauth.core.exceptions import ImmediateHttpResponse
        from django.contrib import messages
        from django.shortcuts import redirect

        messages.error(request, 'Tài khoản quản trị không đăng nhập bằng Google. Vui lòng dùng tên đăng nhập và mật khẩu.')
        raise ImmediateHttpResponse(redirect('dashboard:login'))

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        extra = sociallogin.account.extra_data or {}
        user.email = (user.email or '').lower()
        user.full_name = extra.get('name') or ' '.join(filter(None, [data.get('first_name'), data.get('last_name')]))
        user.auth_provider = 'google'
        user.is_staff = False
        user.is_superuser = False
        if not user.username:
            user.username = self._unique_username(user.email.split('@')[0])
        return user

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        user.is_staff = False
        user.is_superuser = False
        user.set_unusable_password()
        user.save()
        from .services import ensure_profile, save_avatar_from_url

        ensure_profile(user)
        picture = (sociallogin.account.extra_data or {}).get('picture')
        if picture:
            save_avatar_from_url(user, picture)
        return user

    @staticmethod
    def _unique_username(base: str) -> str:
        User = get_user_model()
        base = ''.join(ch for ch in base if ch.isalnum() or ch in '._-')[:30] or 'user'
        candidate, index = base, 1
        while User.objects.filter(username__iexact=candidate).exists():
            index += 1
            candidate = f'{base}{index}'
        return candidate
