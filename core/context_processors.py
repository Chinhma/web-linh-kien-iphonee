from django.conf import settings

from .models import StoreSetting


def store(request):
    """Đưa cài đặt cửa hàng, danh mục menu và số đếm giỏ/yêu thích vào mọi template."""
    from products.models import Category

    store_setting = StoreSetting.get_solo()
    user = request.user
    cart_count = wishlist_count = 0
    is_customer = user.is_authenticated and not user.is_staff
    if is_customer:
        from cart.models import CartItem, WishlistItem

        cart_count = CartItem.objects.filter(cart__user=user).count()
        wishlist_count = WishlistItem.objects.filter(user=user).count()
    nav_categories = Category.objects.filter(is_active=True, parent__isnull=True).order_by('display_order', 'name')
    from django.contrib.messages import get_messages

    django_messages = [{'message': str(m), 'level': (m.tags.split() or ['info'])[-1]} for m in get_messages(request)]
    admin_menu, admin_crumbs = [], []
    if user.is_authenticated and user.is_staff and request.path.startswith('/quan-tri/'):
        from dashboard.menu import build_menu

        admin_menu, admin_crumbs = build_menu(request)
    return {
        'admin_menu': admin_menu,
        'admin_crumbs': admin_crumbs,
        'django_messages': django_messages,
        'store': store_setting,
        'nav_categories': nav_categories,
        'cart_count': cart_count,
        'wishlist_count': wishlist_count,
        'is_customer': is_customer,
        'is_customer_user': is_customer,
        'is_admin_user': user.is_authenticated and user.is_staff,
        'google_oauth_configured': settings.GOOGLE_OAUTH_CONFIGURED,
    }
