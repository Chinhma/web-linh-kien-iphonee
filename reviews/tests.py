"""Test đánh giá: chỉ đã mua + đã giao, mỗi OrderItem một lần, duyệt cập nhật điểm TB."""

import uuid

from django.test import TestCase

from cart.services import add_to_cart
from core.tests.factories import make_admin, make_customer, make_product
from orders.services import CheckoutData, change_order_status, create_order
from products.models import Product
from reviews.models import Review
from reviews.services import ReviewError, create_review, set_review_status


class ReviewTests(TestCase):
    def setUp(self):
        self.user = make_customer()
        self.product = make_product()
        add_to_cart(self.user, self.product.pk, 1)
        data = CheckoutData(recipient_name='A', recipient_phone='0889400470', recipient_email='a@a.vn', province_code='01', province_name='Thành phố Hà Nội', ward_code='00166', ward_name='Phường Cầu Giấy', street_address='d')
        self.order = create_order(self.user, data, str(uuid.uuid4()))
        self.item = self.order.items.first()

    def deliver(self):
        admin = make_admin()
        for st in ['confirmed', 'preparing', 'shipping', 'delivered']:
            self.order = change_order_status(self.order, st, admin)

    def test_not_delivered_cannot_review(self):
        with self.assertRaises(ReviewError):
            create_review(self.user, self.item.pk, 5, 'Sản phẩm rất tốt luôn')

    def test_one_review_per_item_and_rating_update(self):
        self.deliver()
        review = create_review(self.user, self.item.pk, 4, 'Sản phẩm rất tốt luôn')
        with self.assertRaises(ReviewError):
            create_review(self.user, self.item.pk, 5, 'Đánh giá lần hai nè')
        self.assertEqual(Product.objects.get(pk=self.product.pk).rating_count, 0)  # chưa duyệt
        set_review_status([review.pk], Review.Status.APPROVED)
        p = Product.objects.get(pk=self.product.pk)
        self.assertEqual((p.rating_count, float(p.rating_avg)), (1, 4.0))
