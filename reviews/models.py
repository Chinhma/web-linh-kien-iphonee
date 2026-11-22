from django.conf import settings
from django.core.validators import MaxLengthValidator, MaxValueValidator, MinLengthValidator, MinValueValidator
from django.db import models

from core.utils import short_name


class Review(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Chờ duyệt'
        APPROVED = 'approved', 'Đã duyệt'
        HIDDEN = 'hidden', 'Đã ẩn'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='reviews')
    order_item = models.OneToOneField('orders.OrderItem', on_delete=models.CASCADE, related_name='review')
    rating = models.PositiveSmallIntegerField('Số sao', validators=[MinValueValidator(1), MaxValueValidator(5)])
    content = models.TextField('Nội dung', validators=[MinLengthValidator(10), MaxLengthValidator(1000)])
    status = models.CharField('Trạng thái', max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    admin_reply = models.TextField('Phản hồi của cửa hàng', blank=True)
    created_at = models.DateTimeField('Ngày viết', auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Đánh giá'
        verbose_name_plural = 'Đánh giá'
        ordering = ['-created_at']
        constraints = [models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name='review_rating_1_5')]

    def __str__(self):
        return f'{self.rating}★ {self.product} – {self.user}'

    @property
    def author_display(self) -> str:
        return short_name(self.user.display_name)
