from django.core.management.base import BaseCommand

from orders.services import expire_unpaid_orders


class Command(BaseCommand):
    help = 'Hủy các đơn thanh toán online đã quá hạn (hoàn kho, hoàn lượt mã giảm giá).'

    def handle(self, *args, **options):
        count = expire_unpaid_orders()
        self.stdout.write(self.style.SUCCESS(f'Đã hủy {count} đơn quá hạn thanh toán.'))
