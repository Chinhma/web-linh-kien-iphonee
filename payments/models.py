from django.db import models


class Payment(models.Model):
    """Một lần thanh toán của đơn hàng. Một đơn có thể có nhiều Payment (thanh toán lại). Không lưu dữ liệu thẻ."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Đang chờ'
        SUCCESS = 'success', 'Thành công'
        FAILED = 'failed', 'Thất bại'
        CANCELLED = 'cancelled', 'Đã hủy'
        REFUNDED = 'refunded', 'Đã hoàn tiền'

    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='payments')
    method = models.CharField('Phương thức', max_length=10)
    amount = models.PositiveIntegerField('Số tiền')
    status = models.CharField('Trạng thái', max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    transaction_ref = models.CharField('Mã giao dịch nội bộ', max_length=64, unique=True)
    gateway_transaction_id = models.CharField('Mã giao dịch cổng', max_length=100, blank=True)
    gateway_response_code = models.CharField('Mã phản hồi', max_length=20, blank=True)
    raw_response = models.JSONField('Dữ liệu phản hồi', default=dict, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Giao dịch thanh toán'
        verbose_name_plural = 'Giao dịch thanh toán'
        ordering = ['-created_at']

    def __str__(self):
        return self.transaction_ref
