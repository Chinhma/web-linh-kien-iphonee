"""Thống kê doanh thu cho Admin Dashboard.

QUY TẮC DOANH THU GHI NHẬN (bắt buộc):
    Doanh thu ghi nhận = tổng Order.total của các đơn có status = delivered VÀ payment_status = paid,
    tính theo NGÀY delivered_at (giờ Việt Nam, Asia/Ho_Chi_Minh).

Hệ quả:
    - Không tính đơn đã hủy, đơn thanh toán thất bại, đơn đang xử lý.
    - Đơn COD được tính khi giao thành công (lúc đó hệ thống tự chuyển payment_status = paid).
    - Đơn online đã paid nhưng chưa giao: chưa tính; hiển thị riêng ở "Doanh thu chờ ghi nhận".
    - Mỗi đơn chỉ tính một lần (tổng theo Order, không theo Payment).
    - Doanh thu theo danh mục/sản phẩm dùng OrderItem.line_total = "doanh thu trước giảm giá coupon".
"""

from datetime import date, datetime, time, timedelta

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone

from orders.models import Order, OrderItem

RANGE_LABELS = {
    '7d': '7 ngày gần nhất', 'today': 'Hôm nay', '30d': '30 ngày gần nhất', 'this_month': 'Tháng này',
    'last_month': 'Tháng trước', 'this_year': 'Năm nay', 'custom': 'Tùy chọn',
}
STATUS_COLORS = {
    'pending': '#F59E0B', 'confirmed': '#3B82F6', 'preparing': '#6366F1', 'shipping': '#1D4ED8',
    'delivered': '#16A34A', 'cancelled': '#DC2626',
}


def recognized_orders():
    return Order.objects.filter(status=Order.Status.DELIVERED, payment_status=Order.PaymentStatus.PAID)


def _aware(d: date, end: bool = False) -> datetime:
    return timezone.make_aware(datetime.combine(d, time.max if end else time.min))


def resolve_range(range_key: str, date_from: str = '', date_to: str = '') -> tuple[date, date, str, str]:
    """Trả về (từ ngày, đến ngày, key, lỗi). Tùy chọn: kiểm tra từ ≤ đến và tối đa 366 ngày."""
    today = timezone.localdate()
    error = ''
    if range_key == 'today':
        start, end = today, today
    elif range_key == '7d':
        start, end = today - timedelta(days=6), today
    elif range_key == 'this_month':
        start, end = today.replace(day=1), today
    elif range_key == 'last_month':
        end = today.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1)
    elif range_key == 'this_year':
        start, end = today.replace(month=1, day=1), today
    elif range_key == 'custom':
        try:
            start = date.fromisoformat(date_from)
            end = date.fromisoformat(date_to)
            if start > end:
                error = 'Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.'
            elif (end - start).days > 365:
                error = 'Khoảng thời gian tối đa 366 ngày.'
        except ValueError:
            error = 'Ngày không hợp lệ.'
        if error:
            range_key, start, end = '30d', today - timedelta(days=29), today
    else:
        range_key, start, end = '30d', today - timedelta(days=29), today
    return start, end, range_key, error


def revenue_between(start: date, end: date) -> int:
    return recognized_orders().filter(delivered_at__range=(_aware(start), _aware(end, True))).aggregate(
        s=Sum('total'))['s'] or 0


def _change(current, previous) -> float | None:
    if not previous:
        return None if not current else 100.0
    return round((current - previous) * 100 / previous, 1)


def summary(start: date, end: date) -> dict:
    from django.contrib.auth import get_user_model

    from products.models import Product

    User = get_user_model()
    length = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=length - 1)
    today = timezone.localdate()
    rng = (_aware(start), _aware(end, True))
    prev_rng = (_aware(prev_start), _aware(prev_end, True))

    revenue = revenue_between(start, end)
    prev_revenue = revenue_between(prev_start, prev_end)
    today_rev = revenue_between(today, today)
    yesterday_rev = revenue_between(today - timedelta(days=1), today - timedelta(days=1))
    month_start = today.replace(day=1)
    month_rev = revenue_between(month_start, today)
    prev_month_end = month_start - timedelta(days=1)
    prev_month_rev = revenue_between(prev_month_end.replace(day=1), prev_month_end.replace(day=min(today.day, prev_month_end.day)))
    orders = Order.objects.filter(created_at__range=rng)
    prev_orders = Order.objects.filter(created_at__range=prev_rng)
    order_count, prev_order_count = orders.count(), prev_orders.count()
    cancelled = orders.filter(status=Order.Status.CANCELLED).count()
    delivered_count = recognized_orders().filter(delivered_at__range=rng).count()
    customers = User.objects.filter(is_staff=False)
    new_customers = customers.filter(date_joined__range=rng).count()
    prev_new_customers = customers.filter(date_joined__range=prev_rng).count()
    products = Product.objects.filter(status=Product.Status.ACTIVE)
    low = products.filter(stock_quantity__gt=0, stock_quantity__lte=F('low_stock_threshold')).count()
    out = products.filter(stock_quantity=0).count()
    pending_recognition = Order.objects.filter(payment_status=Order.PaymentStatus.PAID).exclude(
        status__in=[Order.Status.DELIVERED, Order.Status.CANCELLED]).aggregate(s=Sum('total'))['s'] or 0
    return {
        'revenue': revenue, 'revenue_change': _change(revenue, prev_revenue),
        'today_revenue': today_rev, 'today_change': _change(today_rev, yesterday_rev),
        'month_revenue': month_rev, 'month_change': _change(month_rev, prev_month_rev),
        'orders': order_count, 'orders_change': _change(order_count, prev_order_count),
        'pending_orders': Order.objects.filter(status=Order.Status.PENDING).count(),
        'active_products': products.count(),
        'customers': customers.count(), 'new_customers': new_customers,
        'new_customers_change': _change(new_customers, prev_new_customers),
        'low_stock': low, 'out_of_stock': out,
        'aov': revenue // delivered_count if delivered_count else 0,
        'aov_change': _change(revenue // delivered_count if delivered_count else 0,
                              _aov(prev_start, prev_end)),
        'cancel_rate': round(cancelled * 100 / order_count, 1) if order_count else 0,
        'pending_recognition': pending_recognition,
    }


def _aov(start: date, end: date) -> int:
    agg = recognized_orders().filter(delivered_at__range=(_aware(start), _aware(end, True))).aggregate(s=Sum('total'), n=Count('id'))
    return (agg['s'] or 0) // agg['n'] if agg['n'] else 0


WEEKDAYS = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']


def revenue_trend(period: str) -> dict:
    """Doanh thu ghi nhận cho biểu đồ Dashboard: 7d / 30d (theo ngày) hoặc 12m (theo tháng)."""
    today = timezone.localdate()
    if period == '12m':
        labels, values = [], []
        cursor = today.replace(day=1)
        months = []
        for _ in range(12):
            months.insert(0, cursor)
            cursor = (cursor - timedelta(days=1)).replace(day=1)
        rows = (recognized_orders().filter(delivered_at__gte=_aware(months[0]))
                .annotate(m=TruncMonth('delivered_at', tzinfo=timezone.get_current_timezone()))
                .values('m').annotate(total=Sum('total'), count=Count('id')))
        by_month = {(r['m'].year, r['m'].month): r for r in rows}
        counts = []
        for m in months:
            r = by_month.get((m.year, m.month), {})
            labels.append(f'T{m.month}/{m.year % 100}')
            values.append(r.get('total', 0) or 0)
            counts.append(r.get('count', 0) or 0)
        return {'labels': labels, 'datasets': [{'label': 'Doanh thu', 'data': values}], 'orders': counts}
    days = 30 if period == '30d' else 7
    data = revenue_daily(today - timedelta(days=days - 1), today)
    start = today - timedelta(days=days - 1)
    data['labels'] = [f'{WEEKDAYS[(start + timedelta(days=i)).weekday()]} {(start + timedelta(days=i)):%d/%m}' for i in range(days)]
    return data


def products_by_category() -> dict:
    """Số sản phẩm đang có trong DB theo nhóm danh mục cấp 1 (kèm slug để bấm lọc)."""
    from products.models import Category, Product

    groups = list(Category.objects.filter(parent__isnull=True).order_by('display_order'))
    counts = {}
    for g in groups:
        counts[g.pk] = Product.objects.filter(category_id__in=g.descendant_ids()).count()
    groups = [g for g in groups if counts[g.pk]]
    return {'labels': [g.name for g in groups], 'datasets': [{'label': 'Sản phẩm', 'data': [counts[g.pk] for g in groups]}],
            'slugs': [g.slug for g in groups], 'total': sum(counts.values())}


def revenue_daily(start: date, end: date) -> dict:
    """Doanh thu theo ngày – đủ mọi ngày trong kỳ (ngày không có doanh thu = 0)."""
    rows = (recognized_orders().filter(delivered_at__range=(_aware(start), _aware(end, True)))
            .annotate(day=TruncDate('delivered_at', tzinfo=timezone.get_current_timezone()))
            .values('day').annotate(total=Sum('total'), count=Count('id')))
    by_day = {r['day']: r for r in rows}
    labels, values, counts = [], [], []
    current = start
    while current <= end:
        row = by_day.get(current, {})
        labels.append(current.strftime('%d/%m'))
        values.append(row.get('total', 0) or 0)
        counts.append(row.get('count', 0) or 0)
        current += timedelta(days=1)
    return {'labels': labels, 'datasets': [{'label': 'Doanh thu', 'data': values}], 'orders': counts}


def revenue_monthly(year: int) -> dict:
    def by_month(y):
        rows = (recognized_orders().filter(delivered_at__year=y)
                .annotate(m=TruncMonth('delivered_at', tzinfo=timezone.get_current_timezone()))
                .values('m').annotate(total=Sum('total')))
        data = [0] * 12
        for r in rows:
            data[r['m'].month - 1] = r['total'] or 0
        return data

    return {'labels': [f'T{i}' for i in range(1, 13)],
            'datasets': [{'label': f'Năm {year}', 'data': by_month(year)},
                         {'label': f'Năm {year - 1}', 'data': by_month(year - 1)}]}


def _recognized_items(start: date, end: date):
    return OrderItem.objects.filter(order__status=Order.Status.DELIVERED, order__payment_status=Order.PaymentStatus.PAID,
                                    order__delivered_at__range=(_aware(start), _aware(end, True)))


def revenue_by_category(start: date, end: date) -> dict:
    """Doanh thu (trước giảm giá) theo danh mục gốc; danh mục < 3% gộp vào "Khác"."""
    rows = (_recognized_items(start, end)
            .values('product__category__name', 'product__category__parent__name')
            .annotate(total=Sum('line_total'), qty=Sum('quantity')))
    totals: dict[str, int] = {}
    for r in rows:
        name = r['product__category__parent__name'] or r['product__category__name'] or 'Khác'
        totals[name] = totals.get(name, 0) + (r['total'] or 0)
    grand = sum(totals.values())
    labels, values, other = [], [], 0
    for name, value in sorted(totals.items(), key=lambda x: -x[1]):
        if grand and value * 100 / grand < 3:
            other += value
        else:
            labels.append(name)
            values.append(value)
    if other:
        labels.append('Khác')
        values.append(other)
    return {'labels': labels, 'datasets': [{'label': 'Doanh thu', 'data': values}], 'total': grand}


def top_products(start: date, end: date, limit: int = 5) -> dict:
    rows = (_recognized_items(start, end).values('product_name')
            .annotate(qty=Sum('quantity'), revenue=Sum('line_total')).order_by('-qty', '-revenue')[:limit])
    return {'labels': [r['product_name'][:40] for r in rows],
            'datasets': [{'label': 'Số lượng bán', 'data': [r['qty'] for r in rows]}],
            'revenue': [r['revenue'] for r in rows]}


def orders_by_status(start: date, end: date) -> dict:
    rows = dict(Order.objects.filter(created_at__range=(_aware(start), _aware(end, True)))
                .values_list('status').annotate(c=Count('id')))
    return {'labels': [label for _, label in Order.Status.choices],
            'datasets': [{'label': 'Số đơn', 'data': [rows.get(code, 0) for code, _ in Order.Status.choices],
                          'backgroundColor': [STATUS_COLORS[code] for code, _ in Order.Status.choices]}]}


def revenue_report(start: date, end: date, group: str = 'day') -> list[dict]:
    """Bảng báo cáo doanh thu theo ngày/tuần/tháng: số đơn, doanh thu, giảm giá, phí ship, AOV."""
    from django.db.models.functions import TruncWeek

    trunc = {'day': TruncDate, 'week': TruncWeek, 'month': TruncMonth}.get(group, TruncDate)
    rows = (recognized_orders().filter(delivered_at__range=(_aware(start), _aware(end, True)))
            .annotate(period=trunc('delivered_at', tzinfo=timezone.get_current_timezone()))
            .values('period').annotate(orders=Count('id'), revenue=Sum('total'), discount=Sum('discount_amount'),
                                       shipping=Sum('shipping_fee')).order_by('period'))
    result = []
    for r in rows:
        period = r['period']
        if isinstance(period, datetime):
            period = timezone.localtime(period).date() if timezone.is_aware(period) else period.date()
        label = period.strftime('%m/%Y') if group == 'month' else (
            f'Tuần {period.strftime("%d/%m/%Y")}' if group == 'week' else period.strftime('%d/%m/%Y'))
        result.append({**r, 'label': label, 'aov': (r['revenue'] or 0) // r['orders'] if r['orders'] else 0})
    return result


def order_report(start: date, end: date) -> dict:
    orders = Order.objects.filter(created_at__range=(_aware(start), _aware(end, True)))
    total = orders.count()
    by_status = {code: 0 for code, _ in Order.Status.choices}
    by_status.update(dict(orders.values_list('status').annotate(c=Count('id'))))
    by_method = dict(orders.values_list('payment_method').annotate(c=Count('id')))
    reasons = list(orders.filter(status=Order.Status.CANCELLED).exclude(cancel_reason='')
                   .values('cancel_reason').annotate(c=Count('id')).order_by('-c')[:8])
    return {'total': total, 'by_status': by_status, 'by_method': by_method, 'reasons': reasons,
            'cancel_rate': round(by_status['cancelled'] * 100 / total, 1) if total else 0,
            'delivered': orders.filter(Q(status=Order.Status.DELIVERED)).count()}
