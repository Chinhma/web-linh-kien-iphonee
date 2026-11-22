from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.utils import catalog_image_upload_to, product_image_upload_to, strip_accents, unique_slug
from core.validators import validate_image_file


class Category(models.Model):
    name = models.CharField('Tên danh mục', max_length=100, unique=True)
    slug = models.SlugField('Slug', unique=True, max_length=120, blank=True)
    code = models.CharField('Mã (dùng cho SKU)', max_length=10, unique=True)
    description = models.TextField('Mô tả', blank=True)
    image = models.ImageField('Ảnh', upload_to=catalog_image_upload_to, max_length=300, blank=True, validators=[validate_image_file])
    icon = models.CharField('Icon Lucide', max_length=50, default='package')
    parent = models.ForeignKey('self', verbose_name='Danh mục cha', null=True, blank=True,
                               on_delete=models.PROTECT, related_name='children')
    display_order = models.PositiveIntegerField('Thứ tự', default=0)
    is_active = models.BooleanField('Hoạt động', default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Danh mục'
        verbose_name_plural = 'Danh mục'
        ordering = ['display_order', 'name']

    def __str__(self):
        return f'{self.parent.name} › {self.name}' if self.parent_id else self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        self.code = (self.code or '').upper()
        super().save(*args, **kwargs)

    def clean(self):
        if self.parent_id and self.parent_id == self.pk:
            raise ValidationError({'parent': 'Danh mục cha không được là chính nó.'})

    def get_absolute_url(self):
        return reverse('products:category', args=[self.slug])

    def descendant_ids(self) -> list[int]:
        return [self.pk] + list(self.children.values_list('pk', flat=True))


class Brand(models.Model):
    name = models.CharField('Tên thương hiệu', max_length=100, unique=True)
    slug = models.SlugField('Slug', unique=True, max_length=120, blank=True)
    logo = models.ImageField('Logo', upload_to=catalog_image_upload_to, max_length=300, blank=True, validators=[validate_image_file])
    is_active = models.BooleanField('Hoạt động', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Thương hiệu'
        verbose_name_plural = 'Thương hiệu'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)


class IPhoneModel(models.Model):
    name = models.CharField('Tên dòng máy', max_length=100, unique=True)
    slug = models.SlugField('Slug', unique=True, max_length=120, blank=True)
    series = models.PositiveSmallIntegerField('Thế hệ', db_index=True, help_text='Ví dụ 13 cho iPhone 13 series; X/XS/XR = 10')
    model_codes = models.CharField('Mã A-number', max_length=200, blank=True)
    release_year = models.PositiveSmallIntegerField('Năm ra mắt', null=True, blank=True)
    image = models.ImageField('Ảnh', upload_to=catalog_image_upload_to, max_length=300, blank=True, validators=[validate_image_file])
    description = models.TextField('Mô tả', blank=True)
    display_order = models.PositiveIntegerField('Thứ tự', default=0)
    is_active = models.BooleanField('Hoạt động', default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Dòng iPhone'
        verbose_name_plural = 'Dòng iPhone'
        ordering = ['series', 'display_order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)

    @property
    def series_label(self) -> str:
        return 'iPhone X / XS / XR' if self.series == 10 else f'iPhone {self.series} series'


class Product(models.Model):
    class Quality(models.TextChoices):
        ORIGINAL = 'original', 'Chính hãng tháo máy'
        OEM = 'oem', 'OEM'
        AFTERMARKET = 'aftermarket', 'Linh kiện thay thế'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Nháp'
        ACTIVE = 'active', 'Đang bán'
        DISCONTINUED = 'discontinued', 'Ngừng kinh doanh'

    name = models.CharField('Tên sản phẩm', max_length=200)
    slug = models.SlugField('Slug', unique=True, max_length=220, blank=True)
    sku = models.CharField('SKU', max_length=50, unique=True, db_index=True)
    category = models.ForeignKey(Category, verbose_name='Danh mục', on_delete=models.PROTECT, related_name='products')
    brand = models.ForeignKey(Brand, verbose_name='Thương hiệu', null=True, blank=True,
                              on_delete=models.SET_NULL, related_name='products')
    quality_grade = models.CharField('Chất lượng', max_length=20, choices=Quality.choices, default=Quality.OEM, db_index=True)
    short_description = models.CharField('Mô tả ngắn', max_length=300, blank=True)
    description = models.TextField('Mô tả chi tiết', blank=True)
    specifications = models.JSONField('Thông số kỹ thuật', default=list, blank=True)
    usage_guide = models.TextField('Hướng dẫn & lưu ý lắp đặt', blank=True)
    part_code = models.CharField('Mã linh kiện', max_length=50, blank=True, db_index=True,
                                 help_text='Mã của nhà sản xuất/nhà cung cấp (nếu có)')
    highlights = models.JSONField('Điểm nổi bật', default=list, blank=True)
    requires_technician = models.BooleanField('Yêu cầu kỹ thuật viên lắp đặt', default=False)
    install_difficulty = models.CharField('Độ khó lắp đặt', max_length=10, blank=True,
                                          choices=[('easy', 'Dễ'), ('medium', 'Trung bình'), ('hard', 'Khó')])
    cost_price = models.PositiveIntegerField('Giá nhập', default=0)
    price = models.PositiveIntegerField('Giá bán', validators=[MinValueValidator(1)])
    sale_price = models.PositiveIntegerField('Giá khuyến mãi', null=True, blank=True)
    sale_start = models.DateTimeField('Bắt đầu khuyến mãi', null=True, blank=True)
    sale_end = models.DateTimeField('Kết thúc khuyến mãi', null=True, blank=True)
    stock_quantity = models.PositiveIntegerField('Tồn kho', default=0, editable=False)
    low_stock_threshold = models.PositiveIntegerField('Ngưỡng sắp hết', default=5)
    warranty_months = models.PositiveSmallIntegerField('Bảo hành (tháng)', default=6)
    status = models.CharField('Trạng thái', max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    is_featured = models.BooleanField('Nổi bật', default=False, db_index=True)
    sold_count = models.PositiveIntegerField('Đã bán', default=0, editable=False)
    rating_avg = models.DecimalField('Điểm đánh giá', max_digits=3, decimal_places=2, default=0, editable=False)
    rating_count = models.PositiveIntegerField('Số đánh giá', default=0, editable=False)
    view_count = models.PositiveIntegerField('Lượt xem', default=0, editable=False)
    search_text = models.TextField('Chuỗi tìm kiếm không dấu', blank=True, editable=False)
    compatible_models = models.ManyToManyField(IPhoneModel, through='Compatibility', related_name='products', blank=True)
    created_at = models.DateTimeField('Ngày tạo', auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Sản phẩm'
        verbose_name_plural = 'Sản phẩm'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gt=0), name='product_price_positive'),
            models.CheckConstraint(
                condition=models.Q(sale_price__isnull=True) | models.Q(sale_price__lt=models.F('price')),
                name='product_sale_lt_price',
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.sale_price is not None and self.price and self.sale_price >= self.price:
            raise ValidationError({'sale_price': 'Giá khuyến mãi phải nhỏ hơn giá bán.'})
        if self.sale_start and self.sale_end and self.sale_end <= self.sale_start:
            raise ValidationError({'sale_end': 'Thời gian kết thúc phải sau thời gian bắt đầu.'})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        self.sku = (self.sku or '').upper()
        if not isinstance(self.specifications, list):  # Ô thông số để trống -> danh sách rỗng (tránh lỗi NOT NULL)
            self.specifications = []
        if not isinstance(self.highlights, list):
            self.highlights = []
        self.search_text = strip_accents(f'{self.name} {self.sku} {self.part_code} {self.short_description}').lower()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('products:detail', args=[self.slug])

    # ---- Giá ----
    @property
    def is_on_sale(self) -> bool:
        if self.sale_price is None or self.sale_price >= self.price:
            return False
        now = timezone.now()
        if self.sale_start and now < self.sale_start:
            return False
        if self.sale_end and now > self.sale_end:
            return False
        return True

    @property
    def effective_price(self) -> int:
        """Giá đang áp dụng: giá KM nếu đang trong thời gian KM, ngược lại giá bán."""
        return self.sale_price if self.is_on_sale else self.price

    @property
    def discount_percent(self) -> int:
        if not self.is_on_sale or not self.price:
            return 0
        return round((self.price - self.effective_price) * 100 / self.price)

    # ---- Tồn kho ----
    @property
    def stock_status(self) -> str:
        if self.stock_quantity <= 0:
            return 'out_of_stock'
        if self.stock_quantity <= self.low_stock_threshold:
            return 'low_stock'
        return 'in_stock'

    @property
    def stock_label(self) -> str:
        status = self.stock_status
        if status == 'out_of_stock':
            return 'Hết hàng'
        if status == 'low_stock':
            return f'Sắp hết hàng (còn {self.stock_quantity})'
        return 'Còn hàng'

    @property
    def is_purchasable(self) -> bool:
        return self.status == self.Status.ACTIVE and self.stock_quantity > 0 and self.category.is_active

    @property
    def is_new(self) -> bool:
        return self.created_at and (timezone.now() - self.created_at).days < 14

    # ---- Ảnh ----
    @property
    def primary_image(self):
        images = list(self.images.all())  # Dùng cache prefetch nếu có
        for image in images:
            if image.is_primary:
                return image
        return images[0] if images else None

    @property
    def secondary_image(self):
        images = [img for img in self.images.all() if not img.is_primary]
        return images[0] if images else None

    @property
    def image_url(self) -> str:
        image = self.primary_image
        return image.image.url if image and image.image else settings.STATIC_URL + 'images/placeholders/product.svg'

    # ---- Tương thích (chỉ verified hiển thị cho khách) ----
    @property
    def verified_models(self) -> list:
        return [c.iphone_model for c in self.compatibilities.all()
                if c.status == Compatibility.Status.VERIFIED and c.iphone_model.is_active]

    @property
    def compat_short(self) -> str:
        """'iPhone 13, 13 Pro +2' – chỉ các model đã xác nhận."""
        names = [m.name for m in self.verified_models]
        if not names:
            return ''
        shown = [names[0]] + [n.replace('iPhone ', '') for n in names[1:2]]
        text = ', '.join(shown)
        return f'{text} +{len(names) - 2}' if len(names) > 2 else text


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField('Ảnh', upload_to=product_image_upload_to, max_length=300, validators=[validate_image_file])
    alt_text = models.CharField('Mô tả ảnh', max_length=200, blank=True)
    is_primary = models.BooleanField('Ảnh chính', default=False)
    display_order = models.PositiveIntegerField('Thứ tự', default=0)

    class Meta:
        verbose_name = 'Ảnh sản phẩm'
        verbose_name_plural = 'Ảnh sản phẩm'
        ordering = ['-is_primary', 'display_order', 'id']

    def __str__(self):
        return self.alt_text or f'Ảnh của {self.product}'

    def save(self, *args, **kwargs):
        if self.is_primary:
            ProductImage.objects.filter(product_id=self.product_id, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        elif not ProductImage.objects.filter(product_id=self.product_id, is_primary=True).exclude(pk=self.pk).exists():
            self.is_primary = True
        super().save(*args, **kwargs)


class Compatibility(models.Model):
    """Quan hệ tương thích Product ↔ IPhoneModel – nguồn dữ liệu duy nhất cho tra cứu, trang sản phẩm và chatbot."""

    class Status(models.TextChoices):
        VERIFIED = 'verified', 'Đã xác nhận'
        UNVERIFIED = 'unverified', 'Chưa xác nhận'
        INCOMPATIBLE = 'incompatible', 'Không tương thích'

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='compatibilities')
    iphone_model = models.ForeignKey(IPhoneModel, on_delete=models.CASCADE, related_name='compatibilities')
    status = models.CharField('Trạng thái', max_length=20, choices=Status.choices, default=Status.UNVERIFIED, db_index=True)
    note = models.CharField('Ghi chú', max_length=300, blank=True)
    source = models.CharField('Nguồn thông tin', max_length=200, blank=True)
    is_sample_data = models.BooleanField('Dữ liệu mẫu', default=False)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='Người xác nhận', null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='+')
    verified_at = models.DateTimeField('Ngày xác nhận', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tương thích'
        verbose_name_plural = 'Linh kiện tương thích'
        ordering = ['iphone_model__series', 'iphone_model__display_order', 'product__name']
        constraints = [models.UniqueConstraint(fields=['product', 'iphone_model'], name='unique_product_iphone')]

    def __str__(self):
        return f'{self.product} ↔ {self.iphone_model} ({self.get_status_display()})'

    def set_status(self, status: str, user=None) -> None:
        """Đổi trạng thái; ghi lại người/ngày xác nhận khi chuyển sang verified."""
        self.status = status
        if status == self.Status.VERIFIED:
            self.verified_by = user
            self.verified_at = timezone.now()
