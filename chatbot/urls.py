from django.urls import path

from . import views

app_name = 'chatbot'

urlpatterns = [
    path('api/chatbot/message/', views.api_message, name='api_message'),
    path('api/chatbot/history/', views.api_history, name='api_history'),
    path('api/chatbot/reset/', views.api_reset, name='api_reset'),
]
