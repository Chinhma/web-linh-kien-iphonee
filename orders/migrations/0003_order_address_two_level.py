"""Địa chỉ nhận hàng 2 cấp (sau 01/07/2025): bỏ Quận/Huyện, lưu mã + tên Tỉnh/Thành và Phường/Xã.

Đơn cũ: Quận/Huyện được gộp vào street_address để snapshot địa chỉ không mất thông tin.
"""

from django.db import migrations, models


def merge_district(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    for o in Order.objects.exclude(district=''):
        o.street_address = ', '.join(p for p in [o.street_address, o.district] if p)[:255]
        o.save(update_fields=['street_address'])


class Migration(migrations.Migration):
    dependencies = [('orders', '0002_initial')]

    operations = [
        migrations.RenameField('order', 'province', 'province_name'),
        migrations.RenameField('order', 'ward', 'ward_name'),
        migrations.AlterField('order', 'province_name', models.CharField('Tỉnh/Thành phố', max_length=100)),
        migrations.AlterField('order', 'ward_name', models.CharField('Phường/Xã', max_length=100)),
        migrations.AddField('order', 'province_code', models.CharField('Mã tỉnh/thành', max_length=5, blank=True)),
        migrations.AddField('order', 'ward_code', models.CharField('Mã phường/xã', max_length=10, blank=True)),
        migrations.RunPython(merge_district, migrations.RunPython.noop),
        migrations.RemoveField('order', 'district'),
    ]
