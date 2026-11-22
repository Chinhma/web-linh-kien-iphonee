from django.contrib import admin, messages
from django.utils.html import format_html

from core.templatetags.iparts import vnd

from .models import Order, OrderItem, OrderStatusHistory
from .services import OrderError, change_order_status, expire_unpaid_orders, mark_refunded

COLORS = {'pending': '#F59E0B', 'confirmed': '#2563EB', 'preparing': '#2563EB', 'shipping': '#1D4ED8',
          'delivered': '#16A34A', 'cancelled': '#DC2626'}


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ['product', 'product_name', 'product_sku', 'unit_price', 'quantity', 'line_total']

    def has_add_permission(self, request, obj=None):
        return False


class StatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    can_delete = False
    readonly_fields = ['from_status', 'to_status', 'changed_by', 'note', 'created_at']

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Đơn hàng: KHÔNG sửa tự do trạng thái/tổng tiền. Đổi trạng thái bằng các action (đi qua change_order_status)."""

    list_display = ['code', 'recipient_name', 'recipient_phone', 'created_at', 'total_display', 'payment_method',
                    'payment_status', 'status_badge']
    list_filter = ['status', 'payment_status', 'payment_method', 'created_at']
    search_fields = ['code', 'recipient_name', 'recipient_phone', 'user__email']
    date_hierarchy = 'created_at'
    list_per_page = 20
    inlines = [OrderItemInline, StatusHistoryInline]
    actions = ['to_confirmed', 'to_preparing', 'to_shipping', 'to_delivered', 'to_cancelled', 'to_refunded']
    readonly_fields = [f.name for f in Order._meta.fields if f.name not in ('note',)]
    fieldsets = [
        ('Đơn hàng', {'fields': ['code', 'user', 'status', 'created_at', 'confirmed_at', 'shipped_at', 'delivered_at',
                                 'cancelled_at', 'cancel_reason', 'cancelled_by']}),
        ('Người nhận', {'fields': ['recipient_name', 'recipient_phone', 'recipient_email', 'province_name', 'ward_name',
                                   'street_address', 'note', 'shipping_method']}),
        ('Thanh toán', {'fields': ['payment_method', 'payment_status', 'paid_at', 'payment_expires_at', 'subtotal',
                                   'discount_amount', 'coupon_code', 'shipping_fee', 'total']}),
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        expire_unpaid_orders()
        return super().changelist_view(request, extra_context)

    @admin.display(description='Tổng tiền', ordering='total')
    def total_display(self, obj):
        return vnd(obj.total)

    @admin.display(description='Trạng thái', ordering='status')
    def status_badge(self, obj):
        return format_html('<b style="color:{}">{}</b>', COLORS.get(obj.status, '#64748B'), obj.get_status_display())

    def _change(self, request, queryset, status, note=''):
        ok = 0
        for order in queryset:
            try:
                change_order_status(order, status, request.user, note)
                ok += 1
            except OrderError as exc:
                messages.error(request, f'{order.code}: {exc.message}')
        if ok:
            messages.success(request, f'Đã cập nhật {ok} đơn hàng.')

    @admin.action(description='Xác nhận đơn')
    def to_confirmed(self, request, queryset):
        self._change(request, queryset, 'confirmed')

    @admin.action(description='Chuyển "Đang chuẩn bị hàng"')
    def to_preparing(self, request, queryset):
        self._change(request, queryset, 'preparing')

    @admin.action(description='Chuyển "Đang giao hàng"')
    def to_shipping(self, request, queryset):
        self._change(request, queryset, 'shipping')

    @admin.action(description='Xác nhận "Giao thành công"')
    def to_delivered(self, request, queryset):
        self._change(request, queryset, 'delivered')

    @admin.action(description='Hủy đơn (hoàn kho, hoàn mã giảm giá)')
    def to_cancelled(self, request, queryset):
        self._change(request, queryset, 'cancelled', 'Hủy bởi quản trị viên')

    @admin.action(description='Đánh dấu đã hoàn tiền')
    def to_refunded(self, request, queryset):
        for order in queryset:
            try:
                mark_refunded(order, request.user, 'Cập nhật từ Django admin')
            except OrderError as exc:
                messages.error(request, f'{order.code}: {exc.message}')
