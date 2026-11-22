"""Module phân quyền dùng chung cho toàn hệ thống (Guest / Customer / Admin).

Mọi view và API đều kiểm tra quyền ở backend thông qua các decorator/mixin dưới đây.
Ẩn nút trên giao diện chỉ là lớp phụ trợ.
"""

from functools import wraps
from urllib.parse import quote

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .utils import api_error, is_ajax

ADMIN_CANNOT_BUY = 'Tài khoản quản trị không dùng để mua hàng'
ADMIN_FEATURE_BLOCKED = 'Tài khoản quản trị không sử dụng chức năng này'
LOGIN_REQUIRED_MESSAGE = 'Bạn cần đăng nhập để sử dụng chức năng này.'


def is_customer(user) -> bool:
    return user.is_authenticated and user.is_active and not user.is_staff


def safe_next_url(request, fallback: str = '/') -> str:
    """Trả về URL `next` nếu cùng host (chống open redirect), ngược lại trả fallback."""
    target = request.POST.get('next') or request.GET.get('next') or ''
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return fallback


def _login_redirect(request, login_url: str):
    return redirect(f'{login_url}?next={quote(request.get_full_path())}')


def customer_required(view_func):
    """Chỉ Customer: Guest -> chuyển đăng nhập (hoặc JSON 401); Admin -> từ chối mua hàng."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            login_url = reverse('accounts:login')
            if is_ajax(request) or request.path.startswith('/api/'):
                return api_error('LOGIN_REQUIRED', LOGIN_REQUIRED_MESSAGE, status=401,
                                 login_url=f'{login_url}?next={quote(request.META.get("HTTP_REFERER", "/"))}')
            return _login_redirect(request, login_url)
        if user.is_staff:
            if is_ajax(request) or request.path.startswith('/api/'):
                return api_error('ADMIN_CANNOT_PURCHASE', ADMIN_CANNOT_BUY, status=403)
            from django.contrib import messages
            messages.warning(request, ADMIN_FEATURE_BLOCKED)
            return redirect('products:home')
        return view_func(request, *args, **kwargs)

    return _wrapped


def staff_required(view_func):
    """Chỉ Admin (is_staff): Guest -> trang đăng nhập Admin; Customer -> 403."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            if is_ajax(request):
                return api_error('LOGIN_REQUIRED', LOGIN_REQUIRED_MESSAGE, status=401)
            return _login_redirect(request, reverse('dashboard:login'))
        if not (user.is_active and user.is_staff):
            if is_ajax(request):
                return api_error('FORBIDDEN', 'Bạn không có quyền truy cập.', status=403)
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped


def superuser_required(view_func):
    @wraps(view_func)
    @staff_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            from django.shortcuts import render

            return render(request, 'dashboard/403.html', {'page_title': 'Không có quyền truy cập'}, status=403)
        return view_func(request, *args, **kwargs)

    return _wrapped


class CustomerRequiredMixin:
    @classmethod
    def as_view(cls, **initkwargs):
        return customer_required(super().as_view(**initkwargs))


class StaffRequiredMixin:
    @classmethod
    def as_view(cls, **initkwargs):
        return staff_required(super().as_view(**initkwargs))


def get_object_owned_or_404(model_or_qs, user, **lookup):
    """Lấy đối tượng thuộc về user; không thuộc về -> 404 (không 403 để tránh lộ sự tồn tại)."""
    qs = model_or_qs.objects.all() if hasattr(model_or_qs, 'objects') else model_or_qs
    obj = qs.filter(user=user, **lookup).first()
    if obj is None:
        raise Http404
    return obj
