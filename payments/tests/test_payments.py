"""Test ký/xác minh VNPay, MoMo và xử lý callback (Phần 19.1)."""

import uuid

from django.test import TestCase, override_settings

from cart.services import add_to_cart
from core.tests.factories import make_customer, make_product
from orders.services import CheckoutData, create_order
from payments.gateways import GatewayResult, momo, vnpay
from payments.services import apply_gateway_result, create_payment_record

SECRET = 'TESTSECRET'


class SignatureTests(TestCase):
    def test_vnpay_sign_verify(self):
        params = {'vnp_Amount': '100000', 'vnp_TxnRef': 'IPS1', 'vnp_ResponseCode': '00', 'vnp_OrderInfo': 'Thanh toan don'}
        params['vnp_SecureHash'] = vnpay.sign(params, SECRET)
        self.assertTrue(vnpay.verify_signature(params, SECRET))
        params['vnp_Amount'] = '1'
        self.assertFalse(vnpay.verify_signature(params, SECRET))

    def test_momo_sign_verify(self):
        params = {'amount': '100000', 'orderId': 'IPS1', 'resultCode': '0', 'partnerCode': 'P', 'requestId': 'r', 'transId': '9'}
        params['signature'] = momo.response_signature(params, 'ACCESS', SECRET)
        self.assertTrue(momo.verify_signature(params, 'ACCESS', SECRET))
        params['resultCode'] = '1'
        self.assertFalse(momo.verify_signature(params, 'ACCESS', SECRET))


@override_settings(VNPAY_TMN_CODE='TMN', VNPAY_HASH_SECRET=SECRET)
class CallbackTests(TestCase):
    def setUp(self):
        user = make_customer()
        add_to_cart(user, make_product(price=500000).pk, 1)
        data = CheckoutData(recipient_name='A', recipient_phone='0889400470', recipient_email='a@a.vn', province_code='01', province_name='Thành phố Hà Nội', ward_code='00166', ward_name='Phường Cầu Giấy', street_address='d', payment_method='vnpay')
        self.order = create_order(user, data, str(uuid.uuid4()))
        self.payment = create_payment_record(self.order)

    def params(self, amount=None, code='00'):
        p = {'vnp_TxnRef': self.payment.transaction_ref, 'vnp_Amount': str((amount or self.payment.amount) * 100),
             'vnp_ResponseCode': code, 'vnp_TransactionStatus': code, 'vnp_TransactionNo': '123'}
        p['vnp_SecureHash'] = vnpay.sign(p, SECRET)
        return p

    def test_invalid_signature_rejected(self):
        p = self.params()
        p['vnp_SecureHash'] = 'sai'
        r = self.client.get('/thanh-toan/vnpay/ipn/', p)
        self.assertEqual(r.json()['RspCode'], '97')
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, 'pending')

    def test_success_and_duplicate_callback(self):
        r1 = self.client.get('/thanh-toan/vnpay/ipn/', self.params())
        r2 = self.client.get('/thanh-toan/vnpay/ipn/', self.params())
        self.assertEqual(r1.json()['RspCode'], '00')
        self.assertEqual(r2.json()['RspCode'], '02')
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, 'paid')
        self.assertEqual(self.order.status, 'pending')  # Vẫn chờ Admin xác nhận

    def test_wrong_amount_rejected(self):
        r = self.client.get('/thanh-toan/vnpay/ipn/', self.params(amount=1000))
        self.assertEqual(r.json()['RspCode'], '04')

    def test_apply_result_requires_valid_signature(self):
        result = GatewayResult(valid_signature=False, transaction_ref=self.payment.transaction_ref, amount=self.payment.amount, success=True)
        self.assertEqual(apply_gateway_result(result), 'invalid')
