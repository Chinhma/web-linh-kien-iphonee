from django import forms
from django.contrib.auth import get_user_model

from accounts.forms import style_fields
from chatbot.models import ChatbotSetting
from core.models import FAQ, Banner, Page, StoreSetting
from core.validators import validate_image_file
from products.models import generate_sku  # noqa: F401  (dùng lại ở views)
from products.models import Brand, Category, Compatibility, IPhoneModel, Product
from promotions.models import Coupon

User = get_user_model()
DT = {'type': 'datetime-local'}


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)


class CategoryForm(StyledModelForm):
    class Meta:
        model = Category
        fields = ['name', 'code', 'parent', 'icon', 'description', 'image', 'display_order', 'is_active']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Category.objects.filter(parent__isnull=True)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        self.fields['parent'].queryset = qs
        self.fields['parent'].help_text = 'Để trống nếu là danh mục cấp 1 (nhóm linh kiện).'
        self.fields['code'].help_text = 'Mã dùng để sinh SKU, ví dụ SCR (màn hình), BAT (pin) – chữ in hoa.'
        self.fields['icon'].help_text = 'Tên icon Lucide (xem trước bên dưới), ví dụ: battery-full, camera, plug-zap'
        self.fields['display_order'].help_text = 'Số nhỏ hiển thị trước.'
        self.fields['is_active'].help_text = 'Tắt thì danh mục và sản phẩm bên trong bị ẩn khỏi website.'
        self.fields['image'].help_text = 'Ảnh đại diện danh mục (tùy chọn).'


class BrandForm(StyledModelForm):
    class Meta:
        model = Brand
        fields = ['name', 'logo', 'is_active']


class IPhoneModelForm(StyledModelForm):
    class Meta:
        model = IPhoneModel
        fields = ['name', 'series', 'model_codes', 'release_year', 'image', 'description', 'display_order', 'is_active']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}


class BannerForm(StyledModelForm):
    class Meta:
        model = Banner
        fields = ['title', 'subtitle', 'image', 'button_text', 'button_url', 'display_order', 'is_active']
        help_texts = {'image': 'Khuyến nghị 1600×600 px (JPG/PNG/WebP, tối đa 5MB).', 'button_url': 'Ví dụ: /san-pham/ hoặc /danh-muc/pin/'}


class PageForm(StyledModelForm):
    class Meta:
        model = Page
        fields = ['title', 'slug', 'content', 'is_published']
        widgets = {'content': forms.Textarea(attrs={'rows': 16})}
        help_texts = {'content': 'Hỗ trợ Markdown đơn giản: ## tiêu đề, **in đậm**, - danh sách, [chữ](/link).'}


class FAQForm(StyledModelForm):
    class Meta:
        model = FAQ
        fields = ['question', 'answer', 'display_order', 'is_active']
        widgets = {'answer': forms.Textarea(attrs={'rows': 4})}


class CouponForm(StyledModelForm):
    class Meta:
        model = Coupon
        fields = ['code', 'description', 'discount_type', 'value', 'max_discount', 'min_order_value', 'usage_limit',
                  'usage_limit_per_user', 'start_at', 'end_at', 'is_public', 'is_active']
        widgets = {'start_at': forms.DateTimeInput(attrs=DT, format='%Y-%m-%dT%H:%M'),
                   'end_at': forms.DateTimeInput(attrs=DT, format='%Y-%m-%dT%H:%M')}

    def clean_code(self):
        return self.cleaned_data['code'].strip().upper()


class CategoryLeafChoiceField(forms.ModelChoiceField):
    """Danh mục sản phẩm: nhóm theo cấp 1, chỉ chọn được danh mục lá (cấp 2, hoặc cấp 1 không có con)."""

    def __init__(self, *args, **kwargs):
        super().__init__(Category.objects.all(), *args, **kwargs)

    def _get_choices(self):
        groups = [('', '— Chọn danh mục —')]
        for parent in Category.objects.filter(parent__isnull=True).prefetch_related('children').order_by('display_order'):
            children = list(parent.children.order_by('display_order', 'name'))
            if children:
                groups.append((parent.name, [(c.pk, c.name) for c in children]))
            else:
                groups.append((parent.pk, parent.name))
        return groups

    choices = property(_get_choices, forms.ChoiceField.choices.fset)

    def validate(self, value):
        super().validate(value)
        if value is not None and value.children.exists():
            raise forms.ValidationError('Hãy chọn danh mục con cụ thể (ví dụ Camera trước / Camera sau).')


class ProductForm(StyledModelForm):
    initial_stock = forms.IntegerField(label='Tồn kho đầu kỳ', min_value=0, initial=0, required=False)
    specifications = forms.JSONField(required=False, widget=forms.HiddenInput)
    highlights = forms.JSONField(required=False, widget=forms.HiddenInput)
    options_data = forms.JSONField(label='Loại màn', required=False, widget=forms.HiddenInput)
    colors_data = forms.JSONField(label='Màu sắc', required=False, widget=forms.HiddenInput)
    variants_data = forms.JSONField(label='Biến thể', required=False, widget=forms.HiddenInput)
    category = CategoryLeafChoiceField(label='Danh mục')

    class Meta:
        model = Product
        fields = ['name', 'slug', 'sku', 'part_code', 'category', 'quality_grade', 'status', 'is_featured',
                  'requires_technician', 'install_difficulty', 'cost_price', 'price', 'sale_price', 'sale_start',
                  'sale_end', 'low_stock_threshold', 'short_description', 'description',
                  'highlights', 'usage_guide', 'specifications', 'option_label']
        widgets = {
            'sale_start': forms.DateTimeInput(attrs=DT, format='%Y-%m-%dT%H:%M'),
            'sale_end': forms.DateTimeInput(attrs=DT, format='%Y-%m-%dT%H:%M'),
            'description': forms.Textarea(attrs={'rows': 6}),
            'usage_guide': forms.Textarea(attrs={'rows': 4}),
            'short_description': forms.Textarea(attrs={'rows': 2}),
        }
        help_texts = {
            'slug': 'Để trống sẽ tự sinh từ tên (không dấu).',
            'cost_price': 'Chỉ Admin thấy.',
            'low_stock_threshold': 'Tồn ≤ ngưỡng này sẽ báo "Sắp hết hàng".',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields.pop('initial_stock')
        self.fields['option_label'].widget.attrs['placeholder'] = 'Loại màn hình'
        self.fields['slug'].required = False
        self.fields['sku'].required = False
        self.fields['sku'].help_text = 'Để trống sẽ tự sinh theo dạng IP-{MÃ_DANH_MỤC}-{MÃ_MODEL}-{SỐ}.'
        self.fields['category'].widget.attrs['class'] = 'form-input'

    @staticmethod
    def _clean_rows(data, keys):
        if not isinstance(data, list):
            return []
        rows = []
        for row in data:
            if isinstance(row, dict) and str(row.get(keys[0], '')).strip():
                rows.append({k: str(row.get(k, '')).strip()[:200] for k in keys})
            elif isinstance(row, str) and row.strip():
                rows.append(row.strip()[:200])
        return rows

    def clean_specifications(self):
        return self._clean_rows(self.cleaned_data.get('specifications') or [], ['label', 'value'])

    def clean_highlights(self):
        data = self.cleaned_data.get('highlights') or []
        return [str(x).strip()[:200] for x in data if str(x).strip()][:10] if isinstance(data, list) else []

    # ------------------------------------------------------------ Biến thể: LOẠI MÀN × MÀU
    @staticmethod
    def _int(v):
        try:
            n = int(str(v).replace('.', '').replace(',', '').strip())
            return n if n >= 0 else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _rows(data, limit):
        return [r for r in (data if isinstance(data, list) else [])[:limit] if isinstance(r, dict)]

    def _clean_group(self, field, label, extra=()):
        """Loại màn / màu: [{id, key, name, ..., is_default, is_active}] – tên không trùng, tối đa 1 mặc định."""
        rows, names = [], set()
        for i, row in enumerate(self._rows(self.cleaned_data.get(field), 30)):
            name = str(row.get('name', '')).strip()[:100]
            if not name:
                continue
            if name.lower() in names:
                raise forms.ValidationError(f'{label} "{name}" bị trùng tên.')
            names.add(name.lower())
            item = {'id': self._int(row.get('id')), 'key': str(row.get('key') or f'new{i}')[:20], 'name': name,
                    'is_default': bool(row.get('is_default')), 'is_active': bool(row.get('is_active', True)),
                    'display_order': i}
            for key, fn in extra:
                item[key] = fn(row.get(key))
            rows.append(item)
        if sum(r['is_default'] for r in rows) > 1:
            raise forms.ValidationError(f'Chỉ được chọn 1 {label.lower()} mặc định.')
        if rows and not any(r['is_default'] and r['is_active'] for r in rows):
            first = next((r for r in rows if r['is_active']), rows[0])
            for r in rows:
                r['is_default'] = r is first
        return rows

    def clean_options_data(self):
        return self._clean_group('options_data', 'Loại màn',
                                 extra=[('description', lambda v: str(v or '').strip()[:300])])

    def clean_colors_data(self):
        import re

        return self._clean_group('colors_data', 'Màu', extra=[
            ('hex_code', lambda v: v if re.fullmatch(r'#[0-9a-fA-F]{6}', str(v or '')) else '#E2E8F0'),
            ('remove_image', bool)])

    def clean_variants_data(self):
        """Bảng biến thể: [{id, key, option_key, color_key, price, compare_price, stock, sku, is_active, remove_image}].
        Dòng để trống giá = không bán tổ hợp đó (không tạo / xóa)."""
        rows = []
        for i, row in enumerate(self._rows(self.cleaned_data.get('variants_data'), 400)):
            price = self._int(row.get('price'))
            if not price:
                continue
            compare = self._int(row.get('compare_price')) or None
            name = ' – '.join(x for x in (row.get('option_name'), row.get('color_name')) if x) or 'Biến thể'
            if compare is not None and compare <= price:
                raise forms.ValidationError(f'"{name}": giá gốc phải lớn hơn giá bán (hoặc để trống).')
            rows.append({'id': self._int(row.get('id')), 'key': str(row.get('key') or f'v{i}')[:40],
                         'option_key': str(row.get('option_key') or ''), 'color_key': str(row.get('color_key') or ''),
                         'price': price, 'compare_price': compare, 'stock': self._int(row.get('stock')) or 0,
                         'sku': str(row.get('sku', '')).strip()[:50], 'is_active': bool(row.get('is_active', True)),
                         'remove_image': bool(row.get('remove_image'))})
        return rows

    def save_variants(self, product, files=None, user=None) -> None:
        """Lưu loại màn, màu, biến thể (kèm ảnh); xóa dòng bị bỏ; đồng bộ giá hiển thị + tồn kho sản phẩm."""
        from core.validators import validate_image_file
        from products.models import ProductColor, ProductOption, ProductVariant

        files = files or {}

        def take_image(obj, prefix, key, remove):
            if remove and obj.image:
                obj.image = ''
            upload = files.get(f'{prefix}_{key}')
            if upload:
                try:
                    validate_image_file(upload)
                    obj.image = upload
                except forms.ValidationError:
                    pass  # Ảnh sai định dạng/dung lượng: bỏ qua, giữ ảnh cũ

        def save_group(model, rows, fields, image_prefix=None):
            existing = {o.pk: o for o in model.objects.filter(product=product)}
            by_key, keep = {}, set()
            for row in rows:
                obj = existing.get(row['id']) or model(product=product)
                for f in fields:
                    setattr(obj, f, row[f])
                if image_prefix:
                    take_image(obj, image_prefix, row['key'], row.get('remove_image'))
                obj.save()
                keep.add(obj.pk)
                by_key[row['key']] = obj
                if row['id']:
                    by_key[str(row['id'])] = obj
            model.objects.filter(product=product).exclude(pk__in=keep).delete()
            return by_key

        common = ('name', 'is_default', 'is_active', 'display_order')
        options = save_group(ProductOption, self.cleaned_data.get('options_data') or [], common + ('description',))
        colors = save_group(ProductColor, self.cleaned_data.get('colors_data') or [], common + ('hex_code',), 'color_image')

        existing = {v.pk: v for v in ProductVariant.objects.filter(product=product)}
        by_pair = {(v.option_id, v.color_id): v for v in existing.values()}
        keep = set()
        for row in self.cleaned_data.get('variants_data') or []:
            option = options.get(row['option_key']) if row['option_key'] else None
            color = colors.get(row['color_key']) if row['color_key'] else None
            if (row['option_key'] and option is None) or (row['color_key'] and color is None):
                continue  # Tổ hợp của loại/màu vừa bị xóa
            pair = (option.pk if option else None, color.pk if color else None)
            variant = existing.get(row['id']) or by_pair.get(pair) or ProductVariant(product=product)
            if variant.pk in keep:
                continue
            variant.option, variant.color = option, color
            for f in ('price', 'compare_price', 'stock', 'sku', 'is_active'):
                setattr(variant, f, row[f])
            take_image(variant, 'variant_image', row['key'], row['remove_image'])
            variant.save()
            keep.add(variant.pk)
        ProductVariant.objects.filter(product=product).exclude(pk__in=keep).delete()
        product.sync_from_variants(user)

    def clean_sku(self):
        return (self.cleaned_data.get('sku') or '').strip().upper()

    def clean_slug(self):
        return (self.cleaned_data.get('slug') or '').strip()

    def clean(self):
        data = super().clean()
        if (data.get('options_data') or data.get('colors_data')) and not data.get('variants_data')                 and 'variants_data' in self.cleaned_data:
            self.add_error('variants_data', 'Đã có loại màn / màu – vui lòng nhập giá cho ít nhất 1 tổ hợp ở bảng biến thể.')
        if not data.get('sku') and data.get('category'):
            model = IPhoneModel.objects.filter(pk__in=self.data.getlist('compat_models')).order_by('series', 'display_order').first()
            data['sku'] = generate_sku(data['category'], model.name if model else '')
            self.instance.sku = data['sku']
        return data


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.FileField):
    """Nhận NHIỀU ảnh cùng lúc: kiểm tra từng tệp trong danh sách (FileField gốc chỉ nhận 1 tệp)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleImageInput(attrs={'accept': 'image/jpeg,image/png,image/webp', 'multiple': True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else ([data] if data else [])
        cleaned = [super(MultipleImageField, self).clean(f, initial) for f in files if f]
        for f in cleaned:
            validate_image_file(f)
        return cleaned


class ProductImagesForm(forms.Form):
    images = MultipleImageField(required=False)


class CompatibilityAddForm(forms.Form):
    product = forms.ModelChoiceField(label='Sản phẩm', queryset=Product.objects.all())
    iphone_models = forms.ModelMultipleChoiceField(label='Dòng iPhone', queryset=IPhoneModel.objects.all())
    status = forms.ChoiceField(label='Trạng thái', choices=Compatibility.Status.choices)
    note = forms.CharField(label='Ghi chú', max_length=300, required=False)
    source = forms.CharField(label='Nguồn thông tin', max_length=200, required=False)


class CompatibilityEditForm(StyledModelForm):
    class Meta:
        model = Compatibility
        fields = ['status', 'note', 'source', 'is_sample_data']


class StockImportForm(forms.Form):
    product = forms.ModelChoiceField(label='Sản phẩm', queryset=Product.objects.all())
    quantity = forms.IntegerField(label='Số lượng nhập', min_value=1, max_value=10000)
    unit_cost = forms.IntegerField(label='Giá nhập (₫)', min_value=0, required=False)
    note = forms.CharField(label='Ghi chú / Nhà cung cấp', max_length=255, required=False)
    update_cost_price = forms.BooleanField(label='Cập nhật giá nhập của sản phẩm', required=False, initial=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)


class StocktakeForm(forms.Form):
    product = forms.ModelChoiceField(label='Sản phẩm', queryset=Product.objects.all())
    actual_quantity = forms.IntegerField(label='Số tồn thực tế', min_value=0)
    reason = forms.CharField(label='Lý do điều chỉnh', max_length=255)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)


class StoreSettingForm(StyledModelForm):
    class Meta:
        model = StoreSetting
        exclude = ['updated_at']
        widgets = {'about_short': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from payments.gateways import GATEWAYS

        # Phương thức chưa cấu hình .env: khóa công tắc (không bật được)
        for code, gw in GATEWAYS.items():
            name = f'enable_{code}'
            if name in self.fields and not gw.is_configured():
                self.fields[name].disabled = True
                self.fields[name].help_text = 'Chưa cấu hình trong .env – không thể bật.'

    def clean(self):
        cleaned = super().clean()
        from payments.gateways import GATEWAYS

        usable = [c for c, gw in GATEWAYS.items() if gw.is_configured() and cleaned.get(f'enable_{c}')]
        if not usable:
            raise forms.ValidationError('Phải bật ít nhất một phương thức thanh toán đang hoạt động.')
        return cleaned


class ChatbotSettingForm(StyledModelForm):
    suggested_questions_text = forms.CharField(label='Câu hỏi gợi ý (mỗi dòng một câu)', required=False,
                                               widget=forms.Textarea(attrs={'rows': 6}))

    class Meta:
        model = ChatbotSetting
        fields = ['is_enabled', 'greeting_message', 'extra_store_info', 'max_messages_per_hour_guest',
                  'max_messages_per_hour_customer']
        widgets = {'greeting_message': forms.Textarea(attrs={'rows': 3}), 'extra_store_info': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['suggested_questions_text'].initial = '\n'.join(self.instance.suggested_questions or [])

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.suggested_questions = [q.strip()[:120] for q in self.cleaned_data['suggested_questions_text'].splitlines() if q.strip()][:10]
        if commit:
            obj.save()
        return obj


class AdminAccountForm(forms.Form):
    full_name = forms.CharField(label='Họ tên', max_length=100)
    email = forms.EmailField(label='Email')
    password = forms.CharField(label='Mật khẩu tạm', min_length=8, required=False, widget=forms.PasswordInput,
                               help_text='Để trống để hệ thống tạo mật khẩu ngẫu nhiên (chỉ hiển thị 1 lần).')
    is_superuser = forms.BooleanField(label='Cấp quyền Superuser', required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Email đã được sử dụng.')
        return email

    def clean_password(self):
        from django.contrib.auth import password_validation

        password = self.cleaned_data['password']
        if password:  # để trống → hệ thống tạo mật khẩu ngẫu nhiên
            password_validation.validate_password(password)
        return password


class CustomerNoteForm(forms.Form):
    note_by_admin = forms.CharField(label='Ghi chú nội bộ', required=False, widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-input'}))
