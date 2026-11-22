import re

from django.core.exceptions import ValidationError

PHONE_REGEX = re.compile(r'^(0|\+84)(3|5|7|8|9)\d{8}$')


def validate_vn_phone(value: str) -> None:
    if not PHONE_REGEX.match((value or '').replace(' ', '')):
        raise ValidationError('Số điện thoại Việt Nam không hợp lệ (ví dụ 0889400470).')


class LetterAndDigitValidator:
    """Mật khẩu phải có cả chữ và số."""

    def validate(self, password, user=None):
        if not (re.search(r'[A-Za-z]', password) and re.search(r'\d', password)):
            raise ValidationError('Mật khẩu phải có cả chữ và số.', code='password_no_letter_digit')

    def get_help_text(self):
        return 'Mật khẩu phải có cả chữ và số.'
