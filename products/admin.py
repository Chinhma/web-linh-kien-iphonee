from django import forms
from django.contrib import admin, messages
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.html import format_html

from core.templatetags.iparts import vnd
from inventory.models import InventoryTransaction
from inventory.services import StockError, adjust_stock

from .models import (Category, Compatibility, IPhoneModel, Product, ProductColor, ProductImage, ProductOption,
                     ProductVariant)


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


class SingleDefaultFormSet(forms.BaseInlineFormSet):
    """Chỉ cho đánh dấu 1 dòng "Mặc định"."""

    def clean(self):
        super().clean()
        rows = [f.cleaned_data for f in self.forms
                if getattr(f, 'cleaned_data', None) and not f.cleaned_data.get('DELETE') and f.cleaned_data.get('name')]
        if sum(1 for r in rows if r.get('is_default')) > 1:
            raise forms.ValidationError('Chỉ được chọn 1 dòng mặc định.')


class ProductOptionForm(forms.ModelForm):
    class Meta:
        model = ProductOption
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['price'].required = True  # Mỗi loại màn bắt buộc có giá bán
        for name in ('cost_price', 'price', 'sale_price'):
            self.fields[name].widget.attrs.update({'style': 'width:130px', 'placeholder': 'VD 1200000'})
        self.fields['description'].widget.attrs.update({'style': 'width:520px'})


class ProductOptionInline(admin.StackedInline):
    """Loại màn – mỗi loại có bộ giá riêng (giá nhập, giá bán, khuyến mãi theo khung giờ), áp cho mọi màu."""

    model = ProductOption
    form = ProductOptionForm
    formset = SingleDefaultFormSet
    extra = 0
    fieldsets = [
        (None, {'fields': [('name', 'is_default', 'is_active', 'display_order')]}),
        ('Giá của loại này', {'fields': [('cost_price', 'price', 'sale_price', 'discount'), ('sale_start', 'sale_end')]}),
        (None, {'fields': ['description']}),
    ]
    readonly_fields = ['discount']

    @admin.display(description='% giảm')
    def discount(self, obj):
        if obj.pk and obj.price and obj.sale_price is not None:
            if obj.sale_price >= obj.price:
                return '0% (không khuyến mãi)'
            note = '' if obj.is_on_sale else ' (ngoài thời gian KM)'
            return f'-{round((obj.price - obj.sale_price) * 100 / obj.price)}%{note}'
        return '—'


class ProductColorInline(admin.TabularInline):
    model = ProductColor
    formset = SingleDefaultFormSet
    extra = 0
    fields = ['name', 'hex_code', 'image', 'is_default', 'is_active', 'display_order']


class ProductVariantInline(admin.TabularInline):
    """Biến thể = loại màn × màu. Lưu loại màn/màu trước, sau đó chọn ở đây. (Bảng tự sinh có ở /quan-tri/.)"""

    model = ProductVariant
    extra = 0
    fields = ['option', 'color', 'price', 'compare_price', 'discount', 'stock', 'sku', 'image', 'is_active']
    readonly_fields = ['discount']

    def get_readonly_fields(self, request, obj=None):
        # Sản phẩm có loại màn: giá nhập ở dòng Loại màn phía trên, ở đây chỉ xem
        if obj is not None and obj.options.exists():
            return ['price', 'compare_price', 'discount']
        return self.readonly_fields

    @admin.display(description='% giảm')
    def discount(self, obj):
        return f'-{obj.discount_percent}%' if obj.pk and obj.discount_percent else '—'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Chỉ cho chọn loại màn / màu của chính sản phẩm đang sửa
        product_id = request.resolver_match.kwargs.get('object_id') if request.resolver_match else None
        if db_field.name in ('option', 'color'):
            model = ProductOption if db_field.name == 'option' else ProductColor
            kwargs['queryset'] = model.objects.filter(product_id=product_id) if product_id else model.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


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

    def _option_prices_in_post(self) -> list:
        """Giá bán các dòng Loại màn đang gửi lên (bỏ dòng tick Xóa)."""
        prices, i = [], 0
        while f'options-{i}-name' in self.data:
            if not self.data.get(f'options-{i}-DELETE') and self.data.get(f'options-{i}-name', '').strip():
                try:
                    prices.append(int(str(self.data.get(f'options-{i}-price') or '0').replace('.', '')))
                except ValueError:
                    prices.append(0)
            i += 1
        return prices

    def clean(self):
        data = super().clean()
        if 'price' in self.fields and not data.get('price'):
            prices = [p for p in self._option_prices_in_post() if p > 0]
            if prices:
                data['price'] = prices[0]  # Tạm – khi lưu sẽ đồng bộ theo loại màn mặc định
                data['cost_price'] = data.get('cost_price') or 0
            else:
                self.add_error('price', 'Nhập giá bán, hoặc nhập giá cho từng dòng Loại màn bên dưới.')
        return data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'sku' in self.fields:
            self.fields['sku'].required = False
            self.fields['sku'].help_text = 'Để trống sẽ tự sinh, vd. IP-SCR-8PLUS-001 (mã danh mục – dòng máy đoán từ tên – số thứ tự).'
        if 'price' in self.fields:
            self.fields['price'].required = False
            self.fields['price'].help_text = 'Sản phẩm có Loại màn: để trống, nhập giá ở từng dòng Loại màn bên dưới.'
        if 'cost_price' in self.fields:
            self.fields['cost_price'].required = False
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

    class Media:
        js = ['js/admin/discount-preview.js']  # Tự tính % giảm khi gõ giá bán / giá khuyến mãi

    list_display = ['thumb', 'name', 'sku', 'category', 'price_display', 'stock_display', 'sold_count', 'status', 'is_featured']
    list_display_links = ['thumb', 'name']
    list_editable = ['status', 'is_featured']
    list_filter = ['status', 'category', 'quality_grade', 'is_featured']
    search_fields = ['name', 'sku']
    list_per_page = 20
    prepopulated_fields = {'slug': ['name']}
    readonly_fields = ['stock_quantity', 'sold_count', 'rating_avg', 'rating_count', 'view_count', 'created_at']
    inlines = [ProductOptionInline, ProductColorInline, ProductVariantInline, ProductImageInline, CompatibilityInline]
    actions = ['make_active', 'make_discontinued']
    fieldsets = [
        ('Thông tin cơ bản', {'fields': ['name', 'slug', 'sku', 'category', 'quality_grade', 'status', 'is_featured']}),
        ('Giá', {'fields': ['cost_price', 'price', 'sale_price', 'sale_start', 'sale_end']}),
        ('Kho', {'fields': ['stock_quantity', 'stock_change', 'stock_note', 'low_stock_threshold', 'option_label']}),
        ('Nội dung', {'fields': ['short_description', 'description', 'usage_guide', 'specifications']}),
        ('Thống kê', {'fields': ['sold_count', 'rating_avg', 'rating_count', 'view_count', 'created_at'], 'classes': ['collapse']}),
    ]

    def get_fieldsets(self, request, obj=None):
        """Sản phẩm có Loại màn: bỏ khung Giá chung (giá nhập ở từng loại màn).
        Sản phẩm mới / không có loại màn (pin, cáp…): khung Giá chung thu gọn, bấm để mở khi cần."""
        fieldsets = []
        for name, opts in super().get_fieldsets(request, obj):
            if name == 'Giá':
                if obj is not None and obj.options.exists():
                    continue
                opts = {**opts, 'classes': ['collapse'] if obj is None else [],
                        'description': 'Chỉ dùng cho sản phẩm KHÔNG có loại màn (pin, cáp…). Sản phẩm màn hình: nhập giá ở '
                                       'từng dòng "Loại màn" bên dưới. Bảo hành cố định 12 tháng miễn phí.'}
                name = 'Giá chung (sản phẩm không có loại màn)'
            fieldsets.append((name, opts))
        return fieldsets

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
        if delta and obj.variants.filter(is_active=True).exists():
            messages.warning(request, 'Sản phẩm có biến thể: tồn kho nhập ở từng biến thể, ô "Điều chỉnh tồn kho" được bỏ qua.')
            delta = 0
        if delta:
            kind = InventoryTransaction.Type.IMPORT if delta > 0 else InventoryTransaction.Type.ADJUSTMENT
            if not change:
                kind = InventoryTransaction.Type.INITIAL
            try:
                adjust_stock(obj, delta, kind, request.user, form.cleaned_data.get('stock_note') or 'Điều chỉnh từ Django admin',
                             unit_cost=obj.cost_price if delta > 0 else None)
            except StockError as exc:
                messages.error(request, str(exc))

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        product = form.instance
        product.apply_option_prices()  # Giá ở dòng Loại màn -> mọi màu của loại đó
        # Có loại màn / màu mà thiếu tổ hợp -> tự sinh để trang sản phẩm hiện ngay các lựa chọn
        created = product.ensure_variants()
        if created:
            messages.warning(request, f'Đã tự tạo {created} biến thể (loại màn × màu). Kéo xuống bảng "Biến thể" '
                                      'để nhập TỒN KHO cho từng dòng rồi Lưu.')
        missing = list(product.options.filter(price=None, is_active=True).values_list('name', flat=True))
        if missing:
            messages.warning(request, f'Chưa nhập giá bán cho: {", ".join(missing)} – đang dùng giá tạm.')
        # Có biến thể: giá hiển thị = tổ hợp mặc định, tồn kho = tổng tồn các biến thể
        form.instance.sync_from_variants(request.user)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for inst in instances:
            if isinstance(inst, Compatibility) and inst.status == Compatibility.Status.VERIFIED and not inst.verified_at:
                inst.verified_by, inst.verified_at = request.user, timezone.now()
            inst.save()
        for obj in formset.deleted_objects:
            obj.delete()
        formset.save_m2m()

    def get_deleted_objects(self, objs, request):
        """Cho phép xóa dù không có quyền xóa "Giao dịch kho": lịch sử kho của sản phẩm bị xóa được dọn ở
        delete_model/delete_queryset; sản phẩm đã có trong đơn hàng sẽ chuyển "Ngừng kinh doanh" thay vì xóa."""
        deleted, model_count, _perms_needed, _protected = super().get_deleted_objects(objs, request)
        return deleted, model_count, set(), []

    @staticmethod
    def _delete_or_discontinue(obj) -> bool:
        """True nếu đã xóa hẳn; False nếu SP đã có trong đơn hàng (giữ lại, chuyển Ngừng kinh doanh)."""
        from django.db import transaction

        if obj.order_items.exists():
            Product.objects.filter(pk=obj.pk).update(status=Product.Status.DISCONTINUED)
            return False
        with transaction.atomic():
            InventoryTransaction.objects.filter(product=obj).delete()
            obj.delete()
        return True

    def delete_model(self, request, obj):
        if not self._delete_or_discontinue(obj):
            messages.warning(request, f'"{obj.name}" đã có trong đơn hàng nên không xóa – đã chuyển "Ngừng kinh doanh".')

    def delete_queryset(self, request, queryset):
        kept = [obj.name for obj in queryset if not self._delete_or_discontinue(obj)]
        if kept:
            messages.warning(request, f'{len(kept)} sản phẩm đã có trong đơn hàng nên không xóa, đã chuyển '
                                      f'"Ngừng kinh doanh": {", ".join(kept)}.')

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
