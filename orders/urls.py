from django.urls import path

from . import views

app_name = 'orders'

urlpatterns = [
    path('thanh-toan/', views.checkout, name='checkout'),
    path('dat-hang-thanh-cong/<str:code>/', views.order_success, name='success'),
    path('tai-khoan/don-hang/', views.order_list, name='list'),
    path('tai-khoan/don-hang/<str:code>/', views.order_detail, name='detail'),
    path('tai-khoan/don-hang/<str:code>/huy/', views.order_cancel, name='cancel'),
    path('tai-khoan/don-hang/<str:code>/mua-lai/', views.order_reorder, name='reorder'),
]
