"""Seed dữ liệu demo cho iParts Store.

Chạy: python manage.py seed_data          (chạy lại nhiều lần không nhân đôi dữ liệu)
      python manage.py seed_data --reset  (xóa DỮ LIỆU DEMO rồi tạo lại, có hỏi xác nhận)

Đơn hàng mẫu được tạo qua chính các service nghiệp vụ (create_order, change_order_status, adjust_stock)
nên tồn kho, lịch sử kho, sold_count, coupon và doanh thu luôn nhất quán.
"""

import io
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Address, CustomerProfile
from cart.models import Cart, CartItem
from chatbot.models import ChatbotSetting, ChatConversation, ChatMessage
from core.address import validate as validate_area
from core.models import FAQ, Banner, Page, StoreSetting
from core.utils import strip_accents
from inventory.models import InventoryTransaction
from inventory.services import adjust_stock
from orders.models import Order, OrderStatusHistory
from orders.services import CheckoutData, change_order_status, create_order
from payments.gateways import GatewayResult
from payments.models import Payment
from payments.services import apply_gateway_result, create_payment_record
from products.models import Brand, Category, Compatibility, IPhoneModel, Product, ProductImage
from promotions.models import Coupon, CouponUsage
from reviews.models import Review
from reviews.services import refresh_product_rating

from ._seed_content import FAQS, PAGES, REVIEW_TEXTS

User = get_user_model()
S = Order.Status
DEMO_EMAIL_DOMAIN = '@example.com'

IPHONES = [
    ('iPhone X', 10, 2017), ('iPhone XS', 10, 2018), ('iPhone XS Max', 10, 2018), ('iPhone XR', 10, 2018),
    ('iPhone 11', 11, 2019), ('iPhone 11 Pro', 11, 2019), ('iPhone 11 Pro Max', 11, 2019),
    ('iPhone 12 mini', 12, 2020), ('iPhone 12', 12, 2020), ('iPhone 12 Pro', 12, 2020), ('iPhone 12 Pro Max', 12, 2020),
    ('iPhone 13 mini', 13, 2021), ('iPhone 13', 13, 2021), ('iPhone 13 Pro', 13, 2021), ('iPhone 13 Pro Max', 13, 2021),
    ('iPhone 14', 14, 2022), ('iPhone 14 Plus', 14, 2022), ('iPhone 14 Pro', 14, 2022), ('iPhone 14 Pro Max', 14, 2022),
    ('iPhone 15', 15, 2023), ('iPhone 15 Plus', 15, 2023), ('iPhone 15 Pro', 15, 2023), ('iPhone 15 Pro Max', 15, 2023),
    ('iPhone 16', 16, 2024), ('iPhone 16 Plus', 16, 2024), ('iPhone 16 Pro', 16, 2024), ('iPhone 16 Pro Max', 16, 2024),
]

# (tên, mã, icon, cha, màu gradient)
CATEGORIES = [
    ('Màn hình', 'SCR', 'monitor-smartphone', None, ('#1D4ED8', '#60A5FA')),
    ('Pin', 'BAT', 'battery-full', None, ('#15803D', '#4ADE80')),
    ('Camera', 'CAM', 'camera', None, ('#7C3AED', '#C4B5FD')),
    ('Camera trước', 'FCM', 'scan-face', 'Camera', ('#6D28D9', '#A78BFA')),
    ('Camera sau', 'RCM', 'aperture', 'Camera', ('#5B21B6', '#8B5CF6')),
    ('Chân sạc', 'CHG', 'plug-zap', None, ('#B45309', '#FBBF24')),
    ('Loa', 'SPK', 'speaker', None, ('#BE123C', '#FB7185')),
    ('Loa trong', 'ESP', 'ear', 'Loa', ('#9F1239', '#F43F5E')),
    ('Loa ngoài', 'LSP', 'volume-2', 'Loa', ('#E11D48', '#FDA4AF')),
    ('Micro', 'MIC', 'mic', None, ('#0F766E', '#5EEAD4')),
    ('Vỏ máy', 'HSG', 'smartphone', None, ('#334155', '#94A3B8')),
    ('Khung máy', 'FRM', 'frame', None, ('#475569', '#CBD5E1')),
    ('Nút nguồn & âm lượng', 'BTN', 'power', None, ('#0369A1', '#7DD3FC')),
    ('Cáp và linh kiện khác', 'OTH', 'cable', None, ('#4D7C0F', '#A3E635')),
]
BRANDS = ['Linh kiện chính hãng (tháo máy)', 'OEM', 'JK', 'GX', 'Pisen', 'EU']

T = 'True Tone cần chuyển dữ liệu từ màn cũ'


def P(cat, name, models, quality, price, specs, warranty=6, brand='OEM', note='', short=''):
    return dict(cat=cat, name=name, models=models, quality=quality, price=price, specs=specs, warranty=warranty,
                brand=brand, note=note, short=short)


PRODUCTS = [
    P('SCR', 'Màn hình OLED iPhone 13 Pro — Chính hãng tháo máy', ['iPhone 13 Pro'], 'original', 3900000,
      [('Công nghệ', 'Super Retina XDR OLED'), ('Kích thước', '6.1 inch'), ('Tần số quét', '120Hz ProMotion'), ('Độ phân giải', '2532 x 1170')],
      12, 'Linh kiện chính hãng (tháo máy)', T),
    P('SCR', 'Màn hình OLED iPhone 13 Pro — Linh kiện OEM', ['iPhone 13 Pro'], 'oem', 2150000,
      [('Công nghệ', 'OLED'), ('Kích thước', '6.1 inch'), ('Tần số quét', '120Hz')], 6, 'GX', T),
    P('SCR', 'Màn hình OLED iPhone 13 Pro Max — Chính hãng tháo máy', ['iPhone 13 Pro Max'], 'original', 4500000,
      [('Công nghệ', 'Super Retina XDR OLED'), ('Kích thước', '6.7 inch'), ('Tần số quét', '120Hz ProMotion')], 12,
      'Linh kiện chính hãng (tháo máy)', T),
    P('SCR', 'Màn hình OLED iPhone 13 — Linh kiện OEM', ['iPhone 13'], 'oem', 1850000,
      [('Công nghệ', 'OLED'), ('Kích thước', '6.1 inch'), ('Độ phân giải', '2532 x 1170')], 6, 'GX', T),
    P('SCR', 'Màn hình iPhone 12 / 12 Pro OLED — Linh kiện thay thế', ['iPhone 12', 'iPhone 12 Pro'], 'aftermarket', 1350000,
      [('Công nghệ', 'Soft OLED'), ('Kích thước', '6.1 inch')], 6, 'JK', 'Dùng chung cho iPhone 12 và 12 Pro'),
    P('SCR', 'Màn hình OLED iPhone 12 Pro Max — OEM', ['iPhone 12 Pro Max'], 'oem', 2250000,
      [('Công nghệ', 'OLED'), ('Kích thước', '6.7 inch')], 6, 'GX', T),
    P('SCR', 'Màn hình LCD iPhone 11 — Linh kiện thay thế', ['iPhone 11'], 'aftermarket', 690000,
      [('Công nghệ', 'LCD In-cell'), ('Kích thước', '6.1 inch'), ('Độ phân giải', '1792 x 828')], 6, 'JK', T),
    P('SCR', 'Màn hình OLED iPhone 11 Pro — OEM', ['iPhone 11 Pro'], 'oem', 1450000,
      [('Công nghệ', 'OLED'), ('Kích thước', '5.8 inch')], 6, 'GX', T),
    P('SCR', 'Màn hình OLED iPhone 14 Pro — Chính hãng tháo máy', ['iPhone 14 Pro'], 'original', 5900000,
      [('Công nghệ', 'Super Retina XDR OLED'), ('Kích thước', '6.1 inch'), ('Tần số quét', '120Hz'), ('Dynamic Island', 'Có')],
      12, 'Linh kiện chính hãng (tháo máy)', T),
    P('SCR', 'Màn hình OLED iPhone 14 — OEM', ['iPhone 14'], 'oem', 2350000,
      [('Công nghệ', 'OLED'), ('Kích thước', '6.1 inch')], 6, 'GX', 'Không dùng chung với iPhone 13 dù cùng kích thước'),
    P('SCR', 'Màn hình OLED iPhone 15 Pro Max — Chính hãng tháo máy', ['iPhone 15 Pro Max'], 'original', 7900000,
      [('Công nghệ', 'Super Retina XDR OLED'), ('Kích thước', '6.7 inch'), ('Tần số quét', '120Hz')], 12,
      'Linh kiện chính hãng (tháo máy)', T),
    P('SCR', 'Màn hình LCD iPhone XR — Linh kiện thay thế', ['iPhone XR'], 'aftermarket', 590000,
      [('Công nghệ', 'LCD'), ('Kích thước', '6.1 inch')], 3, 'JK'),
    P('SCR', 'Màn hình OLED iPhone X / XS — OEM', ['iPhone X', 'iPhone XS'], 'oem', 990000,
      [('Công nghệ', 'OLED'), ('Kích thước', '5.8 inch')], 6, 'GX', 'Dùng chung cho iPhone X và XS'),
    P('BAT', 'Pin iPhone 11 dung lượng chuẩn 3110 mAh', ['iPhone 11'], 'oem', 450000,
      [('Dung lượng', '3110 mAh'), ('Điện áp', '3.83V'), ('Cell', 'Li-ion')], 6, 'Pisen',
      'Có thể hiện thông báo "pin không xác định" trên iOS mới'),
    P('BAT', 'Pin iPhone 11 dung lượng cao 3500 mAh', ['iPhone 11'], 'aftermarket', 590000,
      [('Dung lượng', '3500 mAh'), ('Điện áp', '3.83V')], 6, 'EU'),
    P('BAT', 'Pin iPhone 11 Pro 3046 mAh', ['iPhone 11 Pro'], 'oem', 520000, [('Dung lượng', '3046 mAh')], 6, 'Pisen'),
    P('BAT', 'Pin iPhone 11 Pro Max 3969 mAh', ['iPhone 11 Pro Max'], 'oem', 560000, [('Dung lượng', '3969 mAh')], 6, 'Pisen'),
    P('BAT', 'Pin iPhone 12 / 12 Pro 2815 mAh', ['iPhone 12', 'iPhone 12 Pro'], 'oem', 590000,
      [('Dung lượng', '2815 mAh'), ('Điện áp', '3.83V')], 6, 'Pisen', 'Dùng chung cho iPhone 12 và 12 Pro'),
    P('BAT', 'Pin iPhone 13 3227 mAh', ['iPhone 13'], 'oem', 690000, [('Dung lượng', '3227 mAh'), ('Điện áp', '3.88V')], 6, 'Pisen'),
    P('BAT', 'Pin iPhone 13 Pro 3095 mAh — Chính hãng tháo máy', ['iPhone 13 Pro'], 'original', 990000,
      [('Dung lượng', '3095 mAh'), ('Điện áp', '3.88V'), ('Hiển thị tình trạng pin', 'Có')], 12, 'Linh kiện chính hãng (tháo máy)'),
    P('BAT', 'Pin iPhone 13 Pro Max 4352 mAh', ['iPhone 13 Pro Max'], 'oem', 790000, [('Dung lượng', '4352 mAh')], 6, 'Pisen'),
    P('BAT', 'Pin iPhone 14 3279 mAh', ['iPhone 14'], 'oem', 790000, [('Dung lượng', '3279 mAh')], 6, 'Pisen'),
    P('BAT', 'Pin iPhone 14 Pro Max 4323 mAh', ['iPhone 14 Pro Max'], 'oem', 890000, [('Dung lượng', '4323 mAh')], 6, 'EU'),
    P('BAT', 'Pin iPhone XR 2942 mAh', ['iPhone XR'], 'oem', 390000, [('Dung lượng', '2942 mAh')], 6, 'Pisen'),
    P('BAT', 'Pin iPhone X 2716 mAh', ['iPhone X'], 'aftermarket', 350000, [('Dung lượng', '2716 mAh')], 3, 'EU'),
    P('BAT', 'Pin iPhone 15 Pro 3274 mAh', ['iPhone 15 Pro'], 'oem', 990000, [('Dung lượng', '3274 mAh')], 6, 'Pisen'),
    P('RCM', 'Camera sau iPhone 13 Pro — Chính hãng tháo máy', ['iPhone 13 Pro', 'iPhone 13 Pro Max'], 'original', 2900000,
      [('Cụm camera', '3 camera 12MP'), ('Chống rung', 'Sensor-shift')], 6, 'Linh kiện chính hãng (tháo máy)',
      'Dùng chung cho 13 Pro và 13 Pro Max'),
    P('RCM', 'Camera sau iPhone 11', ['iPhone 11'], 'oem', 890000, [('Cụm camera', '2 camera 12MP')], 6, 'OEM'),
    P('RCM', 'Camera sau iPhone 12', ['iPhone 12'], 'oem', 1150000, [('Cụm camera', '2 camera 12MP')], 6, 'OEM'),
    P('FCM', 'Camera trước iPhone 12 / 12 Pro', ['iPhone 12', 'iPhone 12 Pro'], 'oem', 650000,
      [('Độ phân giải', '12MP TrueDepth')], 6, 'OEM', 'Face ID có thể không hoạt động nếu không chuyển cụm Face ID'),
    P('FCM', 'Camera trước iPhone 11', ['iPhone 11'], 'oem', 550000, [('Độ phân giải', '12MP')], 6, 'OEM'),
    P('CHG', 'Cụm chân sạc iPhone 11 (kèm mic)', ['iPhone 11'], 'oem', 320000, [('Cổng', 'Lightning'), ('Kèm micro', 'Có')], 6, 'JK'),
    P('CHG', 'Cụm chân sạc iPhone 12 / 12 Pro', ['iPhone 12', 'iPhone 12 Pro'], 'oem', 380000, [('Cổng', 'Lightning')], 6, 'JK'),
    P('CHG', 'Cụm chân sạc iPhone 13', ['iPhone 13'], 'oem', 420000, [('Cổng', 'Lightning')], 6, 'JK'),
    P('CHG', 'Cụm chân sạc iPhone 15 Pro USB-C', ['iPhone 15 Pro'], 'oem', 650000, [('Cổng', 'USB-C'), ('Tốc độ', 'USB 3')], 6, 'JK'),
    P('LSP', 'Loa ngoài iPhone 11', ['iPhone 11'], 'oem', 220000, [('Loại', 'Loa chuông')], 6, 'OEM'),
    P('LSP', 'Loa ngoài iPhone 13 Pro', ['iPhone 13 Pro'], 'oem', 290000, [('Loại', 'Loa chuông')], 6, 'OEM'),
    P('ESP', 'Loa trong (loa thoại) iPhone 12', ['iPhone 12', 'iPhone 12 Pro'], 'oem', 180000, [('Loại', 'Loa thoại')], 6, 'OEM'),
    P('MIC', 'Micro iPhone 13 (cáp flex)', ['iPhone 13'], 'oem', 150000, [('Loại', 'Flex micro')], 3, 'OEM'),
    P('HSG', 'Vỏ (kính lưng + khung) iPhone 12 Pro — Xanh Pacific', ['iPhone 12 Pro'], 'aftermarket', 1290000,
      [('Màu', 'Xanh Pacific'), ('Chất liệu', 'Thép không gỉ + kính')], 3, 'GX'),
    P('HSG', 'Kính lưng iPhone 14 Pro Max — Tím', ['iPhone 14 Pro Max'], 'aftermarket', 450000, [('Màu', 'Tím Deep Purple')], 3, 'GX'),
    P('FRM', 'Khung xương iPhone 13 — Hồng', ['iPhone 13'], 'aftermarket', 790000, [('Màu', 'Hồng'), ('Chất liệu', 'Nhôm')], 3, 'GX'),
    P('BTN', 'Cáp nút nguồn iPhone 11', ['iPhone 11'], 'oem', 160000, [('Loại', 'Flex nút nguồn + flash')], 3, 'OEM'),
    P('BTN', 'Cáp nút âm lượng iPhone 13 Pro', ['iPhone 13 Pro'], 'oem', 190000, [('Loại', 'Flex âm lượng')], 3, 'OEM'),
    P('OTH', 'Rung Taptic Engine iPhone 12', ['iPhone 12', 'iPhone 12 Pro'], 'oem', 260000, [('Loại', 'Motor rung')], 6, 'OEM'),
    P('OTH', 'Cáp Face ID iPhone X', ['iPhone X'], 'oem', 350000, [('Loại', 'Flex Face ID')], 3, 'OEM',
      'Cần thợ có kinh nghiệm, Face ID gắn với main máy'),
]

CUSTOMERS = ['Nguyễn Văn An', 'Trần Thị Bình', 'Lê Hoàng Cường', 'Phạm Minh Dũng', 'Hoàng Thu Hà', 'Vũ Đức Huy',
             'Đặng Ngọc Lan', 'Bùi Quang Minh', 'Đỗ Thanh Nam', 'Ngô Bảo Ngọc', 'Dương Văn Phúc', 'Lý Thị Quỳnh',
             'Phan Tuấn Sơn', 'Trịnh Mai Trang', 'Võ Gia Vinh']
# Địa chỉ mẫu theo đơn vị hành chính sau 01/07/2025 (mã tỉnh, mã phường/xã) – tên lấy từ static/data/vn-address-2025.json
LOCATIONS = [('01', '00166'), ('01', '00004'), ('79', '26740'), ('79', '26743'), ('48', '20242'),
             ('31', '11383'), ('92', '31135'), ('46', '19789')]


def make_image(title: str, subtitle: str, colors: tuple, icon_kind: str, variant: int = 0) -> bytes:
    """Ảnh placeholder 800x800 bằng Pillow: nền gradient, hình khối linh kiện đơn giản, chữ và logo iParts."""
    from PIL import Image, ImageDraw, ImageFont

    size = 800
    c1 = tuple(int(colors[0][i:i + 2], 16) for i in (1, 3, 5))
    c2 = tuple(int(colors[1][i:i + 2], 16) for i in (1, 3, 5))
    img = Image.new('RGB', (size, size))
    draw = ImageDraw.Draw(img)
    for y in range(size):
        t = y / size
        draw.line([(0, y), (size, y)], fill=tuple(int(c1[k] * (1 - t) + c2[k] * t) for k in range(3)))
    try:
        font_big = ImageFont.truetype('arialbd.ttf', 46)
        font_small = ImageFont.truetype('arial.ttf', 30)
        font_logo = ImageFont.truetype('arialbd.ttf', 26)
    except OSError:  # Máy không có font Arial
        font_big = ImageFont.load_default(size=46)
        font_small = ImageFont.load_default(size=30)
        font_logo = ImageFont.load_default(size=26)
    white = (255, 255, 255)
    cx, cy = 400, 330 + (variant * 10)
    if icon_kind == 'SCR' or icon_kind in ('HSG', 'FRM'):
        draw.rounded_rectangle((cx - 130, cy - 230, cx + 130, cy + 230), 40, outline=white, width=12)
        draw.rounded_rectangle((cx - 45, cy - 210, cx + 45, cy - 185), 12, fill=white)
    elif icon_kind == 'BAT':
        draw.rounded_rectangle((cx - 110, cy - 200, cx + 110, cy + 200), 26, outline=white, width=12)
        draw.rectangle((cx - 40, cy - 225, cx + 40, cy - 200), fill=white)
        draw.polygon([(cx + 10, cy - 100), (cx - 50, cy + 20), (cx, cy + 20), (cx - 10, cy + 100), (cx + 50, cy - 20), (cx, cy - 20)], fill=white)
    elif icon_kind in ('RCM', 'FCM', 'CAM'):
        draw.rounded_rectangle((cx - 170, cy - 170, cx + 170, cy + 170), 50, outline=white, width=12)
        for dx, dy in ((-70, -70), (70, -70), (-70, 70)) if icon_kind == 'RCM' else ((0, 0),):
            draw.ellipse((cx + dx - 55, cy + dy - 55, cx + dx + 55, cy + dy + 55), outline=white, width=10)
    else:
        draw.rounded_rectangle((cx - 200, cy - 60, cx + 200, cy + 60), 30, outline=white, width=12)
        for i in range(5):
            draw.rectangle((cx - 150 + i * 70, cy - 20, cx - 110 + i * 70, cy + 20), fill=white)
    draw.text((400, 640), strip_accents(title)[:28], font=font_big, fill=white, anchor='mm')
    draw.text((400, 700), strip_accents(subtitle)[:40], font=font_small, fill=(240, 240, 255), anchor='mm')
    draw.rounded_rectangle((24, 24, 220, 76), 26, fill=(255, 255, 255))
    draw.text((122, 50), 'iParts Store', font=font_logo, fill=(37, 99, 235), anchor='mm')
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=85)
    return buf.getvalue()


class Command(BaseCommand):
    help = 'Tạo dữ liệu demo cho iParts Store (an toàn khi chạy lại nhiều lần).'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Xóa dữ liệu demo cũ trước khi tạo lại')
        parser.add_argument('--yes', action='store_true', help='Không hỏi xác nhận khi --reset')
        parser.add_argument('--orders', type=int, default=120, help='Số đơn hàng mẫu (mặc định 120)')
        parser.add_argument('--seed', type=int, default=2026, help='Giá trị random seed')

    def handle(self, *args, **opts):
        random.seed(opts['seed'])
        if opts['reset']:
            if not opts['yes']:
                answer = input('Xóa toàn bộ DỮ LIỆU DEMO (sản phẩm mẫu, khách mẫu, đơn mẫu...)? Gõ "yes" để tiếp tục: ')
                if answer.strip().lower() != 'yes':
                    self.stdout.write('Đã hủy.')
                    return
            self.reset_demo()
        self.seed_settings()
        models = self.seed_iphones()
        cats = self.seed_categories()
        brands = {name: Brand.objects.get_or_create(name=name)[0] for name in BRANDS}
        products = self.seed_products(cats, brands, models)
        customers = self.seed_customers()
        self.seed_coupons()
        if not Order.objects.filter(user__email__endswith=DEMO_EMAIL_DOMAIN).exists():
            self.seed_orders(products, customers, opts['orders'])
            self.finalize_stock(products)
            self.seed_reviews()
        else:
            self.stdout.write('  · Đơn hàng mẫu đã tồn tại – bỏ qua.')
        if not ChatConversation.objects.filter(title__startswith='[Mẫu]').exists():
            self.seed_chats(customers)
        self.stdout.write(self.style.SUCCESS(
            f'Hoàn tất: {Product.objects.count()} sản phẩm, {IPhoneModel.objects.count()} dòng iPhone, '
            f'{Order.objects.count()} đơn hàng, {Review.objects.count()} đánh giá, '
            f'{ChatConversation.objects.count()} hội thoại.'))

    # ------------------------------------------------------------------ reset
    @transaction.atomic
    def reset_demo(self):
        demo_users = User.objects.filter(email__endswith=DEMO_EMAIL_DOMAIN, is_staff=False)
        demo_orders = Order.objects.filter(user__in=demo_users)
        seed_products = Product.objects.filter(sku__startswith='IP-')
        Review.objects.filter(user__in=demo_users).delete()
        CouponUsage.objects.filter(order__in=demo_orders).delete()
        InventoryTransaction.objects.filter(product__in=seed_products).delete()
        Payment.objects.filter(order__in=demo_orders).delete()
        demo_orders.delete()
        ChatConversation.objects.filter(title__startswith='[Mẫu]').delete()
        CartItem.objects.filter(product__in=seed_products).delete()
        for product in seed_products:
            if not product.order_items.exists():
                for img in product.images.all():
                    img.image.delete(save=False)
                product.delete()
        demo_users.delete()
        self.stdout.write(self.style.WARNING('Đã xóa dữ liệu demo.'))

    # ------------------------------------------------------------------ settings & nội dung
    def seed_settings(self):
        store = StoreSetting.get_solo()
        if not store.announcement_text:
            store.announcement_text = 'Miễn phí vận chuyển cho đơn từ 2.000.000₫ – Tra cứu linh kiện tương thích theo từng dòng iPhone'
        store.save()
        ChatbotSetting.get_solo().save()
        for slug, (title, content) in PAGES.items():
            Page.objects.update_or_create(slug=slug, defaults={'title': title, 'content': content, 'is_published': True})
        for i, (q, a) in enumerate(FAQS):
            FAQ.objects.get_or_create(question=q, defaults={'answer': a, 'display_order': i})
        banners = [
            ('Linh kiện iPhone chính xác cho từng dòng máy', 'Tra cứu theo model, bảo hành rõ ràng, giao hàng toàn quốc.', 'Tra cứu ngay', '/tra-cuu-tuong-thich/'),
            ('Màn hình OLED chính hãng tháo máy', 'Hiển thị chuẩn màu, bảo hành đến 12 tháng.', 'Xem màn hình', '/danh-muc/man-hinh/'),
            ('Thay pin – máy khỏe như mới', 'Pin dung lượng chuẩn và dung lượng cao cho iPhone X đến 15 series.', 'Xem pin', '/danh-muc/pin/'),
        ]
        for i, (title, sub, btn, url) in enumerate(banners):
            Banner.objects.get_or_create(title=title, defaults={'subtitle': sub, 'button_text': btn, 'button_url': url, 'display_order': i})
        self.stdout.write('  ✓ Cài đặt cửa hàng, trang nội dung, FAQ, banner')

    def seed_iphones(self):
        models = {}
        for order, (name, series, year) in enumerate(IPHONES):
            obj, _ = IPhoneModel.objects.get_or_create(name=name, defaults={'series': series, 'release_year': year, 'display_order': order})
            models[name] = obj
        self.stdout.write(f'  ✓ {len(models)} dòng iPhone')
        return models

    def seed_categories(self):
        cats = {}
        for order, (name, code, icon, parent, colors) in enumerate(CATEGORIES):
            obj, _ = Category.objects.get_or_create(code=code, defaults={
                'name': name, 'icon': icon, 'display_order': order,
                'parent': cats.get(next((c for n, c, *_ in CATEGORIES if n == parent), None)) if parent else None,
                'description': f'Linh kiện {name.lower()} thay thế cho các dòng iPhone, tra cứu tương thích theo model.',
            })
            obj.colors = colors
            cats[code] = obj
        self.stdout.write(f'  ✓ {len(cats)} danh mục')
        return cats

    # ------------------------------------------------------------------ sản phẩm
    def seed_products(self, cats, brands, models):
        now = timezone.now()
        products = []
        counters = {}
        for idx, data in enumerate(PRODUCTS):
            cat = cats[data['cat']]
            first_model = data['models'][0]
            model_code = strip_accents(first_model.replace('iPhone ', '')).upper().replace(' ', '')
            counters[(cat.code, model_code)] = counters.get((cat.code, model_code), 0) + 1
            sku = f'IP-{cat.code}-{model_code}-{counters[(cat.code, model_code)]:03d}'
            product = Product.objects.filter(sku=sku).first()
            if product is None:
                price = data['price']
                sale_price = None
                if idx % 3 == 1:  # ~30% có giá khuyến mãi
                    sale_price = int(price * random.choice([0.85, 0.9, 0.8]) // 10000 * 10000)
                product = Product.objects.create(
                    name=data['name'], sku=sku, category=cat, brand=brands.get(data['brand']),
                    quality_grade=data['quality'], price=price, sale_price=sale_price,
                    sale_end=now + timedelta(days=random.randint(10, 40)) if sale_price else None,
                    cost_price=int(price * random.uniform(0.55, 0.7) // 1000 * 1000),
                    short_description=data['short'] or f'{data["name"]}, tương thích {", ".join(data["models"])}.',
                    description=self.description_for(data), usage_guide=self.guide_for(data['cat']),
                    specifications=[{'label': k, 'value': v} for k, v in data['specs']] + [
                        {'label': 'Bảo hành', 'value': f'{data["warranty"]} tháng'}],
                    warranty_months=data['warranty'], is_featured=idx % 5 == 0, status=Product.Status.ACTIVE,
                    low_stock_threshold=5,
                )
                # Tồn đầu kỳ (13 tháng trước)
                trx = adjust_stock(product, random.randint(40, 70), InventoryTransaction.Type.INITIAL, None,
                                   'Tồn đầu kỳ (dữ liệu mẫu)', unit_cost=product.cost_price)
                InventoryTransaction.objects.filter(pk=trx.pk).update(created_at=now - timedelta(days=400))
                Product.objects.filter(pk=product.pk).update(created_at=now - timedelta(days=random.randint(1, 300)))
                for v in range(random.choice([1, 2, 2, 3])):
                    content = make_image(cat.name, first_model if v == 0 else f'Góc nhìn {v + 1}', cat.colors, cat.code, v)
                    image = ProductImage(product=product, alt_text=f'{product.name} – ảnh {v + 1}', is_primary=v == 0, display_order=v)
                    image.image.save(f'seed-{sku.lower()}-{v}.jpg', ContentFile(content), save=False)
                    image.save()
            for name in data['models']:
                Compatibility.objects.get_or_create(product=product, iphone_model=models[name], defaults={
                    'status': Compatibility.Status.VERIFIED, 'note': data['note'], 'is_sample_data': True,
                    'source': 'Dữ liệu minh họa (seed)', 'verified_at': now})
            products.append(product)
        # Vài quan hệ "không tương thích" / "chưa xác nhận" để minh họa
        extras = [('Màn hình OLED iPhone 14 — OEM', 'iPhone 13', 'incompatible', 'Cùng kích thước nhưng khác cáp kết nối'),
                  ('Pin iPhone 13 3227 mAh', 'iPhone 13 mini', 'incompatible', 'Khác kích thước pin'),
                  ('Màn hình LCD iPhone 11 — Linh kiện thay thế', 'iPhone XR', 'unverified', 'Đang chờ kiểm tra thực tế'),
                  ('Cụm chân sạc iPhone 13', 'iPhone 13 mini', 'unverified', '')]
        for pname, mname, status, note in extras:
            product = Product.objects.filter(name=pname).first()
            if product:
                Compatibility.objects.get_or_create(product=product, iphone_model=models[mname], defaults={
                    'status': status, 'note': note, 'is_sample_data': True, 'source': 'Dữ liệu minh họa (seed)'})
        self.stdout.write(f'  ✓ {len(products)} sản phẩm (kèm ảnh placeholder + tương thích)')
        return products

    @staticmethod
    def description_for(data) -> str:
        models = ', '.join(data['models'])
        return (f'## Giới thiệu\n{data["name"]} là linh kiện thay thế dành cho **{models}**.\n'
                '- Kiểm tra kỹ trước khi xuất kho, đóng gói chống sốc.\n'
                f'- Bảo hành {data["warranty"]} tháng với lỗi kỹ thuật từ nhà sản xuất.\n'
                '- Hỗ trợ tư vấn lắp đặt qua hotline và iParts AI Assistant.\n\n'
                '_Nội dung mô tả là dữ liệu mẫu phục vụ demo đồ án._')

    @staticmethod
    def guide_for(cat_code: str) -> str:
        common = ('- Tắt nguồn máy và tháo SIM trước khi sửa chữa.\n'
                  '- Nên mang máy tới thợ có kinh nghiệm, dùng dụng cụ chuyên dụng.\n'
                  '- Không bảo hành khi lắp sai, rơi vỡ, vào nước hoặc tem bị rách.')
        specific = {
            'SCR': '- Chuyển dữ liệu True Tone từ màn cũ để giữ tính năng True Tone.\n- Kiểm tra cảm ứng và Face ID trước khi dán keo.',
            'BAT': '- Sạc đầy 1 lần trước khi sử dụng.\n- Pin không chính hãng có thể hiển thị thông báo trong Cài đặt > Pin.',
        }.get(cat_code, '')
        return (specific + '\n' + common).strip()

    # ------------------------------------------------------------------ khách hàng
    def seed_customers(self):
        customers = []
        for i, name in enumerate(CUSTOMERS, start=1):
            email = f'khach{i:02d}{DEMO_EMAIL_DOMAIN}'
            user, created = User.objects.get_or_create(email=email, defaults={
                'username': f'khach{i:02d}', 'full_name': name, 'phone': f'09{random.randint(10000000, 99999999)}',
                'is_staff': False})
            if created:
                user.set_unusable_password()
                user.date_joined = timezone.now() - timedelta(days=random.randint(5, 380))
                user.save()
                CustomerProfile.objects.get_or_create(user=user)
                for n in range(random.choice([1, 2])):
                    pcode, wcode = random.choice(LOCATIONS)
                    pname, wname = validate_area(pcode, wcode)
                    Address.objects.create(user=user, full_name=name, phone=user.phone, province_code=pcode, province_name=pname,
                                           ward_code=wcode, ward_name=wname,
                                           street_address=f'{random.randint(1, 200)} đường số {random.randint(1, 30)}',
                                           is_default=n == 0)
            customers.append(user)
        self.stdout.write(f'  ✓ {len(customers)} khách hàng mẫu')
        return customers

    def seed_coupons(self):
        now = timezone.now()
        data = [
            ('WELCOME10', 'Giảm 10% cho khách hàng mới', 'percent', 10, 100000, 500000, None, now - timedelta(days=365), now + timedelta(days=365)),
            ('GIAM50K', 'Giảm 50.000₫ cho đơn từ 1 triệu', 'fixed', 50000, None, 1000000, 500, now - timedelta(days=200), now + timedelta(days=180)),
            ('HETHAN20', 'Mã đã hết hạn (minh họa)', 'percent', 20, 200000, 0, None, now - timedelta(days=120), now - timedelta(days=30)),
            ('TET2027', 'Khuyến mãi Tết (sắp diễn ra)', 'percent', 15, 150000, 800000, 200, now + timedelta(days=40), now + timedelta(days=80)),
        ]
        for code, desc, kind, value, max_d, min_o, limit, start, end in data:
            Coupon.objects.get_or_create(code=code, defaults={
                'description': desc, 'discount_type': kind, 'value': value, 'max_discount': max_d, 'min_order_value': min_o,
                'usage_limit': limit, 'usage_limit_per_user': 1 if code == 'WELCOME10' else 3, 'start_at': start, 'end_at': end})
        self.stdout.write('  ✓ 4 mã giảm giá')

    # ------------------------------------------------------------------ đơn hàng
    def seed_orders(self, products, customers, count):
        now = timezone.now()
        # Phân bố thời gian: 1/3 trong 30 ngày gần đây, còn lại rải đều 12 tháng
        ages = sorted([random.uniform(0, 30) if i < count // 3 else random.uniform(30, 360) for i in range(count)], reverse=True)
        created = 0
        for age in ages:
            customer = random.choice(customers)
            placed_at = now - timedelta(days=age, hours=random.randint(0, 12))
            chosen = random.sample(products, random.choice([1, 1, 2, 2, 3]))
            cart, _ = Cart.objects.get_or_create(user=customer)
            cart.items.all().delete()
            for product in chosen:
                product.refresh_from_db()
                if product.stock_quantity < 5:
                    trx = adjust_stock(product, random.randint(25, 40), InventoryTransaction.Type.IMPORT, None,
                                       'Nhập hàng định kỳ (dữ liệu mẫu)', unit_cost=product.cost_price)
                    InventoryTransaction.objects.filter(pk=trx.pk).update(created_at=placed_at - timedelta(days=1))
                CartItem.objects.create(cart=cart, product=product, quantity=random.choice([1, 1, 1, 2]))
            address = customer.addresses.first()
            method = random.choices(['cod', 'vnpay', 'momo'], weights=[6, 3, 2])[0]
            coupon = ''
            if random.random() < 0.15:
                coupon = random.choice(['GIAM50K', 'WELCOME10'])
            data = CheckoutData(
                recipient_name=customer.full_name, recipient_phone=customer.phone, recipient_email=customer.email,
                province_code=address.province_code, province_name=address.province_name, ward_code=address.ward_code,
                ward_name=address.ward_name, street_address=address.street_address,
                shipping_method=random.choice(['standard', 'standard', 'express']), payment_method=method, coupon_code=coupon)
            try:
                order = create_order(customer, data, idempotency_key=f'seed-{created}-{random.random()}')
            except Exception:
                data.coupon_code = ''
                try:
                    order = create_order(customer, data, idempotency_key=f'seed-{created}-{random.random()}')
                except Exception:
                    continue
            self.simulate_lifecycle(order, age, placed_at)
            created += 1
        Cart.objects.filter(user__in=customers).delete()
        self.stdout.write(f'  ✓ {created} đơn hàng mẫu (qua service create_order / change_order_status)')

    def simulate_lifecycle(self, order, age_days, placed_at):
        if order.payment_method != 'cod':
            if age_days < 0.5 and random.random() < 0.5:
                pass  # Đơn online mới: để ở trạng thái chờ thanh toán
            else:
                payment = create_payment_record(order)
                result = GatewayResult(valid_signature=True, success=True, transaction_ref=payment.transaction_ref,
                                       amount=payment.amount, gateway_transaction_id=f'SEED{random.randint(10**7, 10**8)}',
                                       response_code='00', raw={'sample_data': True, 'note': 'Giao dịch mẫu do seed tạo'})
                apply_gateway_result(result, source='seed')
        # Chọn trạng thái đích theo tuổi đơn
        if age_days > 7:
            path = random.choices([['confirmed', 'preparing', 'shipping', 'delivered'], ['cancelled'],
                                   ['confirmed', 'preparing', 'shipping', 'cancelled']], weights=[85, 10, 5])[0]
        elif age_days > 2:
            path = random.choice([['confirmed', 'preparing', 'shipping', 'delivered'], ['confirmed', 'preparing', 'shipping'],
                                  ['confirmed', 'preparing'], ['cancelled']])
        else:
            path = random.choice([[], ['confirmed'], [], ['cancelled']])
        order.refresh_from_db()
        if order.is_online_payment and order.payment_status != 'paid':
            path = []
        step_time = placed_at
        times = {}
        for status in path:
            note = ''
            if status == 'cancelled':
                note = random.choice(['Đổi ý, không muốn mua nữa', 'Đặt nhầm sản phẩm', 'Khách không nhận hàng', 'Muốn đổi địa chỉ nhận hàng'])
            actor_is_customer = status == 'cancelled' and order.status == 'pending'
            try:
                change_order_status(order, status, order.user if actor_is_customer else self.system_admin(), note)
            except Exception:
                break
            step_time = step_time + timedelta(hours=random.randint(2, 30))
            times[status] = min(step_time, timezone.now())
        # Đưa mốc thời gian về quá khứ cho đúng biểu đồ
        updates = {'created_at': placed_at}
        field_map = {'confirmed': 'confirmed_at', 'shipping': 'shipped_at', 'delivered': 'delivered_at', 'cancelled': 'cancelled_at'}
        for status, ts in times.items():
            if status in field_map:
                updates[field_map[status]] = ts
        order.refresh_from_db()
        if order.paid_at:
            updates['paid_at'] = times.get('delivered', placed_at + timedelta(minutes=5)) if order.payment_method == 'cod' else placed_at + timedelta(minutes=5)
        Order.objects.filter(pk=order.pk).update(**updates)
        history = list(order.status_history.order_by('id'))
        if history:
            OrderStatusHistory.objects.filter(pk=history[0].pk).update(created_at=placed_at)
        for h in history[1:]:
            ts = times.get(h.to_status) or placed_at + timedelta(minutes=5)
            OrderStatusHistory.objects.filter(pk=h.pk).update(created_at=ts)
        InventoryTransaction.objects.filter(order=order, type='export_order').update(created_at=placed_at)
        if 'cancelled' in times:
            InventoryTransaction.objects.filter(order=order, type='return_cancel').update(created_at=times['cancelled'])
        order.payments.update(created_at=placed_at, paid_at=updates.get('paid_at'))
        CouponUsage.objects.filter(order=order).update(created_at=placed_at)

    _admin = None

    def system_admin(self):
        """Admin dùng để thực hiện chuyển trạng thái trong dữ liệu mẫu."""
        if self._admin is None:
            self._admin, created = User.objects.get_or_create(username='seed_admin', defaults={
                'email': 'seed-admin@iparts.local', 'full_name': 'Admin dữ liệu mẫu', 'is_staff': True, 'is_active': False})
            if created:
                self._admin.set_unusable_password()
                self._admin.save()
        return self._admin

    def finalize_stock(self, products):
        """Tạo đa dạng trạng thái kho bằng giao dịch điều chỉnh kiểm kê (vẫn khớp lịch sử)."""
        now = timezone.now()
        sample = random.sample(products, 8)
        for i, product in enumerate(sample):
            product.refresh_from_db()
            target = 0 if i < 3 else random.randint(2, 4)
            diff = target - product.stock_quantity
            if diff:
                trx = adjust_stock(product, diff, InventoryTransaction.Type.ADJUSTMENT, None,
                                   'Kiểm kê cuối kỳ: hàng lỗi/thất lạc (dữ liệu mẫu)')
                InventoryTransaction.objects.filter(pk=trx.pk).update(created_at=now - timedelta(days=1))
        self.stdout.write('  ✓ Điều chỉnh tồn kho (vài sản phẩm hết hàng / sắp hết)')

    def seed_reviews(self):
        from orders.models import OrderItem

        items = list(OrderItem.objects.filter(order__status='delivered', review__isnull=True, product__isnull=False)
                     .select_related('order', 'product'))
        random.shuffle(items)
        created = 0
        for item in items[:85]:
            rating = random.choices([5, 4, 3, 2], weights=[55, 30, 10, 5])[0]
            review = Review.objects.create(
                user=item.order.user, product=item.product, order_item=item, rating=rating,
                content=random.choice(REVIEW_TEXTS[rating]),
                status=random.choices(['approved', 'pending'], weights=[88, 12])[0])
            Review.objects.filter(pk=review.pk).update(created_at=(item.order.delivered_at or timezone.now()) + timedelta(days=random.randint(1, 5)))
            created += 1
        for pid in {i.product_id for i in items[:85]}:
            refresh_product_rating(pid)
        self.stdout.write(f'  ✓ {created} đánh giá mẫu')

    def seed_chats(self, customers):
        from chatbot.services import fallback

        questions = ['Màn hình nào dùng được cho iPhone 13 Pro?', 'ip 11 thay pin giá bao nhiêu', 'Có màn cho iPhone 13 không',
                     'Linh kiện cho iPhone 6', 'Đang có khuyến mãi gì?', 'Chân sạc iPhone 12 còn hàng không',
                     'Pin iPhone 14 có những loại nào?', 'Phí vận chuyển bao nhiêu?', 'Chính sách bảo hành thế nào?',
                     'Camera sau iPhone 13 Pro giá bao nhiêu']
        now = timezone.now()
        for i in range(20):
            user = random.choice(customers) if i % 2 == 0 else None
            started = now - timedelta(days=random.randint(0, 25), hours=random.randint(0, 20))
            conv = ChatConversation.objects.create(user=user, session_key='' if user else f'seed{i}', title=f'[Mẫu] {questions[i % 10]}'[:60])
            for turn in range(random.choice([1, 2])):
                q = questions[(i + turn * 3) % len(questions)]
                ChatMessage.objects.create(conversation=conv, role='user', content=q)
                ans = fallback.answer(q, user=user)
                ChatMessage.objects.create(conversation=conv, role='assistant', content=ans['reply'], products=ans['product_ids'][:8],
                                           intent=ans['intent'], tool_calls=ans['tool_calls'], meta={**ans['meta'], 'mode': 'basic'},
                                           latency_ms=random.randint(300, 2500), is_error=random.random() < 0.05)
            conv.messages.update(created_at=started)
            conv.message_count = conv.messages.count()
            conv.last_message_at = started
            conv.save()
            ChatConversation.objects.filter(pk=conv.pk).update(created_at=started)
        self.stdout.write('  ✓ 20 hội thoại chatbot mẫu')
