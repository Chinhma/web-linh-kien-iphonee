from django.urls import path

from . import views

app_name = 'payments'

urlpatterns = [
    path('thanh-toan/don/<str:code>/', views.start_payment, name='start'),
    path('thanh-toan/vnpay/return/', views.vnpay_return, name='vnpay_return'),
    path('thanh-toan/vnpay/ipn/', views.vnpay_ipn, name='vnpay_ipn'),
    path('thanh-toan/momo/return/', views.momo_return, name='momo_return'),
    path('thanh-toan/momo/ipn/', views.momo_ipn, name='momo_ipn'),
]
