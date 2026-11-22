"""Nghiệp vụ đánh giá: chỉ khách đã nhận hàng mới được đánh giá, duyệt mới hiển thị."""

from django.db import transaction
from django.db.models import Avg, Count

from orders.models import Order, OrderItem
from products.models import Product

from .models import Review


class ReviewError(Exception):
    pass


def reviewable_items(user):
    """Các OrderItem thuộc đơn đã giao của user mà chưa được đánh giá."""
    return (OrderItem.objects.filter(order__user=user, order__status=Order.Status.DELIVERED, review__isnull=True,
                                     product__isnull=False)
            .select_related('order', 'product'))


def can_review_product(user, product) -> OrderItem | None:
    if not user.is_authenticated or user.is_staff:
        return None
    return reviewable_items(user).filter(product=product).first()


def create_review(user, order_item_id: int, rating: int, content: str) -> Review:
    item = reviewable_items(user).filter(pk=order_item_id).first()
    if item is None:
        raise ReviewError('Bạn chỉ có thể đánh giá sản phẩm đã mua và đã nhận hàng (mỗi sản phẩm một lần).')
    if not 1 <= int(rating) <= 5:
        raise ReviewError('Số sao phải từ 1 đến 5.')
    content = (content or '').strip()
    if not 10 <= len(content) <= 1000:
        raise ReviewError('Nội dung đánh giá từ 10 đến 1000 ký tự.')
    return Review.objects.create(user=user, product=item.product, order_item=item, rating=int(rating), content=content)


def refresh_product_rating(product_id: int) -> None:
    stats = Review.objects.filter(product_id=product_id, status=Review.Status.APPROVED).aggregate(
        avg=Avg('rating'), count=Count('id'))
    Product.objects.filter(pk=product_id).update(rating_avg=round(stats['avg'] or 0, 2), rating_count=stats['count'])


@transaction.atomic
def set_review_status(review_ids, status: str) -> int:
    reviews = list(Review.objects.filter(pk__in=review_ids))
    for review in reviews:
        review.status = status
        review.save(update_fields=['status', 'updated_at'])
    for product_id in {r.product_id for r in reviews}:
        refresh_product_rating(product_id)
    return len(reviews)


@transaction.atomic
def delete_review(review: Review) -> None:
    product_id = review.product_id
    review.delete()
    refresh_product_rating(product_id)
