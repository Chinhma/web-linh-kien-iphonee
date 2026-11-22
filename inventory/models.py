from django.conf import settings
from django.db import models


class InventoryTransaction(models.Model):
    """Nhật ký nhập/xuất kho. Mọi thay đổi Product.stock_quantity đều có một dòng ở đây."""

    class Type(models.TextChoices):
        IMPORT = 'import', 'Nhập kho'
        EXPORT_ORDER = 'export_order', 'Xuất theo đơn'
        RETURN_CANCEL = 'return_cancel', 'Hoàn kho do hủy'
        ADJUSTMENT = 'adjustment', 'Điều chỉnh kiểm kê'
        INITIAL = 'initial', 'Tồn đầu kỳ'

    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='inventory_transactions')
    type = models.CharField('Loại', max_length=20, choices=Type.choices, db_index=True)
    quantity_change = models.IntegerField('Thay đổi')
    stock_before = models.PositiveIntegerField('Tồn trước')
    stock_after = models.PositiveIntegerField('Tồn sau')
    unit_cost = models.PositiveIntegerField('Giá nhập', null=True, blank=True)
    order = models.ForeignKey('orders.Order', null=True, blank=True, on_delete=models.SET_NULL, related_name='inventory_transactions')
    note = models.CharField('Ghi chú', max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField('Thời gian', auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Giao dịch kho'
        verbose_name_plural = 'Lịch sử nhập xuất kho'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.get_type_display()} {self.quantity_change:+d} – {self.product}'
