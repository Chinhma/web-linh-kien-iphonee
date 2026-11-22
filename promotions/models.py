from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

coupon_code_validator = RegexValidator(r'^[A-Z0-9]{4,20}$', 'Mã chỉ gồm chữ in hoa và số, 4–20 ký tự.')


class Coupon(models.Model):
    class DiscountType(models.TextChoices):
        PERCENT = 'percent', 'Phần trăm'
        FIXED = 'fixed', 'Số tiền cố định'

    code = models.CharField('Mã', max_length=20, unique=True, validators=[coupon_code_validator])
    description = models.CharField('Mô tả', max_length=255, blank=True)
    discount_type = models.CharField('Loại giảm', max_length=10, choices=DiscountType.choices, default=DiscountType.PERCENT)
    value = models.PositiveIntegerField('Giá trị')
    max_discount = models.PositiveIntegerField('Giảm tối đa', null=True, blank=True)
    min_order_value = models.PositiveIntegerField('Đơn tối thiểu', default=0)
    usage_limit = models.PositiveIntegerField('Tổng lượt dùng', null=True, blank=True, help_text='Để trống = không giới hạn')
    usage_limit_per_user = models.PositiveIntegerField('Lượt mỗi khách', default=1)
    used_count = models.PositiveIntegerField('Đã dùng', default=0, editable=False)
    start_at = models.DateTimeField('Bắt đầu')
    end_at = models.DateTimeField('Kết thúc')
    is_public = models.BooleanField('Công khai (chatbot/trang KM được giới thiệu)', default=True)
    is_active = models.BooleanField('Kích hoạt', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Mã giảm giá'
        verbose_name_plural = 'Mã giảm giá'
        ordering = ['-created_at']

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = (self.code or '').strip().upper()
        super().save(*args, **kwargs)

    def clean(self):
        self.code = (self.code or '').strip().upper()
        if self.discount_type == self.DiscountType.PERCENT and not (1 <= (self.value or 0) <= 100):
            raise ValidationError({'value': 'Phần trăm giảm phải từ 1 đến 100.'})
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            raise ValidationError({'end_at': 'Ngày kết thúc phải sau ngày bắt đầu.'})

    @property
    def state(self) -> str:
        now = timezone.now()
        if not self.is_active:
            return 'disabled'
        if now < self.start_at:
            return 'upcoming'
        if now > self.end_at:
            return 'expired'
        return 'running'

    @property
    def state_label(self) -> str:
        return {'disabled': 'Tắt', 'upcoming': 'Sắp diễn ra', 'expired': 'Hết hạn', 'running': 'Đang chạy'}[self.state]

    @property
    def value_label(self) -> str:
        from core.templatetags.iparts import vnd

        if self.discount_type == self.DiscountType.PERCENT:
            text = f'Giảm {self.value}%'
            if self.max_discount:
                text += f' (tối đa {vnd(self.max_discount)})'
            return text
        return f'Giảm {vnd(self.value)}'


class CouponUsage(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usages')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='coupon_usages')
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='coupon_usages')
    discount_amount = models.PositiveIntegerField('Số tiền giảm')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Lượt dùng mã'
        verbose_name_plural = 'Lượt dùng mã'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.coupon} – {self.order}'
