"""Cổng VNPay Sandbox – API phiên bản 2.1.0, chữ ký HMAC-SHA512."""

import hashlib
import hmac
import urllib.parse
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from core.utils import client_ip, strip_accents

from .base import GatewayResult, PaymentGateway

VNPAY_MESSAGES = {
    '00': 'Giao dịch thành công.',
    '07': 'Giao dịch bị nghi ngờ gian lận.',
    '09': 'Thẻ/Tài khoản chưa đăng ký Internet Banking.',
    '10': 'Xác thực thông tin thẻ/tài khoản không đúng quá 3 lần.',
    '11': 'Đã hết hạn chờ thanh toán.',
    '12': 'Thẻ/Tài khoản bị khóa.',
    '13': 'Nhập sai mật khẩu xác thực giao dịch (OTP).',
    '24': 'Khách hàng hủy giao dịch.',
    '51': 'Tài khoản không đủ số dư.',
    '65': 'Tài khoản vượt quá hạn mức giao dịch trong ngày.',
    '75': 'Ngân hàng thanh toán đang bảo trì.',
    '79': 'Nhập sai mật khẩu thanh toán quá số lần quy định.',
    '99': 'Lỗi không xác định.',
}


def build_query(params: dict) -> str:
    """Sắp xếp tham số theo tên và URL-encode (quote_plus) đúng chuẩn VNPay."""
    return '&'.join(f'{k}={urllib.parse.quote_plus(str(v))}' for k, v in sorted(params.items()) if v not in (None, ''))


def sign(params: dict, secret: str) -> str:
    return hmac.new(secret.encode(), build_query(params).encode(), hashlib.sha512).hexdigest()


def verify_signature(params: dict, secret: str) -> bool:
    data = {k: v for k, v in params.items() if k.startswith('vnp_') and k not in ('vnp_SecureHash', 'vnp_SecureHashType')}
    received = params.get('vnp_SecureHash', '')
    return bool(received) and hmac.compare_digest(sign(data, secret).lower(), received.lower())


class VNPayGateway(PaymentGateway):
    code = 'vnpay'
    name = 'VNPay'

    def is_configured(self) -> bool:
        return bool(settings.VNPAY_TMN_CODE and settings.VNPAY_HASH_SECRET)

    def create_payment(self, payment, request) -> str:
        now = timezone.localtime()
        expire = timezone.localtime(payment.order.payment_expires_at) if payment.order.payment_expires_at else now + timedelta(minutes=15)
        params = {
            'vnp_Version': '2.1.0',
            'vnp_Command': 'pay',
            'vnp_TmnCode': settings.VNPAY_TMN_CODE,
            'vnp_Amount': payment.amount * 100,
            'vnp_CurrCode': 'VND',
            'vnp_TxnRef': payment.transaction_ref,
            'vnp_OrderInfo': strip_accents(f'Thanh toan don hang {payment.order.code}'),
            'vnp_OrderType': 'other',
            'vnp_Locale': 'vn',
            'vnp_ReturnUrl': settings.VNPAY_RETURN_URL,
            'vnp_IpAddr': client_ip(request),
            'vnp_CreateDate': now.strftime('%Y%m%d%H%M%S'),
            'vnp_ExpireDate': expire.strftime('%Y%m%d%H%M%S'),
        }
        query = build_query(params)
        secure_hash = sign(params, settings.VNPAY_HASH_SECRET)
        return f'{settings.VNPAY_PAYMENT_URL}?{query}&vnp_SecureHash={secure_hash}'

    def verify_return(self, params: dict) -> GatewayResult:
        params = {k: v for k, v in params.items()}
        if not verify_signature(params, settings.VNPAY_HASH_SECRET):
            return GatewayResult(valid_signature=False, message='Sai chữ ký.', raw=params)
        code = params.get('vnp_ResponseCode', '')
        success = code == '00' and params.get('vnp_TransactionStatus') == '00'
        try:
            amount = int(params.get('vnp_Amount', '0')) // 100
        except ValueError:
            amount = -1
        return GatewayResult(
            valid_signature=True, success=success, transaction_ref=params.get('vnp_TxnRef', ''), amount=amount,
            gateway_transaction_id=params.get('vnp_TransactionNo', ''), response_code=code,
            message=VNPAY_MESSAGES.get(code, 'Giao dịch không thành công.'), raw=params,
        )

    def handle_ipn(self, params: dict):
        from payments.services import apply_gateway_result

        result = self.verify_return(params)
        if not result.valid_signature:
            return result, {'RspCode': '97', 'Message': 'Invalid Checksum'}
        outcome = apply_gateway_result(result, source='ipn')
        mapping = {
            'ok': ('00', 'Confirm Success'), 'not_found': ('01', 'Order not found'),
            'already': ('02', 'Order already confirmed'), 'amount': ('04', 'Invalid amount'),
        }
        code, message = mapping.get(outcome, ('99', 'Unknown error'))
        return result, {'RspCode': code, 'Message': message}
