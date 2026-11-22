from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm

from core.validators import validate_image_file

from .models import Address, CustomerProfile
from .validators import validate_vn_phone

User = get_user_model()
INPUT = 'form-input'


def style_fields(form):
    for name, field in form.fields.items():
        widget = field.widget
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault('class', 'form-check mt-0.5')
        elif isinstance(widget, (forms.RadioSelect, forms.CheckboxSelectMultiple)):
            continue
        else:
            widget.attrs.setdefault('class', INPUT)


class RegisterForm(forms.Form):
    full_name = forms.CharField(label='Họ và tên', min_length=2, max_length=100,
                                widget=forms.TextInput(attrs={'autocomplete': 'name', 'placeholder': 'Nguyễn Văn A'}))
    email = forms.EmailField(label='Email', widget=forms.EmailInput(attrs={'autocomplete': 'email', 'placeholder': 'ban@example.com'}))
    phone = forms.CharField(label='Số điện thoại', max_length=15, validators=[validate_vn_phone],
                            widget=forms.TextInput(attrs={'autocomplete': 'tel', 'inputmode': 'tel', 'placeholder': '0889400470'}))
    password1 = forms.CharField(label='Mật khẩu', strip=False,
                                widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'data-strength': '1'}),
                                help_text='Tối thiểu 8 ký tự, có cả chữ và số.')
    password2 = forms.CharField(label='Xác nhận mật khẩu', strip=False,
                                widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    terms = forms.BooleanField(label='Tôi đồng ý với', error_messages={'required': 'Bạn cần đồng ý với điều khoản sử dụng.'})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Email này đã được sử dụng.')
        return email

    def clean_phone(self):
        return self.cleaned_data['phone'].replace(' ', '')

    def clean(self):
        data = super().clean()
        p1, p2 = data.get('password1'), data.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'Mật khẩu xác nhận không khớp.')
        if p1:
            temp_user = User(email=data.get('email', ''), full_name=data.get('full_name', ''))
            try:
                password_validation.validate_password(p1, temp_user)
            except forms.ValidationError as exc:
                self.add_error('password1', exc)
        return data

    def save(self) -> User:
        from accounts.adapters import SocialAccountAdapter

        email = self.cleaned_data['email']
        user = User(
            username=SocialAccountAdapter._unique_username(email.split('@')[0]),
            email=email, full_name=self.cleaned_data['full_name'], phone=self.cleaned_data['phone'],
            auth_provider=User.AuthProvider.LOCAL, is_staff=False, is_superuser=False,
        )
        user.set_password(self.cleaned_data['password1'])
        user.save()
        CustomerProfile.objects.get_or_create(user=user)
        return user


class LoginForm(forms.Form):
    identifier = forms.CharField(label='Email hoặc tên đăng nhập', max_length=150,
                                 widget=forms.TextInput(attrs={'autocomplete': 'username', 'autofocus': True}))
    password = forms.CharField(label='Mật khẩu', strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))
    remember = forms.BooleanField(label='Ghi nhớ đăng nhập', required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)


class ProfileForm(forms.ModelForm):
    """Form hồ sơ Customer – liệt kê rõ fields, KHÔNG có is_staff/is_superuser/is_active/groups."""

    date_of_birth = forms.DateField(label='Ngày sinh', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    gender = forms.ChoiceField(label='Giới tính', required=False, choices=[('', '— Chọn —')] + CustomerProfile.Gender.choices)
    avatar = forms.ImageField(label='Ảnh đại diện', required=False, validators=[validate_image_file],
                              widget=forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}))

    class Meta:
        model = User
        fields = ['full_name', 'phone', 'avatar']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['full_name'].required = True
        self.fields['full_name'].min_length = 2
        self.fields['phone'].validators.append(validate_vn_phone)
        profile = getattr(self.instance, 'profile', None)
        if profile:
            self.fields['date_of_birth'].initial = profile.date_of_birth
            self.fields['gender'].initial = profile.gender
        style_fields(self)

    def save(self, commit=True):
        user = super().save(commit=commit)
        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        profile.date_of_birth = self.cleaned_data.get('date_of_birth')
        profile.gender = self.cleaned_data.get('gender') or ''
        profile.save()
        return user


class AdministrativeAreaMixin:
    """Trường Tỉnh/Thành + Phường/Xã (2 cấp, sau 01/07/2025).

    Trình duyệt chỉ gửi MÃ; backend kiểm tra mã có trong static/data/vn-address-2025.json,
    xã thuộc đúng tỉnh, rồi tự lấy TÊN từ dữ liệu (không tin tên gửi lên).
    """

    def add_area_fields(self):
        self.fields['province_code'] = forms.CharField(label='Tỉnh/Thành phố', max_length=5,
                                                       error_messages={'required': 'Vui lòng chọn Tỉnh/Thành phố.'})
        self.fields['ward_code'] = forms.CharField(label='Phường/Xã', max_length=10,
                                                   error_messages={'required': 'Vui lòng chọn Phường/Xã.'})
        for name in ('province_code', 'ward_code'):
            self.fields[name].widget = forms.HiddenInput()

    def clean_area(self, data):
        from core.address import province_name, ward_name

        pcode, wcode = data.get('province_code'), data.get('ward_code')
        if pcode and not province_name(pcode):
            self.add_error('province_code', 'Tỉnh/Thành phố không hợp lệ.')
        elif pcode and wcode and not ward_name(pcode, wcode):
            self.add_error('ward_code', 'Phường/Xã không thuộc Tỉnh/Thành phố đã chọn.')
        elif pcode and wcode:
            data['province_name'] = province_name(pcode)
            data['ward_name'] = ward_name(pcode, wcode)
        return data


class AddressForm(AdministrativeAreaMixin, forms.ModelForm):
    class Meta:
        model = Address
        fields = ['full_name', 'phone', 'street_address', 'is_default']
        widgets = {'street_address': forms.TextInput(attrs={'placeholder': 'Số nhà, tên đường, thôn/xóm...', 'autocomplete': 'off'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['phone'].validators.append(validate_vn_phone)
        self.add_area_fields()
        if self.instance.pk:
            self.initial.setdefault('province_code', self.instance.province_code)
            self.initial.setdefault('ward_code', self.instance.ward_code)
        style_fields(self)

    def clean(self):
        return self.clean_area(super().clean())

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.province_code = self.cleaned_data['province_code']
        obj.province_name = self.cleaned_data['province_name']
        obj.ward_code = self.cleaned_data['ward_code']
        obj.ward_name = self.cleaned_data['ward_name']
        if commit:
            obj.save()
        return obj


class IPartsPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)


class IPartsSetPasswordForm(SetPasswordForm):
    """Dùng cho tài khoản Google chưa có mật khẩu (không yêu cầu mật khẩu cũ)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)
