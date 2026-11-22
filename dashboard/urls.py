from django.urls import path

from .views import catalog, extra, home, sales, system
from .views.crud import make_views

app_name = 'dashboard'


def crud_urls(key: str, prefix: str):
    list_view, form_view, delete_view = make_views(key)
    return [
        path(f'{prefix}/', list_view, name=f'{key}_list'),
        path(f'{prefix}/them/', form_view, name=f'{key}_add'),
        path(f'{prefix}/<int:pk>/sua/', form_view, name=f'{key}_edit'),
        path(f'{prefix}/<int:pk>/xoa/', delete_view, name=f'{key}_delete'),
    ]


urlpatterns = [
    path('dang-nhap/', home.admin_login, name='login'),
    path('dang-xuat/', home.admin_logout, name='logout'),
    path('', home.home, name='home'),
    path('api/stats/<slug:kind>/', home.stats_api, name='stats_api'),
    path('api/thong-bao/', home.notifications_api, name='notifications'),
    path('api/tim-kiem/', home.quick_search, name='quick_search'),
    # Sản phẩm
    path('san-pham/', catalog.product_list, name='product_list'),
    path('san-pham/them/', catalog.product_form, name='product_add'),
    path('san-pham/<int:pk>/sua/', catalog.product_form, name='product_edit'),
    path('san-pham/<int:pk>/xoa/', catalog.product_delete, name='product_delete'),
    path('san-pham/<int:pk>/nhan-ban/', catalog.product_duplicate, name='product_duplicate'),
    path('san-pham/<int:pk>/noi-bat/', catalog.product_toggle_featured, name='product_toggle_featured'),
    path('san-pham/hang-loat/', catalog.product_bulk, name='product_bulk'),
    path('san-pham/goi-y-sku/', catalog.product_suggest_sku, name='product_suggest_sku'),
    path('danh-muc/', catalog.category_tree, name='category_list'),
    *crud_urls('category', 'danh-muc')[1:3],
    path('danh-muc/<int:pk>/xoa/', catalog.category_delete, name='category_delete'),
    *crud_urls('brand', 'thuong-hieu'),
    path('dong-iphone/', catalog.iphone_list, name='iphone_list'),
    path('dong-iphone/<int:pk>/', catalog.iphone_detail, name='iphone_detail'),
    *crud_urls('iphone', 'dong-iphone')[1:],
    # Tương thích
    path('tuong-thich/', catalog.compat_list, name='compat_list'),
    path('tuong-thich/them/', catalog.compat_add, name='compat_add'),
    path('tuong-thich/<int:pk>/sua/', catalog.compat_edit, name='compat_edit'),
    path('tuong-thich/hang-loat/', catalog.compat_bulk, name='compat_bulk'),
    path('tuong-thich/ma-tran/', catalog.compat_matrix, name='compat_matrix'),
    path('tuong-thich/ma-tran/doi/', catalog.compat_matrix_toggle, name='compat_matrix_toggle'),
    path('tuong-thich/do-phu/', extra.compat_coverage, name='compat_coverage'),
    # Kho
    path('kho-hang/', catalog.inventory_overview, name='inventory'),
    path('kho-hang/nhap-kho/', extra.inventory_import, name='inventory_import'),
    path('kho-hang/kiem-ke/', extra.inventory_stocktake, name='inventory_stocktake'),
    path('kho-hang/lich-su/', catalog.inventory_history, name='inventory_history'),
    # Bán hàng
    path('don-hang/', sales.order_list, name='order_list'),
    path('don-hang/hang-loat/', sales.order_bulk, name='order_bulk'),
    path('don-hang/<str:code>/', sales.order_detail, name='order_detail'),
    path('don-hang/<str:code>/trang-thai/', sales.order_change_status, name='order_change_status'),
    path('don-hang/<str:code>/hoan-tien/', sales.order_refunded, name='order_refunded'),
    path('don-hang/<str:code>/ghi-chu/', sales.order_add_note, name='order_add_note'),
    path('don-hang/<str:code>/in/', sales.order_print, name='order_print'),
    path('thanh-toan/', sales.payment_list, name='payment_list'),
    path('thanh-toan/<int:pk>/', sales.payment_detail, name='payment_detail'),
    path('thanh-toan/cho-hoan-tien/', extra.payment_refunds, name='payment_refunds'),
    path('khach-hang/', sales.customer_list, name='customer_list'),
    path('khach-hang/<int:pk>/', sales.customer_detail, name='customer_detail'),
    path('khach-hang/<int:pk>/khoa/', sales.customer_toggle_active, name='customer_toggle_active'),
    path('khach-hang/<int:pk>/dat-lai-mat-khau/', sales.customer_send_reset, name='customer_send_reset'),
    path('danh-gia/', sales.review_list, name='review_list'),
    path('danh-gia/thao-tac/', sales.review_action, name='review_action'),
    *crud_urls('coupon', 'ma-giam-gia'),
    path('ma-giam-gia/<int:pk>/', sales.coupon_detail, name='coupon_detail'),
    path('khuyen-mai/giam-gia-hang-loat/', extra.bulk_discount, name='bulk_discount'),
    # AI
    path('ai/cau-hinh/', system.chatbot_settings, name='chatbot_settings'),
    path('ai/kiem-tra/', system.chatbot_test, name='chatbot_test'),
    path('ai/hoi-thoai/', system.chat_history, name='chat_history'),
    path('ai/hoi-thoai/<int:pk>/', system.chat_detail, name='chat_detail'),
    path('ai/thong-ke/', extra.chatbot_stats, name='chatbot_stats'),
    path('ai/chua-tra-loi/', extra.chatbot_unanswered, name='chatbot_unanswered'),
    # Báo cáo
    path('bao-cao/doanh-thu/', system.report_revenue, name='report_revenue'),
    path('bao-cao/san-pham/', system.report_products, name='report_products'),
    path('bao-cao/danh-muc/', system.report_categories, name='report_categories'),
    path('bao-cao/don-hang/', system.report_orders, name='report_orders'),
    path('bao-cao/kho-hang/', system.report_inventory, name='report_inventory'),
    path('bao-cao/khach-hang/', extra.report_customers, name='report_customers'),
    # Nội dung
    path('api/sap-xep/<slug:model>/', extra.reorder, name='reorder'),
    path('api/xem-truoc-noi-dung/', extra.markdown_preview, name='markdown_preview'),
    *crud_urls('banner', 'banner'),
    *crud_urls('page', 'trang-noi-dung'),
    *crud_urls('faq', 'faq'),
    path('newsletter/', system.newsletter_list, name='newsletter'),
    path('newsletter/<int:pk>/xoa/', system.newsletter_delete, name='newsletter_delete'),
    path('lien-he/', system.contact_list, name='contacts'),
    path('lien-he/<int:pk>/da-doc/', system.contact_read, name='contact_read'),
    # Hệ thống
    path('tai-khoan-admin/', system.admin_accounts, name='admin_accounts'),
    path('tai-khoan-admin/<int:pk>/', system.admin_account_action, name='admin_account_action'),
    path('cai-dat/', system.store_settings, name='store_settings'),
    path('he-thong/', system.system_info, name='system_info'),
    path('ho-so/', extra.profile, name='profile'),
    path('api/san-pham/', extra.api_product_suggest, name='api_product_suggest'),
    path('api/bat-tat/<slug:model>/<int:pk>/', extra.toggle_field, name='toggle_field'),
]
