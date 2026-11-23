"""Nghiệp vụ đơn hàng: tạo đơn (checkout), máy trạng thái, hủy đơn quá hạn thanh toán.

Mọi thay đổi `Order.status` đều phải đi qua `change_order_status()` – không nơi nào khác gán trực tiếp.
"""

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from cart.models import CartItem
from cart.services import variant_is_sellable
from core.models import StoreSetting
from inventory.models import InventoryTransaction
from inventory.services import StockError, adjust_stock
from core.constants import WARRANTY_MONTHS
from products.models import Product, ProductVariant
from promotions import services as coupon_services

from .models import Order, OrderItem, OrderStatusHistory

S = Order.Status
PS = Order.PaymentStatus


class OrderError(Exception):
    def __init__(self, message: str, errors: dict | None = None, code: str = 'ORDER_ERROR'):
        super().__init__(message)
        self.message = message
        self.errors = errors or {}
        self.code = code


# ---------------------------------------------------------------- Phí vận chuyển
def calculate_shipping_fee(shipping_method: str, amount_after_discount: int) -> int:
    """Tiêu chuẩn: miễn phí nếu (tạm tính – giảm giá) ≥ ngưỡng. Nhanh: luôn tính phí."""
    store = StoreSetting.get_solo()
    if shipping_method == Order.ShippingMethod.EXPRESS:
        return store.shipping_fee_express
    if amount_after_discount >= store.free_shipping_threshold:
        return 0
    return store.shipping_fee_standard


@dataclass
class CheckoutData:
    recipient_name: str
    recipient_phone: str
    recipient_email: str
    province_code: str
    province_name: str
    ward_code: str
    ward_name: str
    street_address: str
    note: str = ''
    shipping_method: str = Order.ShippingMethod.STANDARD
    payment_method: str = Order.PaymentMethod.COD
    coupon_code: str = ''


# ---------------------------------------------------------------- Tạo đơn
def create_order(user, data: CheckoutData, idempotency_key: str) -> Order:
    """Tạo đơn hàng từ các sản phẩm đã chọn trong giỏ – toàn bộ trong một transaction.

    1. Cùng idempotency_key -> trả lại đơn đã tạo (chống bấm Đặt hàng 2 lần).
    2. Khóa sản phẩm, kiểm tra còn bán & đủ tồn kho (lỗi -> rollback toàn bộ).
    3. Trừ kho bằng UPDATE có điều kiện (chống bán vượt tồn kho), ghi InventoryTransaction.
    4. Tính lại giá, coupon, phí ship HOÀN TOÀN ở backend (bỏ qua giá trình duyệt gửi lên).
    5. Tạo Order + OrderItem (snapshot) + lịch sử trạng thái + CouponUsage, xóa dòng giỏ đã đặt.
    """
    if idempotency_key:
        existing = Order.objects.filter(idempotency_key=idempotency_key, user=user).first()
        if existing:
            return existing

    with transaction.atomic():
        cart_items = list(CartItem.objects.filter(cart__user=user, is_selected=True).select_related('product'))
        if not cart_items:
            raise OrderError('Vui lòng chọn sản phẩm để thanh toán.', code='EMPTY_SELECTION')
        product_ids = [ci.product_id for ci in cart_items]
        products = {p.pk: p for p in Product.objects.select_for_update().select_related('category').filter(pk__in=product_ids)}
        # Khóa biến thể để kiểm tra & trừ tồn kho theo biến thể (không tin dữ liệu trình duyệt)
        variants = {v.pk: v for v in ProductVariant.objects.select_for_update().select_related('option', 'color').filter(
            pk__in=[ci.variant_id for ci in cart_items if ci.variant_id])}
        for ci in cart_items:
            if ci.variant_id:
                ci.variant = variants[ci.variant_id]

        errors = {}
        for ci in cart_items:
            product = products.get(ci.product_id)
            if product is None or product.status != Product.Status.ACTIVE or not product.category.is_active:
                errors[str(ci.product_id)] = f'"{ci.product.name}" đã ngừng kinh doanh.'
            elif product.stock_quantity < ci.quantity:
                errors[str(ci.product_id)] = f'"{product.name}" chỉ còn {product.stock_quantity} sản phẩm.'
            elif ci.variant_id and not variant_is_sellable(ci.variant):
                errors[str(ci.product_id)] = f'"{product.name} – {ci.variant.label}" đã ngừng bán.'
            elif ci.variant_id and ci.variant.stock < ci.quantity:
                errors[str(ci.product_id)] = f'"{product.name} – {ci.variant.label}" chỉ còn {ci.variant.stock} sản phẩm.'
            elif not ci.variant_id and product.variants.filter(is_active=True).exists():
                errors[str(ci.product_id)] = f'Vui lòng chọn lại loại màn / màu cho "{product.name}".'
        if errors:
            raise OrderError('Một số sản phẩm không đủ điều kiện đặt hàng.', errors, code='OUT_OF_STOCK')

        def unit_price(ci) -> int:  # Giá luôn tính lại ở backend theo biến thể (BH 12 tháng miễn phí)
            ci.product = products[ci.product_id]
            return ci.unit_price

        subtotal = sum(unit_price(ci) * ci.quantity for ci in cart_items)
        discount, coupon = 0, None
        if data.coupon_code:
            ok, discount, message, coupon = coupon_services.validate_coupon(data.coupon_code, user, subtotal)
            if not ok:
                raise OrderError(message, {'coupon': message}, code='COUPON_INVALID')
        shipping_fee = calculate_shipping_fee(data.shipping_method, subtotal - discount)
        total = subtotal - discount + shipping_fee

        now = timezone.now()
        online = data.payment_method != Order.PaymentMethod.COD
        order = Order.objects.create(
            user=user,
            status=S.PENDING,
            payment_method=data.payment_method,
            payment_status=PS.PENDING if online else PS.UNPAID,
            payment_expires_at=now + timedelta(minutes=settings.PAYMENT_TIMEOUT_MINUTES) if online else None,
            shipping_method=data.shipping_method,
            recipient_name=data.recipient_name, recipient_phone=data.recipient_phone,
            recipient_email=data.recipient_email, province_code=data.province_code, province_name=data.province_name,
            ward_code=data.ward_code, ward_name=data.ward_name, street_address=data.street_address, note=data.note,
            subtotal=subtotal, discount_amount=discount, shipping_fee=shipping_fee, total=total,
            coupon=coupon, coupon_code=coupon.code if coupon else '',
            idempotency_key=idempotency_key or None,
        )
        for ci in cart_items:
            product = products[ci.product_id]
            try:
                adjust_stock(product, -ci.quantity, InventoryTransaction.Type.EXPORT_ORDER, user,
                             f'Xuất kho cho đơn {order.code}', order=order)
            except StockError as exc:
                raise OrderError(str(exc), {str(product.pk): str(exc)}, code='OUT_OF_STOCK')
            if ci.variant_id:  # Trừ tồn biến thể bằng UPDATE có điều kiện (chống bán vượt tồn)
                if not ProductVariant.objects.filter(pk=ci.variant_id, stock__gte=ci.quantity).update(
                        stock=F('stock') - ci.quantity):
                    msg = f'"{product.name} – {ci.variant.label}" không đủ hàng.'
                    raise OrderError(msg, {str(product.pk): msg}, code='OUT_OF_STOCK')
            v = ci.variant if ci.variant_id else None
            image = product.primary_image
            OrderItem.objects.create(  # Bản chụp lúc mua: loại màn, màu, số tháng BH, giá
                order=order, product=product, product_name=product.name, product_sku=(v.sku if v and v.sku else product.sku),
                variant=v, option=v.option if v else None,
                option_name=v.option.name if v and v.option_id else '', color_name=v.color.name if v and v.color_id else '',
                warranty_months=WARRANTY_MONTHS,
                product_image=(v.image.name if v and v.image else (image.image.name if image else '')),
                unit_price=unit_price(ci), quantity=ci.quantity,
                line_total=unit_price(ci) * ci.quantity,
            )
        OrderStatusHistory.objects.create(order=order, from_status='', to_status=S.PENDING, changed_by=user,
                                          note='Khách hàng đặt hàng')
        if coupon:
            coupon_services.record_usage(coupon, user, order, discount)
        CartItem.objects.filter(pk__in=[ci.pk for ci in cart_items]).delete()
    return order


# ---------------------------------------------------------------- Máy trạng thái
ADMIN, CUSTOMER, SYSTEM = 'admin', 'customer', 'system'

# (từ, sang) -> tập vai trò được phép
TRANSITIONS: dict[tuple[str, str], set[str]] = {
    (S.PENDING, S.CONFIRMED): {ADMIN},
    (S.PENDING, S.CANCELLED): {CUSTOMER, ADMIN, SYSTEM},
    (S.CONFIRMED, S.PREPARING): {ADMIN},
    (S.CONFIRMED, S.CANCELLED): {CUSTOMER, ADMIN},
    (S.PREPARING, S.SHIPPING): {ADMIN},
    (S.PREPARING, S.CANCELLED): {ADMIN},
    (S.SHIPPING, S.DELIVERED): {ADMIN},
    (S.SHIPPING, S.CANCELLED): {ADMIN},
}
REASON_REQUIRED = {(S.PREPARING, S.CANCELLED), (S.SHIPPING, S.CANCELLED)}

ACTION_LABELS = {
    S.CONFIRMED: 'Xác nhận đơn', S.PREPARING: 'Chuẩn bị hàng', S.SHIPPING: 'Bắt đầu giao hàng',
    S.DELIVERED: 'Đã giao thành công', S.CANCELLED: 'Hủy đơn',
}


def actor_role(actor) -> str:
    if actor is None:
        return SYSTEM
    return ADMIN if actor.is_staff else CUSTOMER


def can_transition(order: Order, new_status: str, actor) -> tuple[bool, str]:
    role = actor_role(actor)
    allowed = TRANSITIONS.get((order.status, new_status))
    if not allowed:
        return False, f'Không thể chuyển đơn từ "{order.get_status_display()}" sang "{S(new_status).label}".'
    if role not in allowed:
        return False, 'Bạn không có quyền thực hiện thao tác này với đơn hàng.'
    if role == CUSTOMER:
        if order.user_id != actor.pk:
            return False, 'Không tìm thấy đơn hàng.'
        if order.status == S.CONFIRMED and order.payment_method != Order.PaymentMethod.COD:
            return False, 'Đơn thanh toán online đã xác nhận, vui lòng liên hệ cửa hàng để hủy.'
    if new_status == S.CONFIRMED and order.is_online_payment and order.payment_status != PS.PAID:
        return False, 'Đơn thanh toán online phải được thanh toán trước khi xác nhận.'
    return True, ''


def available_transitions(order: Order, actor) -> list[tuple[str, str]]:
    """Các hành động hợp lệ cho actor (dùng để chỉ hiện đúng nút trong giao diện)."""
    result = []
    for (from_status, to_status) in TRANSITIONS:
        if from_status == order.status and can_transition(order, to_status, actor)[0]:
            label = 'Giao thất bại / Hủy' if (from_status, to_status) == (S.SHIPPING, S.CANCELLED) else ACTION_LABELS[to_status]
            result.append((to_status, label))
    return result


def change_order_status(order: Order, new_status: str, actor=None, note: str = '') -> Order:
    """Hàm DUY NHẤT đổi trạng thái đơn: kiểm tra bảng chuyển trạng thái, ghi mốc thời gian,
    lịch sử, xử lý kho / coupon / thanh toán – tất cả trong transaction.atomic()."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        ok, message = can_transition(order, new_status, actor)
        if not ok:
            raise OrderError(message, code='INVALID_TRANSITION')
        if (order.status, new_status) in REASON_REQUIRED and not note.strip():
            raise OrderError('Vui lòng nhập lý do hủy đơn.', {'note': 'Bắt buộc'}, code='REASON_REQUIRED')
        old_status = order.status
        now = timezone.now()
        order.status = new_status
        fields = ['status', 'updated_at']
        if new_status == S.CONFIRMED:
            order.confirmed_at = now
            fields.append('confirmed_at')
        elif new_status == S.SHIPPING:
            order.shipped_at = now
            fields.append('shipped_at')
        elif new_status == S.DELIVERED:
            order.delivered_at = now
            fields.append('delivered_at')
            if order.payment_method == Order.PaymentMethod.COD:
                order.payment_status = PS.PAID
                order.paid_at = now
                fields += ['payment_status', 'paid_at']
                order.payments.filter(status='pending').update(status='success', paid_at=now)
            for item in order.items.all():
                if item.product_id:
                    Product.objects.filter(pk=item.product_id).update(sold_count=F('sold_count') + item.quantity)
        elif new_status == S.CANCELLED:
            order.cancelled_at = now
            order.cancel_reason = note
            order.cancelled_by = actor_role(actor)
            fields += ['cancelled_at', 'cancel_reason', 'cancelled_by']
            _restock(order, actor)
            coupon_services.release_usage(order)
            if order.payment_status == PS.PAID:
                order.payment_status = PS.REFUND_PENDING
            elif order.payment_status in (PS.PENDING, PS.FAILED):
                order.payment_status = PS.FAILED if order.payment_status == PS.FAILED else PS.UNPAID
                order.payments.filter(status='pending').update(status='cancelled')
            fields.append('payment_status')
        order.save(update_fields=fields)
        OrderStatusHistory.objects.create(order=order, from_status=old_status, to_status=new_status,
                                          changed_by=actor, note=note[:500])
    return order


def _restock(order: Order, actor) -> None:
    for item in order.items.select_related('product'):
        if item.product_id:
            adjust_stock(item.product, item.quantity, InventoryTransaction.Type.RETURN_CANCEL, actor,
                         f'Hoàn kho do hủy đơn {order.code}', order=order)
            if item.variant_id:
                ProductVariant.objects.filter(pk=item.variant_id).update(stock=F('stock') + item.quantity)


def mark_refunded(order: Order, actor, note: str) -> Order:
    """Admin xác nhận đã hoàn tiền ngoài hệ thống (refund_pending -> refunded)."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.payment_status != PS.REFUND_PENDING:
            raise OrderError('Đơn không ở trạng thái chờ hoàn tiền.')
        order.payment_status = PS.REFUNDED
        order.save(update_fields=['payment_status', 'updated_at'])
        order.payments.filter(status='success').update(status='refunded')
        OrderStatusHistory.objects.create(order=order, from_status=order.status, to_status=order.status,
                                          changed_by=actor, note=f'Đã hoàn tiền. {note}'.strip())
    return order


def expire_unpaid_orders() -> int:
    """Hủy các đơn online quá hạn thanh toán (hoàn kho, hoàn lượt coupon). Trả về số đơn đã hủy."""
    expired = Order.objects.filter(
        status=S.PENDING, payment_status__in=[PS.PENDING, PS.FAILED],
        payment_expires_at__lt=timezone.now(),
    ).exclude(payment_method=Order.PaymentMethod.COD)
    count = 0
    for order in expired:
        try:
            change_order_status(order, S.CANCELLED, None, 'Quá hạn thanh toán')
            count += 1
        except OrderError:
            continue
    return count


def reorder(user, order: Order) -> int:
    """Mua lại: thêm các sản phẩm của đơn cũ vào giỏ (bỏ qua sản phẩm không còn bán)."""
    from cart.services import CartError, add_to_cart

    added = 0
    for item in order.items.all():
        if not item.product_id:
            continue
        # Đúng biến thể cũ; nếu đã bị xóa thì tìm biến thể cùng tên loại màn + màu
        variant_id = (item.product.variants.filter(pk=item.variant_id, is_active=True).values_list('pk', flat=True).first()
                      or item.product.variants.filter(option__name=item.option_name or None, color__name=item.color_name or None,
                                                      is_active=True).values_list('pk', flat=True).first())
        try:
            add_to_cart(user, item.product_id, item.quantity, variant_id=variant_id)
            added += 1
        except CartError:
            continue
    return added
