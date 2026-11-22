import uuid

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.models import Address
from cart.services import COUPON_SESSION_KEY, build_cart_summary
from core.models import StoreSetting
from core.permissions import customer_required, get_object_owned_or_404
from payments.gateways import GATEWAYS

from . import services
from .forms import CANCEL_REASONS, CheckoutForm
from .models import Order
from .services import CheckoutData, OrderError

STATUS_TABS = [
    ('', 'Tất cả', None),
    ('pending', 'Chờ xác nhận', ['pending']),
    ('processing', 'Đang xử lý', ['confirmed', 'preparing']),
    ('shipping', 'Đang giao', ['shipping']),
    ('delivered', 'Đã giao', ['delivered']),
    ('cancelled', 'Đã hủy', ['cancelled']),
]
TIMELINE = [('pending', 'Đặt hàng', 'created_at'), ('confirmed', 'Xác nhận', 'confirmed_at'),
            ('preparing', 'Chuẩn bị', None), ('shipping', 'Đang giao', 'shipped_at'), ('delivered', 'Đã giao', 'delivered_at')]


def enabled_payment_methods() -> dict:
    """Phương thức dùng được = đã cấu hình .env VÀ Admin đang bật trong Cài đặt cửa hàng."""
    from core.models import StoreSetting

    store = StoreSetting.get_solo()
    return {code: gw.is_configured() and getattr(store, f'enable_{code}', True) for code, gw in GATEWAYS.items()}


@customer_required
def checkout(request):
    if request.method == 'POST':  # Bấm "Đặt hàng" lần 2 với cùng idempotency_key -> về đơn đã tạo
        existing = Order.objects.filter(user=request.user, idempotency_key=request.POST.get('idempotency_key') or '-').first()
        if existing:
            return redirect('payments:start' if existing.can_retry_payment else 'orders:success', code=existing.code)
    summary = build_cart_summary(request.user, request.session)
    if not summary.has_valid_selection:
        messages.warning(request, 'Vui lòng chọn sản phẩm hợp lệ trong giỏ hàng để thanh toán.')
        return redirect('cart:cart')
    methods = enabled_payment_methods()
    enabled = {m for m, ok in methods.items() if ok}
    addresses = list(Address.objects.filter(user=request.user))
    default = next((a for a in addresses if a.is_default), addresses[0] if addresses else None)
    initial = {'recipient_email': request.user.email, 'recipient_name': request.user.display_name,
               'recipient_phone': request.user.phone, 'shipping_method': 'standard', 'payment_method': 'cod',
               'idempotency_key': uuid.uuid4()}
    if default:
        initial.update({'recipient_name': default.full_name, 'recipient_phone': default.phone,
                        'province_code': default.province_code, 'ward_code': default.ward_code,
                        'street_address': default.street_address})
    form = CheckoutForm(request.POST or None, initial=initial, enabled_methods=enabled)
    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
        data = CheckoutData(
            recipient_name=cd['recipient_name'], recipient_phone=cd['recipient_phone'],
            recipient_email=cd['recipient_email'], province_code=cd['province_code'], province_name=cd['province_name'],
            ward_code=cd['ward_code'], ward_name=cd['ward_name'],
            street_address=cd['street_address'], note=cd['note'], shipping_method=cd['shipping_method'],
            payment_method=cd['payment_method'], coupon_code=request.session.get(COUPON_SESSION_KEY, ''),
        )
        try:
            order = services.create_order(request.user, data, str(cd['idempotency_key']))
        except OrderError as exc:
            messages.error(request, exc.message)
            for detail in exc.errors.values():
                messages.error(request, detail)
            if exc.code in ('OUT_OF_STOCK', 'EMPTY_SELECTION'):
                return redirect('cart:cart')
            if exc.code == 'COUPON_INVALID':
                request.session.pop(COUPON_SESSION_KEY, None)
            return redirect('orders:checkout')
        request.session.pop(COUPON_SESSION_KEY, None)
        if cd['save_address'] and Address.objects.filter(user=request.user).count() < 10:
            exists = Address.objects.filter(user=request.user, street_address=cd['street_address'],
                                            ward_code=cd['ward_code'], province_code=cd['province_code']).exists()
            if not exists:
                Address.objects.create(user=request.user, full_name=cd['recipient_name'], phone=cd['recipient_phone'],
                                       province_code=cd['province_code'], province_name=cd['province_name'],
                                       ward_code=cd['ward_code'], ward_name=cd['ward_name'],
                                       street_address=cd['street_address'], is_default=not addresses)
        _send_order_email(order)
        if order.is_online_payment:
            return redirect('payments:start', code=order.code)
        return redirect('orders:success', code=order.code)
    store = StoreSetting.get_solo()
    after_discount = summary.subtotal - summary.discount
    shipping_fees = {
        'standard': services.calculate_shipping_fee('standard', after_discount),
        'express': services.calculate_shipping_fee('express', after_discount),
    }
    return render(request, 'checkout/checkout.html', {
        'form': form, 'summary': summary, 'addresses': addresses, 'default_address': default,
        'methods': methods, 'shipping_fees': shipping_fees, 'store': store,
        'checkout_data': {'subtotal': summary.subtotal, 'discount': summary.discount, 'fees': shipping_fees},
        'breadcrumbs': [('Giỏ hàng', '/gio-hang/'), ('Thanh toán', None)],
    })


def _send_order_email(order: Order) -> None:
    from django.core.mail import send_mail

    from core.templatetags.iparts import vnd

    send_mail(f'[iParts Store] Xác nhận đơn hàng {order.code}',
              f'Cảm ơn bạn đã đặt hàng tại iParts Store.\nMã đơn: {order.code}\nTổng thanh toán: {vnd(order.total)}\n'
              f'Phương thức: {order.get_payment_method_display()}', None, [order.recipient_email], fail_silently=True)


@customer_required
def order_success(request, code):
    order = get_object_owned_or_404(Order, request.user, code=code)
    return render(request, 'checkout/result.html', {'order': order, 'success': True})


@customer_required
def order_list(request):
    services.expire_unpaid_orders()
    orders = Order.objects.filter(user=request.user)
    counts = orders.aggregate(**{key or 'all': Count('id', filter=Q(status__in=sts)) if sts else Count('id')
                                 for key, _, sts in STATUS_TABS})
    tab = request.GET.get('tab', '')
    statuses = dict((k, s) for k, _, s in STATUS_TABS).get(tab)
    if statuses:
        orders = orders.filter(status__in=statuses)
    q = (request.GET.get('q') or '').strip()
    if q:
        orders = orders.filter(code__icontains=q)
    page = Paginator(orders.prefetch_related('items').order_by('-created_at'), 10).get_page(request.GET.get('page'))
    return render(request, 'customer/orders.html', {
        'account_active': 'orders', 'page_obj': page, 'tabs': [(k, label, counts[k or 'all']) for k, label, _ in STATUS_TABS],
        'tab': tab, 'q': q,
    })


@customer_required
def order_detail(request, code):
    services.expire_unpaid_orders()
    order = get_object_owned_or_404(Order.objects.prefetch_related('items__review', 'status_history', 'payments'),
                                    request.user, code=code)
    reached = {h.to_status: h.created_at for h in order.status_history.all()}
    timeline = [{'code': c, 'label': label, 'time': reached.get(c) or (getattr(order, attr) if attr else None),
                 'done': c in reached} for c, label, attr in TIMELINE]
    can_cancel = services.can_transition(order, Order.Status.CANCELLED, request.user)[0]
    return render(request, 'customer/order_detail.html', {
        'account_active': 'orders', 'order': order, 'timeline': timeline, 'can_cancel': can_cancel,
        'cancel_reasons': CANCEL_REASONS,
    })


@customer_required
@require_POST
def order_cancel(request, code):
    order = get_object_owned_or_404(Order, request.user, code=code)
    reason = request.POST.get('reason', '').strip()
    if reason == 'Lý do khác' or not reason:
        reason = request.POST.get('reason_other', '').strip() or 'Lý do khác'
    try:
        services.change_order_status(order, Order.Status.CANCELLED, request.user, reason[:500])
        messages.success(request, f'Đã hủy đơn hàng {order.code}.')
    except OrderError as exc:
        messages.error(request, exc.message)
    return redirect('orders:detail', code=code)


@customer_required
@require_POST
def order_reorder(request, code):
    order = get_object_owned_or_404(Order, request.user, code=code)
    added = services.reorder(request.user, order)
    if added:
        messages.success(request, f'Đã thêm {added} sản phẩm vào giỏ hàng.')
    else:
        messages.warning(request, 'Các sản phẩm trong đơn hiện không còn bán hoặc đã hết hàng.')
    return redirect('cart:cart')
