from django.conf import settings
from django.core.exceptions import ValidationError

ALLOWED_IMAGE_FORMATS = {'JPEG', 'PNG', 'WEBP'}


def validate_image_file(file) -> None:
    """Kiểm tra ảnh upload: tối đa 5 MB, định dạng JPG/PNG/WEBP (kiểm tra bằng Pillow, không dựa vào đuôi file)."""
    if not file:
        return
    if getattr(file, 'size', 0) > settings.MAX_UPLOAD_SIZE:
        raise ValidationError('Ảnh vượt quá 5 MB.')
    # Chỉ kiểm tra file mới upload (file đã lưu thì bỏ qua)
    if getattr(file, '_committed', True) and not hasattr(file, 'content_type'):
        return
    from PIL import Image, UnidentifiedImageError

    try:
        file.seek(0)
        with Image.open(file) as img:
            fmt = img.format
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise ValidationError('File không phải ảnh hợp lệ.')
    finally:
        try:
            file.seek(0)
        except Exception:  # pragma: no cover
            pass
    if fmt not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError('Chỉ chấp nhận ảnh JPG, PNG hoặc WEBP.')
