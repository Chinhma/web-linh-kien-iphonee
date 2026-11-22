"""Test giá, giỏ hàng, coupon, đặt hàng, máy trạng thái (Phần 19.1)."""

import threading
import uuid

from django.test import TestCase, TransactionTestCase

from cart.models import CartItem
from cart.services import CartError, add_to_cart
from core.tests.factories import days, make_admin, make_customer, make_product
from inventory.models import InventoryTransaction
from orders.models import Order
from orders.services import CheckoutData, OrderError, change_order_status, create_order
from products.models import Product
from promotions.models import Coupon, CouponUsage
from promotions.services import validate_coupon


def checkout_data(**kw):
    data = dict(recipient_name='Khách', recipient_phone='0889400470', recipient_email='k@example.com', province_code='01', province_name='Thành phố Hà Nội', ward_code='00166', ward_name='Phường Cầu Giấy', street_address='1 Xuân Thủy')
    data.update(kw)
    return CheckoutData(**data)


class PriceCartTests(TestCase):
    def test_effective_price_in_and_out_of_sale_window(self):
        p = make_product(price=1000000, sale_price=800000, sale_start=days(-1), sale_end=days(1))
        self.assertEqual(p.effective_price, 800000)
        self.assertEqual(p.discount_percent, 20)
        p.sale_end = days(-0.5)
        self.assertEqual(p.effective_price, 1000000)

    def test_add_over_stock_is_limited(self):
        user = make_customer()
        p = make_product(stock=3)
        item, message = add_to_cart(user, p.pk, 8)
        self.assertEqual(item.quantity, 3)
        self.assertIn('Chỉ còn 3', message)

    def test_discontinued_product_cannot_be_added(self):
        p = make_product(status=Product.Status.DISCONTINUED)
        with self.assertRaises(CartError):
            add_to_cart(make_customer(), p.pk, 1)


class CouponTests(TestCase):
    def setUp(self):
        self.user = make_customer()

    def coupon(self, **kw):
        data = dict(code='GIAM10', discount_type='percent', value=10, start_at=days(-1), end_at=days(10))
        data.update(kw)
        return Coupon.objects.create(**data)

    def test_all_conditions(self):
        self.assertEqual(validate_coupon('KHONGCO', self.user, 100000)[2], 'Mã giảm giá không tồn tại.')
        self.coupon(code='TAT', is_active=False)
        self.assertIn('ngừng áp dụng', validate_coupon('tat', self.user, 100000)[2])
        self.coupon(code='CHUA', start_at=days(1))
        self.assertIn('chưa bắt đầu', validate_coupon('CHUA', self.user, 100000)[2])
        self.coupon(code='HET', end_at=days(-0.1), start_at=days(-5))
        self.assertIn('hết hạn', validate_coupon('HET', self.user, 100000)[2])
        c = self.coupon(code='LUOT', usage_limit=1)
        Coupon.objects.filter(pk=c.pk).update(used_count=1)
        self.assertIn('hết lượt', validate_coupon('LUOT', self.user, 100000)[2])
        self.coupon(code='TOITHIEU', min_order_value=500000)
        self.assertIn('tối thiểu', validate_coupon('TOITHIEU', self.user, 100000)[2])

    def test_per_user_limit(self):
        c = self.coupon()
        order = Order.objects.create(user=self.user, recipient_name='A', recipient_phone='0889400470', recipient_email='a@a.vn',
                                     province_code='01', province_name='Thành phố Hà Nội', ward_code='00166', ward_name='Phường Cầu Giấy', street_address='d', subtotal=1, total=1)
        CouponUsage.objects.create(coupon=c, user=self.user, order=order, discount_amount=1)
        self.assertEqual(validate_coupon('GIAM10', self.user, 100000)[2], 'Bạn đã sử dụng mã này.')

    def test_percent_capped_and_never_exceeds_subtotal(self):
        self.coupon(code='PHANTRAM', value=50, max_discount=100000)
        self.assertEqual(validate_coupon('PHANTRAM', self.user, 1000000)[1], 100000)
        self.coupon(code='CODINH', discount_type='fixed', value=500000)
        self.assertEqual(validate_coupon('CODINH', self.user, 200000)[1], 200000)


class CreateOrderTests(TestCase):
    def setUp(self):
        self.user = make_customer()
        self.product = make_product(price=600000, stock=5)

    def test_success_deducts_stock_and_logs(self):
        add_to_cart(self.user, self.product.pk, 2)
        order = create_order(self.user, checkout_data(), str(uuid.uuid4()))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 3)
        self.assertTrue(InventoryTransaction.objects.filter(order=order, type='export_order', quantity_change=-2).exists())
        self.assertEqual(order.subtotal, 1200000)
        self.assertFalse(CartItem.objects.filter(cart__user=self.user).exists())

    def test_client_price_ignored(self):
        add_to_cart(self.user, self.product.pk, 1)
        self.client.force_login(self.user)
        key = str(uuid.uuid4())
        self.client.post('/thanh-toan/', {'recipient_name': 'Khách', 'recipient_phone': '0889400470', 'recipient_email': 'k@e.com',
                                         'province_code': '01', 'ward_code': '00166', 'street_address': '1',
                                         'shipping_method': 'standard', 'payment_method': 'cod', 'agree': 'on',
                                         'idempotency_key': key, 'total': '1000', 'price': '1'})
        order = Order.objects.get(idempotency_key=key)
        self.assertEqual(order.subtotal, 600000)
        self.assertEqual(order.total, 600000 + order.shipping_fee)

    def test_insufficient_stock_rolls_back(self):
        add_to_cart(self.user, self.product.pk, 5)
        Product.objects.filter(pk=self.product.pk).update(stock_quantity=2)
        with self.assertRaises(OrderError):
            create_order(self.user, checkout_data(), str(uuid.uuid4()))
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(Product.objects.get(pk=self.product.pk).stock_quantity, 2)

    def test_same_idempotency_key_single_order(self):
        add_to_cart(self.user, self.product.pk, 1)
        key = str(uuid.uuid4())
        first = create_order(self.user, checkout_data(), key)
        second = create_order(self.user, checkout_data(), key)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Order.objects.count(), 1)


class LastItemRaceTests(TransactionTestCase):
    """Hai đơn tranh nhau sản phẩm cuối cùng: chỉ một đơn thành công."""

    def test_only_one_succeeds(self):
        product = make_product(stock=1)
        users = [make_customer('u1'), make_customer('u2')]
        for u in users:
            add_to_cart(u, product.pk, 1)
        results = []

        def buy(user):
            import time

            from django.db import OperationalError, connection

            key = str(uuid.uuid4())
            try:
                for _ in range(20):  # SQLite có thể báo "database is locked" khi 2 luồng ghi cùng lúc -> thử lại
                    try:
                        create_order(user, checkout_data(), key)
                        results.append('ok')
                        return
                    except OperationalError:
                        time.sleep(0.05)
                    except OrderError:
                        results.append('fail')  # Hết hàng: lỗi nghiệp vụ đúng mong đợi
                        return
                results.append('fail')
            finally:
                connection.close()

        threads = [threading.Thread(target=buy, args=(u,)) for u in users]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(results.count('ok'), 1)
        self.assertEqual(Product.objects.get(pk=product.pk).stock_quantity, 0)


class StatusMachineTests(TestCase):
    def setUp(self):
        self.user = make_customer()
        self.admin = make_admin()
        self.product = make_product(stock=10)

    def order(self, **kw):
        add_to_cart(self.user, self.product.pk, 2)
        return create_order(self.user, checkout_data(**kw), str(uuid.uuid4()))

    def test_valid_flow_and_cod_auto_paid(self):
        o = self.order()
        for st in ['confirmed', 'preparing', 'shipping', 'delivered']:
            o = change_order_status(o, st, self.admin)
        self.assertEqual(o.payment_status, 'paid')
        self.assertIsNotNone(o.delivered_at)
        self.assertEqual(Product.objects.get(pk=self.product.pk).sold_count, 2)

    def test_invalid_transition_rejected(self):
        o = self.order()
        with self.assertRaises(OrderError):
            change_order_status(o, 'delivered', self.admin)
        with self.assertRaises(OrderError):
            change_order_status(o, 'confirmed', self.user)  # Customer không được xác nhận

    def test_cancel_restocks_and_releases_coupon(self):
        c = Coupon.objects.create(code='GIAM5', discount_type='fixed', value=5000, start_at=days(-1), end_at=days(1))
        o = self.order(coupon_code='GIAM5')
        self.assertEqual(Coupon.objects.get(pk=c.pk).used_count, 1)
        change_order_status(o, 'cancelled', self.user, 'Đổi ý')
        self.assertEqual(Product.objects.get(pk=self.product.pk).stock_quantity, 10)
        self.assertEqual(Coupon.objects.get(pk=c.pk).used_count, 0)

    def test_customer_cannot_cancel_shipping(self):
        o = self.order()
        for st in ['confirmed', 'preparing', 'shipping']:
            o = change_order_status(o, st, self.admin)
        with self.assertRaises(OrderError):
            change_order_status(o, 'cancelled', self.user, 'x')

    def test_admin_cancel_shipping_requires_reason(self):
        o = self.order()
        for st in ['confirmed', 'preparing', 'shipping']:
            o = change_order_status(o, st, self.admin)
        with self.assertRaises(OrderError):
            change_order_status(o, 'cancelled', self.admin, '')
