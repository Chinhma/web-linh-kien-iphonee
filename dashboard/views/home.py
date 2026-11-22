"""Đăng nhập Admin, Dashboard tổng quan, API biểu đồ, thông báo và tìm kiếm nhanh."""

from django.contrib import messages
from django.contrib.auth import get_user_model, logout
from django.db.models import F, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.forms import LoginForm
from accounts.views import _finish_login, authenticate_with_limit
from core.permissions import safe_next_url, staff_required
from core.utils import to_int
from orders.models import Order
from products.models import Product
from reviews.models import Review

from ..services import revenue

User = get_user_model()


def admin_login(request):
    """Trang đăng nhập riêng iParts Store Admin. Tài khoản không phải staff không được đăng nhập ở đây."""
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('dashboard:home')
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = authenticate_with_limit(request, form, staff_only=True)
        if user is not None:
            _finish_login(request, user, form.cleaned_data['remember'])
            messages.success(request, f'Xin chào {user.display_name}!')
            return redirect(safe_next_url(request, '/quan-tri/'))
    return render(request, 'dashboard/login.html', {'form': form, 'next': safe_next_url(request, '')})


@require_POST
def admin_logout(request):
    logout(request)
    messages.success(request, 'Bạn đã đăng xuất.')
    return redirect('dashboard:login')


def _range(request):
    return revenue.resolve_range(request.GET.get('range', '7d'), request.GET.get('from', ''), request.GET.get('to', ''))


@staff_required
def home(request):
    from orders.services import expire_unpaid_orders

    expire_unpaid_orders()
    start, end, key, error = _range(request)
    if error:
        messages.error(request, error)
    low_stock = (Product.objects.filter(status='active', stock_quantity__lte=F('low_stock_threshold'))
                 .select_related('category').prefetch_related('images').order_by('stock_quantity')[:8])
    from reviews.models import Review

    stats = revenue.summary(start, end)
    return render(request, 'dashboard/home.html', {
        'page_title': 'Dashboard', 'page_description': f'Tình hình kinh doanh – {revenue.RANGE_LABELS.get(key, "").lower()}',
        'stats': stats, 'range_key': key, 'range_labels': revenue.RANGE_LABELS,
        'date_from': start.isoformat(), 'date_to': end.isoformat(),
        'pending_reviews': Review.objects.filter(status='pending').count(),
        'recent_orders': Order.objects.select_related('user').order_by('-created_at')[:8],
        'low_stock': low_stock,
    })


@staff_required
def stats_api(request, kind):
    """API biểu đồ (chỉ staff): summary, revenue-daily, revenue-monthly, revenue-by-category, top-products, orders-by-status."""
    start, end, _, error = _range(request)
    if error:
        return JsonResponse({'ok': False, 'message': error}, status=400)
    if kind == 'summary':
        data = revenue.summary(start, end)
    elif kind == 'revenue-daily':
        data = revenue.revenue_daily(start, end)
    elif kind == 'revenue-monthly':
        data = revenue.revenue_monthly(to_int(request.GET.get('year'), timezone.localdate().year, 2000, 2100))
    elif kind == 'revenue-trend':
        data = revenue.revenue_trend(request.GET.get('period', '7d'))
    elif kind == 'products-by-category':
        data = revenue.products_by_category()
    elif kind == 'revenue-by-category':
        data = revenue.revenue_by_category(start, end)
    elif kind == 'top-products':
        data = revenue.top_products(start, end, to_int(request.GET.get('limit'), 5, 1, 20))
    elif kind == 'orders-by-status':
        data = revenue.orders_by_status(start, end)
    else:
        return JsonResponse({'ok': False, 'message': 'Không hỗ trợ'}, status=404)
    return JsonResponse({'ok': True, 'data': data})


@staff_required
def notifications_api(request):
    pending = Order.objects.filter(status='pending').order_by('-created_at')
    low = Product.objects.filter(status='active', stock_quantity__lte=F('low_stock_threshold')).order_by('stock_quantity')
    reviews = Review.objects.filter(status='pending')
    items = [{'icon': 'shopping-bag', 'text': f'Đơn mới {o.code} – {o.recipient_name}', 'url': f'/quan-tri/don-hang/{o.code}/'}
             for o in pending[:5]]
    items += [{'icon': 'package-x', 'text': f'{p.name[:40]} – còn {p.stock_quantity}', 'url': f'/quan-tri/kho-hang/?product={p.pk}'}
              for p in low[:5]]
    if reviews.exists():
        items.append({'icon': 'star', 'text': f'{reviews.count()} đánh giá chờ duyệt', 'url': '/quan-tri/danh-gia/?status=pending'})
    return JsonResponse({'ok': True, 'data': {'count': pending.count() + low.count() + reviews.count(), 'items': items}})


@staff_required
def quick_search(request):
    q = (request.GET.get('q') or '').strip()[:100]
    results = []
    if len(q) >= 2:
        results += [{'type': 'Đơn hàng', 'text': f'{o.code} – {o.recipient_name}', 'url': f'/quan-tri/don-hang/{o.code}/'}
                    for o in Order.objects.filter(Q(code__icontains=q) | Q(recipient_phone__icontains=q))[:5]]
        results += [{'type': 'Sản phẩm', 'text': f'{p.name} ({p.sku})', 'url': f'/quan-tri/san-pham/{p.pk}/sua/'}
                    for p in Product.objects.filter(Q(name__icontains=q) | Q(sku__icontains=q))[:5]]
        results += [{'type': 'Khách hàng', 'text': f'{u.display_name} – {u.email}', 'url': f'/quan-tri/khach-hang/{u.pk}/'}
                    for u in User.objects.filter(is_staff=False).filter(Q(email__icontains=q) | Q(full_name__icontains=q))[:5]]
    return JsonResponse({'ok': True, 'data': {'results': results}})
