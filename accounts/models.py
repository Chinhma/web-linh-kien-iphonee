from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.db import models, transaction

from core.utils import avatar_upload_to
from core.validators import validate_image_file

MAX_ADDRESSES = 10


class IPartsUserManager(UserManager):
    def get_by_natural_key(self, username):
        return self.get(**{f'{self.model.USERNAME_FIELD}__iexact': username})


class User(AbstractUser):
    """Tài khoản người dùng. Vai trò: Customer (is_staff=False) hoặc Admin (is_staff=True)."""

    class AuthProvider(models.TextChoices):
        LOCAL = 'local', 'Email'
        GOOGLE = 'google', 'Google'

    email = models.EmailField('Email', unique=True)
    full_name = models.CharField('Họ và tên', max_length=100, blank=True)
    phone = models.CharField('Số điện thoại', max_length=15, blank=True)
    avatar = models.ImageField('Ảnh đại diện', upload_to=avatar_upload_to, max_length=300, blank=True, validators=[validate_image_file])
    auth_provider = models.CharField('Đăng ký bằng', max_length=10, choices=AuthProvider.choices, default=AuthProvider.LOCAL)
    created_at = models.DateTimeField('Ngày tạo', auto_now_add=True)

    objects = IPartsUserManager()

    class Meta:
        verbose_name = 'Người dùng'
        verbose_name_plural = 'Người dùng'
        ordering = ['-date_joined']

    def __str__(self):
        return self.display_name

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    @property
    def display_name(self) -> str:
        return self.full_name or self.get_full_name() or self.username

    @property
    def role_label(self) -> str:
        if self.is_superuser:
            return 'Superuser'
        if self.is_staff:
            return 'Admin'
        return 'Khách hàng'


class CustomerProfile(models.Model):
    class Gender(models.TextChoices):
        MALE = 'male', 'Nam'
        FEMALE = 'female', 'Nữ'
        OTHER = 'other', 'Khác'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    date_of_birth = models.DateField('Ngày sinh', null=True, blank=True)
    gender = models.CharField('Giới tính', max_length=10, choices=Gender.choices, blank=True)
    newsletter_subscribed = models.BooleanField('Nhận bản tin', default=False)
    note_by_admin = models.TextField('Ghi chú nội bộ (chỉ Admin)', blank=True)

    class Meta:
        verbose_name = 'Hồ sơ khách hàng'
        verbose_name_plural = 'Hồ sơ khách hàng'

    def __str__(self):
        return f'Hồ sơ của {self.user}'


class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    full_name = models.CharField('Họ tên người nhận', max_length=100)
    phone = models.CharField('Số điện thoại', max_length=15)
    # Đơn vị hành chính sau 01/07/2025: chỉ 2 cấp Tỉnh/Thành phố -> Phường/Xã
    province_code = models.CharField('Mã tỉnh/thành', max_length=5, blank=True)
    province_name = models.CharField('Tỉnh/Thành phố', max_length=100)
    ward_code = models.CharField('Mã phường/xã', max_length=10, blank=True)
    ward_name = models.CharField('Phường/Xã', max_length=100)
    street_address = models.CharField('Địa chỉ chi tiết', max_length=255)
    is_default = models.BooleanField('Mặc định', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Địa chỉ'
        verbose_name_plural = 'Sổ địa chỉ'
        ordering = ['-is_default', '-updated_at']
        constraints = [
            models.UniqueConstraint(fields=['user'], condition=models.Q(is_default=True), name='one_default_address_per_user'),
        ]

    def __str__(self):
        return f'{self.full_name} – {self.full_address}'

    @property
    def full_address(self) -> str:
        from core.address import format_address

        return format_address(self.street_address, self.ward_name, self.province_name)

    def clean(self):
        if not self.pk and self.user_id and Address.objects.filter(user_id=self.user_id).count() >= MAX_ADDRESSES:
            raise ValidationError(f'Mỗi tài khoản lưu tối đa {MAX_ADDRESSES} địa chỉ.')

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.is_default:
                Address.objects.filter(user_id=self.user_id, is_default=True).exclude(pk=self.pk).update(is_default=False)
            elif not Address.objects.filter(user_id=self.user_id, is_default=True).exclude(pk=self.pk).exists():
                self.is_default = True
            super().save(*args, **kwargs)
