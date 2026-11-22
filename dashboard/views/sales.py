"""Quản lý đơn hàng, thanh toán, khách hàng, đánh giá, mã giảm giá."""

import json

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.sessions.models import Session
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import CustomerProfile
from core.permissions import staff_required
from core.utils import to_int
from orders.models import Order
from orders.services import OrderError, available_transitions, change_order_status, expire_unpaid_orders, mark_refunded
from payments.models import Payment
from promotions.models import Coupon
from reviews.models import Review
from reviews.services import delete_review, set_review_status

from ..forms import CustomerNoteForm
from .common import csv_response, table

User = get_user_model()
ORDER_TABS = [('', 'Tất cả')] + list(Order.Status.choices)


# ------------------------------------------------------------------ Đơn hàng
@staff_required
def order_list(request):
    expire_unpaid_orders()
    qs = Order.objects.select_related('user').annotate(items_count=Sum('items__quantity'))
    g = request.GET
    counts = dict(Order.objects.values_list('status').annotate(c=Count('id')))
    counts[''] = sum(counts.values())
    if g.get('status') == 'processing':
        qs = qs.filter(status__in=['confirmed', 'preparing', 'shipping'])
    elif g.get('status'):
        qs = qs.filter(status=g['status'])
    if g.get('payment_method'):
        qs = qs.filter(payment_method=g['payment_method'])
    if g.get('payment_status'):
        qs = qs.filter(payment_status=g['payment_status'])
    if g.get('from'):
        qs = qs.filter(created_at__date__gte=g['from'])
    if g.get('to'):
        qs = qs.filter(created_at__date__lte=g['to'])
    if g.get('export') == 'csv':
        return _orders_csv(qs.order_by('-created_at'))
    ctx = table(request, qs, ('code', 'recipient_name', 'recipient_phone', 'user__email'),
                {'code': 'code', 'date': 'created_at', 'total': 'total'}, '-date')
    titles = {'pending': 'Đơn chờ xác nhận', 'processing': 'Đơn đang xử lý & đang giao', 'delivered': 'Đơn đã giao', 'cancelled': 'Đơn đã hủy'}
    return render(request, 'dashboard/orders.html', {
        **ctx, 'page_title': titles.get(g.get('status'), 'Đơn hàng'),
        'page_description': 'Xử lý đơn theo đúng quy trình: Chờ xác nhận → Xác nhận → Chuẩn bị → Đang giao → Đã giao.', 'tabs': [(k, v, counts.get(k, 0)) for k, v in ORDER_TABS],
        'payment_methods': Order.PaymentMethod.choices, 'payment_statuses': Order.PaymentStatus.choices})


@staff_required
def order_detail(request, code):
    order = get_object_or_404(Order.objects.select_related('user').prefetch_related(
        'items', 'payments', 'status_history__changed_by'), code=code)
    steps = [('pending', 'Đặt hàng', order.created_at), ('confirmed', 'Xác nhận', order.confirmed_at),
             ('preparing', 'Chuẩn bị', None), ('shipping', 'Đang giao', order.shipped_at), ('delivered', 'Đã giao', order.delivered_at)]
    reached = {h.to_status: h.created_at for h in order.status_history.all()}
    flow = ['pending', 'confirmed', 'preparing', 'shipping', 'delivered']
    current = flow.index(order.status) if order.status in flow else -1
    progress = [{'label': label, 'time': reached.get(code) or ts, 'done': i <= current} for i, (code, label, ts) in enumerate(steps)]
    return render(request, 'dashboard/order_detail.html', {
        'page_title': f'Đơn hàng {order.code}', 'extra_crumb': order.code, 'order': order, 'progress': progress,
        'actions': available_transitions(order, request.user),
        'reason_required': {'cancelled'} if order.status in ('preparing', 'shipping') else set(),
    })


@staff_required
@require_POST
def order_change_status(request, code):
    order = get_object_or_404(Order, code=code)
    try:
        change_order_status(order, request.POST.get('status', ''), request.user, request.POST.get('note', '').strip())
        messages.success(request, 'Đã cập nhật trạng thái đơn hàng.')
    except OrderError as exc:
        messages.error(request, exc.message)
    return redirect('dashboard:order_detail', code=code)


@staff_required
@require_POST
def order_add_note(request, code):
    """Thêm ghi chú nội bộ (chỉ Admin thấy) vào đơn hàng."""
    order = get_object_or_404(Order, code=code)
    text = request.POST.get('text', '').strip()[:1000]
    if text:
        notes = list(order.admin_notes or [])
        notes.append({'text': text, 'by': request.user.display_name, 'at': timezone.localtime().strftime('%d/%m/%Y %H:%M')})
        Order.objects.filter(pk=order.pk).update(admin_notes=notes)
        messages.success(request, 'Đã thêm ghi chú nội bộ.')
    return redirect('dashboard:order_detail', code=code)


@staff_required
@require_POST
def order_bulk(request):
    """Thao tác hàng loạt: xác nhận các đơn đã chọn (chỉ đơn hợp lệ) hoặc xuất CSV."""
    codes = request.POST.getlist('ids')
    orders = Order.objects.filter(code__in=codes).select_related('user')
    if request.POST.get('action') == 'export':
        return _orders_csv(orders.order_by('-created_at'))
    ok, skipped = 0, 0
    for order in orders:
        try:
            change_order_status(order, Order.Status.CONFIRMED, request.user, 'Xác nhận hàng loạt')
            ok += 1
        except OrderError:
            skipped += 1
    if ok:
        messages.success(request, f'Đã xác nhận {ok} đơn hàng.')
    if skipped:
        messages.warning(request, f'Bỏ qua {skipped} đơn không hợp lệ (không ở trạng thái chờ xác nhận hoặc chưa thanh toán online).')
    return redirect(request.POST.get('next') or 'dashboard:order_list')


def _orders_csv(qs):
    return csv_response('don-hang', ['Mã đơn', 'Ngày đặt', 'Khách hàng', 'Email', 'SĐT nhận', 'Địa chỉ', 'Tổng tiền', 'Thanh toán',
                                     'TT thanh toán', 'Trạng thái'],
                        ([o.code, timezone.localtime(o.created_at).strftime('%d/%m/%Y %H:%M'), o.recipient_name, o.user.email,
                          o.recipient_phone, o.full_address, o.total, o.get_payment_method_display(),
                          o.get_payment_status_display(), o.get_status_display()] for o in qs))


@staff_required
@require_POST
def order_refunded(request, code):
    order = get_object_or_404(Order, code=code)
    try:
        mark_refunded(order, request.user, request.POST.get('note', '').strip())
        messages.success(request, 'Đã đánh dấu đã hoàn tiền.')
    except OrderError as exc:
        messages.error(request, exc.message)
    return redirect('dashboard:order_detail', code=code)


@staff_required
def order_print(request, code):
    order = get_object_or_404(Order.objects.prefetch_related('items'), code=code)
    return render(request, 'dashboard/order_print.html', {'order': order})


# ------------------------------------------------------------------ Thanh toán (chỉ xem)
@staff_required
def payment_list(request):
    qs = Payment.objects.select_related('order', 'order__user')
    g = request.GET
    if g.get('method'):
        qs = qs.filter(method=g['method'])
    if g.get('status'):
        qs = qs.filter(status=g['status'])
    if g.get('from'):
        qs = qs.filter(created_at__date__gte=g['from'])
    if g.get('to'):
        qs = qs.filter(created_at__date__lte=g['to'])
    totals = {row['method']: row['s'] for row in Payment.objects.filter(status='success').values('method').annotate(s=Sum('amount'))}
    ctx = table(request, qs, ('transaction_ref', 'gateway_transaction_id', 'order__code', 'order__user__email'),
                {'time': 'created_at', 'amount': 'amount'}, '-time')
    return render(request, 'dashboard/payments.html', {
        **ctx, 'menu': 'payment', 'page_title': 'Thanh toán', 'totals': totals,
        'failed_count': Payment.objects.filter(status='failed').count(),
        'refund_pending': Order.objects.filter(payment_status='refund_pending').count(),
        'methods': Order.PaymentMethod.choices, 'statuses': Payment.Status.choices})


@staff_required
def payment_detail(request, pk):
    payment = get_object_or_404(Payment.objects.select_related('order', 'order__user'), pk=pk)
    return render(request, 'dashboard/payment_detail.html', {
        'menu': 'payment', 'page_title': f'Giao dịch {payment.transaction_ref}', 'payment': payment,
        'raw_json': json.dumps(payment.raw_response, ensure_ascii=False, indent=2)})


# ------------------------------------------------------------------ Khách hàng
def _customers():
    return User.objects.filter(is_staff=False).annotate(
        order_total=Count('orders', distinct=True),
        spent=Sum('orders__total', filter=Q(orders__status='delivered')),
    )


@staff_required
def customer_list(request):
    qs = _customers()
    g = request.GET
    if g.get('state') in ('active', 'locked'):
        qs = qs.filter(is_active=g['state'] == 'active')
    if g.get('provider'):
        qs = qs.filter(auth_provider=g['provider'])
    if g.get('from'):
        qs = qs.filter(date_joined__date__gte=g['from'])
    if g.get('to'):
        qs = qs.filter(date_joined__date__lte=g['to'])
    if g.get('export') == 'csv':
        return csv_response('khach-hang', ['Họ tên', 'Email', 'SĐT', 'Đăng ký bằng', 'Ngày đăng ký', 'Số đơn', 'Tổng chi tiêu', 'Trạng thái'],
                            ([u.display_name, u.email, u.phone, u.get_auth_provider_display(),
                              timezone.localtime(u.date_joined).strftime('%d/%m/%Y'), u.order_total, u.spent or 0,
                              'Hoạt động' if u.is_active else 'Đã khóa'] for u in qs))
    ctx = table(request, qs, ('full_name', 'email', 'phone', 'username'),
                {'name': 'full_name', 'joined': 'date_joined', 'orders': 'order_total', 'spent': 'spent'}, '-joined')
    base = User.objects.filter(is_staff=False)
    stats = {
        'total': base.count(),
        'new30': base.filter(date_joined__gte=timezone.now() - timezone.timedelta(days=30)).count(),
        'buyers': base.filter(orders__isnull=False).distinct().count(),
        'locked': base.filter(is_active=False).count(),
    }
    return render(request, 'dashboard/customers.html', {
        **ctx, 'menu': 'customer', 'page_title': 'Khách hàng', 'stats': stats,
        'page_description': 'Tài khoản khách mua hàng (không gồm tài khoản quản trị).'})


@staff_required
def customer_detail(request, pk):
    customer = get_object_or_404(_customers(), pk=pk)
    profile, _ = CustomerProfile.objects.get_or_create(user=customer)
    form = CustomerNoteForm(request.POST or None, initial={'note_by_admin': profile.note_by_admin})
    if request.method == 'POST' and form.is_valid():
        profile.note_by_admin = form.cleaned_data['note_by_admin']
        profile.save()
        messages.success(request, 'Đã lưu ghi chú nội bộ.')
        return redirect('dashboard:customer_detail', pk=pk)
    return render(request, 'dashboard/customer_detail.html', {
        'menu': 'customer', 'page_title': customer.display_name, 'customer': customer, 'profile': profile, 'form': form,
        'orders': customer.orders.order_by('-created_at')[:20], 'addresses': customer.addresses.all(),
        'reviews': customer.reviews.select_related('product')[:20], 'chat_count': customer.chat_conversations.count(),
        'chats': customer.chat_conversations.order_by('-id')[:20], 'extra_crumb': customer.display_name,
        'tab': request.GET.get('tab', 'orders'),
        'aov': (customer.spent or 0) // max(customer.orders.filter(status='delivered').count(), 1)})


def _logout_everywhere(user) -> None:
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        if str(session.get_decoded().get('_auth_user_id')) == str(user.pk):
            session.delete()


@staff_required
@require_POST
def customer_toggle_active(request, pk):
    customer = get_object_or_404(User, pk=pk, is_staff=False)
    customer.is_active = not customer.is_active
    customer.save(update_fields=['is_active'])
    if not customer.is_active:
        _logout_everywhere(customer)
    messages.success(request, f'Đã {"mở khóa" if customer.is_active else "khóa"} tài khoản {customer.email}.')
    return redirect('dashboard:customer_detail', pk=pk)


@staff_required
@require_POST
def customer_send_reset(request, pk):
    customer = get_object_or_404(User, pk=pk, is_staff=False)
    form = PasswordResetForm({'email': customer.email})
    if form.is_valid():
        form.save(request=request, use_https=request.is_secure(), email_template_name='emails/password_reset.txt',
                  html_email_template_name='emails/password_reset.html', subject_template_name='emails/password_reset_subject.txt')
    messages.success(request, f'Đã gửi email đặt lại mật khẩu tới {customer.email}.')
    return redirect('dashboard:customer_detail', pk=pk)


# ------------------------------------------------------------------ Đánh giá
@staff_required
def review_list(request):
    qs = Review.objects.select_related('product', 'user', 'order_item__order')
    status = request.GET.get('status', 'pending')
    counts = dict(Review.objects.values_list('status').annotate(c=Count('id')))
    if status in Review.Status.values:
        qs = qs.filter(status=status)
    if request.GET.get('rating'):
        qs = qs.filter(rating=to_int(request.GET['rating']))
    if request.GET.get('product'):
        qs = qs.filter(product_id=to_int(request.GET['product']))
    ctx = table(request, qs, ('content', 'product__name', 'user__email', 'user__full_name'),
                {'date': 'created_at', 'rating': 'rating'}, '-date')
    approved = Review.objects.filter(status='approved')
    avg = approved.aggregate(a=Avg('rating'))['a']
    titles = {'pending': 'Đánh giá chờ duyệt', 'approved': 'Đánh giá đã duyệt', 'hidden': 'Đánh giá đã ẩn'}
    return render(request, 'dashboard/reviews.html', {
        **ctx, 'menu': 'review', 'page_title': titles.get(status, 'Tất cả đánh giá'), 'status': status,
        'page_description': 'Duyệt, ẩn, xóa hoặc trả lời đánh giá của khách đã mua hàng.',
        'avg_rating': round(avg, 1) if avg else None,
        'tabs': [('all', 'Tất cả', sum(counts.values()))] + [(k, v, counts.get(k, 0)) for k, v in Review.Status.choices]})


@staff_required
@require_POST
def review_action(request):
    ids = [to_int(i) for i in request.POST.getlist('ids') if to_int(i)]
    action = request.POST.get('action')
    if action == 'delete':
        for review in Review.objects.filter(pk__in=ids):
            delete_review(review)
        messages.success(request, f'Đã xóa {len(ids)} đánh giá.')
    elif action in ('approved', 'hidden', 'pending'):
        count = set_review_status(ids, action)
        messages.success(request, f'Đã cập nhật {count} đánh giá.')
    elif action == 'reply' and len(ids) == 1:
        Review.objects.filter(pk=ids[0]).update(admin_reply=request.POST.get('reply', '').strip()[:1000])
        messages.success(request, 'Đã lưu phản hồi.')
    else:
        messages.error(request, 'Thao tác không hợp lệ.')
    return redirect(request.POST.get('next') or 'dashboard:review_list')


# ------------------------------------------------------------------ Mã giảm giá – chi tiết
@staff_required
def coupon_detail(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    return render(request, 'dashboard/coupon_detail.html', {
        'menu': 'coupon', 'page_title': f'Mã {coupon.code}', 'coupon': coupon,
        'usages': coupon.usages.select_related('user', 'order')[:100]})
