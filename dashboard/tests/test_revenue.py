"""Test quy tắc doanh thu (13.5): đơn hủy, COD chưa giao, COD đã giao, online paid chưa giao, qua nửa đêm."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone

from core.tests.factories import make_customer
from dashboard.services.revenue import revenue_between, revenue_daily
from orders.models import Order

VN = ZoneInfo('Asia/Ho_Chi_Minh')


class RevenueTests(TestCase):
    def setUp(self):
        self.user = make_customer()
        self.today = timezone.localdate()

    def order(self, total, status, payment_status, delivered_at=None, method='cod'):
        return Order.objects.create(user=self.user, recipient_name='A', recipient_phone='0889400470', recipient_email='a@a.vn',
                                    province_code='01', province_name='Thành phố Hà Nội', ward_code='00166', ward_name='Phường Cầu Giấy', street_address='d', subtotal=total, total=total,
                                    status=status, payment_status=payment_status, payment_method=method, delivered_at=delivered_at)

    def test_rules(self):
        now = timezone.now()
        self.order(100, 'cancelled', 'refunded')                          # hủy -> không tính
        self.order(200, 'shipping', 'unpaid')                             # COD chưa giao -> không tính
        self.order(300, 'delivered', 'paid', now)                         # COD đã giao -> tính
        self.order(400, 'confirmed', 'paid', None, 'vnpay')               # online paid chưa giao -> không tính
        self.assertEqual(revenue_between(self.today, self.today), 300)

    def test_midnight_timezone(self):
        # 23:30 giờ VN hôm qua = 16:30 UTC hôm qua -> tính cho ngày hôm qua theo giờ VN
        yesterday = self.today - timedelta(days=1)
        late = datetime.combine(yesterday, time(23, 30), tzinfo=VN)
        early = datetime.combine(self.today, time(0, 30), tzinfo=VN)
        self.order(500, 'delivered', 'paid', late)
        self.order(700, 'delivered', 'paid', early)
        self.assertEqual(revenue_between(yesterday, yesterday), 500)
        self.assertEqual(revenue_between(self.today, self.today), 700)
        data = revenue_daily(yesterday, self.today)
        self.assertEqual(data['datasets'][0]['data'], [500, 700])
