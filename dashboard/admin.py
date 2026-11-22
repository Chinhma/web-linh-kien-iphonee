"""Tinh gọn trang quản trị Django (/admin/): ẩn mục kỹ thuật, sắp xếp nhóm theo thứ tự công việc.

App `dashboard` đứng cuối INSTALLED_APPS nên file này chạy sau khi mọi app khác đã đăng ký admin.
"""

from django.contrib import admin
from django.contrib.admin.exceptions import NotRegistered
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site

# Các mục kỹ thuật không cần khi vận hành cửa hàng (hệ thống vẫn dùng ở nền)
HIDDEN = [Group, Site]
try:
    from allauth.account.models import EmailAddress
    from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken

    HIDDEN += [EmailAddress, SocialAccount, SocialApp, SocialToken]
except ImportError:  # pragma: no cover
    pass
from cart.models import Cart, WishlistItem  # noqa: E402

HIDDEN += [Cart, WishlistItem]

for model in HIDDEN:
    try:
        admin.site.unregister(model)
    except NotRegistered:
        pass

# Thứ tự nhóm trên trang chủ admin: việc hằng ngày trước, cài đặt sau
APP_ORDER = ['orders', 'products', 'inventory', 'accounts', 'reviews', 'promotions', 'payments', 'chatbot', 'core']
MODEL_ORDER = {
    'products': ['Product', 'Compatibility', 'Category', 'IPhoneModel', 'Brand'],
    'core': ['StoreSetting', 'Banner', 'Page', 'FAQ', 'ContactMessage', 'NewsletterSubscriber'],
    'chatbot': ['ChatbotSetting', 'ChatConversation'],
}

_original_get_app_list = admin.site.get_app_list


def get_app_list(request, app_label=None):
    apps = _original_get_app_list(request, app_label)
    apps.sort(key=lambda a: APP_ORDER.index(a['app_label']) if a['app_label'] in APP_ORDER else len(APP_ORDER))
    for app in apps:
        order = MODEL_ORDER.get(app['app_label'])
        if order:
            app['models'].sort(key=lambda m: order.index(m['object_name']) if m['object_name'] in order else len(order))
    return apps


admin.site.get_app_list = get_app_list


def _superuser_only(request):
    """Django admin (/django-admin/) chỉ dành cho Superuser – Admin thường dùng /quan-tri/."""
    return request.user.is_active and request.user.is_superuser


admin.site.has_permission = _superuser_only
