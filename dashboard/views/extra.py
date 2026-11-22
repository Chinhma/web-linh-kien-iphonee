"""Các trang Admin Panel bổ sung theo SPEC_ADMIN_PANEL: độ phủ linh kiện, nhập kho/kiểm kê, chờ hoàn tiền,
giảm giá hàng loạt, thống kê chatbot, câu hỏi chưa có câu trả lời, báo cáo khách hàng, hồ sơ của tôi."""

from collections import Counter
from datetime import timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.forms import style_fields
from chatbot.models import ChatConversation, ChatMessage
from core.permissions import staff_required
from core.utils import to_int
from inventory.services import StockError, import_stock, stocktake
from orders.models import Order
from orders.services import OrderError, mark_refunded
from products.models import Category, Compatibility, IPhoneModel, Product

from ..services import revenue
from .common import csv_response, table

User = get_user_model()


# ------------------------------------------------------------------ API gợi ý sản phẩm (ô chọn có ảnh + SKU)
@staff_required
def api_product_suggest(request):
    q = (request.GET.get('q') or '').strip()
    qs = Product.objects.prefetch_related('images').order_by('name')
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(part_code__icontains=q))
    return JsonResponse({'ok': True, 'data': {'products': [
        {'id': p.pk, 'name': p.name, 'sku': p.sku, 'image': p.image_url, 'stock': p.stock_quantity,
         'cost_price': p.cost_price, 'status': p.get_status_display()} for p in qs[:12]]}})


# ------------------------------------------------------------------ Độ phủ linh kiện
@staff_required
def compat_coverage(request):
    """Bảng hàng = dòng iPhone, cột = nhóm danh mục cấp 1, ô = số sản phẩm đang bán đã xác nhận tương thích."""
    groups = list(Category.objects.filter(parent__isnull=True, is_active=True).order_by('display_order'))
    group_of = {}
    for g in groups:
        for cid in g.descendant_ids():
            group_of[cid] = g.pk
    counts = Counter()
    for model_id, cat_id in Compatibility.objects.filter(status='verified', product__status='active').values_list(
            'iphone_model_id', 'product__category_id'):
        if cat_id in group_of:
            counts[(model_id, group_of[cat_id])] += 1
    models = list(IPhoneModel.objects.filter(is_active=True).order_by('-series', 'display_order'))
    rows = [{'model': m, 'cells': [(g, counts.get((m.pk, g.pk), 0)) for g in groups]} for m in models]
    zero = sum(1 for r in rows for _, n in r['cells'] if n == 0)
    return render(request, 'dashboard/compat_coverage.html', {
        'page_title': 'Độ phủ linh kiện', 'page_description': 'Số linh kiện đang bán đã xác nhận tương thích cho từng dòng máy theo nhóm. Ô vàng = chưa có linh kiện.',
        'groups': groups, 'rows': rows, 'zero': zero, 'zero_sub': f'trên tổng {len(rows) * len(groups)} ô'})


# ------------------------------------------------------------------ Kho: nhập kho nhiều dòng, kiểm kê
@staff_required
def inventory_import(request):
    if request.method == 'POST':
        ids, qtys, costs = request.POST.getlist('product'), request.POST.getlist('quantity'), request.POST.getlist('unit_cost')
        note = request.POST.get('note', '').strip()[:255]
        update_cost = bool(request.POST.get('update_cost_price'))
        done, errors = 0, []
        with transaction.atomic():
            for pid, qty, cost in zip(ids, qtys, costs):
                product = Product.objects.filter(pk=to_int(pid)).first()
                quantity = to_int(qty)
                if not product and not quantity:
                    continue
                if not product or not quantity or quantity <= 0:
                    errors.append('Mỗi dòng phải chọn sản phẩm và số lượng > 0.')
                    continue
                try:
                    import_stock(product, quantity, to_int(cost, minimum=0), request.user, note or 'Nhập kho', update_cost)
                    done += 1
                except StockError as exc:
                    errors.append(f'{product.name}: {exc}')
        for e in dict.fromkeys(errors):
            messages.error(request, e)
        if done:
            messages.success(request, f'Đã ghi phiếu nhập cho {done} sản phẩm.')
        return redirect(request.POST.get('next') or 'dashboard:inventory_history')
    product = Product.objects.filter(pk=to_int(request.GET.get('product'))).first()
    return render(request, 'dashboard/inventory_import.html', {
        'page_title': 'Nhập kho', 'page_description': 'Ghi phiếu nhập hàng, có thể nhập nhiều sản phẩm một lúc. Tồn kho được cộng qua service adjust_stock.',
        'preset': product})


@staff_required
def inventory_stocktake(request):
    if request.method == 'POST':
        product = Product.objects.filter(pk=to_int(request.POST.get('product'))).first()
        actual = to_int(request.POST.get('actual_quantity'), minimum=0)
        reason = request.POST.get('reason', '').strip()
        if not product or actual is None or not reason:
            messages.error(request, 'Vui lòng chọn sản phẩm, nhập số tồn thực tế (≥ 0) và lý do.')
        else:
            try:
                trx = stocktake(product, actual, request.user, reason)
                messages.success(request, f'Đã điều chỉnh "{product.name}": {trx.quantity_change:+d}.' if trx else 'Tồn kho không thay đổi.')
                return redirect('dashboard:inventory_history')
            except StockError as exc:
                messages.error(request, str(exc))
    product = Product.objects.filter(pk=to_int(request.GET.get('product') or request.POST.get('product'))).first()
    return render(request, 'dashboard/inventory_stocktake.html', {
        'page_title': 'Điều chỉnh kiểm kê', 'page_description': 'Nhập số tồn thực tế sau kiểm kê – hệ thống tự tính chênh lệch và ghi lịch sử.',
        'preset': product})


# ------------------------------------------------------------------ Thanh toán: chờ hoàn tiền
@staff_required
def payment_refunds(request):
    if request.method == 'POST':
        order = get_object_or_404(Order, code=request.POST.get('code', ''))
        ref = request.POST.get('refund_ref', '').strip()
        if not ref:
            messages.error(request, 'Vui lòng nhập mã giao dịch hoàn tiền.')
        else:
            try:
                mark_refunded(order, request.user, f'Mã giao dịch hoàn: {ref}. {request.POST.get("note", "").strip()}'.strip())
                messages.success(request, f'Đã đánh dấu hoàn tiền đơn {order.code}.')
            except OrderError as exc:
                messages.error(request, exc.message)
        return redirect('dashboard:payment_refunds')
    qs = Order.objects.filter(payment_status=Order.PaymentStatus.REFUND_PENDING).select_related('user').prefetch_related('payments')
    ctx = table(request, qs, ('code', 'recipient_name', 'user__email'), {'date': 'cancelled_at', 'total': 'total'}, '-date')
    return render(request, 'dashboard/payment_refunds.html', {
        **ctx, 'page_title': 'Chờ hoàn tiền', 'page_description': 'Đơn đã thanh toán online nhưng bị hủy – hoàn tiền cho khách ngoài hệ thống rồi đánh dấu tại đây.'})


# ------------------------------------------------------------------ Khuyến mãi: giảm giá sản phẩm hàng loạt
class BulkDiscountForm(forms.Form):
    category = forms.ModelChoiceField(label='Danh mục', queryset=Category.objects.all(), required=False,
                                      help_text='Áp dụng cho mọi sản phẩm trong danh mục (gồm danh mục con)')
    products = forms.ModelMultipleChoiceField(label='Hoặc chọn sản phẩm', queryset=Product.objects.order_by('name'), required=False,
                                              widget=forms.SelectMultiple(attrs={'size': 8}))
    percent = forms.IntegerField(label='Giảm (%)', min_value=1, max_value=90)
    sale_start = forms.DateTimeField(label='Bắt đầu', required=False, widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))
    sale_end = forms.DateTimeField(label='Kết thúc', required=False, widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)
        self.fields['percent'].required = False

    def clean(self):
        data = super().clean()
        if not data.get('category') and not data.get('products'):
            raise forms.ValidationError('Chọn một danh mục hoặc ít nhất một sản phẩm.')
        if data.get('sale_start') and data.get('sale_end') and data['sale_end'] <= data['sale_start']:
            self.add_error('sale_end', 'Thời gian kết thúc phải sau thời gian bắt đầu.')
        return data

    def targets(self):
        qs = Product.objects.none()
        if self.cleaned_data.get('category'):
            qs = Product.objects.filter(category_id__in=self.cleaned_data['category'].descendant_ids())
        if self.cleaned_data.get('products'):
            qs = qs | Product.objects.filter(pk__in=[p.pk for p in self.cleaned_data['products']])
        return qs.distinct().select_related('category').order_by('name')


@staff_required
def bulk_discount(request):
    form = BulkDiscountForm(request.POST or None)
    preview = []
    action = request.POST.get('action')
    if request.method == 'POST' and form.is_valid():
        products = list(form.targets())
        pct = form.cleaned_data.get('percent')
        if action == 'remove':
            n = Product.objects.filter(pk__in=[p.pk for p in products]).update(sale_price=None, sale_start=None, sale_end=None)
            messages.success(request, f'Đã gỡ giảm giá cho {n} sản phẩm.')
            return redirect('dashboard:bulk_discount')
        if not pct:
            form.add_error('percent', 'Nhập phần trăm giảm (1–90).')
        else:
            preview = [{'p': p, 'new': max(1000, p.price * (100 - pct) // 100 // 1000 * 1000)} for p in products]
            if action == 'apply':
                with transaction.atomic():
                    for row in preview:
                        if row['new'] < row['p'].price:
                            Product.objects.filter(pk=row['p'].pk).update(
                                sale_price=row['new'], sale_start=form.cleaned_data.get('sale_start'),
                                sale_end=form.cleaned_data.get('sale_end'))
                messages.success(request, f'Đã áp dụng giảm {pct}% cho {len(preview)} sản phẩm.')
                return redirect('dashboard:bulk_discount')
    return render(request, 'dashboard/bulk_discount.html', {
        'page_title': 'Giảm giá sản phẩm hàng loạt', 'page_description': 'Chọn danh mục hoặc sản phẩm → nhập % giảm → xem trước giá mới → Áp dụng.',
        'form': form, 'preview': preview,
        'on_sale': Product.objects.filter(sale_price__isnull=False).count()})


# ------------------------------------------------------------------ Chatbot: thống kê & câu hỏi chưa có câu trả lời
def _chat_topics():
    models_counter, cats_counter = Counter(), Counter()
    for meta in ChatMessage.objects.filter(role='assistant').values_list('meta', flat=True):
        if isinstance(meta, dict):
            if meta.get('iphone_model'):
                models_counter[meta['iphone_model']] += 1
            if meta.get('category'):
                cats_counter[meta['category']] += 1
    return models_counter.most_common(8), cats_counter.most_common(8)


@staff_required
def chatbot_stats(request):
    now = timezone.now()
    bot = ChatMessage.objects.filter(role='assistant')
    daily = {r['d']: r['c'] for r in ChatMessage.objects.filter(created_at__gte=now - timedelta(days=29))
             .annotate(d=TruncDate('created_at', tzinfo=timezone.get_current_timezone())).values('d').annotate(c=Count('id'))}
    days = [timezone.localdate() - timedelta(days=i) for i in range(29, -1, -1)]
    top_models, top_cats = _chat_topics()
    stats = {
        'conversations': ChatConversation.objects.count(),
        'today': ChatMessage.objects.filter(created_at__date=timezone.localdate()).count(),
        'avg_latency': int(bot.aggregate(a=Avg('latency_ms'))['a'] or 0),
        'error_rate': round(bot.filter(is_error=True).count() * 100 / bot.count(), 1) if bot.exists() else 0,
    }
    return render(request, 'dashboard/chatbot_stats.html', {
        'page_title': 'Thống kê chatbot', 'page_description': 'Hoạt động của iParts AI Assistant trong 30 ngày gần nhất.', 'stats': stats,
        'charts': {'daily': {'labels': [d.strftime('%d/%m') for d in days], 'data': [daily.get(d, 0) for d in days]},
                   'models': {'labels': [n for n, _ in top_models], 'data': [c for _, c in top_models]},
                   'categories': {'labels': [n for n, _ in top_cats], 'data': [c for _, c in top_cats]}}})


@staff_required
def chatbot_unanswered(request):
    """Câu hỏi mà chatbot không tìm thấy sản phẩm/tương thích – gợi ý Admin bổ sung dữ liệu."""
    rows = []
    for m in (ChatMessage.objects.filter(role='assistant', meta__no_result=True)
              .select_related('conversation', 'conversation__user').order_by('-created_at')[:200]):
        q = m.conversation.messages.filter(role='user', created_at__lte=m.created_at).order_by('-created_at', '-id').first()
        if q:
            rows.append({'question': q.content, 'time': m.created_at, 'conversation': m.conversation,
                         'model': (m.meta or {}).get('iphone_model', ''), 'category': (m.meta or {}).get('category', '')})
    model_slugs = dict(IPhoneModel.objects.values_list('name', 'pk'))
    for r in rows:
        r['model_pk'] = model_slugs.get(r['model'])
    from django.core.paginator import Paginator

    page = Paginator(rows, 20).get_page(request.GET.get('page'))
    return render(request, 'dashboard/chatbot_unanswered.html', {
        'page_title': 'Câu hỏi chưa có câu trả lời', 'page_obj': page, 'per_page': 20,
        'page_description': 'Khách hỏi nhưng hệ thống chưa có sản phẩm/tương thích phù hợp. Bổ sung dữ liệu để chatbot trả lời được.'})


# ------------------------------------------------------------------ Báo cáo khách hàng
@staff_required
def report_customers(request):
    start, end, key, error = revenue.resolve_range(request.GET.get('range', '30d'), request.GET.get('from', ''), request.GET.get('to', ''))
    if error:
        messages.error(request, error)
    rng = (revenue._aware(start), revenue._aware(end, True))
    customers = User.objects.filter(is_staff=False)
    new_qs = customers.filter(date_joined__range=rng)
    trend = {r['m']: r['c'] for r in customers.filter(date_joined__gte=timezone.now() - timedelta(days=365))
             .annotate(m=TruncMonth('date_joined', tzinfo=timezone.get_current_timezone())).values('m').annotate(c=Count('id'))}
    months = []
    cursor = timezone.localdate().replace(day=1)
    for _ in range(12):
        months.insert(0, cursor)
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    buyers = customers.annotate(n=Count('orders', filter=Q(orders__status='delivered')),
                                spent=Sum('orders__total', filter=Q(orders__status='delivered'))).filter(n__gt=0)
    repeat = buyers.filter(n__gte=2).count()
    top = buyers.order_by('-spent')[:10]
    if request.GET.get('export') == 'csv':
        return csv_response('bao-cao-khach-hang', ['Khách hàng', 'Email', 'Số đơn đã giao', 'Tổng chi tiêu'],
                            ([u.display_name, u.email, u.n, u.spent or 0] for u in buyers.order_by('-spent')))
    return render(request, 'dashboard/report_customers.html', {
        'page_title': 'Báo cáo khách hàng', 'range_key': key, 'range_labels': revenue.RANGE_LABELS,
        'date_from': start.isoformat(), 'date_to': end.isoformat(),
        'stats': {'total': customers.count(), 'new': new_qs.count(), 'buyers': buyers.count(),
                  'repeat_rate': round(repeat * 100 / buyers.count(), 1) if buyers.count() else 0},
        'top': top,
        'chart_data': {'new': {'labels': [f'T{m.month}/{m.year % 100}' for m in months],
                               'data': [next((c for k, c in trend.items() if k.year == m.year and k.month == m.month), 0)
                                        for m in months]}}})


# ------------------------------------------------------------------ Hồ sơ của tôi
class AdminProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['full_name', 'phone', 'avatar']  # Không có trường phân quyền

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)


@staff_required
def profile(request):
    user = request.user
    has_password = user.has_usable_password()
    pw_class = PasswordChangeForm if has_password else SetPasswordForm
    form = AdminProfileForm(instance=user)
    pw_form = pw_class(user)
    if request.method == 'POST' and request.POST.get('section') == 'profile':
        form = AdminProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Đã lưu hồ sơ.')
            return redirect('dashboard:profile')
    elif request.method == 'POST' and request.POST.get('section') == 'password':
        pw_form = pw_class(user, request.POST)
        if pw_form.is_valid():
            pw_form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Đã đổi mật khẩu.')
            return redirect('dashboard:profile')
    style_fields(pw_form)
    return render(request, 'dashboard/profile.html', {
        'page_title': 'Hồ sơ của tôi', 'form': form, 'pw_form': pw_form, 'has_password': has_password})


@staff_required
@require_POST
def toggle_field(request, model, pk):
    """Bật/tắt nhanh một trường boolean từ bảng danh sách (Nổi bật, Hoạt động...)."""
    from core.models import Banner, FAQ
    from promotions.models import Coupon

    allowed = {'product-featured': (Product, 'is_featured'), 'category-active': (Category, 'is_active'),
               'iphone-active': (IPhoneModel, 'is_active'), 'coupon-active': (Coupon, 'is_active'),
               'banner-active': (Banner, 'is_active'), 'faq-active': (FAQ, 'is_active')}
    if model not in allowed:
        return JsonResponse({'ok': False, 'message': 'Không hỗ trợ'}, status=404)
    klass, field = allowed[model]
    obj = get_object_or_404(klass, pk=pk)
    value = not getattr(obj, field)
    klass.objects.filter(pk=pk).update(**{field: value})
    return JsonResponse({'ok': True, 'data': {field: value, 'value': value}, 'message': 'Đã bật.' if value else 'Đã tắt.'})


@staff_required
@require_POST
def reorder(request, model):
    """Lưu thứ tự sau khi kéo thả: body JSON {"ids": [3, 1, 2]} → display_order = 1, 2, 3..."""
    import json as _json

    from core.models import FAQ, Banner

    allowed = {'banner': Banner, 'faq': FAQ}
    if model not in allowed:
        return JsonResponse({'ok': False, 'message': 'Không hỗ trợ'}, status=404)
    try:
        ids = [int(i) for i in _json.loads(request.body or b'{}').get('ids', [])][:500]
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({'ok': False, 'message': 'Dữ liệu không hợp lệ'}, status=400)
    klass = allowed[model]
    objs = {o.pk: o for o in klass.objects.filter(pk__in=ids)}
    for index, pk in enumerate(ids, start=1):
        if pk in objs:
            objs[pk].display_order = index
    klass.objects.bulk_update(objs.values(), ['display_order'])
    return JsonResponse({'ok': True, 'message': 'Đã lưu thứ tự.'})


@staff_required
@require_POST
def markdown_preview(request):
    """Xem trước nội dung trang (dùng đúng bộ lọc simple_markdown như trên website)."""
    import json as _json

    from core.templatetags.iparts import simple_markdown

    try:
        text = str(_json.loads(request.body or b'{}').get('text', ''))[:100000]
    except (ValueError, AttributeError):
        text = ''
    return JsonResponse({'ok': True, 'data': {'html': str(simple_markdown(text))}})
