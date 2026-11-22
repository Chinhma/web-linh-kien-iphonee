"""Nghiệp vụ mã giảm giá."""

from django.db.models import F
from django.utils import timezone

from core.templatetags.iparts import vnd

from .models import Coupon, CouponUsage


def calculate_discount(coupon: Coupon, subtotal: int) -> int:
    if coupon.discount_type == Coupon.DiscountType.PERCENT:
        discount = subtotal * coupon.value // 100
        if coupon.max_discount:
            discount = min(discount, coupon.max_discount)
    else:
        discount = coupon.value
    return max(0, min(discount, subtotal))  # Không bao giờ vượt tạm tính


def validate_coupon(code: str, user, subtotal: int) -> tuple[bool, int, str, Coupon | None]:
    """Kiểm tra mã giảm giá theo đúng thứ tự nghiệp vụ.

    Trả về (ok, số tiền giảm, thông báo, coupon).
    """
    code = (code or '').strip().upper()
    coupon = Coupon.objects.filter(code__iexact=code).first() if code else None
    if coupon is None:
        return False, 0, 'Mã giảm giá không tồn tại.', None
    if not coupon.is_active:
        return False, 0, 'Mã giảm giá đã ngừng áp dụng.', coupon
    now = timezone.now()
    if now < coupon.start_at:
        return False, 0, 'Mã giảm giá chưa bắt đầu.', coupon
    if now > coupon.end_at:
        return False, 0, 'Mã giảm giá đã hết hạn.', coupon
    if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
        return False, 0, 'Mã giảm giá đã hết lượt sử dụng.', coupon
    if user is not None and user.is_authenticated:
        used = CouponUsage.objects.filter(coupon=coupon, user=user).count()
        if used >= coupon.usage_limit_per_user:
            return False, 0, 'Bạn đã sử dụng mã này.', coupon
    if subtotal < coupon.min_order_value:
        return False, 0, f'Đơn hàng tối thiểu {vnd(coupon.min_order_value)} để dùng mã này.', coupon
    discount = calculate_discount(coupon, subtotal)
    return True, discount, f'Áp dụng mã {coupon.code} thành công, giảm {vnd(discount)}.', coupon


def record_usage(coupon: Coupon, user, order, discount: int) -> None:
    """Chỉ gọi khi đơn được tạo thành công (trong transaction tạo đơn)."""
    Coupon.objects.filter(pk=coupon.pk).update(used_count=F('used_count') + 1)
    CouponUsage.objects.create(coupon=coupon, user=user, order=order, discount_amount=discount)


def release_usage(order) -> None:
    """Hoàn lượt dùng mã khi đơn bị hủy."""
    usages = CouponUsage.objects.filter(order=order)
    for usage in usages:
        Coupon.objects.filter(pk=usage.coupon_id, used_count__gt=0).update(used_count=F('used_count') - 1)
    usages.delete()


def public_active_coupons():
    now = timezone.now()
    return Coupon.objects.filter(is_active=True, is_public=True, start_at__lte=now, end_at__gte=now)
