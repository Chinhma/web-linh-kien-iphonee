from django.contrib import admin
from django.shortcuts import redirect

from .models import FAQ, Banner, ContactMessage, NewsletterSubscriber, Page, StoreSetting

admin.site.site_header = 'iParts Store Admin'
admin.site.site_title = 'iParts Store Admin'
admin.site.index_title = 'Quản trị hệ thống'


class SingletonAdmin(admin.ModelAdmin):
    """Model chỉ có 1 bản ghi: bấm vào là mở thẳng form sửa."""

    def has_add_permission(self, request):
        return not self.model.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = self.model.get_solo()
        return redirect(f'{request.path}{obj.pk}/change/')


@admin.register(StoreSetting)
class StoreSettingAdmin(SingletonAdmin):
    fieldsets = [
        ('Thông tin cửa hàng', {'fields': ['store_name', 'logo', 'hotline', 'email', 'address', 'working_hours', 'about_short']}),
        ('Mạng xã hội (để trống thì ẩn)', {'fields': ['facebook_url', 'zalo_url', 'messenger_url', 'telegram_url']}),
        ('Vận chuyển & hiển thị', {'fields': ['shipping_fee_standard', 'shipping_fee_express', 'free_shipping_threshold',
                                               'announcement_text', 'show_sample_data_notice']}),
    ]


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'is_published', 'updated_at']
    list_editable = ['is_published']
    search_fields = ['title', 'content']
    prepopulated_fields = {'slug': ['title']}


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ['question', 'display_order', 'is_active']
    list_editable = ['display_order', 'is_active']
    search_fields = ['question', 'answer']


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ['title', 'button_text', 'display_order', 'is_active']
    list_editable = ['display_order', 'is_active']


@admin.register(NewsletterSubscriber)
class NewsletterAdmin(admin.ModelAdmin):
    list_display = ['email', 'created_at']
    search_fields = ['email']
    date_hierarchy = 'created_at'


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone', 'created_at', 'is_read']
    list_filter = ['is_read']
    list_editable = ['is_read']
    search_fields = ['name', 'email', 'message']
    readonly_fields = ['name', 'email', 'phone', 'message', 'created_at']
