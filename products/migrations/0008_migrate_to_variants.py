"""Chuyển dữ liệu sang biến thể = loại màn × màu.

- Mỗi loại màn cũ (có giá/tồn/SKU/ảnh) × mỗi màu của sản phẩm -> 1 biến thể cùng giá. Tồn kho của loại màn
  chia đều cho các màu (phần dư dồn vào màu đầu tiên) để tổng tồn không đổi.
- Sản phẩm chỉ có màu -> mỗi màu 1 biến thể theo giá sản phẩm (giá + giá chênh cũ).
- Giỏ hàng / đơn hàng đang trỏ loại màn + màu -> trỏ sang biến thể tương ứng.
"""

from django.db import migrations


def forwards(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    ProductOption = apps.get_model('products', 'ProductOption')
    ProductColor = apps.get_model('products', 'ProductColor')
    ProductVariant = apps.get_model('products', 'ProductVariant')
    CartItem = apps.get_model('cart', 'CartItem')
    OrderItem = apps.get_model('orders', 'OrderItem')

    pids = set(ProductOption.objects.values_list('product_id', flat=True)) | set(
        ProductColor.objects.values_list('product_id', flat=True))
    for product in Product.objects.filter(pk__in=pids):
        options = list(ProductOption.objects.filter(product=product).order_by('display_order', 'id'))
        colors = list(ProductColor.objects.filter(product=product).order_by('display_order', 'id'))
        if options:
            for o in options:
                targets = colors or [None]
                share, extra = divmod(o.stock, len(targets))
                for i, c in enumerate(targets):
                    price = o.price + (c.extra_price if c else 0)
                    compare = (o.compare_price + (c.extra_price if c else 0)) if o.compare_price else None
                    ProductVariant.objects.create(
                        product=product, option=o, color=c, price=max(1, price), compare_price=compare,
                        stock=share + (extra if i == 0 else 0),
                        sku=(f'{o.sku}-{c.slug.upper()}' if o.sku and c else o.sku)[:50],
                        image=o.image, is_active=o.is_active)
        else:
            base = product.sale_price if product.sale_price else product.price
            share, extra = divmod(product.stock_quantity, len(colors))
            for i, c in enumerate(colors):
                ProductVariant.objects.create(product=product, color=c, price=max(1, base + c.extra_price),
                                              stock=share + (extra if i == 0 else 0), is_active=True)

    def find(product_id, option_id, color_id):
        qs = ProductVariant.objects.filter(product_id=product_id, option_id=option_id)
        return qs.filter(color_id=color_id).first() or qs.first()

    for ci in CartItem.objects.exclude(option_id=None, color_id=None):
        v = find(ci.product_id, ci.option_id, ci.color_id)
        if v is None:
            ci.delete()
        else:
            ci.variant_id = v.pk
            ci.save(update_fields=['variant'])
    for item in OrderItem.objects.exclude(option_id=None):
        color = ProductColor.objects.filter(product_id=item.product_id, name=item.color_name).first()
        v = find(item.product_id, item.option_id, color.pk if color else None)
        if v:
            item.variant_id = v.pk
            item.warranty_months = item.warranty_months or 12
            item.save(update_fields=['variant', 'warranty_months'])


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0007_productvariant'),
        ('cart', '0004_cartitem_variant'),
        ('orders', '0008_orderitem_variant_alter_orderitem_option'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
