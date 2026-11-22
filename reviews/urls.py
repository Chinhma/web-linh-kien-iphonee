from django.urls import path

from . import views

app_name = 'reviews'

urlpatterns = [
    path('danh-gia/viet/', views.review_create, name='create'),
    path('tai-khoan/danh-gia/', views.my_reviews, name='mine'),
]
