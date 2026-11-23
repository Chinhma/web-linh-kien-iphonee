"""Phân loại đầy đủ: giá gốc, tồn kho, SKU, ảnh, hạn khuyến mãi, mặc định, slug.

Chuyển dữ liệu cũ: (price, sale_price) -> (compare_price=price, price=sale_price);
tồn kho sản phẩm gán cho phân loại đầu tiên (giữ tổng tồn không đổi); phân loại đầu tiên làm mặc định.
"""

import django.core.validators
from django.db import migrations, models

import core.utils
import core.validators


def forwards(apps, schema_editor):
    ProductOption = apps.get_model('products', 'ProductOption')
    Product = apps.get_model('products', 'Product')
    from core.utils import vi_slugify

    for product in Product.objects.filter(options__isnull=False).distinct():
        options = list(ProductOption.objects.filter(product=product).order_by('display_order', 'id'))
        used = set()
        for i, o in enumerate(options):
            if o.sale_price and o.sale_price < o.price:
                o.compare_price, o.price = o.price, o.sale_price
            base = vi_slugify(o.name)[:110] or 'phan-loai'
            slug, n = base, 2
            while slug in used:
                slug, n = f'{base}-{n}', n + 1
            used.add(slug)
            o.slug = slug
            o.is_default = i == 0
            o.stock = product.stock_quantity if i == 0 else 0
            o.save()


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0004_product_option_label_productoption'),
    ]

    operations = [
        migrations.AddField(model_name='productoption', name='compare_price',
                            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Giá gốc',
                                                              help_text='Lớn hơn giá bán thì hiện gạch ngang và % giảm')),
        migrations.AddField(model_name='productoption', name='promo_end_at',
                            field=models.DateTimeField(blank=True, null=True, verbose_name='Kết thúc khuyến mãi',
                                                       help_text='Sau thời điểm này khách trả giá gốc. Để trống = không hết hạn')),
        migrations.AddField(model_name='productoption', name='stock',
                            field=models.PositiveIntegerField(default=0, verbose_name='Tồn kho')),
        migrations.AddField(model_name='productoption', name='sku',
                            field=models.CharField(blank=True, max_length=50, verbose_name='SKU')),
        migrations.AddField(model_name='productoption', name='image',
                            field=models.ImageField(blank=True, max_length=300, upload_to=core.utils.product_image_upload_to,
                                                    validators=[core.validators.validate_image_file], verbose_name='Ảnh riêng')),
        migrations.AddField(model_name='productoption', name='is_default',
                            field=models.BooleanField(default=False, verbose_name='Mặc định')),
        migrations.AddField(model_name='productoption', name='slug',
                            field=models.SlugField(blank=True, max_length=120, verbose_name='Slug')),
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.RemoveField(model_name='productoption', name='sale_price'),
        migrations.AlterField(model_name='productoption', name='name',
                              field=models.CharField(max_length=100, verbose_name='Tên phân loại')),
        migrations.AlterField(model_name='productoption', name='is_active',
                              field=models.BooleanField(default=True, verbose_name='Hiển thị')),
        migrations.AlterField(model_name='productoption', name='price',
                              field=models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)], verbose_name='Giá bán')),
        migrations.AlterModelOptions(name='productoption',
                                     options={'ordering': ['display_order', 'id'], 'verbose_name': 'Phân loại',
                                              'verbose_name_plural': 'Phân loại sản phẩm'}),
    ]
