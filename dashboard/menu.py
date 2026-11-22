"""Cấu hình menu sidebar Admin Panel – MỘT NƠI DUY NHẤT.

Mỗi mục: (nhãn, icon Lucide, url_name, query, badge, superuser_only, children)
Mục đang chọn được xác định theo request.resolver_match.url_name + tham số query trên URL.
"""

from dataclasses import dataclass, field

from django.db.models import F
from django.urls import reverse


def _pending_orders():
    from orders.models import Order

    return Order.objects.filter(status='pending').count()


def _refund_pending():
    from orders.models import Order

    return Order.objects.filter(payment_status='refund_pending').count()


def _pending_reviews():
    from reviews.models import Review

    return Review.objects.filter(status='pending').count()


def _low_stock():
    from products.models import Product

    return Product.objects.filter(status='active', stock_quantity__lte=F('low_stock_threshold')).count()


def _new_contacts():
    from core.models import ContactMessage

    return ContactMessage.objects.filter(is_read=False).count()


BADGES = {'orders': _pending_orders, 'refunds': _refund_pending, 'reviews': _pending_reviews,
          'low_stock': _low_stock, 'contacts': _new_contacts}


@dataclass
class Item:
    label: str
    url_name: str = ''
    icon: str = ''
    query: dict = field(default_factory=dict)
    badge: str = ''
    superuser_only: bool = False
    children: list = field(default_factory=list)
    # Được tính khi render
    url: str = ''
    active: bool = False
    open: bool = False
    badge_count: int = 0
    key: str = ''


def I(label, url_name='', icon='', query=None, badge='', superuser_only=False, children=None):  # noqa: E743
    return Item(label, url_name, icon, query or {}, badge, superuser_only, children or [])


MENU = [
    ('Tổng quan', [I('Dashboard', 'home', 'layout-dashboard')]),
    ('Sản phẩm', [
        I('Sản phẩm', icon='package', badge='low_stock', children=[
            I('Danh sách sản phẩm', 'product_list'),
            I('Thêm sản phẩm mới', 'product_add'),
            I('Sản phẩm sắp hết hàng', 'product_list', query={'stock': 'low'}, badge='low_stock'),
        ]),
        I('Danh mục', icon='folder-tree', children=[
            I('Cây danh mục', 'category_list'),
            I('Thêm danh mục', 'category_add'),
        ]),
        I('Dòng iPhone', icon='smartphone', children=[
            I('Danh sách dòng máy', 'iphone_list'),
            I('Thêm dòng máy', 'iphone_add'),
        ]),
        I('Linh kiện tương thích', icon='git-compare-arrows', children=[
            I('Danh sách tương thích', 'compat_list'),
            I('Thêm tương thích', 'compat_add'),
            I('Ma trận tương thích', 'compat_matrix'),
            I('Độ phủ linh kiện', 'compat_coverage'),
        ]),
        I('Thương hiệu', 'brand_list', 'badge-check'),
    ]),
    ('Kho hàng', [
        I('Tồn kho', icon='warehouse', children=[
            I('Tổng quan tồn kho', 'inventory'),
            I('Nhập kho', 'inventory_import'),
            I('Điều chỉnh kiểm kê', 'inventory_stocktake'),
            I('Lịch sử nhập xuất', 'inventory_history'),
        ]),
    ]),
    ('Bán hàng', [
        I('Đơn hàng', icon='shopping-bag', badge='orders', children=[
            I('Tất cả đơn hàng', 'order_list'),
            I('Chờ xác nhận', 'order_list', query={'status': 'pending'}, badge='orders'),
            I('Đang xử lý & đang giao', 'order_list', query={'status': 'processing'}),
            I('Đã giao', 'order_list', query={'status': 'delivered'}),
            I('Đã hủy', 'order_list', query={'status': 'cancelled'}),
        ]),
        I('Thanh toán', icon='credit-card', badge='refunds', children=[
            I('Danh sách giao dịch', 'payment_list'),
            I('Chờ hoàn tiền', 'payment_refunds', badge='refunds'),
        ]),
        I('Khách hàng', icon='users', children=[
            I('Danh sách khách hàng', 'customer_list'),
            I('Khách hàng bị khóa', 'customer_list', query={'state': 'locked'}),
        ]),
        I('Đánh giá', icon='star', badge='reviews', children=[
            I('Chờ duyệt', 'review_list', query={'status': 'pending'}, badge='reviews'),
            I('Đã duyệt', 'review_list', query={'status': 'approved'}),
            I('Đã ẩn', 'review_list', query={'status': 'hidden'}),
        ]),
        I('Khuyến mãi', icon='ticket-percent', children=[
            I('Mã giảm giá', 'coupon_list'),
            I('Thêm mã giảm giá', 'coupon_add'),
            I('Giảm giá sản phẩm hàng loạt', 'bulk_discount'),
        ]),
    ]),
    ('AI System', [
        I('iParts AI Assistant', icon='bot', children=[
            I('Cấu hình chatbot', 'chatbot_settings'),
            I('Lịch sử hội thoại', 'chat_history'),
            I('Thống kê chatbot', 'chatbot_stats'),
            I('Câu hỏi chưa có câu trả lời', 'chatbot_unanswered'),
        ]),
    ]),
    ('Báo cáo & thống kê', [
        I('Báo cáo', icon='bar-chart-3', children=[
            I('Doanh thu', 'report_revenue'),
            I('Sản phẩm', 'report_products'),
            I('Danh mục', 'report_categories'),
            I('Đơn hàng', 'report_orders'),
            I('Kho hàng', 'report_inventory'),
            I('Khách hàng', 'report_customers'),
        ]),
    ]),
    ('Nội dung website', [
        I('Nội dung', icon='layout-template', badge='contacts', children=[
            I('Banner trang chủ', 'banner_list'),
            I('Trang chính sách', 'page_list'),
            I('Câu hỏi thường gặp', 'faq_list'),
            I('Người đăng ký nhận tin', 'newsletter'),
            I('Tin nhắn liên hệ', 'contacts', badge='contacts'),
        ]),
    ]),
    ('Hệ thống', [
        I('Cài đặt', icon='settings', children=[
            I('Thông tin cửa hàng', 'store_settings', query={'tab': 'info'}),
            I('Vận chuyển & thanh toán', 'store_settings', query={'tab': 'shipping'}),
            I('Liên hệ & mạng xã hội', 'store_settings', query={'tab': 'contact'}),
            I('Trạng thái tích hợp', 'system_info'),
        ]),
        I('Tài khoản quản trị', 'admin_accounts', 'shield', superuser_only=True),
        I('Hồ sơ của tôi', 'profile', 'user-cog'),
    ]),
]

# Các trang con không có trong menu nhưng thuộc một mục menu (để tô sáng đúng mục cha)
ALIASES = {
    'product_edit': 'product_list', 'category_edit': 'category_list', 'category_delete': 'category_list', 'iphone_edit': 'iphone_list',
    'iphone_detail': 'iphone_list', 'brand_add': 'brand_list', 'brand_edit': 'brand_list', 'compat_edit': 'compat_list',
    'order_detail': 'order_list', 'payment_detail': 'payment_list', 'customer_detail': 'customer_list',
    'coupon_edit': 'coupon_list', 'coupon_detail': 'coupon_list', 'chat_detail': 'chat_history',
    'banner_add': 'banner_list', 'banner_edit': 'banner_list', 'page_add': 'page_list', 'page_edit': 'page_list',
    'faq_add': 'faq_list', 'faq_edit': 'faq_list',
}


def _url(item: Item) -> str:
    url = reverse(f'dashboard:{item.url_name}')
    if item.query:
        url += '?' + '&'.join(f'{k}={v}' for k, v in item.query.items())
    return url


def build_menu(request) -> tuple[list, list]:
    """Trả về (danh sách nhóm menu đã tính trạng thái, breadcrumb)."""
    match = getattr(request, 'resolver_match', None)
    current = ALIASES.get(match.url_name if match else '', match.url_name if match else '')
    counts = {}

    def badge(name):
        if name and name not in counts:
            counts[name] = BADGES[name]()
        return counts.get(name, 0)

    def score(item: Item) -> int:
        if item.url_name != current:
            return -1
        if any(request.GET.get(k) != str(v) for k, v in item.query.items()):
            return -1
        return 1 + len(item.query)

    groups, best, best_score = [], None, 0
    for title, items in MENU:
        visible = []
        for item in items:
            if item.superuser_only and not request.user.is_superuser:
                continue
            node = Item(**{**item.__dict__, 'children': []})
            node.key = item.label
            node.badge_count = badge(item.badge)
            if item.url_name:
                node.url = _url(item)
                s = score(item)
                if s > best_score:
                    best, best_score = (node, None, title), s
            for child in item.children:
                c = Item(**{**child.__dict__})
                c.url = _url(child)
                c.badge_count = badge(child.badge)
                node.children.append(c)
                s = score(child)
                if s > best_score:
                    best, best_score = (c, node, title), s
            visible.append(node)
        if visible:
            groups.append({'title': title, 'items': visible})
    crumbs = []
    if best:
        leaf, parent, title = best
        leaf.active = True
        if parent:
            parent.open = True
            crumbs = [(parent.label, parent.children[0].url), (leaf.label, leaf.url)]
        else:
            crumbs = [(leaf.label, leaf.url)]
    return groups, crumbs
