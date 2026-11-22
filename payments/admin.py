from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Chỉ xem – không cho sửa giao dịch."""

    list_display = ['transaction_ref', 'order', 'method', 'amount', 'status', 'gateway_response_code', 'created_at']
    list_filter = ['method', 'status', 'created_at']
    search_fields = ['transaction_ref', 'gateway_transaction_id', 'order__code']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
