"""Nghiệp vụ tài khoản: hồ sơ, giới hạn đăng nhập sai."""

import logging

from django.core.cache import cache
from django.core.files.base import ContentFile

from .models import CustomerProfile

logger = logging.getLogger('iparts')

LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCK_SECONDS = 15 * 60


def ensure_profile(user) -> CustomerProfile:
    profile, _ = CustomerProfile.objects.get_or_create(user=user)
    return profile


def save_avatar_from_url(user, url: str) -> None:
    """Tải ảnh đại diện Google (bỏ qua nếu lỗi mạng)."""
    try:
        import requests

        response = requests.get(url, timeout=5)
        if response.ok and len(response.content) < 2 * 1024 * 1024:
            user.avatar.save(f'google-{user.pk}.jpg', ContentFile(response.content), save=True)
    except Exception:  # Không để lỗi tải avatar làm hỏng đăng nhập
        logger.warning('Không tải được avatar Google cho user %s', user.pk)


def _attempt_key(ip: str, identifier: str) -> str:
    return f'login-fail:{ip}:{(identifier or "").strip().lower()}'


def login_locked_seconds(ip: str, identifier: str) -> int:
    """Trả về số giây còn bị khóa (0 nếu không bị khóa). Khóa theo cặp IP + tài khoản."""
    data = cache.get(_attempt_key(ip, identifier))
    if not data or data.get('count', 0) < LOGIN_MAX_ATTEMPTS:
        return 0
    import time

    remaining = int(data['locked_until'] - time.time())
    return max(remaining, 0)


def register_login_failure(ip: str, identifier: str) -> None:
    import time

    key = _attempt_key(ip, identifier)
    data = cache.get(key) or {'count': 0}
    data['count'] += 1
    data['locked_until'] = time.time() + LOGIN_LOCK_SECONDS
    cache.set(key, data, LOGIN_LOCK_SECONDS)


def reset_login_failures(ip: str, identifier: str) -> None:
    cache.delete(_attempt_key(ip, identifier))
