"""Test biến thể LOẠI MÀN × MÀU: chọn sẵn mặc định, API đổi lựa chọn, tự chuyển màu hết hàng, giỏ/đơn, admin, BH 12 tháng."""

import json
import uuid

from django.test import TestCase
from django.urls import reverse

from cart.services import CartError, add_to_cart, build_cart_summary
from core.constants import WARRANTY_LABEL
from core.tests.factories import PASSWORD, make_admin, make_category, make_customer, make_product
from orders.services import change_order_status, create_order
from products.models import ProductColor, ProductOption, ProductVariant

from .test_orders import checkout_data


class VariantMatrixTests(TestCase):
    def setUp(self):
        self.product = make_product(name='Màn hình iPhone 8 Plus', sku='IP-SCR-8P-001', price=300000, stock=0,
                                    category=make_category('Màn hình', 'SCR'), option_label='Loại màn hình')
        opt = lambda name, **kw: ProductOption.objects.create(product=self.product, name=name, **kw)  # noqa: E731
        self.zin = opt('Màn zin bóc máy', is_default=True, display_order=0,
                       description='Màn Apple tháo máy, màu sắc – độ sáng – cảm ứng gần như nguyên bản.')
        self.ep = opt('Màn zin ép kính', display_order=1)
        self.gx = opt('Màn GX', display_order=2)
        self.white = ProductColor.objects.create(product=self.product, name='Trắng', hex_code='#FFFFFF', is_default=True)
        self.black = ProductColor.objects.create(product=self.product, name='Đen', hex_code='#111111', display_order=1)
        v = lambda o, c, price, **kw: ProductVariant.objects.create(product=self.product, option=o, color=c, price=price, **kw)  # noqa: E731
        self.zin_w = v(self.zin, self.white, 1200000, compare_price=1250000, stock=5, sku='8P-ZIN-W')
        self.zin_b = v(self.zin, self.black, 1200000, stock=4, sku='8P-ZIN-B')
        self.ep_w = v(self.ep, self.white, 900000, stock=0)  # hết hàng
        self.ep_b = v(self.ep, self.black, 880000, stock=3)
        self.gx_w = v(self.gx, self.white, 650000, stock=0)
        self.gx_b = v(self.gx, self.black, 640000, stock=0)  # GX hết sạch
        self.product.sync_from_variants()
        self.user = make_customer()

    def page(self, query=''):
        r = self.client.get(self.product.get_absolute_url() + query)
        return r.context['sel'], r.content.decode()

    def api(self, query=''):
        r = self.client.get(reverse('products:api_product_variant', args=[self.product.pk]) + query)
        self.assertEqual(r.status_code, 200)
        return r.json()['data']

    # ---- Vào trang lần đầu: Zin bóc máy + màu mặc định, đúng giá tổ hợp, không "Chỉ từ"
    def test_first_visit(self):
        sel, html = self.page()
        self.assertEqual((sel['option'], sel['color'], sel['variant']), (self.zin, self.white, self.zin_w))
        self.assertEqual((sel['price'], sel['original_price'], sel['discount_percent']), (1200000, 1250000, 4))
        self.assertEqual(sel['sku'], '8P-ZIN-W')
        self.assertNotIn('Chỉ từ', html)
        self.assertIn('Màn Apple tháo máy', html)  # mô tả loại màn đang chọn
        self.assertIn(f'data-variant-id="{self.zin_w.pk}"', html)
        self.assertIn('Màn zin bóc máy · Trắng · BH 12 tháng miễn phí', html)  # thanh mua ở đáy
        self.assertNotIn('Chọn gói dịch vụ bảo hành', html)

    # ---- Thẻ loại màn: giá theo màu đang chọn; thẻ màu: giá theo loại đang chọn; GX hết sạch -> mờ
    def test_card_prices_and_disabled(self):
        s, _ = self.page('?loai=man-zin-ep-kinh&mau=den')
        opts = {c['name']: c for c in s['option_cards']}
        self.assertEqual(opts['Màn zin bóc máy']['price'], 1200000)
        self.assertEqual(opts['Màn zin ép kính']['price'], 880000)
        self.assertTrue(opts['Màn GX']['disabled'])
        cols = {c['name']: c for c in s['color_cards']}
        self.assertEqual((cols['Trắng']['price'], cols['Đen']['price']), (900000, 880000))
        self.assertTrue(cols['Trắng']['disabled'])  # Ép kính – Trắng hết hàng

    # ---- Đổi loại màn qua API: giá + URL + HTML mới
    def test_api_change_option(self):
        d = self.api('?loai=man-zin-boc-may&mau=den')
        self.assertEqual((d['price'], d['variant_id'], d['query']), (1200000, self.zin_b.pk, '?loai=man-zin-boc-may&mau=den'))
        self.assertIn('data-variant-link', d['panel_html'])
        self.assertIn(f'data-variant-id="{self.zin_b.pk}"', d['bar_html'])
        self.assertIn(WARRANTY_LABEL, d['panel_html'])

    # ---- Chọn tổ hợp hết hàng: tự chuyển sang màu còn hàng gần nhất + thông báo
    def test_out_of_stock_color_switches(self):
        d = self.api('?loai=man-zin-ep-kinh&mau=trang')
        self.assertEqual(d['variant_id'], self.ep_b.pk)
        self.assertEqual(d['query'], '?loai=man-zin-ep-kinh&mau=den')
        self.assertEqual(d['notice'], 'Màu Trắng tạm hết, đã chuyển sang Đen.')

    def test_option_fully_out_of_stock(self):
        sel, html = self.page('?loai=man-gx&mau=den')
        self.assertEqual(sel['option'], self.gx)
        self.assertFalse(sel['can_buy'])
        self.assertEqual(sel['stock_label'], 'Hết hàng')
        self.assertNotIn('data-buy-now', html)

    def test_default_option_out_of_stock_on_first_visit(self):
        ProductVariant.objects.filter(option=self.zin).update(stock=0)
        sel, _ = self.page()
        self.assertEqual((sel['option'], sel['color']), (self.ep, self.black))

    # ---- F5 / mở link có tham số -> đúng tổ hợp
    def test_link_params(self):
        sel, _ = self.page('?loai=man-zin-boc-may&mau=den')
        self.assertEqual((sel['variant'], sel['price']), (self.zin_b, 1200000))

    def test_only_one_group(self):
        plain = make_product(name='Kính lưng', sku='IP-HSG-1', price=200000, stock=0)
        red = ProductColor.objects.create(product=plain, name='Đỏ', hex_code='#ff0000')
        ProductVariant.objects.create(product=plain, color=red, price=210000, stock=2)
        plain.sync_from_variants()
        r = self.client.get(plain.get_absolute_url())
        self.assertEqual(r.context['sel']['option_cards'], [])
        self.assertEqual(r.context['sel']['price'], 210000)
        self.assertIn('Màu sắc', r.content.decode())

    def test_product_without_variants(self):
        plain = make_product(name='Pin iPhone 8', sku='IP-BAT-8-001', price=400000)
        r = self.client.get(plain.get_absolute_url())
        html = r.content.decode()
        self.assertEqual(r.context['sel']['price'], 400000)
        self.assertNotIn('data-variant-picker', html)
        self.assertIn(WARRANTY_LABEL, html)

    # ---- Thẻ sản phẩm / danh sách = giá tổ hợp mặc định; tồn kho = tổng biến thể
    def test_listing_price_and_stock(self):
        self.product.refresh_from_db()
        self.assertEqual(self.product.effective_price, 1200000)
        self.assertEqual(self.product.stock_quantity, 5 + 4 + 3)

    # ---- Giỏ / đơn: đúng giá theo variant_id, khác tổ hợp = dòng riêng, snapshot BH 12 tháng
    def test_cart_and_order(self):
        with self.assertRaises(CartError):
            add_to_cart(self.user, self.product.pk, 1)  # thiếu variant
        with self.assertRaises(CartError):
            add_to_cart(self.user, self.product.pk, 1, variant_id=self.ep_w.pk)  # hết hàng
        add_to_cart(self.user, self.product.pk, 1, variant_id=self.zin_w.pk)
        add_to_cart(self.user, self.product.pk, 2, variant_id=self.ep_b.pk)
        add_to_cart(self.user, self.product.pk, 1, variant_id=self.ep_b.pk)
        summary = build_cart_summary(self.user)
        self.assertEqual(len(summary.lines), 2)
        self.assertEqual(summary.subtotal, 1200000 + 3 * 880000)
        labels = {l.item.variant_label for l in summary.lines}
        self.assertIn('Màn zin ép kính – Đen – BH 12 tháng', labels)

        order = create_order(self.user, checkout_data(), str(uuid.uuid4()))
        item = order.items.get(variant=self.ep_b)
        self.assertEqual((item.unit_price, item.option_name, item.color_name, item.warranty_months), (880000, 'Màn zin ép kính', 'Đen', 12))
        self.assertEqual(item.display_name, 'Màn hình iPhone 8 Plus – Màn zin ép kính – Đen – BH 12 tháng')
        self.ep_b.refresh_from_db()
        self.assertEqual(self.ep_b.stock, 0)
        change_order_status(order, 'cancelled', self.user, 'Đổi ý')
        self.ep_b.refresh_from_db()
        self.assertEqual(self.ep_b.stock, 3)

    def test_api_add_ignores_client_price(self):
        self.client.login(username=self.user.username, password=PASSWORD)
        r = self.client.post(reverse('cart:api_add'), json.dumps({'product_id': self.product.pk, 'variant_id': self.zin_b.pk,
                                                                  'price': 1}), content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(build_cart_summary(self.user).subtotal, 1200000)
        self.assertContains(self.client.get(reverse('cart:cart')), 'BH 12 tháng')
        other = make_product(name='Khác', sku='IP-X-1')
        r = self.client.post(reverse('cart:api_add'), json.dumps({'product_id': other.pk, 'variant_id': self.zin_b.pk}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 200)  # SP không có biến thể: bỏ qua variant lạ, giá theo SP
        r = self.client.post(reverse('cart:api_add'), json.dumps({'product_id': self.product.pk, 'variant_id': 999999}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 400)

    # ---- Admin /quan-tri/: lưu loại màn, màu, bảng biến thể
    def test_admin_form_saves_matrix(self):
        admin = make_admin()
        self.client.login(username=admin.username, password=PASSWORD)
        url = reverse('dashboard:product_edit', args=[self.product.pk])
        page = self.client.get(url)
        self.assertContains(page, 'data-variants-section')
        self.assertNotContains(page, 'name="warranty_months"')
        options = [{'id': self.zin.pk, 'key': str(self.zin.pk), 'name': 'Màn zin bóc máy', 'description': 'Zin', 'is_default': False, 'is_active': True},
                   {'id': None, 'key': 'onew', 'name': 'Màn Incell', 'description': '', 'is_default': True, 'is_active': True}]
        colors = [{'id': self.white.pk, 'key': str(self.white.pk), 'name': 'Trắng', 'hex_code': '#ffffff', 'is_default': True, 'is_active': True}]
        variants = [
            {'id': self.zin_w.pk, 'key': 'a', 'option_key': str(self.zin.pk), 'color_key': str(self.white.pk), 'price': '1150000',
             'compare_price': '', 'stock': '7', 'sku': 'zw', 'is_active': True},
            {'id': None, 'key': 'b', 'option_key': 'onew', 'color_key': str(self.white.pk), 'price': '450000',
             'compare_price': '500000', 'stock': '4', 'sku': '', 'is_active': True},
        ]
        data = {'name': self.product.name, 'sku': self.product.sku, 'category': self.product.category_id,
                'quality_grade': 'aftermarket', 'status': 'active', 'cost_price': 0, 'price': 999999, 'low_stock_threshold': 5,
                'option_label': 'Loại màn hình', 'specifications': '[]', 'highlights': '[]',
                'options_data': json.dumps(options), 'colors_data': json.dumps(colors), 'variants_data': json.dumps(variants)}
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(list(self.product.options.values_list('name', flat=True)), ['Màn zin bóc máy', 'Màn Incell'])
        self.assertEqual(list(self.product.colors.values_list('name', flat=True)), ['Trắng'])  # Đen bị xóa
        self.assertEqual(self.product.variants.count(), 2)
        incell = self.product.variants.get(option__name='Màn Incell')
        self.assertEqual((incell.price, incell.discount_percent), (450000, 10))
        self.product.refresh_from_db()
        self.assertEqual((self.product.effective_price, self.product.stock_quantity), (450000, 11))

    def test_admin_requires_variant_price(self):
        admin = make_admin()
        self.client.login(username=admin.username, password=PASSWORD)
        data = {'name': 'SP mới', 'sku': 'NEW-1', 'category': self.product.category_id, 'quality_grade': 'oem',
                'status': 'active', 'cost_price': 0, 'price': 1, 'low_stock_threshold': 5, 'specifications': '[]',
                'highlights': '[]', 'options_data': json.dumps([{'key': 'x', 'name': 'GX', 'is_active': True}]),
                'colors_data': '[]', 'variants_data': json.dumps([{'key': 'v', 'option_key': 'x', 'price': ''}])}
        r = self.client.post(reverse('dashboard:product_add'), data)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'vui lòng nhập giá cho ít nhất 1 tổ hợp')

    def test_django_admin_change_page(self):
        admin = make_admin()
        self.client.login(username=admin.username, password=PASSWORD)
        r = self.client.get(reverse('admin:products_product_change', args=[self.product.pk]))
        self.assertContains(r, 'Biến thể')


class AdminBulkDeleteTests(TestCase):
    def test_bulk_delete_products_with_stock_history(self):
        admin = make_admin()
        self.client.login(username=admin.username, password=PASSWORD)
        a = make_product(name='Màn A', sku='DEL-A', stock=5)  # có lịch sử kho
        b = make_product(name='Màn B', sku='DEL-B', stock=3)
        sold = make_product(name='Màn C', sku='DEL-C', stock=4)
        add_to_cart(make_customer(), sold.pk, 1)
        create_order(sold.cart_items.first().cart.user, checkout_data(), str(uuid.uuid4()))
        url = reverse('admin:products_product_changelist')
        data = {'action': 'delete_selected', '_selected_action': [a.pk, b.pk, sold.pk]}
        confirm = self.client.post(url, data)
        self.assertNotContains(confirm, 'Không thể xóa')
        self.client.post(url, {**data, 'post': 'yes'})
        from products.models import Product
        self.assertFalse(Product.objects.filter(pk__in=[a.pk, b.pk]).exists())
        sold.refresh_from_db()
        self.assertEqual(sold.status, Product.Status.DISCONTINUED)


class EnsureVariantsTests(TestCase):
    def test_missing_combos_are_generated_and_page_shows_choices(self):
        p = make_product(name='Màn hình iPhone 8 Plus', sku='AUTO-1', price=3000000, stock=200)
        for i, name in enumerate(['Màn GX', 'Màn zin bóc máy', 'Màn zin ép kính']):
            ProductOption.objects.create(product=p, name=name, display_order=i, is_default=(i == 1))
        ProductColor.objects.create(product=p, name='Trắng')
        self.assertEqual(p.ensure_variants(), 3)
        self.assertEqual(p.ensure_variants(), 0)  # chạy lại không tạo trùng
        self.assertEqual(sum(p.variants.values_list('stock', flat=True)), 200)  # tổng tồn không đổi
        p.sync_from_variants()
        sel = self.client.get(p.get_absolute_url()).context['sel']
        self.assertEqual(len(sel['option_cards']), 3)
        self.assertEqual(sel['option'].name, 'Màn zin bóc máy')
        ProductColor.objects.create(product=p, name='Đen')
        self.assertEqual(p.ensure_variants(), 3)  # thêm màu -> sinh thêm 3 tổ hợp, tồn kho 0
        self.assertEqual(sum(p.variants.values_list('stock', flat=True)), 200)


class OptionPriceTests(TestCase):
    def setUp(self):
        self.p = make_product(name='Màn hình iPhone 8 Plus', sku='OPT-P-1', price=3000000, stock=90)
        self.gx = ProductOption.objects.create(product=self.p, name='Màn GX', price=650000, display_order=0)
        self.zin = ProductOption.objects.create(product=self.p, name='Màn zin bóc máy', price=1250000, sale_price=1200000,
                                                is_default=True, display_order=1)
        self.white = ProductColor.objects.create(product=self.p, name='Trắng')
        self.black = ProductColor.objects.create(product=self.p, name='Đen')

    def test_each_option_price_applies_to_all_colors(self):
        self.p.ensure_variants()
        self.p.sync_from_variants()
        prices = {(v.option.name, v.color.name): (v.effective_price, v.original_price) for v in self.p.variants.select_related('option', 'color')}
        self.assertEqual(prices[('Màn GX', 'Đen')], (650000, None))
        self.assertEqual(prices[('Màn zin bóc máy', 'Trắng')], (1200000, 1250000))
        self.p.refresh_from_db()
        self.assertEqual(self.p.effective_price, 1200000)  # giá danh sách = loại mặc định
        # Đổi giá loại -> áp cho mọi màu
        self.gx.price = 700000
        self.gx.save()
        self.assertEqual(self.p.apply_option_prices(), 2)
        self.assertEqual(set(self.p.variants.filter(option=self.gx).values_list('price', flat=True)), {700000})
        sel = self.client.get(self.p.get_absolute_url() + '?loai=man-gx').context['sel']
        self.assertEqual(sel['price'], 700000)

    def test_admin_hides_product_price_and_shows_option_price(self):
        admin = make_admin()
        self.client.login(username=admin.username, password=PASSWORD)
        r = self.client.get(reverse('admin:products_product_change', args=[self.p.pk]))
        self.assertNotContains(r, 'name="price"')
        self.assertNotContains(r, 'name="sale_price"')
        self.assertContains(r, 'name="options-0-price"')
        for f in ('cost_price', 'sale_price', 'sale_start_0', 'sale_end_0'):
            self.assertContains(r, f'name="options-0-{f}"')
        plain = make_product(name='Pin', sku='OPT-P-2', price=400000)
        r = self.client.get(reverse('admin:products_product_change', args=[plain.pk]))
        self.assertContains(r, 'name="price"')  # SP không có loại màn vẫn nhập giá như cũ


class OptionSaleWindowTests(TestCase):
    def test_option_sale_window(self):
        from core.tests.factories import days

        p = make_product(name='Màn 8P', sku='WIN-1', price=1, stock=10)
        o = ProductOption.objects.create(product=p, name='Màn GX', price=700000, sale_price=650000, is_default=True,
                                         sale_start=days(-1), sale_end=days(2), cost_price=500000)
        p.ensure_variants()
        p.sync_from_variants()
        sel = self.client.get(p.get_absolute_url()).context['sel']
        self.assertEqual((sel['price'], sel['original_price'], sel['discount_percent']), (650000, 700000, 7))
        self.assertIsNotNone(sel['promo_end'])
        p.refresh_from_db()
        self.assertEqual((p.effective_price, p.cost_price), (650000, 500000))  # danh sách + giá nhập theo loại mặc định
        o.sale_end = days(-0.5)  # hết khuyến mãi -> giá bán
        o.save()
        sel = self.client.get(p.get_absolute_url()).context['sel']
        self.assertEqual((sel['price'], sel['original_price']), (700000, None))
