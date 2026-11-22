"""Test dữ liệu hành chính 2 cấp (sau 01/07/2025) và kiểm tra mã ở backend."""

from django.test import TestCase

from accounts.forms import AddressForm
from core import address


class AddressDataTests(TestCase):
    def test_counts(self):
        data = address._data()
        self.assertEqual(len(data), 34)
        self.assertEqual(sum(len(p['wards']) for p in data.values()), 3321)

    def test_validate(self):
        self.assertEqual(address.validate('01', '00166'), ('Thành phố Hà Nội', 'Phường Cầu Giấy'))
        with self.assertRaises(ValueError):
            address.validate('99', '00166')       # tỉnh không tồn tại
        with self.assertRaises(ValueError):
            address.validate('79', '00166')       # xã không thuộc tỉnh
        self.assertEqual(address.format_address('144 Xuân Thủy', 'Phường Cầu Giấy', 'Thành phố Hà Nội'),
                         '144 Xuân Thủy, Phường Cầu Giấy, Thành phố Hà Nội')

    def form(self, **kw):
        data = {'full_name': 'Nguyễn A', 'phone': '0889400470', 'street_address': '1 Xuân Thủy',
                'province_code': '01', 'ward_code': '00166'}
        data.update(kw)
        return AddressForm(data)

    def test_form_takes_names_from_data_not_browser(self):
        form = self.form(province_name='Tên giả', ward_name='Xã giả')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['province_name'], 'Thành phố Hà Nội')
        self.assertEqual(form.cleaned_data['ward_name'], 'Phường Cầu Giấy')

    def test_form_rejects_invalid_codes(self):
        self.assertIn('province_code', self.form(province_code='99').errors)
        self.assertIn('ward_code', self.form(province_code='79').errors)  # xã Hà Nội nhưng chọn TP.HCM
        self.assertIn('ward_code', self.form(ward_code='').errors)
