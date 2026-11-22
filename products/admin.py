from django import forms
from django.contrib import admin, messages
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.html import format_html

from core.templatetags.iparts import vnd
from inventory.models import InventoryTransaction
from inventory.services import StockError, adjust_stock

from .models import Brand, Category, Compatibility, IPhoneModel, Product, ProductImage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'parent', 'product_count', 'display_order', 'is_active']
    list_editable = ['display_order', 'is_active']
    list_filter = ['is_active', 'parent']
    search_fields = ['name', 'code']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(n=Count('products'))

    @admin.display(description='Số sản phẩm', ordering='n')
    def product_count(self, obj):
        return obj.n

    def delete_model(self, request, obj):
        if obj.products.exists():
            messages.error(request, f'Không thể xóa: danh mục còn {obj.products.count()} sản phẩm.')
            return
        super().delete_model(request, obj)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']
    list_editable = ['is_active']
    search_fields = ['name']


@admin.register(IPhoneModel)
class IPhoneModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'series', 'release_year', 'verified_count', 'display_order', 'is_active']
    list_editable = ['display_order', 'is_active']
    list_filter = ['series', 'is_active']
    search_fields = ['name', 'model_codes']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(n=Count('compatibilities', filter=Q(compatibilities__status='verified')))

    @admin.display(description='Linh kiện tương thích', ordering='n')
    def verified_count(self, obj):
        return obj.n


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ['preview', 'image', 'alt_text', 'is_primary', 'display_order']
    readonly_fields = ['preview']

    @admin.display(description='Xem trước')
    def preview(self, obj):
        return format_html('<img src="{}" style="height:60px;border-radius:8px">', obj.image.url) if obj.pk and obj.image else ''


class CompatibilityInline(admin.TabularInline):
    model = Compatibility
    extra = 1
    fields = ['iphone_model', 'status', 'note', 'source', 'is_sample_data']
    autocomplete_fields = ['iphone_model']


class ProductAdminForm(forms.ModelForm):
    stock_change = forms.IntegerField(label='Điều chỉnh tồn kho (+ nhập / − xuất)', required=False,
                                      help_text='Tồn kho chỉ thay đổi qua ô này và được ghi vào lịch sử kho.')
    stock_note = forms.CharField(label='Ghi chú điều chỉnh kho', required=False, max_length=255)
    specifications = forms.CharField(
        label='Thông số kỹ thuật', required=False, widget=forms.Textarea(attrs={'rows': 6, 'cols': 60}),
        help_text='Mỗi dòng một thông số theo dạng "Tên: Giá trị". Ví dụ:<br>Dung lượng: 3110 mAh<br>Điện áp: 3.83V')

    class Meta:
        model = Product
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        specs = self.instance.specifications if self.instance.pk else []
        if isinstance(specs, list):
            self.initial['specifications'] = '\n'.join(
                f"{s.get('label', '')}: {s.get('value', '')}" for s in specs if isinstance(s, dict))

    def clean_specifications(self):
        """Chuyển các dòng "Tên: Giá trị" thành danh sách [{label, value}] lưu vào JSONField."""
        rows = []
        for line in (self.cleaned_data.get('specifications') or '').splitlines():
            line = line.strip()
            if not line:
                continue
            label, sep, value = line.partition(':')
            if not sep or not label.strip():
                raise forms.ValidationError(f'Dòng "{line}" chưa đúng dạng "Tên: Giá trị".')
            rows.append({'label': label.strip()[:100], 'value': value.strip()[:200]})
        return rows


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = ['thumb', 'name', 'sku', 'category', 'price_display', 'stock_display', 'sold_count', 'status', 'is_featured']
    list_display_links = ['thumb', 'name']
    list_editable = ['status', 'is_featured']
    list_filter = ['status', 'category', 'brand', 'quality_grade', 'is_featured']
    search_fields = ['name', 'sku']
    list_per_page = 20
    prepopulated_fields = {'slug': ['name']}
    readonly_fields = ['stock_quantity', 'sold_count', 'rating_avg', 'rating_count', 'view_count', 'created_at']
    inlines = [ProductImageInline, CompatibilityInline]
    actions = ['make_active', 'make_discontinued']
    fieldsets = [
        ('Thông tin cơ bản', {'fields': ['name', 'slug', 'sku', 'category', 'brand', 'quality_grade', 'status', 'is_featured']}),
        ('Giá', {'fields': ['cost_price', 'price', 'sale_price', 'sale_start', 'sale_end']}),
        ('Kho & bảo hành', {'fields': ['stock_quantity', 'stock_change', 'stock_note', 'low_stock_threshold', 'warranty_months']}),
        ('Nội dung', {'fields': ['short_description', 'description', 'usage_guide', 'specifications']}),
        ('Thống kê', {'fields': ['sold_count', 'rating_avg', 'rating_count', 'view_count', 'created_at'], 'classes': ['collapse']}),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category').prefetch_related('images')

    @admin.display(description='Ảnh')
    def thumb(self, obj):
        return format_html('<img src="{}" style="height:44px;width:44px;object-fit:cover;border-radius:6px">', obj.image_url)

    @admin.display(description='Giá', ordering='price')
    def price_display(self, obj):
        if obj.is_on_sale:
            return format_html('{} <s style="color:#94a3b8">{}</s>', vnd(obj.effective_price), vnd(obj.price))
        return vnd(obj.price)

    @admin.display(description='Tồn kho', ordering='stock_quantity')
    def stock_display(self, obj):
        color = {'in_stock': '#16A34A', 'low_stock': '#F59E0B', 'out_of_stock': '#DC2626'}[obj.stock_status]
        return format_html('<b style="color:{}">{}</b>', color, obj.stock_quantity)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        delta = form.cleaned_data.get('stock_change')
        if delta:
            kind = InventoryTransaction.Type.IMPORT if delta > 0 else InventoryTransaction.Type.ADJUSTMENT
            if not change:
                kind = InventoryTransaction.Type.INITIAL
            try:
                adjust_stock(obj, delta, kind, request.user, form.cleaned_data.get('stock_note') or 'Điều chỉnh từ Django admin',
                             unit_cost=obj.cost_price if delta > 0 else None)
            except StockError as exc:
                messages.error(request, str(exc))

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for inst in instances:
            if isinstance(inst, Compatibility) and inst.status == Compatibility.Status.VERIFIED and not inst.verified_at:
                inst.verified_by, inst.verified_at = request.user, timezone.now()
            inst.save()
        for obj in formset.deleted_objects:
            obj.delete()
        formset.save_m2m()

    def delete_model(self, request, obj):
        if obj.order_items.exists():
            Product.objects.filter(pk=obj.pk).update(status=Product.Status.DISCONTINUED)
            messages.warning(request, 'Sản phẩm đã có trong đơn hàng nên không xóa – đã chuyển "Ngừng kinh doanh".')
            return
        InventoryTransaction.objects.filter(product=obj).delete()
        super().delete_model(request, obj)

    @admin.action(description='Chuyển sang "Đang bán"')
    def make_active(self, request, queryset):
        queryset.update(status=Product.Status.ACTIVE)

    @admin.action(description='Chuyển sang "Ngừng kinh doanh"')
    def make_discontinued(self, request, queryset):
        queryset.update(status=Product.Status.DISCONTINUED)


@admin.register(Compatibility)
class CompatibilityAdmin(admin.ModelAdmin):
    list_display = ['product', 'iphone_model', 'status', 'note', 'is_sample_data', 'verified_by', 'verified_at']
    list_editable = ['status']
    list_filter = ['status', 'is_sample_data', 'iphone_model__series', 'product__category']
    search_fields = ['product__name', 'product__sku', 'iphone_model__name']
    autocomplete_fields = ['product', 'iphone_model']
    readonly_fields = ['verified_by', 'verified_at']
    actions = ['mark_verified', 'mark_unverified', 'mark_incompatible']

    def save_model(self, request, obj, form, change):
        if 'status' in form.changed_data or not change:
            obj.set_status(obj.status, request.user)
        super().save_model(request, obj, form, change)

    def _set(self, request, queryset, status):
        for comp in queryset:
            comp.set_status(status, request.user)
            comp.save()

    @admin.action(description='Xác nhận tương thích (verified)')
    def mark_verified(self, request, queryset):
        self._set(request, queryset, 'verified')

    @admin.action(description='Chuyển "Chưa xác nhận"')
    def mark_unverified(self, request, queryset):
        self._set(request, queryset, 'unverified')

    @admin.action(description='Đánh dấu "Không tương thích"')
    def mark_incompatible(self, request, queryset):
        self._set(request, queryset, 'incompatible')
