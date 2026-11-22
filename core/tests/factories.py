"""Hàm tạo dữ liệu nhanh cho test."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from inventory.models import InventoryTransaction
from inventory.services import adjust_stock
from products.models import Category, Compatibility, IPhoneModel, Product

User = get_user_model()
PASSWORD = 'Matkhau123'


def make_customer(username='khach', email=None):
    user = User.objects.create_user(username=username, email=email or f'{username}@example.com', password=PASSWORD,
                                    full_name='Nguyễn Văn Khách', phone='0889400470')
    return user


def make_admin(username='quantri', superuser=True):
    return User.objects.create_user(username=username, email=f'{username}@example.com', password=PASSWORD,
                                    is_staff=True, is_superuser=superuser)


def make_category(name='Pin', code='BAT'):
    return Category.objects.get_or_create(code=code, defaults={'name': name})[0]


def make_model(name='iPhone 13 Pro', series=13):
    return IPhoneModel.objects.get_or_create(name=name, defaults={'series': series})[0]


def make_product(name='Pin iPhone 13 Pro', sku='IP-BAT-13PRO-001', price=500000, stock=10, category=None, **kwargs):
    product = Product.objects.create(name=name, sku=sku, price=price, category=category or make_category(), **kwargs)
    if stock:
        adjust_stock(product, stock, InventoryTransaction.Type.INITIAL, None, 'test')
    product.refresh_from_db()
    return product


def verify(product, model, status='verified'):
    return Compatibility.objects.create(product=product, iphone_model=model, status=status)


def days(n):
    return timezone.now() + timedelta(days=n)
