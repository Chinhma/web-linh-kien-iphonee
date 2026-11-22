"""Địa chỉ 2 cấp (sau 01/07/2025): bỏ Quận/Huyện, lưu mã + tên Tỉnh/Thành và Phường/Xã.

Dữ liệu cũ: giá trị Quận/Huyện được gộp vào street_address để không mất thông tin.
"""

from django.db import migrations, models


def merge_district(apps, schema_editor):
    Address = apps.get_model('accounts', 'Address')
    for a in Address.objects.exclude(district=''):
        a.street_address = ', '.join(p for p in [a.street_address, a.district] if p)[:255]
        a.save(update_fields=['street_address'])


class Migration(migrations.Migration):
    dependencies = [('accounts', '0001_initial')]

    operations = [
        migrations.RenameField('address', 'province', 'province_name'),
        migrations.RenameField('address', 'ward', 'ward_name'),
        migrations.AlterField('address', 'province_name', models.CharField('Tỉnh/Thành phố', max_length=100)),
        migrations.AlterField('address', 'ward_name', models.CharField('Phường/Xã', max_length=100)),
        migrations.AddField('address', 'province_code', models.CharField('Mã tỉnh/thành', max_length=5, blank=True)),
        migrations.AddField('address', 'ward_code', models.CharField('Mã phường/xã', max_length=10, blank=True)),
        migrations.RunPython(merge_district, migrations.RunPython.noop),
        migrations.RemoveField('address', 'district'),
    ]
