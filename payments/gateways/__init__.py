from .base import CODGateway, GatewayError, GatewayResult, PaymentGateway
from .momo import MoMoGateway
from .vnpay import VNPayGateway

GATEWAYS = {'cod': CODGateway(), 'vnpay': VNPayGateway(), 'momo': MoMoGateway()}


def get_gateway(method: str) -> PaymentGateway:
    return GATEWAYS[method]


__all__ = ['GATEWAYS', 'get_gateway', 'GatewayError', 'GatewayResult', 'PaymentGateway']
