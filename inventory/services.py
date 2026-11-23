"""Dịch vụ tồn kho – CÁCH DUY NHẤT để thay đổi Product.stock_quantity."""

from django.db import transaction
from django.db.models import F

from products.models import Product

from .models import InventoryTransaction


class StockError(Exception):
    """Lỗi tồn kho (không đủ hàng / tồn âm)."""


@transaction.atomic
def adjust_stock(product: Product, change: int, type: str, user=None, note: str = '',
                 order=None, unit_cost: int | None = None) -> InventoryTransaction:
    """Cộng/trừ tồn kho và ghi InventoryTransaction (tồn trước/sau).

    - Chạy trong transaction, khóa dòng sản phẩm (select_for_update).
    - Khi trừ kho dùng UPDATE có điều kiện `stock_quantity >= n` để không bao giờ bán vượt tồn kho,
      kể cả khi hai yêu cầu xảy ra đồng thời.
    """
    if change == 0:
        raise StockError('Số lượng thay đổi phải khác 0.')
    locked = Product.objects.select_for_update().get(pk=product.pk)
    before = locked.stock_quantity
    if change < 0:
        updated = Product.objects.filter(pk=product.pk, stock_quantity__gte=-change).update(
            stock_quantity=F('stock_quantity') + change)
        if not updated:
            raise StockError(f'"{locked.name}" chỉ còn {before} sản phẩm trong kho.')
    else:
        Product.objects.filter(pk=product.pk).update(stock_quantity=F('stock_quantity') + change)
    locked.refresh_from_db(fields=['stock_quantity'])
    product.stock_quantity = locked.stock_quantity
    return InventoryTransaction.objects.create(
        product=locked, type=type, quantity_change=change,
        stock_before=locked.stock_quantity - change, stock_after=locked.stock_quantity,
        unit_cost=unit_cost, order=order, note=note[:255], created_by=user,
    )


VARIANT_STOCK_MESSAGE = ('Sản phẩm có biến thể (loại màn × màu) – vui lòng nhập tồn kho cho từng biến thể '
                         'trong trang sửa sản phẩm (tồn kho sản phẩm = tổng các biến thể).')


def _ensure_no_variants(product: Product) -> None:
    if product.variants.filter(is_active=True).exists():
        raise StockError(VARIANT_STOCK_MESSAGE)


def import_stock(product: Product, quantity: int, unit_cost: int | None, user, note: str = '',
                 update_cost_price: bool = True) -> InventoryTransaction:
    _ensure_no_variants(product)
    if quantity <= 0:
        raise StockError('Số lượng nhập phải lớn hơn 0.')
    with transaction.atomic():
        trx = adjust_stock(product, quantity, InventoryTransaction.Type.IMPORT, user, note, unit_cost=unit_cost)
        if update_cost_price and unit_cost:
            Product.objects.filter(pk=product.pk).update(cost_price=unit_cost)
    return trx


def stocktake(product: Product, actual_quantity: int, user, reason: str) -> InventoryTransaction | None:
    """Điều chỉnh kiểm kê: nhập số tồn thực tế, hệ thống tự tính chênh lệch."""
    _ensure_no_variants(product)
    if actual_quantity < 0:
        raise StockError('Số tồn thực tế không được âm.')
    if not reason.strip():
        raise StockError('Vui lòng nhập lý do điều chỉnh.')
    product.refresh_from_db(fields=['stock_quantity'])
    diff = actual_quantity - product.stock_quantity
    if diff == 0:
        return None
    return adjust_stock(product, diff, InventoryTransaction.Type.ADJUSTMENT, user, reason)
