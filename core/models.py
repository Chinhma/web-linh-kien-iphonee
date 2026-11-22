from django.core.cache import cache
from django.db import models
from django.urls import reverse

from .validators import validate_image_file

STORE_SETTING_CACHE_KEY = 'iparts:store_setting'


class SingletonModel(models.Model):
    """Model chỉ có đúng một bản ghi (pk=1)."""

    cache_key = ''

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        if self.cache_key:
            cache.delete(self.cache_key)

    def delete(self, *args, **kwargs):  # Không cho xóa singleton
        return None

    @classmethod
    def get_solo(cls):
        if cls.cache_key:
            obj = cache.get(cls.cache_key)
            if obj is not None:
                return obj
        obj, _ = cls.objects.get_or_create(pk=1)
        if cls.cache_key:
            cache.set(cls.cache_key, obj, 300)
        return obj


class StoreSetting(SingletonModel):
    cache_key = STORE_SETTING_CACHE_KEY

    store_name = models.CharField('Tên cửa hàng', max_length=100, default='iParts Store')
    logo = models.ImageField('Logo', upload_to='brand/', max_length=300, blank=True, validators=[validate_image_file])
    hotline = models.CharField('Hotline', max_length=20, default='0889400470')
    email = models.EmailField('Email', default='achinhofficial@gmail.com')
    address = models.CharField('Địa chỉ', max_length=255, blank=True)
    working_hours = models.CharField('Giờ làm việc', max_length=100, default='8:00 – 21:00, Thứ 2 – Chủ nhật')
    about_short = models.TextField(
        'Giới thiệu ngắn', blank=True,
        default='iParts Store chuyên cung cấp linh kiện thay thế iPhone: màn hình, pin, camera, chân sạc, loa... '
                'được tra cứu tương thích theo từng dòng máy.',
    )
    facebook_url = models.URLField('Facebook', blank=True, default='https://www.facebook.com/achinh.gaming')
    zalo_url = models.URLField('Zalo', blank=True, default='https://zalo.me/0889400470')
    messenger_url = models.URLField('Messenger', blank=True, default='https://m.me/achinh.gaming')
    telegram_url = models.URLField('Telegram', blank=True)
    shipping_fee_standard = models.PositiveIntegerField('Phí giao tiêu chuẩn', default=30000)
    shipping_fee_express = models.PositiveIntegerField('Phí giao nhanh', default=50000)
    free_shipping_threshold = models.PositiveIntegerField('Ngưỡng miễn phí ship', default=2000000)
    announcement_text = models.CharField('Thanh thông báo', max_length=255, blank=True)
    show_sample_data_notice = models.BooleanField('Hiện thông báo dữ liệu mẫu', default=True)
    enable_cod = models.BooleanField('Bật thanh toán khi nhận hàng (COD)', default=True)
    enable_vnpay = models.BooleanField('Bật VNPay', default=True, help_text='Chỉ có tác dụng khi đã cấu hình VNPay trong .env')
    enable_momo = models.BooleanField('Bật MoMo', default=True, help_text='Chỉ có tác dụng khi đã cấu hình MoMo trong .env')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cài đặt cửa hàng'
        verbose_name_plural = 'Cài đặt cửa hàng'

    def __str__(self):
        return self.store_name

    @property
    def hotline_display(self) -> str:
        digits = ''.join(ch for ch in self.hotline if ch.isdigit())
        if len(digits) == 10:
            return f'{digits[:4]} {digits[4:7]} {digits[7:]}'
        return self.hotline

    @property
    def has_social(self) -> bool:
        return bool(self.facebook_url or self.zalo_url or self.messenger_url or self.telegram_url)


class Page(models.Model):
    title = models.CharField('Tiêu đề', max_length=200)
    slug = models.SlugField('Slug', unique=True)
    content = models.TextField('Nội dung (Markdown đơn giản)')
    is_published = models.BooleanField('Hiển thị', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Trang nội dung'
        verbose_name_plural = 'Trang nội dung'
        ordering = ['title']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('core:page', args=[self.slug])


class FAQ(models.Model):
    question = models.CharField('Câu hỏi', max_length=255)
    answer = models.TextField('Trả lời')
    display_order = models.PositiveIntegerField('Thứ tự', default=0)
    is_active = models.BooleanField('Hiển thị', default=True)

    class Meta:
        verbose_name = 'Câu hỏi thường gặp'
        verbose_name_plural = 'Câu hỏi thường gặp'
        ordering = ['display_order', 'id']

    def __str__(self):
        return self.question


class Banner(models.Model):
    title = models.CharField('Tiêu đề', max_length=200)
    subtitle = models.CharField('Mô tả', max_length=300, blank=True)
    image = models.ImageField('Ảnh', upload_to='banners/', max_length=300, blank=True, validators=[validate_image_file])
    button_text = models.CharField('Chữ trên nút', max_length=50, blank=True)
    button_url = models.CharField('Link nút', max_length=255, blank=True)
    display_order = models.PositiveIntegerField('Thứ tự', default=0)
    is_active = models.BooleanField('Hiển thị', default=True)

    class Meta:
        verbose_name = 'Banner'
        verbose_name_plural = 'Banner'
        ordering = ['display_order', 'id']

    def __str__(self):
        return self.title


class NewsletterSubscriber(models.Model):
    email = models.EmailField('Email', unique=True)
    created_at = models.DateTimeField('Ngày đăng ký', auto_now_add=True)

    class Meta:
        verbose_name = 'Người đăng ký nhận tin'
        verbose_name_plural = 'Người đăng ký nhận tin'
        ordering = ['-created_at']

    def __str__(self):
        return self.email


class ContactMessage(models.Model):
    name = models.CharField('Họ tên', max_length=100)
    email = models.EmailField('Email')
    phone = models.CharField('Số điện thoại', max_length=20, blank=True)
    message = models.TextField('Nội dung', max_length=2000)
    is_read = models.BooleanField('Đã đọc', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tin nhắn liên hệ'
        verbose_name_plural = 'Tin nhắn liên hệ'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} – {self.email}'
