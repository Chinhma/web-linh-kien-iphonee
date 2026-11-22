from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('trang/<slug:slug>/', views.page_view, name='page'),
    path('cau-hoi-thuong-gap/', views.faq_view, name='faq'),
    path('lien-he/', views.contact_view, name='contact'),
    path('api/newsletter/', views.api_newsletter, name='api_newsletter'),
]
