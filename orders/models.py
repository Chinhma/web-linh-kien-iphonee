import secrets
import string

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


def generate_order_code() -> str:
    """Mã đơn: IPS + YYMMDD + 5 ký tự ngẫu nhiên in hoa, ví dụ IPS261119A7K3Q."""
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = 'IPS' + timezone.localtime().strftime('%y%m%d') + ''.join(secrets.choice(alphabet) for _ in range(5))
        if not Order.objects.filter(code=code).exists():
            return code


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Chờ xác nhận'
        CONFIRMED = 'confirmed', 'Đã xác nhận'
        PREPARING = 'preparing', 'Đang chuẩn bị hàng'
        SHIPPING = 'shipping', 'Đang giao hàng'
        DELIVERED = 'delivered', 'Giao thành công'
        CANCELLED = 'cancelled', 'Đã hủy'

    class PaymentMethod(models.TextChoices):
        COD = 'cod', 'Thanh toán khi nhận hàng (COD)'
        VNPAY = 'vnpay', 'VNPay'
        MOMO = 'momo', 'Ví MoMo'

    class PaymentStatus(models.TextChoices):
        UNPAID = 'unpaid', 'Chưa thanh toán'
        PENDING = 'pending', 'Đang chờ thanh toán'
        PAID = 'paid', 'Đã thanh toán'
        FAILED = 'failed', 'Thanh toán thất bại'
        REFUND_PENDING = 'refund_pending', 'Chờ hoàn tiền'
        REFUNDED = 'refunded', 'Đã hoàn tiền'

    class ShippingMethod(models.TextChoices):
        STANDARD = 'standard', 'Giao tiêu chuẩn (3–5 ngày)'
        EXPRESS = 'express', 'Giao nhanh (1–2 ngày)'

    class CancelledBy(models.TextChoices):
        CUSTOMER = 'customer', 'Khách hàng'
        ADMIN = 'admin', 'Quản trị viên'
        SYSTEM = 'system', 'Hệ thống'

    code = models.CharField('Mã đơn', max_length=20, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='Khách hàng', on_delete=models.PROTECT, related_name='orders')
    status = models.CharField('Trạng thái', max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    payment_method = models.CharField('Thanh toán', max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.COD)
    payment_status = models.CharField('Trạng thái thanh toán', max_length=20, choices=PaymentStatus.choices,
                                      default=PaymentStatus.UNPAID, db_index=True)
    shipping_method = models.CharField('Vận chuyển', max_length=10, choices=ShippingMethod.choices, default=ShippingMethod.STANDARD)
    recipient_name = models.CharField('Người nhận', max_length=100)
    recipient_phone = models.CharField('SĐT người nhận', max_length=15)
    recipient_email = models.EmailField('Email người nhận')
    # Snapshot địa chỉ 2 cấp (sau 01/07/2025)
    province_code = models.CharField('Mã tỉnh/thành', max_length=5, blank=True)
    province_name = models.CharField('Tỉnh/Thành phố', max_length=100)
    ward_code = models.CharField('Mã phường/xã', max_length=10, blank=True)
    ward_name = models.CharField('Phường/Xã', max_length=100)
    street_address = models.CharField('Địa chỉ', max_length=255)
    note = models.CharField('Ghi chú', max_length=500, blank=True)
    subtotal = models.PositiveIntegerField('Tạm tính')
    discount_amount = models.PositiveIntegerField('Giảm giá', default=0)
    shipping_fee = models.PositiveIntegerField('Phí vận chuyển', default=0)
    total = models.PositiveIntegerField('Tổng thanh toán')
    coupon = models.ForeignKey('promotions.Coupon', null=True, blank=True, on_delete=models.SET_NULL, related_name='orders')
    coupon_code = models.CharField('Mã giảm giá', max_length=20, blank=True)
    cancel_reason = models.TextField('Lý do hủy', blank=True)
    admin_notes = models.JSONField('Ghi chú nội bộ (Admin)', default=list, blank=True)
    cancelled_by = models.CharField('Hủy bởi', max_length=10, choices=CancelledBy.choices, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True, db_index=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_expires_at = models.DateTimeField('Hạn thanh toán', null=True, blank=True)
    idempotency_key = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)
    created_at = models.DateTimeField('Ngày đặt', default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Đơn hàng'
        verbose_name_plural = 'Đơn hàng'
        ordering = ['-created_at']
        constraints = [models.CheckConstraint(condition=models.Q(total__gte=0), name='order_total_non_negative')]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_order_code()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('orders:detail', args=[self.code])

    @property
    def full_address(self) -> str:
        from core.address import format_address

        return format_address(self.street_address, self.ward_name, self.province_name)

    @property
    def is_online_payment(self) -> bool:
        return self.payment_method != self.PaymentMethod.COD

    @property
    def can_retry_payment(self) -> bool:
        return (
            self.is_online_payment
            and self.status == self.Status.PENDING
            and self.payment_status in (self.PaymentStatus.PENDING, self.PaymentStatus.FAILED)
            and self.payment_expires_at is not None
            and timezone.now() < self.payment_expires_at
        )

    @property
    def item_count(self) -> int:
        return sum(item.quantity for item in self.items.all())


class OrderItem(models.Model):
    """Snapshot sản phẩm tại thời điểm đặt hàng."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', null=True, on_delete=models.PROTECT, related_name='order_items')
    product_name = models.CharField('Tên sản phẩm', max_length=200)
    product_sku = models.CharField('SKU', max_length=50)
    product_image = models.CharField('Ảnh', max_length=255, blank=True)
    unit_price = models.PositiveIntegerField('Đơn giá')
    quantity = models.PositiveIntegerField('Số lượng')
    line_total = models.PositiveIntegerField('Thành tiền')

    class Meta:
        verbose_name = 'Sản phẩm trong đơn'
        verbose_name_plural = 'Sản phẩm trong đơn'
        ordering = ['id']

    def __str__(self):
        return f'{self.product_name} × {self.quantity}'


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    from_status = models.CharField('Từ', max_length=20, blank=True)
    to_status = models.CharField('Sang', max_length=20)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    note = models.CharField('Ghi chú', max_length=500, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Lịch sử trạng thái'
        verbose_name_plural = 'Lịch sử trạng thái'
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'{self.order}: {self.from_status or "—"} → {self.to_status}'

    @property
    def to_status_label(self) -> str:
        return Order.Status(self.to_status).label if self.to_status in Order.Status.values else self.to_status
