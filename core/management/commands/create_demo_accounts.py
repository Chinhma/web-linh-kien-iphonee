"""Tạo 1 tài khoản Admin (superuser) và 1 Customer demo.

Mật khẩu đọc từ biến môi trường DEMO_ADMIN_PASSWORD / DEMO_CUSTOMER_PASSWORD.
Không có biến -> sinh mật khẩu ngẫu nhiên và in ra màn hình MỘT lần. Không hardcode mật khẩu trong mã nguồn.
"""

import os
import secrets
import string

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import Address, CustomerProfile

ACCOUNTS = [
    {'username': 'admin', 'email': 'admin@iparts.local', 'full_name': 'Quản trị viên iParts', 'staff': True, 'env': 'DEMO_ADMIN_PASSWORD'},
    {'username': 'khachdemo', 'email': 'khachdemo@iparts.local', 'full_name': 'Khách Hàng Demo', 'staff': False, 'env': 'DEMO_CUSTOMER_PASSWORD'},
]


def random_password() -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        pwd = ''.join(secrets.choice(alphabet) for _ in range(12))
        if any(c.isdigit() for c in pwd) and any(c.isalpha() for c in pwd):
            return pwd


class Command(BaseCommand):
    help = 'Tạo tài khoản Admin và Customer demo (mật khẩu lấy từ biến môi trường hoặc sinh ngẫu nhiên).'

    def add_arguments(self, parser):
        parser.add_argument('--reset-password', action='store_true', help='Đặt lại mật khẩu nếu tài khoản đã tồn tại')

    def handle(self, *args, **opts):
        User = get_user_model()
        for acc in ACCOUNTS:
            user = User.objects.filter(email__iexact=acc['email']).first()
            created = user is None
            if created:
                user = User(username=acc['username'], email=acc['email'], full_name=acc['full_name'],
                            phone='0889400470', is_staff=acc['staff'], is_superuser=acc['staff'])
            elif not opts['reset_password']:
                self.stdout.write(f'· {acc["email"]} đã tồn tại (dùng --reset-password để đặt lại mật khẩu).')
                continue
            password = os.getenv(acc['env'], '').strip()
            generated = not password
            if generated:
                password = random_password()
            user.set_password(password)
            user.is_active = True
            user.save()
            if not acc['staff']:
                CustomerProfile.objects.get_or_create(user=user)
                if not user.addresses.exists():
                    Address.objects.create(user=user, full_name=user.full_name, phone=user.phone,
                                           province_code='01', province_name='Thành phố Hà Nội', ward_code='00166',
                                           ward_name='Phường Cầu Giấy', street_address='144 Xuân Thủy', is_default=True)
            role = 'Admin (Superuser)' if acc['staff'] else 'Customer'
            self.stdout.write(self.style.SUCCESS(f'✓ {role}: {acc["email"]} / tên đăng nhập: {acc["username"]}'))
            if generated:
                self.stdout.write(self.style.WARNING(f'  Mật khẩu (chỉ hiển thị một lần): {password}'))
            else:
                self.stdout.write(f'  Mật khẩu lấy từ biến môi trường {acc["env"]}.')
