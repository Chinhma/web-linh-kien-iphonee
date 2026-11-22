from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Giỏ hàng'
        verbose_name_plural = 'Giỏ hàng'

    def __str__(self):
        return f'Giỏ hàng của {self.user}'


class CartItem(models.Model):
    """Dòng giỏ hàng. KHÔNG lưu giá – luôn tính theo giá hiện tại của sản phẩm."""

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='cart_items')
    quantity = models.PositiveIntegerField('Số lượng', default=1, validators=[MinValueValidator(1)])
    is_selected = models.BooleanField('Chọn thanh toán', default=True)
    added_at = models.DateTimeField('Thêm lúc', auto_now_add=True)

    class Meta:
        verbose_name = 'Sản phẩm trong giỏ'
        verbose_name_plural = 'Sản phẩm trong giỏ'
        ordering = ['-added_at']
        constraints = [models.UniqueConstraint(fields=['cart', 'product'], name='unique_cart_product')]

    def __str__(self):
        return f'{self.product} × {self.quantity}'

    @property
    def line_total(self) -> int:
        return self.product.effective_price * self.quantity


class WishlistItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlist_items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='wishlisted_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Sản phẩm yêu thích'
        verbose_name_plural = 'Sản phẩm yêu thích'
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['user', 'product'], name='unique_wishlist_product')]

    def __str__(self):
        return f'{self.user} ♥ {self.product}'
