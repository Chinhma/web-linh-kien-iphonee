from django import forms
from django.contrib.auth import get_user_model

from accounts.forms import style_fields
from chatbot.models import ChatbotSetting
from core.models import FAQ, Banner, Page, StoreSetting
from core.validators import validate_image_file
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
    category = CategoryLeafChoiceField(label='Danh mục')

    class Meta:
        model = Product
        fields = ['name', 'slug', 'sku', 'part_code', 'category', 'brand', 'quality_grade', 'status', 'is_featured',
                  'requires_technician', 'install_difficulty', 'cost_price', 'price', 'sale_price', 'sale_start',
                  'sale_end', 'low_stock_threshold', 'warranty_months', 'short_description', 'description',
                  'highlights', 'usage_guide', 'specifications']
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

    def clean_sku(self):
        return (self.cleaned_data.get('sku') or '').strip().upper()

    def clean_slug(self):
        return (self.cleaned_data.get('slug') or '').strip()

    def clean(self):
        data = super().clean()
        if not data.get('sku') and data.get('category'):
            model = IPhoneModel.objects.filter(pk__in=self.data.getlist('compat_models')).order_by('series', 'display_order').first()
            data['sku'] = generate_sku(data['category'], model.name if model else '')
            self.instance.sku = data['sku']
        return data


def generate_sku(category, model_name: str = '') -> str:
    """SKU dạng IP-{MÃ_DANH_MỤC}-{MÃ_MODEL}-{SỐ}, ví dụ IP-SCR-13PRO-001 (số tự tăng, không trùng)."""
    from core.utils import strip_accents

    code = (category.parent.code if category.parent_id and not category.code else category.code) or 'GEN'
    model = strip_accents(model_name).upper().replace('IPHONE', '').replace(' ', '')[:10] or 'GEN'
    prefix = f'IP-{code}-{model}-'
    n = 1
    while Product.objects.filter(sku=f'{prefix}{n:03d}').exists():
        n += 1
    return f'{prefix}{n:03d}'


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
