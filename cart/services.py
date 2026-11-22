"""Nghiệp vụ giỏ hàng và yêu thích. Giá luôn tính lại từ DB, không tin dữ liệu từ trình duyệt."""

from dataclasses import dataclass, field

from django.db import transaction

from products.models import Product

from .models import Cart, CartItem, WishlistItem

MAX_QTY_PER_LINE = 10
COUPON_SESSION_KEY = 'cart_coupon'


class CartError(Exception):
    def __init__(self, message: str, code: str = 'CART_ERROR'):
        super().__init__(message)
        self.message = message
        self.code = code


def get_cart(user) -> Cart:
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def max_quantity_for(product: Product) -> int:
    return max(0, min(product.stock_quantity, MAX_QTY_PER_LINE))


@transaction.atomic
def add_to_cart(user, product_id: int, quantity: int = 1, select_only: bool = False) -> tuple[CartItem, str]:
    """Thêm vào giỏ (cộng dồn). Giới hạn 1 ≤ SL ≤ min(tồn kho, 10). Trả về (dòng giỏ, thông báo)."""
    product = Product.objects.select_related('category').filter(pk=product_id).first()
    if product is None or product.status != Product.Status.ACTIVE or not product.category.is_active:
        raise CartError('Sản phẩm không tồn tại hoặc đã ngừng kinh doanh.', 'PRODUCT_UNAVAILABLE')
    if product.stock_quantity <= 0:
        raise CartError('Sản phẩm đã hết hàng.', 'OUT_OF_STOCK')
    quantity = max(1, int(quantity or 1))
    cart = get_cart(user)
    item, created = CartItem.objects.select_for_update().get_or_create(
        cart=cart, product=product, defaults={'quantity': 0})
    desired = item.quantity + quantity
    limit = max_quantity_for(product)
    message = 'Đã thêm sản phẩm vào giỏ hàng.'
    if desired > limit:
        desired = limit
        message = (f'Chỉ còn {product.stock_quantity} sản phẩm trong kho.' if product.stock_quantity < MAX_QTY_PER_LINE
                   else f'Mỗi sản phẩm mua tối đa {MAX_QTY_PER_LINE} chiếc.')
    item.quantity = desired
    item.is_selected = True
    item.save()
    if select_only:  # "Mua ngay": chỉ chọn sản phẩm này để thanh toán
        CartItem.objects.filter(cart=cart).exclude(pk=item.pk).update(is_selected=False)
    return item, message


def _owned_item(user, item_id) -> CartItem:
    item = CartItem.objects.select_related('product', 'product__category').filter(pk=item_id, cart__user=user).first()
    if item is None:
        raise CartError('Không tìm thấy sản phẩm trong giỏ.', 'NOT_FOUND')
    return item


def update_quantity(user, item_id: int, quantity: int) -> tuple[CartItem, str]:
    item = _owned_item(user, item_id)
    limit = max_quantity_for(item.product)
    if limit == 0:
        raise CartError('Sản phẩm đã hết hàng.', 'OUT_OF_STOCK')
    quantity = max(1, int(quantity or 1))
    message = 'Đã cập nhật số lượng.'
    if quantity > limit:
        quantity = limit
        message = f'Chỉ còn {item.product.stock_quantity} sản phẩm trong kho.' if item.product.stock_quantity < MAX_QTY_PER_LINE \
            else f'Mỗi sản phẩm mua tối đa {MAX_QTY_PER_LINE} chiếc.'
    item.quantity = quantity
    item.save(update_fields=['quantity'])
    return item, message


def remove_item(user, item_id: int) -> None:
    _owned_item(user, item_id).delete()


def set_selected(user, item_ids: list[int], selected: bool) -> int:
    return CartItem.objects.filter(cart__user=user, pk__in=item_ids).update(is_selected=bool(selected))


@dataclass
class CartLine:
    item: CartItem
    unit_price: int
    line_total: int
    valid: bool
    warning: str = ''

    @property
    def max_qty(self) -> int:
        return max(1, max_quantity_for(self.item.product))


@dataclass
class CartSummary:
    lines: list = field(default_factory=list)
    subtotal: int = 0
    selected_count: int = 0
    discount: int = 0
    coupon_code: str = ''
    coupon_message: str = ''
    total: int = 0
    messages: list = field(default_factory=list)

    @property
    def has_valid_selection(self) -> bool:
        return self.selected_count > 0


def build_cart_summary(user, session=None, fix_quantities: bool = True) -> CartSummary:
    """Kiểm tra lại từng dòng giỏ (ngừng bán/hết hàng/vượt tồn), tính tạm tính & giảm giá theo giá hiện tại."""
    from promotions.services import validate_coupon

    cart = get_cart(user)
    items = (cart.items.select_related('product', 'product__category')
             .prefetch_related('product__images', 'product__compatibilities__iphone_model'))
    summary = CartSummary()
    for item in items:
        product = item.product
        valid, warning = True, ''
        if product.status != Product.Status.ACTIVE or not product.category.is_active:
            valid, warning = False, 'Sản phẩm đã ngừng kinh doanh.'
        elif product.stock_quantity <= 0:
            valid, warning = False, 'Sản phẩm đã hết hàng.'
        elif item.quantity > max_quantity_for(product):
            if fix_quantities:
                item.quantity = max_quantity_for(product)
                item.save(update_fields=['quantity'])
                warning = f'Chỉ còn {product.stock_quantity} sản phẩm trong kho, số lượng đã được điều chỉnh.'
                summary.messages.append(f'{product.name}: {warning}')
        if not valid and item.is_selected:
            item.is_selected = False
            item.save(update_fields=['is_selected'])
        unit_price = product.effective_price
        line = CartLine(item=item, unit_price=unit_price, line_total=unit_price * item.quantity, valid=valid, warning=warning)
        summary.lines.append(line)
        if valid and item.is_selected:
            summary.subtotal += line.line_total
            summary.selected_count += 1
    if session is not None and session.get(COUPON_SESSION_KEY):
        ok, discount, message, _ = validate_coupon(session[COUPON_SESSION_KEY], user, summary.subtotal)
        summary.coupon_code = session[COUPON_SESSION_KEY]
        summary.coupon_message = message
        summary.discount = discount if ok else 0
        if not ok:
            summary.coupon_code = ''
            session.pop(COUPON_SESSION_KEY, None)
            if summary.subtotal:
                summary.messages.append(message)
    summary.total = max(0, summary.subtotal - summary.discount)
    return summary


def toggle_wishlist(user, product_id: int) -> bool:
    """Bật/tắt yêu thích. Trả về True nếu sau thao tác sản phẩm đang được yêu thích."""
    product = Product.objects.filter(pk=product_id, status__in=[Product.Status.ACTIVE, Product.Status.DISCONTINUED]).first()
    if product is None:
        raise CartError('Sản phẩm không tồn tại.', 'NOT_FOUND')
    deleted, _ = WishlistItem.objects.filter(user=user, product=product).delete()
    if deleted:
        return False
    WishlistItem.objects.create(user=user, product=product)
    return True
