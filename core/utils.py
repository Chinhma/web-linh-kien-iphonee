"""Tiện ích dùng chung: slug tiếng Việt, đường dẫn upload, phản hồi JSON chuẩn, ép kiểu an toàn."""

import os
import unicodedata
import uuid

from django.http import JsonResponse
from django.utils import timezone
from django.utils.text import slugify


def strip_accents(text: str) -> str:
    """Bỏ dấu tiếng Việt: 'Màn hình Đẹp' -> 'Man hinh Dep'."""
    text = (text or '').replace('đ', 'd').replace('Đ', 'D')
    normalized = unicodedata.normalize('NFD', text)
    return ''.join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')


def vi_slugify(text: str) -> str:
    return slugify(strip_accents(text))


def unique_slug(instance, value: str, field: str = 'slug', max_length: int = 200) -> str:
    """Sinh slug duy nhất cho model từ chuỗi tiếng Việt."""
    base = vi_slugify(value)[:max_length - 6] or 'item'
    slug = base
    model = type(instance)
    index = 2
    while model.objects.filter(**{field: slug}).exclude(pk=instance.pk).exists():
        slug = f'{base}-{index}'
        index += 1
    return slug


def uuid_upload_to(prefix: str):
    """Trả về hàm upload_to đổi tên file thành UUID, lưu theo thư mục prefix/%Y/%m/."""

    def _upload_to(instance, filename):
        ext = os.path.splitext(filename)[1].lower() or '.jpg'
        now = timezone.now()
        return f'{prefix}/{now:%Y}/{now:%m}/{uuid.uuid4().hex}{ext}'

    _upload_to.__name__ = f'upload_to_{prefix.replace("/", "_")}'
    return _upload_to


# Django migrations cần tham chiếu hàm cấp module
def product_image_upload_to(instance, filename):
    return uuid_upload_to('products')(instance, filename)


def avatar_upload_to(instance, filename):
    return uuid_upload_to('avatars')(instance, filename)


def catalog_image_upload_to(instance, filename):
    return uuid_upload_to('catalog')(instance, filename)


def is_ajax(request) -> bool:
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )


def api_ok(data=None, message: str = '', status: int = 200) -> JsonResponse:
    return JsonResponse({'ok': True, 'data': data or {}, 'message': message}, status=status)


def api_error(code: str, message: str, status: int = 400, errors=None, **extra) -> JsonResponse:
    payload = {'ok': False, 'code': code, 'message': message, 'errors': errors or {}}
    payload.update(extra)
    return JsonResponse(payload, status=status)


def to_int(value, default=None, minimum=None, maximum=None):
    """Ép kiểu số nguyên an toàn cho tham số GET/POST; giá trị lỗi trả về default."""
    try:
        result = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    if minimum is not None and result < minimum:
        return default
    if maximum is not None and result > maximum:
        return maximum
    return result


def client_ip(request) -> str:
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def short_name(full_name: str) -> str:
    """'Nguyễn Văn An' -> 'Nguyễn V. A.' để bảo vệ thông tin cá nhân."""
    parts = (full_name or '').split()
    if not parts:
        return 'Khách hàng'
    if len(parts) == 1:
        return parts[0]
    return parts[0] + ' ' + ' '.join(p[0].upper() + '.' for p in parts[1:])
