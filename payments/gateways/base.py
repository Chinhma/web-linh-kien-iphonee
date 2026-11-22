from dataclasses import dataclass, field


@dataclass
class GatewayResult:
    """Kết quả đã chuẩn hóa từ cổng thanh toán (sau khi xác minh chữ ký)."""

    valid_signature: bool
    success: bool = False
    transaction_ref: str = ''
    amount: int = 0
    gateway_transaction_id: str = ''
    response_code: str = ''
    message: str = ''
    raw: dict = field(default_factory=dict)


class GatewayError(Exception):
    pass


class PaymentGateway:
    code = ''
    name = ''

    def is_configured(self) -> bool:
        raise NotImplementedError

    def create_payment(self, payment, request) -> str:
        """Tạo yêu cầu thanh toán, trả về URL chuyển hướng khách tới cổng."""
        raise NotImplementedError

    def verify_return(self, params: dict) -> GatewayResult:
        raise NotImplementedError

    def handle_ipn(self, params: dict):
        """Xử lý IPN, trả về (GatewayResult, response cho cổng)."""
        raise NotImplementedError


class CODGateway(PaymentGateway):
    code = 'cod'
    name = 'Thanh toán khi nhận hàng (COD)'

    def is_configured(self) -> bool:
        return True
