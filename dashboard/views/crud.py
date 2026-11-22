"""Cấu hình CRUD cho các model đơn giản."""

from django.db.models import Count, Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import format_html

from core.models import FAQ, Banner, Page
from core.permissions import staff_required
from core.templatetags.iparts import d, vnd
from products.models import Brand, Category, IPhoneModel
from promotions.models import Coupon

from ..forms import BannerForm, BrandForm, CategoryForm, CouponForm, FAQForm, IPhoneModelForm, PageForm
from .common import CrudConfig, crud_delete, crud_form, crud_list


def _active(obj):
    return format_html('<span class="badge-{}">{}</span>', 'success' if obj.is_active else 'muted',
                       'Hoạt động' if obj.is_active else 'Tắt')


def _category_delete_check(cat):
    count = cat.products.count()
    if count:
        return f'Không thể xóa: danh mục "{cat.name}" còn {count} sản phẩm.'
    if cat.children.exists():
        return 'Không thể xóa: danh mục còn danh mục con.'
    return ''


def _iphone_delete_check(model):
    count = model.compatibilities.count()
    return f'Không thể xóa: "{model.name}" đang có {count} dữ liệu tương thích. Hãy tắt (ẩn) dòng máy thay vì xóa.' if count else ''


def _switch(url_model):
    """Cột công tắc bật/tắt nhanh (AJAX) – dùng component switch.html."""
    def render(obj):
        return render_to_string('dashboard/components/switch.html', {'url_model': url_model, 'obj': obj, 'on': obj.is_active})
    return render


def _coupon_usage(c):
    if not c.usage_limit:
        return format_html('<span class="text-sm">{} / ∞</span>', c.used_count)
    pct = min(100, round(c.used_count * 100 / c.usage_limit))
    color = 'bg-danger' if pct >= 90 else 'bg-warning' if pct >= 60 else 'bg-success'
    return format_html('<div class="w-28"><div class="text-xs">{} / {}</div><div class="mt-1 h-1.5 rounded-full bg-slate-100">'
                       '<div class="h-1.5 rounded-full {}" style="width:{}%"></div></div></div>', c.used_count, c.usage_limit, color, pct)


def coupon_state_q(value):
    now = timezone.now()
    return {'running': Q(is_active=True, start_at__lte=now, end_at__gte=now), 'upcoming': Q(is_active=True, start_at__gt=now),
            'expired': Q(is_active=True, end_at__lt=now), 'disabled': Q(is_active=False)}.get(value, Q())


COUPON_STATE_FILTER = ('state', 'Tình trạng', [('running', 'Đang chạy'), ('upcoming', 'Sắp diễn ra'), ('expired', 'Hết hạn'),
                                               ('disabled', 'Tắt')], coupon_state_q)


def _coupon_state(c):
    color = {'running': 'success', 'upcoming': 'primary', 'expired': 'muted', 'disabled': 'danger'}[c.state]
    return format_html('<span class="badge-{}">{}</span>', color, c.state_label)


ACTIVE_FILTER = ('is_active', 'Trạng thái', [('1', 'Hoạt động'), ('0', 'Tắt')], 'is_active')

CONFIGS = {
    'category': CrudConfig(
        key='category', model=Category, form_class=CategoryForm, title='Danh mục linh kiện', singular='danh mục',
        columns=[('Tên', lambda c: format_html('<i data-lucide="{}" class="mr-2 inline h-4 w-4 text-primary"></i>{}', c.icon, c.name), 'name'),
                 ('Mã', 'code', 'code'), ('Danh mục cha', lambda c: c.parent.name if c.parent_id else '—', None),
                 ('Số sản phẩm', 'product_total', 'product_total'), ('Thứ tự', 'display_order', 'display_order'),
                 ('Trạng thái', _active, None)],
        search_fields=('name', 'code'), sort_fields={'name': 'name', 'code': 'code', 'product_total': 'product_total',
                                                     'display_order': 'display_order'},
        default_sort='display_order', queryset=lambda: Category.objects.select_related('parent').annotate(product_total=Count('products')),
        filters=[ACTIVE_FILTER], delete_check=_category_delete_check),
    'brand': CrudConfig(
        key='brand', model=Brand, form_class=BrandForm, title='Thương hiệu', singular='thương hiệu',
        columns=[('Tên', 'name', 'name'), ('Số sản phẩm', 'product_total', 'product_total'), ('Trạng thái', _active, None)],
        search_fields=('name',), sort_fields={'name': 'name', 'product_total': 'product_total'}, default_sort='name',
        queryset=lambda: Brand.objects.annotate(product_total=Count('products')), filters=[ACTIVE_FILTER]),
    'iphone': CrudConfig(
        key='iphone', model=IPhoneModel, form_class=IPhoneModelForm, title='Dòng iPhone', singular='dòng iPhone',
        columns=[('Tên', 'name', 'name'), ('Thế hệ', 'series', 'series'), ('Năm ra mắt', 'release_year', 'release_year'),
                 ('Linh kiện tương thích', 'verified_total', 'verified_total'), ('Trạng thái', _active, None)],
        search_fields=('name', 'model_codes'), sort_fields={'name': 'name', 'series': 'series', 'release_year': 'release_year',
                                                           'verified_total': 'verified_total'},
        default_sort='series', queryset=lambda: IPhoneModel.objects.annotate(
            verified_total=Count('compatibilities', filter=Q(compatibilities__status='verified'))),
        filters=[ACTIVE_FILTER], delete_check=_iphone_delete_check),
    'banner': CrudConfig(
        key='banner', model=Banner, form_class=BannerForm, title='Banner trang chủ', singular='banner',
        columns=[('Tiêu đề', 'title', 'title'), ('Nút', 'button_text', None), ('Thứ tự', 'display_order', 'display_order'),
                 ('Hiển thị', _switch('banner-active'), None)],
        search_fields=('title',), sort_fields={'title': 'title', 'display_order': 'display_order'}, default_sort='display_order',
        sortable='banner', list_template='dashboard/banner_list.html'),
    'page': CrudConfig(
        key='page', model=Page, form_class=PageForm, title='Trang nội dung', singular='trang',
        columns=[('Tiêu đề', 'title', 'title'), ('Slug', 'slug', 'slug'),
                 ('Hiển thị', lambda p: format_html('<span class="badge-{}">{}</span>', 'success' if p.is_published else 'muted',
                                                     'Có' if p.is_published else 'Ẩn'), None),
                 ('Cập nhật', lambda p: d(p.updated_at), 'updated_at')],
        search_fields=('title', 'slug'), sort_fields={'title': 'title', 'slug': 'slug', 'updated_at': 'updated_at'},
        default_sort='title', detail_url=lambda p: p.get_absolute_url()),
    'faq': CrudConfig(
        key='faq', model=FAQ, form_class=FAQForm, title='Câu hỏi thường gặp', singular='câu hỏi',
        columns=[('Câu hỏi', 'question', 'question'), ('Thứ tự', 'display_order', 'display_order'), ('Hiển thị', _switch('faq-active'), None)],
        search_fields=('question', 'answer'), sort_fields={'question': 'question', 'display_order': 'display_order'},
        default_sort='display_order', filters=[ACTIVE_FILTER], sortable='faq'),
    'coupon': CrudConfig(
        key='coupon', model=Coupon, form_class=CouponForm, title='Mã giảm giá', singular='mã giảm giá',
        columns=[('Mã', lambda c: format_html('<strong>{}</strong>', c.code), 'code'), ('Ưu đãi', 'value_label', None),
                 ('Đơn tối thiểu', lambda c: vnd(c.min_order_value), 'min_order_value'),
                 ('Đã dùng', _coupon_usage, 'used_count'),
                 ('Thời gian', lambda c: f'{d(c.start_at)} – {d(c.end_at)}', 'start_at'),
                 ('Tình trạng', _coupon_state, None), ('Bật', _switch('coupon-active'), None)],
        filters=[COUPON_STATE_FILTER],
        search_fields=('code', 'description'), sort_fields={'code': 'code', 'min_order_value': 'min_order_value',
                                                           'used_count': 'used_count', 'start_at': 'start_at'},
        default_sort='-start_at', menu='coupon', detail_url=lambda c: f'/quan-tri/ma-giam-gia/{c.pk}/'),
}


def make_views(key):
    cfg = CONFIGS[key]

    @staff_required
    def list_view(request):
        return crud_list(request, cfg)

    @staff_required
    def form_view(request, pk=None):
        return crud_form(request, cfg, pk)

    @staff_required
    def delete_view(request, pk):
        return crud_delete(request, cfg, pk)

    return list_view, form_view, delete_view
