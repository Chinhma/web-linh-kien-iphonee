from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.utils import catalog_image_upload_to, product_image_upload_to, strip_accents, unique_slug
from core.validators import validate_image_file


def guess_model_code(name: str) -> str:
    """Đoán mã dòng máy từ tên sản phẩm: "Màn hình Iphone 8 plus" -> "8PLUS", "Pin iPhone 13 Pro Max" -> "13PROMAX"."""
    import re

    text = strip_accents(name or '').lower()
    names = sorted(IPhoneModel.objects.values_list('name', flat=True), key=len, reverse=True)
    for model_name in names:  # Ưu tiên dòng máy có trong danh mục Dòng iPhone (tên dài khớp trước)
        if strip_accents(model_name).lower() in text:
            return strip_accents(model_name).upper().replace('IPHONE', '').replace(' ', '')[:10]
    m = re.search(r'iphone\s*((?:\d+|x[rs]?|se)(?:\s*(?:pro|max|plus|mini|e))*)', text)
    return m.group(1).upper().replace(' ', '')[:10] if m else ''


def generate_sku(category, model_name: str = '') -> str:
    """SKU dạng IP-{MÃ_DANH_MỤC}-{MÃ_MODEL}-{SỐ}, ví dụ IP-SCR-13PRO-001 (số tự tăng, không trùng)."""
    code = (category.parent.code if category.parent_id and not category.code else category.code) or 'GEN'
    model = strip_accents(model_name).upper().replace('IPHONE', '').replace(' ', '')[:10] or 'GEN'
    prefix = f'IP-{code}-{model}-'
    n = 1
    while Product.objects.filter(sku=f'{prefix}{n:03d}').exists():
        n += 1
    return f'{prefix}{n:03d}'


def _abbr(text: str) -> str:
    """"Màn zin bóc máy" -> "ZBM" (bỏ chữ "Màn"), "Trắng" -> "TRANG"."""
    words = [w for w in strip_accents(text or '').upper().split() if w not in ('MAN', 'HINH', 'MAU')]
    if len(words) == 1:
        return words[0][:6]
    return ''.join(w[0] for w in words if w)[:6]


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
    option_label = models.CharField('Tiêu đề nhóm lựa chọn', max_length=60, blank=True,
                                    help_text='Ví dụ "Loại màn hình" hoặc "Dòng máy". Để trống sẽ hiện "Chọn phân loại".')
    created_at = models.DateTimeField('Ngày tạo', auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Sản phẩm'
        verbose_name_plural = 'Sản phẩm'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gt=0), name='product_price_positive'),
            models.CheckConstraint(
                # Giá KM bằng giá bán = không khuyến mãi (0%) – hợp lệ; chỉ cấm giá KM lớn hơn giá bán
                condition=models.Q(sale_price__isnull=True) | models.Q(sale_price__lte=models.F('price')),
                name='product_sale_lte_price',
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.sale_price is not None and self.price and self.sale_price > self.price:
            raise ValidationError({'sale_price': 'Giá khuyến mãi không được lớn hơn giá bán.'})
        if self.sale_start and self.sale_end and self.sale_end <= self.sale_start:
            raise ValidationError({'sale_end': 'Thời gian kết thúc phải sau thời gian bắt đầu.'})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        self.sku = (self.sku or '').strip().upper()
        if not self.sku and self.category_id:  # Để trống SKU -> tự sinh
            self.sku = generate_sku(self.category, guess_model_code(self.name))
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

    # ---- Lựa chọn (option) ----
    @property
    def active_options(self) -> list:
        """Loại màn (nhóm lựa chọn 1) đang hiển thị – dùng cache prefetch nếu có."""
        return [o for o in self.options.all() if o.is_active]

    @property
    def active_colors(self) -> list:
        """Màu sắc (nhóm lựa chọn 2) đang hiển thị."""
        return [c for c in self.colors.all() if c.is_active]

    @property
    def default_option(self):
        options = self.active_options
        return next((o for o in options if o.is_default), options[0] if options else None)

    @property
    def default_color(self):
        colors = self.active_colors
        return next((c for c in colors if c.is_default), colors[0] if colors else None)

    @property
    def active_variants(self) -> list:
        """Biến thể bán được: biến thể bật + loại màn/màu của nó đang hiển thị."""
        result = []
        for v in self.variants.all():
            if not v.is_active:
                continue
            if v.option_id and not any(o.pk == v.option_id for o in self.active_options):
                continue
            if v.color_id and not any(c.pk == v.color_id for c in self.active_colors):
                continue
            v.product = self
            result.append(v)
        return result

    @property
    def has_variants(self) -> bool:
        return bool(self.active_variants)

    @property
    def default_variant(self):
        """Tổ hợp mặc định: loại màn mặc định + màu mặc định (dùng cho giá ở danh sách/thẻ/tìm kiếm)."""
        variants = self.active_variants
        if not variants:
            return None
        opt, col = self.default_option, self.default_color
        match = [v for v in variants if v.option_id == (opt.pk if opt else None)]
        exact = next((v for v in match if v.color_id == (col.pk if col else None)), None)
        return exact or next((v for v in match if v.stock > 0), None) or (match[0] if match else variants[0])

    def apply_option_prices(self) -> int:
        """Giá đặt ở LOẠI MÀN -> áp cho mọi biến thể (mọi màu) của loại đó. Trả về số biến thể được cập nhật."""
        updated = 0
        for option in self.options.exclude(price=None):
            updated += ProductVariant.objects.filter(product=self, option=option).exclude(
                price=option.price, compare_price=None).update(price=option.price, compare_price=None)
        return updated

    def ensure_variants(self) -> int:
        """Tự sinh các tổ hợp LOẠI MÀN × MÀU còn thiếu (để admin chỉ việc sửa giá từng dòng).

        Biến thể mới lấy giá đang hiển thị của sản phẩm. Lần đầu tạo (chưa có biến thể nào) thì chia đều tồn kho
        hiện tại của sản phẩm cho các biến thể, để tổng tồn không đổi; thêm loại/màu về sau thì tồn kho = 0.
        Trả về số biến thể vừa tạo.
        """
        options = list(self.options.all())
        colors = list(self.colors.all())
        if not options and not colors:
            return 0
        existing = list(self.variants.all())
        have = {(v.option_id, v.color_id) for v in existing}
        missing = [(o, c) for o in (options or [None]) for c in (colors or [None])
                   if (o.pk if o else None, c.pk if c else None) not in have]
        if not missing:
            return 0
        self.refresh_from_db(fields=['price', 'sale_price', 'sale_start', 'sale_end', 'stock_quantity'])
        price = self.effective_price
        compare = self.price if self.is_on_sale else None
        share, extra = divmod(self.stock_quantity, len(missing)) if not existing else (0, 0)
        for i, (o, c) in enumerate(missing):
            has_own = o is not None and o.price  # Loại màn có giá riêng -> dùng giá của loại
            ProductVariant.objects.create(
                product=self, option=o, color=c, price=o.price if has_own else price,
                compare_price=None if has_own else compare,
                stock=share + (extra if i == 0 else 0))
        return len(missing)

    def sync_from_variants(self, user=None) -> None:
        """Có biến thể: giá hiển thị = tổ hợp mặc định; tồn kho sản phẩm = tổng tồn các biến thể bán được."""
        product = Product.objects.prefetch_related('options', 'colors', 'variants').get(pk=self.pk)
        variants = product.active_variants
        if not variants:
            return
        display = product.default_variant
        opt = display.priced_option
        if opt is not None:  # Giá + khuyến mãi (kể cả khung giờ) theo loại màn mặc định
            fields = {'price': opt.price, 'sale_price': opt.sale_price if (opt.sale_price or 0) < opt.price else None,
                      'sale_start': opt.sale_start, 'sale_end': opt.sale_end}
            if opt.cost_price is not None:
                fields['cost_price'] = opt.cost_price
        elif display.has_discount:
            fields = {'price': display.compare_price, 'sale_price': display.price, 'sale_start': None, 'sale_end': None}
        else:
            fields = {'price': display.price, 'sale_price': None, 'sale_start': None, 'sale_end': None}
        Product.objects.filter(pk=self.pk).update(**fields)
        for k, v in fields.items():
            setattr(self, k, v)
        total = sum(v.stock for v in variants)
        self.refresh_from_db(fields=['stock_quantity'])
        if total != self.stock_quantity:
            from inventory.models import InventoryTransaction
            from inventory.services import adjust_stock

            adjust_stock(self, total - self.stock_quantity, InventoryTransaction.Type.ADJUSTMENT, user,
                         'Đồng bộ tồn kho theo biến thể')

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


def _unique_slug_in_product(instance, model, base: str) -> str:
    slug, n = base, 2
    while model.objects.filter(product_id=instance.product_id, slug=slug).exclude(pk=instance.pk).exists():
        slug, n = f'{base}-{n}', n + 1
    return slug


class ProductOption(models.Model):
    """Nhóm lựa chọn 1 – LOẠI MÀN (vd. Zin bóc máy / Zin ép kính / GX / JK / Incell / Màn lô).
    Giá, tồn kho, SKU, ảnh nằm ở biến thể (ProductVariant = loại màn × màu)."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='options')
    name = models.CharField('Tên loại', max_length=100)
    slug = models.SlugField('Slug', max_length=120, blank=True)
    description = models.CharField('Mô tả ngắn', max_length=300, blank=True,
                                   help_text='2–3 dòng hiện dưới nhóm chọn, vd. "Màn Apple tháo máy, màu sắc – độ sáng gần như nguyên bản."')
    cost_price = models.PositiveIntegerField('Giá nhập', null=True, blank=True)
    price = models.PositiveIntegerField('Giá bán', null=True, blank=True, validators=[MinValueValidator(1)],
                                        help_text='Giá của loại màn này – áp cho mọi màu của loại')
    sale_price = models.PositiveIntegerField('Giá khuyến mãi', null=True, blank=True,
                                             help_text='Không lớn hơn giá bán. Bằng giá bán hoặc để trống = không khuyến mãi (0%). % giảm tự tính')
    sale_start = models.DateTimeField('Bắt đầu khuyến mãi', null=True, blank=True)
    sale_end = models.DateTimeField('Kết thúc khuyến mãi', null=True, blank=True)
    is_default = models.BooleanField('Mặc định', default=False)
    is_active = models.BooleanField('Hiển thị', default=True)
    display_order = models.PositiveIntegerField('Thứ tự', default=0)

    class Meta:
        verbose_name = 'Loại màn / phân loại'
        verbose_name_plural = 'Loại màn / phân loại'
        ordering = ['display_order', 'id']

    def __str__(self):
        return self.name

    def clean(self):
        if self.sale_price is not None and self.price and self.sale_price > self.price:
            raise ValidationError({'sale_price': 'Giá khuyến mãi không được lớn hơn giá bán.'})
        if self.sale_start and self.sale_end and self.sale_end <= self.sale_start:
            raise ValidationError({'sale_end': 'Thời gian kết thúc phải sau thời gian bắt đầu.'})

    # ---- Giá (giống sản phẩm: giá bán + giá khuyến mãi trong khung giờ)
    @property
    def is_on_sale(self) -> bool:
        if not self.price or self.sale_price is None or self.sale_price >= self.price:
            return False
        now = timezone.now()
        return not (self.sale_start and now < self.sale_start) and not (self.sale_end and now > self.sale_end)

    @property
    def effective_price(self):
        return self.sale_price if self.is_on_sale else self.price

    @property
    def discount_percent(self) -> int:
        return round((self.price - self.sale_price) * 100 / self.price) if self.is_on_sale else 0

    def save(self, *args, **kwargs):
        from core.utils import vi_slugify

        if not self.slug:
            self.slug = _unique_slug_in_product(self, ProductOption, vi_slugify(self.name)[:110] or 'loai')
        super().save(*args, **kwargs)
        if self.is_default:  # Mỗi sản phẩm chỉ 1 loại mặc định
            ProductOption.objects.filter(product_id=self.product_id, is_default=True).exclude(pk=self.pk).update(is_default=False)


class ProductColor(models.Model):
    """Nhóm lựa chọn 2 – MÀU SẮC (vd. màn iPhone 8 Plus: Trắng / Đen). Số màu tùy từng sản phẩm."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='colors')
    name = models.CharField('Tên màu', max_length=60)
    slug = models.SlugField('Slug', max_length=80, blank=True)
    hex_code = models.CharField('Mã màu', max_length=7, default='#E2E8F0', help_text='Ví dụ #FFFFFF (trắng), #111111 (đen)')
    image = models.ImageField('Ảnh màu', upload_to=product_image_upload_to, max_length=300, blank=True,
                              validators=[validate_image_file])
    is_default = models.BooleanField('Mặc định', default=False)
    is_active = models.BooleanField('Hiển thị', default=True)
    display_order = models.PositiveIntegerField('Thứ tự', default=0)

    class Meta:
        verbose_name = 'Màu sắc'
        verbose_name_plural = 'Màu sắc'
        ordering = ['display_order', 'id']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        from core.utils import vi_slugify

        if not self.slug:
            self.slug = _unique_slug_in_product(self, ProductColor, vi_slugify(self.name)[:70] or 'mau')
        super().save(*args, **kwargs)
        if self.is_default:
            ProductColor.objects.filter(product_id=self.product_id, is_default=True).exclude(pk=self.pk).update(is_default=False)


class ProductVariant(models.Model):
    """Biến thể = 1 loại màn × 1 màu (một trong hai có thể trống). Giá cuối = giá biến thể, không cộng gì thêm."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    option = models.ForeignKey(ProductOption, verbose_name='Loại màn', null=True, blank=True, on_delete=models.CASCADE,
                               related_name='variants')
    color = models.ForeignKey(ProductColor, verbose_name='Màu', null=True, blank=True, on_delete=models.CASCADE,
                              related_name='variants')
    price = models.PositiveIntegerField('Giá bán', validators=[MinValueValidator(1)])
    compare_price = models.PositiveIntegerField('Giá gốc', null=True, blank=True,
                                                help_text='Lớn hơn giá bán thì hiện gạch ngang và % giảm')
    stock = models.PositiveIntegerField('Tồn kho', default=0)
    sku = models.CharField('SKU', max_length=50, blank=True)
    image = models.ImageField('Ảnh riêng', upload_to=product_image_upload_to, max_length=300, blank=True,
                              validators=[validate_image_file])
    is_active = models.BooleanField('Bật', default=True)

    class Meta:
        verbose_name = 'Biến thể'
        verbose_name_plural = 'Biến thể (loại màn × màu)'
        ordering = ['option__display_order', 'option_id', 'color__display_order', 'color_id']

    def __str__(self):
        return f'{self.product.name} – {self.label}' if self.label else self.product.name

    def clean(self):
        if self.compare_price is not None and self.price and self.compare_price <= self.price:
            raise ValidationError({'compare_price': 'Giá gốc phải lớn hơn giá bán (hoặc để trống).'})

    def save(self, *args, **kwargs):
        self.sku = (self.sku or '').strip().upper()
        if not self.sku:  # vd. IP-SCR-8PLUS-001-ZBM-TRANG
            parts = [Product.objects.values_list('sku', flat=True).get(pk=self.product_id)]
            parts += [_abbr(x.name) for x in (self.option, self.color) if x is not None]
            self.sku = '-'.join(p for p in parts if p)[:50]
        if self.option_id and self.option.price:  # Loại màn có giá riêng -> biến thể theo giá loại
            self.price = self.option.price
            self.compare_price = None
        if not self.price:
            self.price = Product.objects.get(pk=self.product_id).effective_price
        super().save(*args, **kwargs)

    @property
    def label(self) -> str:
        return ' · '.join(x.name for x in (self.option, self.color) if x is not None)

    @property
    def priced_option(self):
        """Loại màn có đặt giá -> giá & khuyến mãi lấy theo loại màn (áp cho mọi màu)."""
        return self.option if self.option_id and self.option.price else None

    @property
    def has_discount(self) -> bool:
        opt = self.priced_option
        if opt is not None:
            return opt.is_on_sale
        return bool(self.compare_price and self.compare_price > self.price)

    @property
    def effective_price(self) -> int:
        opt = self.priced_option
        return opt.effective_price if opt is not None else self.price

    @property
    def original_price(self):
        """Giá gạch ngang (khi đang giảm giá)."""
        opt = self.priced_option
        if opt is not None:
            return opt.price if opt.is_on_sale else None
        return self.compare_price if self.has_discount else None

    @property
    def discount_percent(self) -> int:
        opt = self.priced_option
        if opt is not None:
            return opt.discount_percent
        return round((self.compare_price - self.price) * 100 / self.compare_price) if self.has_discount else 0

    @property
    def stock_status(self) -> str:
        if self.stock <= 0:
            return 'out_of_stock'
        if self.stock <= self.product.low_stock_threshold:
            return 'low_stock'
        return 'in_stock'

    @property
    def stock_label(self) -> str:
        status = self.stock_status
        if status == 'out_of_stock':
            return 'Hết hàng'
        if status == 'low_stock':
            return f'Sắp hết hàng (còn {self.stock})'
        return 'Còn hàng'


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
