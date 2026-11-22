from django.contrib import admin

from .models import InventoryTransaction


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    """Lịch sử nhập xuất kho – chỉ xem. Điều chỉnh tồn kho tại trang Sản phẩm."""

    list_display = ['created_at', 'product', 'type', 'quantity_change', 'stock_before', 'stock_after', 'order', 'created_by', 'note']
    list_filter = ['type', 'created_at']
    search_fields = ['product__name', 'product__sku', 'note', 'order__code']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
