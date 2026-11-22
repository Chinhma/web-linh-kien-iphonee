from django.contrib import admin

from .models import Coupon, CouponUsage


class CouponUsageInline(admin.TabularInline):
    model = CouponUsage
    extra = 0
    can_delete = False
    readonly_fields = ['user', 'order', 'discount_amount', 'created_at']

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'value_label', 'min_order_value', 'used_count', 'usage_limit', 'start_at', 'end_at', 'state_label', 'is_active']
    list_filter = ['is_active', 'discount_type']
    search_fields = ['code', 'description']
    readonly_fields = ['used_count']
    inlines = [CouponUsageInline]
