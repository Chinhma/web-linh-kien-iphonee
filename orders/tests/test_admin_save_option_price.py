"""Bấm Lưu thật trong Django admin: nhập giá ở dòng Loại màn -> mọi màu của loại đó đổi giá, trang sản phẩm đúng giá."""

from django.test import TestCase
from django.urls import reverse

from core.tests.factories import PASSWORD, make_admin, make_product
from products.models import ProductColor, ProductOption


def form_data(response) -> dict:
    """Dựng dữ liệu POST từ form admin đang hiển thị (form chính + mọi inline)."""
    data = {}

    def add(form):
        for name, field in form.fields.items():
            value = form[name].value()
            if value is None or value is False:
                continue
            if isinstance(value, (list, tuple)):
                value = list(value)
            elif value is True:
                value = 'on'
            elif hasattr(value, 'name') and not isinstance(value, str):  # file
                continue
            data[form.add_prefix(name)] = value

    add(response.context['adminform'].form)
    for inline in response.context['inline_admin_formsets']:
        fs = inline.formset
        for k, v in fs.management_form.initial.items():
            data[f'{fs.prefix}-{k}'] = v
        for f in fs.forms:
            add(f)
    return data


class AdminSaveOptionPriceTests(TestCase):
    def test_save_option_prices_in_django_admin(self):
        p = make_product(name='Màn hình iPhone 8 Plus', sku='ADM-1', price=3000000, stock=90)
        for i, name in enumerate(['Màn GX', 'Màn zin bóc máy', 'Màn zin ép kính']):
            ProductOption.objects.create(product=p, name=name, price=3000000, display_order=i, is_default=(i == 1))
        ProductColor.objects.create(product=p, name='Trắng')
        ProductColor.objects.create(product=p, name='Đen')
        p.ensure_variants()
        p.sync_from_variants()

        admin = make_admin()
        self.client.login(username=admin.username, password=PASSWORD)
        url = reverse('admin:products_product_change', args=[p.pk])
        data = form_data(self.client.get(url))
        new = {'Màn GX': '650000', 'Màn zin bóc máy': '1250000', 'Màn zin ép kính': '900000'}
        i = 0
        while f'options-{i}-name' in data:
            data[f'options-{i}-price'] = new[data[f'options-{i}-name']]
            i += 1
        data['options-1-sale_price'] = '1200000'  # Zin bóc máy: giá bán 1.250.000, KM 1.200.000
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 302, getattr(r, 'context', None) and [
            r.context['adminform'].form.errors, [f.errors for i in r.context['inline_admin_formsets'] for f in i.formset.forms],
            [i.formset.non_form_errors() for i in r.context['inline_admin_formsets']]])

        prices = {(v.option.name, v.color.name): v.price for v in p.variants.select_related('option', 'color')}
        self.assertEqual(prices[('Màn GX', 'Đen')], 650000)
        self.assertEqual(prices[('Màn zin ép kính', 'Trắng')], 900000)
        self.assertEqual(prices[('Màn zin bóc máy', 'Đen')], 1250000)
        p.refresh_from_db()
        self.assertEqual(p.effective_price, 1200000)
        sel = self.client.get(p.get_absolute_url()).context['sel']
        self.assertEqual((sel['price'], sel['original_price']), (1200000, 1250000))
        self.assertEqual({c['name']: c['price'] for c in sel['option_cards']},
                         {'Màn GX': 650000, 'Màn zin bóc máy': 1200000, 'Màn zin ép kính': 900000})


class AdminAddProductWithOptionPricesTests(TestCase):
    def test_add_new_product_only_option_prices(self):
        from core.tests.factories import make_category

        admin = make_admin()
        self.client.login(username=admin.username, password=PASSWORD)
        url = reverse('admin:products_product_add')
        r = self.client.get(url)
        self.assertContains(r, 'Giá chung (sản phẩm không có loại màn)')
        data = form_data(r)
        data.update({'name': 'Màn hình iPhone 8 Plus', 'sku': 'ADD-8P', 'category': make_category('Màn hình', 'SCR').pk,
                     'quality_grade': 'oem', 'status': 'active', 'low_stock_threshold': 5, 'price': '', 'cost_price': ''})
        rows = [('Màn zin bóc máy', '1250000', '1200000', 'on'), ('Màn GX', '650000', '', '')]
        data['options-TOTAL_FORMS'] = str(len(rows))
        for i, (name, price, sale, default) in enumerate(rows):
            data.update({f'options-{i}-name': name, f'options-{i}-price': price, f'options-{i}-sale_price': sale,
                         f'options-{i}-cost_price': '900000', f'options-{i}-is_active': 'on', f'options-{i}-display_order': i})
            if default:
                data[f'options-{i}-is_default'] = 'on'
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 302, getattr(r, 'context', None) and [
            r.context['adminform'].form.errors, [f.errors for i in r.context['inline_admin_formsets'] for f in i.formset.forms]])
        from products.models import Product
        p = Product.objects.get(sku='ADD-8P')
        self.assertEqual(p.variants.count(), 2)
        self.assertEqual(p.effective_price, 1200000)
        sel = self.client.get(p.get_absolute_url()).context['sel']
        self.assertEqual({c['name']: c['price'] for c in sel['option_cards']}, {'Màn zin bóc máy': 1200000, 'Màn GX': 650000})


class AutoSkuTests(TestCase):
    def test_blank_sku_is_generated_in_django_admin(self):
        from core.tests.factories import make_category
        from products.models import Product

        admin = make_admin()
        self.client.login(username=admin.username, password=PASSWORD)
        url = reverse('admin:products_product_add')
        data = form_data(self.client.get(url))
        data.update({'name': 'Màn hình Iphone 8 plus', 'sku': '', 'category': make_category('Màn hình', 'SCR').pk,
                     'quality_grade': 'oem', 'status': 'active', 'low_stock_threshold': 5, 'price': '1200000', 'cost_price': '0'})
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 302, getattr(r, 'context', None) and r.context['adminform'].form.errors)
        p = Product.objects.get(name='Màn hình Iphone 8 plus')
        self.assertEqual(p.sku, 'IP-SCR-8PLUS-001')
        # Lần 2 cùng tên -> số tự tăng, không trùng
        r = self.client.post(url, {**data, 'name': 'Màn hình Iphone 8 plus', 'slug': ''})
        self.assertTrue(Product.objects.filter(sku='IP-SCR-8PLUS-002').exists())

    def test_variant_sku_generated(self):
        p = make_product(name='Màn hình Iphone 8 plus', sku='', price=1000, stock=0)
        o = ProductOption.objects.create(product=p, name='Màn zin bóc máy', price=1200000)
        ProductColor.objects.create(product=p, name='Trắng')
        p.ensure_variants()
        self.assertEqual(p.variants.get().sku, f'{p.sku}-ZBM-TRANG')
        self.assertTrue(p.sku.startswith('IP-'))
        self.assertTrue(o.pk)


class SalePriceEqualTests(TestCase):
    def test_sale_equal_price_is_valid_zero_percent(self):
        from django.core.exceptions import ValidationError

        p = make_product(name='Màn GX 8P', sku='EQ-1', price=650000, sale_price=650000)  # DB cho phép bằng nhau
        self.assertEqual((p.is_on_sale, p.discount_percent, p.effective_price), (False, 0, 650000))
        p.full_clean()  # không lỗi
        o = ProductOption(product=p, name='Màn GX', price=650000, sale_price=650000, cost_price=600000)
        o.full_clean()
        o.save()
        self.assertEqual((o.is_on_sale, o.discount_percent, o.effective_price), (False, 0, 650000))
        o.sale_price = 700000
        with self.assertRaisesMessage(ValidationError, 'không được lớn hơn giá bán'):
            o.full_clean()

    def test_admin_page_loads_discount_script(self):
        admin = make_admin()
        self.client.login(username=admin.username, password=PASSWORD)
        self.assertContains(self.client.get(reverse('admin:products_product_add')), 'js/admin/discount-preview.js')
