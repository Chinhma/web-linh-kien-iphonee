from django.urls import path

from . import views

app_name = 'cart'

urlpatterns = [
    path('gio-hang/', views.cart_page, name='cart'),
    path('yeu-thich/', views.wishlist_page, name='wishlist'),
    path('api/cart/add/', views.api_add, name='api_add'),
    path('api/cart/update/', views.api_update, name='api_update'),
    path('api/cart/remove/', views.api_remove, name='api_remove'),
    path('api/cart/select/', views.api_select, name='api_select'),
    path('api/cart/coupon/', views.api_coupon, name='api_coupon'),
    path('api/cart/summary/', views.api_summary, name='api_summary'),
    path('api/wishlist/toggle/', views.api_wishlist_toggle, name='api_wishlist_toggle'),
    path('api/wishlist/add-all/', views.api_wishlist_add_all, name='api_wishlist_add_all'),
]
