"""AI System (chatbot), báo cáo, nội dung (newsletter, liên hệ), tài khoản Admin, cài đặt."""

import platform
import time
from datetime import timedelta

import django
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from chatbot.models import ChatbotSetting, ChatConversation, ChatMessage
from chatbot.services import gemini_client
from core.models import ContactMessage, NewsletterSubscriber, StoreSetting
from core.permissions import staff_required, superuser_required
from inventory.models import InventoryTransaction
from orders.models import Order, OrderItem
from payments.gateways import GATEWAYS
from products.models import Category, Product

from ..forms import AdminAccountForm, ChatbotSettingForm, StoreSettingForm
from ..services import revenue
from .common import csv_response, table

User = get_user_model()


# ------------------------------------------------------------------ Chatbot
@staff_required
def chatbot_settings(request):
    setting = ChatbotSetting.get_solo()
    form = ChatbotSettingForm(request.POST or None, instance=setting)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Đã lưu cấu hình iParts AI Assistant.')
        return redirect('dashboard:chatbot_settings')
    today = timezone.localdate()
    summary = {
        'today': ChatConversation.objects.filter(created_at__date=today).count(),
        'week': ChatConversation.objects.filter(created_at__gte=timezone.now() - timedelta(days=7)).count(),
        'unanswered': ChatMessage.objects.filter(role='assistant', meta__no_result=True).count(),
    }
    return render(request, 'dashboard/chatbot_settings.html', {
        'menu': 'chatbot', 'page_title': 'Cấu hình AI Chatbot', 'form': form, 'summary': summary,
        'page_description': 'Lời chào, câu hỏi gợi ý, thông tin bổ sung và giới hạn tin nhắn của iParts AI Assistant.',
        'gemini_configured': gemini_client.is_configured(), 'gemini_model': settings.GEMINI_MODEL,
        'suggestions': list(setting.suggested_questions or []),
    })


@staff_required
@require_POST
def chatbot_test(request):
    """Kiểm tra kết nối Gemini: gửi một câu thử và đo thời gian phản hồi."""
    if not gemini_client.is_configured():
        return JsonResponse({'ok': False, 'message': 'Chưa cấu hình GEMINI_API_KEY trong .env – chatbot đang chạy chế độ cơ bản.'})
    started = time.monotonic()
    try:
        from chatbot.prompts import build_system_prompt

        result = gemini_client.generate_reply(build_system_prompt(), [{'role': 'user', 'content': 'Xin chào, bạn là ai?'}])
        ms = int((time.monotonic() - started) * 1000)
        return JsonResponse({'ok': True, 'message': f'Kết nối thành công ({ms} ms): {result["reply"][:120]}'})
    except Exception as exc:
        return JsonResponse({'ok': False, 'message': f'Không kết nối được Gemini ({type(exc).__name__}). Kiểm tra API key, tên model hoặc quota.'})


@staff_required
def chat_history(request):
    qs = ChatConversation.objects.select_related('user').filter(message_count__gt=0)
    g = request.GET
    if g.get('who') == 'customer':
        qs = qs.filter(user__isnull=False)
    elif g.get('who') == 'guest':
        qs = qs.filter(user__isnull=True)
    if g.get('error') == '1':
        qs = qs.filter(has_error=True)
    if g.get('from'):
        qs = qs.filter(created_at__date__gte=g['from'])
    if g.get('to'):
        qs = qs.filter(created_at__date__lte=g['to'])
    q = (g.get('q') or '').strip()
    if q:
        qs = qs.filter(Q(messages__content__icontains=q) | Q(user__email__icontains=q)).distinct()
    ctx = table(request, qs, (), {'time': 'last_message_at', 'count': 'message_count'}, '-time')
    ctx['q'] = q
    return render(request, 'dashboard/chat_history.html', {**ctx, 'menu': 'chat_history', 'page_title': 'Lịch sử hội thoại'})


@staff_required
def chat_detail(request, pk):
    conversation = get_object_or_404(ChatConversation.objects.select_related('user'), pk=pk)
    return render(request, 'dashboard/chat_detail.html', {
        'menu': 'chat_history', 'page_title': f'Hội thoại #{conversation.pk}', 'conversation': conversation,
        'chat_messages': conversation.messages.all()})


# ------------------------------------------------------------------ Báo cáo
def _report_range(request):
    start, end, key, error = revenue.resolve_range(request.GET.get('range', '30d'), request.GET.get('from', ''), request.GET.get('to', ''))
    if error:
        messages.error(request, error)
    return start, end, key


def _base_ctx(request, menu, title, start, end, key):
    return {'menu': menu, 'page_title': title, 'range_key': key, 'range_labels': revenue.RANGE_LABELS,
            'date_from': start.isoformat(), 'date_to': end.isoformat()}


@staff_required
def report_revenue(request):
    start, end, key = _report_range(request)
    group = request.GET.get('group', 'day') if request.GET.get('group') in ('day', 'week', 'month') else 'day'
    rows = revenue.revenue_report(start, end, group)
    if request.GET.get('export') == 'csv':
        return csv_response('bao-cao-doanh-thu', ['Kỳ', 'Số đơn', 'Doanh thu', 'Giảm giá', 'Phí ship', 'Giá trị TB/đơn'],
                            ([r['label'], r['orders'], r['revenue'], r['discount'], r['shipping'], r['aov']] for r in rows))
    totals = {k: sum(r[k] or 0 for r in rows) for k in ('orders', 'revenue', 'discount', 'shipping')}
    # So sánh với kỳ trước có cùng độ dài
    length = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=length - 1)
    prev_rows = revenue.revenue_report(prev_start, prev_end, 'month')
    prev = {k: sum(r[k] or 0 for r in prev_rows) for k in ('orders', 'revenue')}

    def change(cur, old):
        return None if not old else round((cur - old) * 100 / old, 1)

    compare = {'label': f'{prev_start:%d/%m/%Y} – {prev_end:%d/%m/%Y}', 'revenue': prev['revenue'], 'orders': prev['orders'],
               'revenue_change': change(totals['revenue'], prev['revenue']), 'orders_change': change(totals['orders'], prev['orders'])}
    return render(request, 'dashboard/report_revenue.html', {
        **_base_ctx(request, 'report_revenue', 'Báo cáo doanh thu', start, end, key), 'rows': rows, 'group': group,
        'totals': totals, 'compare': compare, 'chart': {'labels': [r['label'] for r in rows], 'data': [r['revenue'] for r in rows]}})


@staff_required
def report_products(request):
    start, end, key = _report_range(request)
    items = revenue._recognized_items(start, end)
    rows = list(items.values('product_id', 'product_name', 'product_sku').annotate(
        qty=Sum('quantity'), revenue=Sum('line_total'), cost=Sum(F('quantity') * F('product__cost_price'))))
    for r in rows:
        r['profit'] = (r['revenue'] or 0) - (r['cost'] or 0)
    ratings = {p.pk: p for p in Product.objects.filter(pk__in=[r['product_id'] for r in rows])}
    for r in rows:
        p = ratings.get(r['product_id'])
        r['rating_avg'], r['rating_count'] = (p.rating_avg, p.rating_count) if p else (0, 0)
    sort = request.GET.get('sort', '-qty')
    if sort.lstrip('-') in ('qty', 'revenue', 'profit', 'rating_avg', 'product_name'):
        rows.sort(key=lambda r: r[sort.lstrip('-')] or 0 if sort.lstrip('-') != 'product_name' else r['product_name'],
                  reverse=sort.startswith('-'))
    unsold = Product.objects.filter(status='active').exclude(pk__in=[r['product_id'] for r in rows if r['product_id']])
    if request.GET.get('export') == 'csv':
        return csv_response('bao-cao-san-pham', ['SKU', 'Sản phẩm', 'SL bán', 'Doanh thu', 'Lợi nhuận gộp ước tính', 'Điểm TB', 'Số đánh giá'],
                            ([r['product_sku'], r['product_name'], r['qty'], r['revenue'], r['profit'], r['rating_avg'], r['rating_count']] for r in rows))
    return render(request, 'dashboard/report_products.html', {
        **_base_ctx(request, 'report_products', 'Báo cáo sản phẩm', start, end, key), 'rows': rows, 'unsold': unsold[:30],
        'sort': sort})


@staff_required
def report_categories(request):
    start, end, key = _report_range(request)
    data = revenue.revenue_by_category(start, end)
    qty = {}
    for r in revenue._recognized_items(start, end).values('product__category__name', 'product__category__parent__name').annotate(q=Sum('quantity')):
        name = r['product__category__parent__name'] or r['product__category__name'] or 'Khác'
        qty[name] = qty.get(name, 0) + r['q']
    total = data['total'] or 0
    rows = [{'name': n, 'revenue': v, 'qty': qty.get(n, ''), 'percent': round(v * 100 / total, 1) if total else 0}
            for n, v in zip(data['labels'], data['datasets'][0]['data'])]
    if request.GET.get('export') == 'csv':
        return csv_response('bao-cao-danh-muc', ['Danh mục', 'Doanh thu', 'Số lượng bán', 'Tỉ lệ %'],
                            ([r['name'], r['revenue'], r['qty'], r['percent']] for r in rows))
    return render(request, 'dashboard/report_categories.html', {
        **_base_ctx(request, 'report_categories', 'Báo cáo danh mục', start, end, key), 'rows': rows, 'total': total,
        'chart': {'labels': data['labels'], 'data': data['datasets'][0]['data']}})


@staff_required
def report_orders(request):
    start, end, key = _report_range(request)
    data = revenue.order_report(start, end)
    if request.GET.get('export') == 'csv':
        rows = [[Order.Status(k).label, v] for k, v in data['by_status'].items()]
        rows += [[f'Thanh toán: {Order.PaymentMethod(k).label}', v] for k, v in data['by_method'].items()]
        return csv_response('bao-cao-don-hang', ['Chỉ tiêu', 'Số đơn'], rows)
    return render(request, 'dashboard/report_orders.html', {
        **_base_ctx(request, 'report_orders', 'Báo cáo đơn hàng', start, end, key), 'data': data,
        'status_rows': [(Order.Status(k).label, k, v) for k, v in data['by_status'].items()],
        'method_rows': [(Order.PaymentMethod(k).label, v) for k, v in data['by_method'].items()]})


@staff_required
def report_inventory(request):
    start, end, key = _report_range(request)
    rng = (revenue._aware(start), revenue._aware(end, True))
    movement = {r['product_id']: r for r in InventoryTransaction.objects.filter(created_at__range=rng).values('product_id').annotate(
        imported=Sum('quantity_change', filter=Q(type='import')),
        exported=Sum('quantity_change', filter=Q(type='export_order')),
        returned=Sum('quantity_change', filter=Q(type='return_cancel')))}
    products = Product.objects.select_related('category').annotate(stock_value=F('stock_quantity') * F('cost_price')).order_by('stock_quantity')
    rows = []
    for p in products:
        m = movement.get(p.pk, {})
        rows.append({'p': p, 'imported': m.get('imported') or 0, 'exported': -(m.get('exported') or 0), 'returned': m.get('returned') or 0})
    if request.GET.get('export') == 'csv':
        return csv_response('bao-cao-kho', ['SKU', 'Sản phẩm', 'Tồn hiện tại', 'Ngưỡng', 'Giá trị tồn', 'Nhập trong kỳ', 'Xuất trong kỳ', 'Hoàn kho'],
                            ([r['p'].sku, r['p'].name, r['p'].stock_quantity, r['p'].low_stock_threshold, r['p'].stock_value,
                              r['imported'], r['exported'], r['returned']] for r in rows))
    totals = {'value': sum(r['p'].stock_value for r in rows), 'low': sum(1 for r in rows if r['p'].stock_status == 'low_stock'),
              'out': sum(1 for r in rows if r['p'].stock_status == 'out_of_stock'),
              'imported': sum(r['imported'] for r in rows), 'exported': sum(r['exported'] for r in rows)}
    return render(request, 'dashboard/report_inventory.html', {
        **_base_ctx(request, 'report_inventory', 'Báo cáo kho hàng', start, end, key), 'rows': rows, 'totals': totals})


# ------------------------------------------------------------------ Nội dung
@staff_required
def newsletter_list(request):
    qs = NewsletterSubscriber.objects.all()
    if request.GET.get('export') == 'csv':
        return csv_response('newsletter', ['Email', 'Ngày đăng ký'],
                            ([s.email, timezone.localtime(s.created_at).strftime('%d/%m/%Y %H:%M')] for s in qs))
    ctx = table(request, qs, ('email',), {'email': 'email', 'date': 'created_at'}, '-date')
    return render(request, 'dashboard/newsletter.html', {**ctx, 'menu': 'newsletter', 'page_title': 'Newsletter'})


@staff_required
@require_POST
def newsletter_delete(request, pk):
    get_object_or_404(NewsletterSubscriber, pk=pk).delete()
    messages.success(request, 'Đã xóa email khỏi danh sách nhận tin.')
    return redirect('dashboard:newsletter')


@staff_required
def contact_list(request):
    status = request.GET.get('status', 'new')
    qs = ContactMessage.objects.all()
    if status == 'new':
        qs = qs.filter(is_read=False)
    elif status == 'done':
        qs = qs.filter(is_read=True)
    ctx = table(request, qs, ('name', 'email', 'phone', 'message'), {'date': 'created_at'}, '-date')
    unread = ContactMessage.objects.filter(is_read=False).count()
    tabs = [('new', 'Mới', unread), ('done', 'Đã xử lý', ContactMessage.objects.filter(is_read=True).count()),
            ('all', 'Tất cả', ContactMessage.objects.count())]
    return render(request, 'dashboard/contacts.html', {
        **ctx, 'menu': 'contact', 'page_title': 'Tin nhắn liên hệ', 'status': status, 'tabs': tabs,
        'page_description': 'Tin nhắn khách gửi từ trang Liên hệ. Đánh dấu “Đã xử lý” sau khi đã phản hồi.'})


@staff_required
@require_POST
def contact_read(request, pk):
    """Chuyển trạng thái Mới ⇄ Đã xử lý."""
    msg = get_object_or_404(ContactMessage, pk=pk)
    msg.is_read = not msg.is_read
    msg.save(update_fields=['is_read'])
    messages.success(request, 'Đã đánh dấu đã xử lý.' if msg.is_read else 'Đã chuyển về trạng thái mới.')
    nxt = request.POST.get('next', '')
    return redirect(nxt if nxt.startswith('/quan-tri/') else 'dashboard:contacts')


# ------------------------------------------------------------------ Hệ thống
def _random_password(length=12):
    import secrets
    import string

    alphabet = string.ascii_letters + string.digits
    while True:
        pwd = ''.join(secrets.choice(alphabet) for _ in range(length))
        if any(c.isdigit() for c in pwd) and any(c.isalpha() for c in pwd):
            return pwd


@superuser_required
def admin_accounts(request):
    form = AdminAccountForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
        from accounts.adapters import SocialAccountAdapter

        user = User(username=SocialAccountAdapter._unique_username(cd['email'].split('@')[0]), email=cd['email'],
                    full_name=cd['full_name'], is_staff=True, is_superuser=cd['is_superuser'])
        password = cd['password'] or _random_password()
        user.set_password(password)
        user.save()
        if not cd['password']:
            # Mật khẩu ngẫu nhiên chỉ hiển thị đúng 1 lần (lấy ra khỏi session ngay khi hiển thị)
            request.session['new_admin_credential'] = {'login': user.username, 'email': user.email, 'password': password}
        messages.success(request, f'Đã tạo tài khoản quản trị {user.email}. Hãy yêu cầu người dùng đổi mật khẩu tạm.')
        return redirect('dashboard:admin_accounts')
    return render(request, 'dashboard/admin_accounts.html', {
        'menu': 'admins', 'page_title': 'Tài khoản Admin', 'form': form,
        'new_credential': request.session.pop('new_admin_credential', None),
        'page_description': 'Chỉ Superuser quản lý. Admin: quản lý cửa hàng; Superuser: thêm quản lý tài khoản Admin và Django admin.',
        'admins': User.objects.filter(is_staff=True).exclude(username='seed_admin').order_by('-is_superuser', 'email')})


@superuser_required
@require_POST
def admin_account_action(request, pk):
    target = get_object_or_404(User, pk=pk, is_staff=True)
    action = request.POST.get('action')
    if target == request.user and action in ('revoke', 'lock', 'superuser'):
        messages.error(request, 'Bạn không thể tự khóa, thu hồi hoặc đổi vai trò của chính mình.')
        return redirect('dashboard:admin_accounts')
    last_superuser = (target.is_superuser and target.is_active
                      and User.objects.filter(is_superuser=True, is_active=True).count() <= 1)
    if action in ('revoke', 'lock') and last_superuser:
        messages.error(request, 'Không thể thu hồi quyền/khóa Superuser cuối cùng của hệ thống.')
        return redirect('dashboard:admin_accounts')
    if action == 'revoke':
        target.is_staff = target.is_superuser = False
        messages.success(request, f'Đã thu hồi quyền quản trị của {target.email}.')
    elif action == 'lock':
        target.is_active = not target.is_active
        messages.success(request, f'Đã {"mở khóa" if target.is_active else "khóa"} {target.email}.')
    elif action == 'superuser' and target != request.user:
        target.is_superuser = not target.is_superuser
        if not target.is_superuser and last_superuser:
            messages.error(request, 'Không thể bỏ quyền Superuser cuối cùng.')
            return redirect('dashboard:admin_accounts')
        messages.success(request, f'Đã cập nhật quyền Superuser của {target.email}.')
    else:
        messages.error(request, 'Thao tác không hợp lệ.')
        return redirect('dashboard:admin_accounts')
    target.save()
    return redirect('dashboard:admin_accounts')


@staff_required
def store_settings(request):
    store = StoreSetting.get_solo()
    form = StoreSettingForm(request.POST or None, request.FILES or None, instance=store)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Đã lưu cài đặt cửa hàng – thay đổi có hiệu lực ngay trên website.')
        tab = request.POST.get('tab', '')
        return redirect(f"{request.path}?tab={tab}" if tab in SETTING_TABS else 'dashboard:store_settings')
    tab = request.GET.get('tab', 'info')
    if form.errors:  # mở tab chứa trường lỗi đầu tiên
        first = next(iter(form.errors))
        tab = next((k for k, fields in SETTING_TAB_FIELDS.items() if first in fields), tab)
    return render(request, 'dashboard/store_settings.html', {
        'menu': 'settings', 'page_title': 'Cài đặt cửa hàng', 'form': form, 'tab': tab if tab in SETTING_TABS else 'info',
        'tabs': SETTING_TABS, 'checks': _integration_checks(), 'python_version': platform.python_version(),
        'django_version': django.get_version(), 'debug': settings.DEBUG,
        'gateways': {code: gw.is_configured() for code, gw in GATEWAYS.items()}})


SETTING_TABS = {'info': 'Thông tin cửa hàng', 'shipping': 'Vận chuyển & thanh toán', 'contact': 'Liên hệ & mạng xã hội',
                'integrations': 'Trạng thái tích hợp'}
SETTING_TAB_FIELDS = {
    'info': ['store_name', 'logo', 'about_short', 'address', 'working_hours', 'announcement_text', 'show_sample_data_notice'],
    'shipping': ['shipping_fee_standard', 'shipping_fee_express', 'free_shipping_threshold', 'enable_cod', 'enable_vnpay',
                 'enable_momo', '__all__'],
    'contact': ['hotline', 'email', 'zalo_url', 'messenger_url', 'telegram_url', 'facebook_url'],
}


def _integration_checks():
    return [
        ('Google OAuth', settings.GOOGLE_OAUTH_CONFIGURED, 'GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET', 'Đăng nhập bằng Google cho khách hàng.'),
        ('Gemini API', gemini_client.is_configured(), f'GEMINI_API_KEY (model: {settings.GEMINI_MODEL})', 'Chưa có: chatbot chạy chế độ cơ bản.'),
        ('VNPay Sandbox', GATEWAYS['vnpay'].is_configured(), 'VNPAY_TMN_CODE, VNPAY_HASH_SECRET', 'Chưa có: VNPay hiện “Đang bảo trì” ở checkout.'),
        ('MoMo Sandbox', GATEWAYS['momo'].is_configured(), 'MOMO_PARTNER_CODE, MOMO_ACCESS_KEY, MOMO_SECRET_KEY', 'Chưa có: MoMo hiện “Đang bảo trì”.'),
        ('SMTP Email', settings.SMTP_CONFIGURED and 'smtp' in settings.EMAIL_BACKEND, 'EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, EMAIL_BACKEND',
         'Chưa có: email chỉ in ra console (không gửi thật).'),
    ]


@staff_required
def system_info(request):
    """Trạng thái cấu hình (KHÔNG hiển thị giá trị key)."""
    checks = [c[:3] for c in _integration_checks()]
    return render(request, 'dashboard/system_info.html', {
        'menu': 'system', 'page_title': 'Cài đặt hệ thống', 'checks': checks,
        'python_version': platform.python_version(), 'django_version': django.get_version(), 'debug': settings.DEBUG,
        'counts': {'Sản phẩm': Product.objects.count(), 'Danh mục': Category.objects.count(), 'Đơn hàng': Order.objects.count(),
                   'Khách hàng': User.objects.filter(is_staff=False).count(), 'Dòng sản phẩm đã bán': OrderItem.objects.count()}})
