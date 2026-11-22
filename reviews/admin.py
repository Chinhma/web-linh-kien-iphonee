from django.contrib import admin

from .models import Review
from .services import refresh_product_rating, set_review_status


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'rating', 'short_content', 'status', 'created_at']
    list_filter = ['status', 'rating', 'created_at']
    search_fields = ['content', 'product__name', 'user__email']
    readonly_fields = ['user', 'product', 'order_item', 'rating', 'content', 'created_at']
    fields = ['user', 'product', 'order_item', 'rating', 'content', 'status', 'admin_reply', 'created_at']
    actions = ['approve', 'hide']

    def has_add_permission(self, request):
        return False

    @admin.display(description='Nội dung')
    def short_content(self, obj):
        return obj.content[:60]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        refresh_product_rating(obj.product_id)  # Cập nhật điểm trung bình khi duyệt/ẩn

    def delete_model(self, request, obj):
        product_id = obj.product_id
        super().delete_model(request, obj)
        refresh_product_rating(product_id)

    @admin.action(description='Duyệt các đánh giá đã chọn')
    def approve(self, request, queryset):
        set_review_status(list(queryset.values_list('pk', flat=True)), 'approved')

    @admin.action(description='Ẩn các đánh giá đã chọn')
    def hide(self, request, queryset):
        set_review_status(list(queryset.values_list('pk', flat=True)), 'hidden')
