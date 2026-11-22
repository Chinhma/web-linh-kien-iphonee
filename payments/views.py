import json
import logging

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.permissions import customer_required, get_object_owned_or_404
from orders.models import Order

from .gateways import GatewayError, get_gateway
from .models import Payment
from .services import apply_gateway_result, create_payment_record

logger = logging.getLogger('iparts')


@customer_required
def start_payment(request, code):
    """Tạo Payment mới và chuyển khách tới cổng (dùng cho lần đầu và "Thanh toán lại")."""
    order = get_object_owned_or_404(Order, request.user, code=code)
    if not order.can_retry_payment:
        messages.error(request, 'Đơn hàng không còn trong thời hạn thanh toán online.')
        return redirect('orders:detail', code=code)
    gateway = get_gateway(order.payment_method)
    if not gateway.is_configured():
        messages.error(request, f'Cổng {gateway.name} đang bảo trì, vui lòng liên hệ cửa hàng.')
        return redirect('orders:detail', code=code)
    order.payments.filter(status=Payment.Status.PENDING).update(status=Payment.Status.CANCELLED)
    payment = create_payment_record(order)
    try:
        return redirect(gateway.create_payment(payment, request))
    except GatewayError as exc:
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=['status'])
        messages.error(request, str(exc))
        return redirect('orders:detail', code=code)


def _result_page(request, gateway_code: str, params: dict):
    gateway = get_gateway(gateway_code)
    result = gateway.verify_return(params)
    if not result.valid_signature:
        logger.warning('Return URL %s sai chữ ký', gateway_code)
        return render(request, 'checkout/result.html', {'success': False, 'order': None,
                                                        'reason': 'Dữ liệu trả về không hợp lệ (sai chữ ký).'}, status=400)
    # Môi trường localhost: cổng không gọi được IPN, nên Return URL (đã xác minh chữ ký) cũng cập nhật
    # trạng thái qua CÙNG một hàm idempotent.
    apply_gateway_result(result, source='return')
    payment = Payment.objects.select_related('order').filter(transaction_ref=result.transaction_ref).first()
    order = payment.order if payment else None
    if order and request.user.is_authenticated and order.user_id != request.user.pk:
        order = None
    if order:
        order.refresh_from_db()
    return render(request, 'checkout/result.html', {
        'order': order, 'success': result.success and order is not None and order.payment_status == 'paid',
        'reason': result.message, 'online': True,
    })


@require_GET
def vnpay_return(request):
    return _result_page(request, 'vnpay', request.GET.dict())


@csrf_exempt  # IPN do VNPay gọi, đã xác minh chữ ký HMAC-SHA512
@require_GET
def vnpay_ipn(request):
    _, response = get_gateway('vnpay').handle_ipn(request.GET.dict())
    return JsonResponse(response)


@require_GET
def momo_return(request):
    return _result_page(request, 'momo', request.GET.dict())


@csrf_exempt  # IPN do MoMo gọi, đã xác minh chữ ký HMAC-SHA256
@require_POST
def momo_ipn(request):
    try:
        params = json.loads(request.body or '{}')
    except ValueError:
        return HttpResponse(status=400)
    get_gateway('momo').handle_ipn(params)
    return HttpResponse(status=204)
