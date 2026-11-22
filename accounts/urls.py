from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('dang-nhap/', views.login_view, name='login'),
    path('dang-ky/', views.register_view, name='register'),
    path('dang-xuat/', views.logout_view, name='logout'),
    path('quen-mat-khau/', views.IPartsPasswordResetView.as_view(), name='password_reset'),
    path('quen-mat-khau/da-gui/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html'), name='password_reset_done'),
    path('dat-lai-mat-khau/<uidb64>/<token>/', views.IPartsPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('dat-lai-mat-khau/hoan-tat/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html'), name='password_reset_complete'),
    path('tai-khoan/', views.overview, name='overview'),
    path('tai-khoan/thong-tin/', views.profile_view, name='profile'),
    path('tai-khoan/dia-chi/', views.addresses, name='addresses'),
    path('tai-khoan/dia-chi/them/', views.address_save, name='address_add'),
    path('tai-khoan/dia-chi/<int:pk>/sua/', views.address_save, name='address_edit'),
    path('tai-khoan/dia-chi/<int:pk>/xoa/', views.address_delete, name='address_delete'),
    path('tai-khoan/dia-chi/<int:pk>/mac-dinh/', views.address_default, name='address_default'),
    path('tai-khoan/doi-mat-khau/', views.change_password, name='change_password'),
    path('tai-khoan/tro-chuyen/', views.chat_history, name='chat_history'),
]
