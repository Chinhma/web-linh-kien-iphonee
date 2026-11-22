from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Address, CustomerProfile, User


class CustomerProfileInline(admin.StackedInline):
    model = CustomerProfile
    can_delete = False
    extra = 0


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'username', 'full_name', 'phone', 'auth_provider', 'is_staff', 'is_active', 'date_joined']
    list_filter = ['is_staff', 'is_superuser', 'is_active', 'auth_provider']
    search_fields = ['email', 'username', 'full_name', 'phone']
    ordering = ['-date_joined']
    inlines = [CustomerProfileInline, AddressInline]
    fieldsets = [
        (None, {'fields': ['username', 'password']}),
        ('Thông tin cá nhân', {'fields': ['full_name', 'email', 'phone', 'avatar', 'auth_provider']}),
        ('Phân quyền', {'fields': ['is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions']}),
        ('Thời gian', {'fields': ['last_login', 'date_joined']}),
    ]
    add_fieldsets = [(None, {'classes': ['wide'], 'fields': ['username', 'email', 'full_name', 'password1', 'password2', 'is_staff']})]

    def get_readonly_fields(self, request, obj=None):
        # Chỉ Superuser mới được cấp/thu hồi quyền quản trị
        if request.user.is_superuser:
            return ['last_login', 'date_joined']
        return ['last_login', 'date_joined', 'is_staff', 'is_superuser', 'groups', 'user_permissions']
