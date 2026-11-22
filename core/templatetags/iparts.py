"""Template filter/tag dùng chung: định dạng tiền VND, ngày giờ, badge trạng thái, markdown an toàn."""

import re

from django import template
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def vnd(value) -> str:
    """1250000 -> '1.250.000₫'."""
    try:
        number = int(round(float(value or 0)))
    except (TypeError, ValueError):
        return ''
    sign = '-' if number < 0 else ''
    return f'{sign}{abs(number):,}'.replace(',', '.') + '₫'


@register.filter
def dt(value) -> str:
    """Định dạng '19/11/2026 14:30' theo giờ Việt Nam."""
    if not value:
        return ''
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return value.strftime('%d/%m/%Y %H:%M')


@register.filter
def d(value) -> str:
    if not value:
        return ''
    if hasattr(value, 'tzinfo') and timezone.is_aware(value):
        value = timezone.localtime(value)
    return value.strftime('%d/%m/%Y')


BADGE_COLORS = {
    # Đơn hàng
    'pending': 'warning', 'confirmed': 'primary', 'preparing': 'primary', 'shipping': 'primary-strong',
    'delivered': 'success', 'cancelled': 'danger',
    # Thanh toán
    'unpaid': 'muted', 'paid': 'success', 'failed': 'danger', 'refund_pending': 'warning', 'refunded': 'muted',
    'success': 'success',
    # Tồn kho
    'in_stock': 'success', 'low_stock': 'warning', 'out_of_stock': 'danger',
    # Tương thích / đánh giá / sản phẩm
    'verified': 'success', 'unverified': 'warning', 'incompatible': 'danger',
    'approved': 'success', 'hidden': 'muted', 'active': 'success', 'draft': 'muted', 'discontinued': 'danger',
    'running': 'success', 'upcoming': 'primary', 'expired': 'muted', 'disabled': 'danger',
}


@register.filter
def badge_color(status) -> str:
    return BADGE_COLORS.get(str(status), 'muted')


@register.inclusion_tag('includes/components/badge.html')
def status_badge(status, label=''):
    return {'color': badge_color(status), 'label': label or status}


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    """Giữ nguyên tham số lọc trên URL khi chuyển trang / đổi sắp xếp."""
    query = context['request'].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ''):
            query.pop(key, None)
        else:
            query[key] = value
    return query.urlencode()


@register.simple_tag(takes_context=True)
def url_without(context, key, value=None):
    """Bỏ một giá trị lọc khỏi URL (dùng cho chip bộ lọc)."""
    query = context['request'].GET.copy()
    if value is None:
        query.pop(key, None)
    else:
        values = [v for v in query.getlist(key) if v != str(value)]
        query.setlist(key, values)
    query.pop('page', None)
    return query.urlencode()


@register.filter
def stars(value):
    """Trả danh sách 5 phần tử 'full' / 'half' / 'empty' để vẽ sao."""
    try:
        rating = float(value or 0)
    except (TypeError, ValueError):
        rating = 0
    result = []
    for i in range(1, 6):
        if rating >= i - 0.25:
            result.append('full')
        elif rating >= i - 0.75:
            result.append('half')
        else:
            result.append('empty')
    return result


@register.filter
def initials(user) -> str:
    name = getattr(user, 'display_name', '') or getattr(user, 'username', '') or '?'
    return name.strip()[:1].upper()


_MD_BOLD = re.compile(r'\*\*(.+?)\*\*')
_MD_ITALIC = re.compile(r'(?<![\w/])_(.+?)_(?![\w/])')
_MD_LINK =re.compile(r'\[([^\]]+)\]\((/[^)\s]*|https?://[^)\s]+)\)')


@register.filter
def simple_markdown(text) -> str:
    """Markdown tối giản AN TOÀN: escape HTML trước, sau đó mới chuyển tiêu đề, in đậm, danh sách, link."""
    html_lines = []
    in_list = False
    for raw in escape(text or '').splitlines():
        line = raw.strip()
        line = _MD_BOLD.sub(r'<strong>\1</strong>', line)
        line = _MD_ITALIC.sub(r'<em>\1</em>', line)
        line = _MD_LINK.sub(r'<a href="\2" class="text-primary underline">\1</a>', line)
        if line.startswith(('- ', '* ')):
            if not in_list:
                html_lines.append('<ul class="list-disc pl-6 space-y-1">')
                in_list = True
            html_lines.append(f'<li>{line[2:]}</li>')
            continue
        if in_list:
            html_lines.append('</ul>')
            in_list = False
        if line.startswith('### '):
            html_lines.append(f'<h4 class="font-semibold text-lg mt-4">{line[4:]}</h4>')
        elif line.startswith('## '):
            html_lines.append(f'<h3 class="font-semibold text-xl mt-6">{line[3:]}</h3>')
        elif line:
            html_lines.append(f'<p>{line}</p>')
    if in_list:
        html_lines.append('</ul>')
    return mark_safe('\n'.join(html_lines))


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def percent_of(value, total):
    try:
        return round(float(value) * 100 / float(total)) if float(total) else 0
    except (TypeError, ValueError):
        return 0
