"""Cổng MoMo Sandbox – API v2 (captureWallet), chữ ký HMAC-SHA256."""

import hashlib
import hmac
import logging
import uuid

from django.conf import settings

from .base import GatewayError, GatewayResult, PaymentGateway

logger = logging.getLogger('iparts')

RESPONSE_FIELDS = ['accessKey', 'amount', 'extraData', 'message', 'orderId', 'orderInfo', 'orderType',
                   'partnerCode', 'payType', 'requestId', 'responseTime', 'resultCode', 'transId']


def hmac_sha256(raw: str, secret: str) -> str:
    return hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()


def create_signature(data: dict, secret: str) -> str:
    keys = ['accessKey', 'amount', 'extraData', 'ipnUrl', 'orderId', 'orderInfo',
            'partnerCode', 'redirectUrl', 'requestId', 'requestType']
    return hmac_sha256('&'.join(f'{k}={data.get(k, "")}' for k in keys), secret)


def response_signature(params: dict, access_key: str, secret: str) -> str:
    data = dict(params)
    data['accessKey'] = access_key
    return hmac_sha256('&'.join(f'{k}={data.get(k, "")}' for k in RESPONSE_FIELDS), secret)


def verify_signature(params: dict, access_key: str, secret: str) -> bool:
    received = str(params.get('signature', ''))
    return bool(received) and hmac.compare_digest(response_signature(params, access_key, secret), received)


class MoMoGateway(PaymentGateway):
    code = 'momo'
    name = 'Ví MoMo'

    def is_configured(self) -> bool:
        return bool(settings.MOMO_PARTNER_CODE and settings.MOMO_ACCESS_KEY and settings.MOMO_SECRET_KEY)

    def create_payment(self, payment, request) -> str:
        import requests

        data = {
            'partnerCode': settings.MOMO_PARTNER_CODE,
            'accessKey': settings.MOMO_ACCESS_KEY,
            'requestId': uuid.uuid4().hex,
            'amount': str(payment.amount),
            'orderId': payment.transaction_ref,
            'orderInfo': f'Thanh toan don hang {payment.order.code}',
            'redirectUrl': settings.MOMO_REDIRECT_URL,
            'ipnUrl': settings.MOMO_IPN_URL,
            'extraData': '',
            'requestType': 'captureWallet',
        }
        data['signature'] = create_signature(data, settings.MOMO_SECRET_KEY)
        body = {k: v for k, v in data.items() if k != 'accessKey'}
        body.update({'lang': 'vi'})
        try:
            response = requests.post(settings.MOMO_ENDPOINT, json=body, timeout=15)
            result = response.json()
        except Exception as exc:
            logger.warning('Không kết nối được MoMo: %s', type(exc).__name__)
            raise GatewayError('Không thể kết nối MoMo, vui lòng thử lại hoặc chọn phương thức khác.')
        if result.get('resultCode') != 0 or not result.get('payUrl'):
            raise GatewayError(result.get('message') or 'MoMo từ chối yêu cầu thanh toán.')
        return result['payUrl']

    def verify_return(self, params: dict) -> GatewayResult:
        params = {k: v for k, v in params.items()}
        if not verify_signature(params, settings.MOMO_ACCESS_KEY, settings.MOMO_SECRET_KEY):
            return GatewayResult(valid_signature=False, message='Sai chữ ký.', raw=params)
        code = str(params.get('resultCode', ''))
        try:
            amount = int(params.get('amount', 0))
        except (TypeError, ValueError):
            amount = -1
        return GatewayResult(
            valid_signature=True, success=code == '0', transaction_ref=str(params.get('orderId', '')),
            amount=amount, gateway_transaction_id=str(params.get('transId', '')), response_code=code,
            message=params.get('message') or ('Giao dịch thành công.' if code == '0' else 'Giao dịch không thành công.'),
            raw=params,
        )

    def handle_ipn(self, params: dict):
        from payments.services import apply_gateway_result

        result = self.verify_return(params)
        if result.valid_signature:
            apply_gateway_result(result, source='ipn')
        return result, None  # MoMo yêu cầu HTTP 204
