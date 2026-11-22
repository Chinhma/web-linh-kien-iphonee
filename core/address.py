"""Dữ liệu đơn vị hành chính Việt Nam sau sáp nhập (hiệu lực 01/07/2025): 34 tỉnh/thành, 3.321 phường/xã/đặc khu.

Chỉ 2 cấp: Tỉnh/Thành phố -> Phường/Xã (KHÔNG còn Quận/Huyện).
Đọc từ file tĩnh static/data/vn-address-2025.json – không gọi API bên ngoài khi chạy.
"""

import json
from functools import lru_cache

from django.conf import settings

DATA_FILE = settings.BASE_DIR / 'static' / 'data' / 'vn-address-2025.json'


@lru_cache(maxsize=1)
def _data() -> dict:
    with open(DATA_FILE, encoding='utf-8') as fh:
        raw = json.load(fh)
    provinces = {}
    for p in raw:
        provinces[p['code']] = {'name': p['name'], 'wards': {w['code']: w['name'] for w in p['wards']}}
    return provinces


def provinces() -> list[tuple[str, str]]:
    return [(code, p['name']) for code, p in _data().items()]


def province_name(code: str) -> str | None:
    p = _data().get(str(code or ''))
    return p['name'] if p else None


def ward_name(province_code: str, ward_code: str) -> str | None:
    """Tên phường/xã nếu mã xã thuộc đúng tỉnh, ngược lại None."""
    p = _data().get(str(province_code or ''))
    if not p:
        return None
    return p['wards'].get(str(ward_code or ''))


def validate(province_code: str, ward_code: str) -> tuple[str, str]:
    """Kiểm tra mã tỉnh, mã xã có trong dữ liệu và xã thuộc đúng tỉnh. Trả về (tên tỉnh, tên xã) hoặc ValueError."""
    pname = province_name(province_code)
    if not pname:
        raise ValueError('province')
    wname = ward_name(province_code, ward_code)
    if not wname:
        raise ValueError('ward')
    return pname, wname


def format_address(street: str, ward: str, province: str) -> str:
    """'Số nhà, Phường X, Thành phố Hà Nội'."""
    return ', '.join(part for part in [street, ward, province] if part)
