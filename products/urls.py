from django.urls import path

from . import views

app_name = 'products'

urlpatterns = [
    path('', views.home, name='home'),
    path('san-pham/', views.product_list, name='list'),
    path('san-pham/<slug:slug>/', views.product_detail, name='detail'),
    path('danh-muc/<slug:slug>/', views.category_detail, name='category'),
    path('khuyen-mai/', views.sale_list, name='sale'),
    path('san-pham-moi/', views.new_list, name='new'),
    path('tra-cuu-tuong-thich/', views.compatibility_page, name='compatibility'),
    path('api/compatibility/', views.api_compatibility, name='api_compatibility'),
    path('api/products/<int:pk>/check/', views.api_product_check, name='api_product_check'),
    path('api/products/<int:pk>/variant/', views.api_product_variant, name='api_product_variant'),
    path('api/iphone-models/', views.api_iphone_models, name='api_iphone_models'),
    path('api/categories/', views.api_categories, name='api_categories'),
    path('api/search/suggest/', views.api_search_suggest, name='api_search_suggest'),
]
