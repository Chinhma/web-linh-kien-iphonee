from django import forms

from accounts.forms import AdministrativeAreaMixin, style_fields
from accounts.validators import validate_vn_phone

from .models import Order


class CheckoutForm(AdministrativeAreaMixin, forms.Form):
    recipient_name = forms.CharField(label='Họ và tên', min_length=2, max_length=100)
    recipient_phone = forms.CharField(label='Số điện thoại', max_length=15, validators=[validate_vn_phone])
    recipient_email = forms.EmailField(label='Email')
    street_address = forms.CharField(label='Địa chỉ chi tiết', max_length=255,
                                     widget=forms.TextInput(attrs={'placeholder': 'Số nhà, tên đường, thôn/xóm...',
                                                                   'autocomplete': 'off'}))
    note = forms.CharField(label='Ghi chú', max_length=500, required=False,
                           widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Ví dụ: giao giờ hành chính'}))
    save_address = forms.BooleanField(label='Lưu địa chỉ này vào sổ địa chỉ', required=False)
    shipping_method = forms.ChoiceField(choices=Order.ShippingMethod.choices, initial='standard', widget=forms.RadioSelect)
    payment_method = forms.ChoiceField(choices=Order.PaymentMethod.choices, initial='cod', widget=forms.RadioSelect)
    agree = forms.BooleanField(label='Tôi đồng ý với điều khoản mua hàng',
                               error_messages={'required': 'Bạn cần đồng ý với điều khoản mua hàng.'})
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, enabled_methods=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.enabled_methods = enabled_methods or {'cod'}
        self.add_area_fields()
        style_fields(self)

    def clean_recipient_phone(self):
        return self.cleaned_data['recipient_phone'].replace(' ', '')

    def clean_payment_method(self):
        method = self.cleaned_data['payment_method']
        if method not in self.enabled_methods:
            raise forms.ValidationError('Phương thức thanh toán này đang bảo trì, vui lòng chọn phương thức khác.')
        return method

    def clean(self):
        return self.clean_area(super().clean())


CANCEL_REASONS = ['Đổi ý, không muốn mua nữa', 'Đặt nhầm sản phẩm', 'Muốn đổi địa chỉ nhận hàng', 'Lý do khác']
