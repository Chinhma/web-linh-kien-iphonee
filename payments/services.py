"""Nghiệp vụ thanh toán: tạo Payment, áp dụng kết quả từ cổng (idempotent, kiểm tra chữ ký và số tiền)."""

import logging
import secrets

from django.db import transaction
from django.utils import timezone

from orders.models import Order, OrderStatusHistory

from .gateways import GatewayResult
from .models import Payment

logger = logging.getLogger('iparts')


def new_transaction_ref(order: Order) -> str:
    return f'{order.code}{secrets.token_hex(3).upper()}'


def create_payment_record(order: Order) -> Payment:
    return Payment.objects.create(order=order, method=order.payment_method, amount=order.total,
                                  transaction_ref=new_transaction_ref(order))


def apply_gateway_result(result: GatewayResult, source: str = 'return') -> str:
    """Áp dụng kết quả ĐÃ XÁC MINH CHỮ KÝ vào Payment + Order.

    Trả về: 'ok' | 'not_found' | 'already' | 'amount' | 'invalid'.
    - Idempotent: Payment đã success thì không xử lý lại.
    - Số tiền phải khớp Payment.amount.
    - Khóa Payment bằng select_for_update trong transaction.
    """
    if not result.valid_signature:
        logger.warning('Callback thanh toán sai chữ ký (%s)', source)
        return 'invalid'
    with transaction.atomic():
        payment = Payment.objects.select_for_update().select_related('order').filter(
            transaction_ref=result.transaction_ref).first()
        if payment is None:
            return 'not_found'
        if payment.status != Payment.Status.PENDING:  # Callback trùng -> không xử lý lại
            return 'already'
        if result.amount != payment.amount:
            logger.warning('Sai số tiền thanh toán cho %s', payment.transaction_ref)
            return 'amount'
        order = Order.objects.select_for_update().get(pk=payment.order_id)
        now = timezone.now()
        payment.gateway_transaction_id = result.gateway_transaction_id
        payment.gateway_response_code = result.response_code
        payment.raw_response = {k: v for k, v in result.raw.items() if 'card' not in k.lower()}
        if result.success:
            payment.status = Payment.Status.SUCCESS
            payment.paid_at = now
            if order.status != Order.Status.CANCELLED:
                order.payment_status = Order.PaymentStatus.PAID
                order.paid_at = now
            else:  # Đơn đã hủy (quá hạn) nhưng tiền vẫn về -> chờ hoàn tiền
                order.payment_status = Order.PaymentStatus.REFUND_PENDING
            order.save(update_fields=['payment_status', 'paid_at', 'updated_at'])
            OrderStatusHistory.objects.create(order=order, from_status=order.status, to_status=order.status,
                                              note=f'Thanh toán {order.get_payment_method_display()} thành công')
        else:
            payment.status = Payment.Status.CANCELLED if result.response_code == '24' else Payment.Status.FAILED
            if order.payment_status == Order.PaymentStatus.PENDING:
                order.payment_status = Order.PaymentStatus.FAILED
                order.save(update_fields=['payment_status', 'updated_at'])
        payment.save()
    return 'ok'
