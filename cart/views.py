import json

from django.core.cache import cache
from django.shortcuts import render
from django.views.decorators.http import require_http_methods, require_POST

from core.permissions import customer_required
from core.utils import api_error, api_ok, client_ip, to_int
from products.models import Product
from products.selectors import public_products, with_card_data

from . import services
from .models import CartItem, WishlistItem
from .services import COUPON_SESSION_KEY, CartError


def _json(request) -> dict:
    try:
        return json.loads(request.body or '{}')
    except (ValueError, UnicodeDecodeError):
        return {}


def _counts(user) -> dict:
    return {'cart_count': CartItem.objects.filter(cart__user=user).count(),
            'wishlist_count': WishlistItem.objects.filter(user=user).count()}


def _summary_payload(request) -> dict:
    s = services.build_cart_summary(request.user, request.session)
    return {
        **_counts(request.user),
        'subtotal': s.subtotal, 'discount': s.discount, 'total': s.total, 'selected_count': s.selected_count,
        'coupon_code': s.coupon_code, 'can_checkout': s.has_valid_selection,
        'lines': {str(line.item.pk): {'quantity': line.item.quantity, 'line_total': line.line_total,
                                      'unit_price': line.unit_price, 'valid': line.valid, 'warning': line.warning,
                                      'selected': line.item.is_selected}
                  for line in s.lines},
    }


@customer_required
def cart_page(request):
    summary = services.build_cart_summary(request.user, request.session)
    featured = []
    if not summary.lines:
        featured = with_card_data(public_products().filter(is_featured=True))[:4]
    return render(request, 'cart/cart.html', {
        'summary': summary, 'featured': featured, 'breadcrumbs': [('Giỏ hàng', None)],
        'all_selected': bool(summary.lines) and all(l.item.is_selected for l in summary.lines if l.valid),
    })


@customer_required
@require_POST
def api_add(request):
    data = _json(request)
    product_id = to_int(data.get('product_id'))
    quantity = to_int(data.get('quantity'), default=1, minimum=1, maximum=10) or 1
    if not product_id:
        return api_error('INVALID', 'Sản phẩm không hợp lệ.')
    try:
        item, message = services.add_to_cart(request.user, product_id, quantity, select_only=bool(data.get('buy_now')),
                                             variant_id=to_int(data.get('variant_id')))
    except CartError as exc:
        return api_error(exc.code, exc.message, status=409 if exc.code == 'OUT_OF_STOCK' else 400)
    return api_ok({**_counts(request.user), 'item_id': item.pk, 'quantity': item.quantity,
                   'limited': message.startswith(('Chỉ còn', 'Mỗi'))}, message)


@customer_required
@require_POST
def api_update(request):
    data = _json(request)
    try:
        _, message = services.update_quantity(request.user, to_int(data.get('item_id')), to_int(data.get('quantity'), 1) or 1)
    except CartError as exc:
        return api_error(exc.code, exc.message, status=404 if exc.code == 'NOT_FOUND' else 409)
    return api_ok(_summary_payload(request), message)


@customer_required
@require_POST
def api_remove(request):
    try:
        services.remove_item(request.user, to_int(_json(request).get('item_id')))
    except CartError as exc:
        return api_error(exc.code, exc.message, status=404)
    return api_ok(_summary_payload(request), 'Đã xóa sản phẩm khỏi giỏ hàng.')


@customer_required
@require_POST
def api_select(request):
    data = _json(request)
    ids = [to_int(i) for i in data.get('item_ids', []) if to_int(i)]
    services.set_selected(request.user, ids, bool(data.get('selected')))
    return api_ok(_summary_payload(request))


@customer_required
@require_http_methods(['POST', 'DELETE'])
def api_coupon(request):
    if request.method == 'DELETE':
        request.session.pop(COUPON_SESSION_KEY, None)
        return api_ok(_summary_payload(request), 'Đã bỏ mã giảm giá.')
    key = f'coupon-rate:{request.user.pk}:{client_ip(request)}'
    attempts = cache.get(key, 0)
    if attempts >= 10:
        return api_error('RATE_LIMITED', 'Bạn thử mã quá nhiều lần, vui lòng đợi 1 phút.', status=429)
    cache.set(key, attempts + 1, 60)
    from promotions.services import validate_coupon

    code = str(_json(request).get('code', '')).strip().upper()[:20]
    summary = services.build_cart_summary(request.user)
    if not summary.subtotal:
        return api_error('EMPTY_SELECTION', 'Vui lòng chọn sản phẩm trước khi áp mã.')
    ok, discount, message, _ = validate_coupon(code, request.user, summary.subtotal)
    if not ok:
        return api_error('COUPON_INVALID', message, errors={'code': message})
    request.session[COUPON_SESSION_KEY] = code
    return api_ok(_summary_payload(request), message)


@customer_required
def api_summary(request):
    return api_ok(_summary_payload(request))


# ------------------------------------------------------------------ Yêu thích
@customer_required
def wishlist_page(request):
    items = (WishlistItem.objects.filter(user=request.user)
             .select_related('product'))
    products = list(with_card_data(
        Product.objects.filter(pk__in=[i.product_id for i in items])))
    order = {i.product_id: idx for idx, i in enumerate(items)}
    products.sort(key=lambda p: order.get(p.pk, 0))
    return render(request, 'store/wishlist.html', {
        'products': products, 'wishlist_ids': {p.pk for p in products},
        'available_count': sum(1 for p in products if p.is_purchasable), 'breadcrumbs': [('Yêu thích', None)],
    })


@customer_required
@require_POST
def api_wishlist_toggle(request):
    try:
        added = services.toggle_wishlist(request.user, to_int(_json(request).get('product_id')))
    except CartError as exc:
        return api_error(exc.code, exc.message, status=404)
    return api_ok({**_counts(request.user), 'in_wishlist': added},
                  'Đã thêm vào danh sách yêu thích.' if added else 'Đã bỏ khỏi danh sách yêu thích.')


@customer_required
@require_POST
def api_wishlist_add_all(request):
    added, skipped = 0, 0
    for item in WishlistItem.objects.filter(user=request.user).select_related('product'):
        try:
            services.add_to_cart(request.user, item.product_id, 1)
            added += 1
        except CartError:
            skipped += 1
    message = f'Đã thêm {added} sản phẩm vào giỏ hàng.' + (f' {skipped} sản phẩm hết hàng hoặc cần chọn loại màn / màu trên trang sản phẩm.' if skipped else '')
    return api_ok(_counts(request.user), message)
