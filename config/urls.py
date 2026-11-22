from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView

urlpatterns = [
    # Django admin mặc định: chỉ Superuser, dự phòng kỹ thuật. Giao diện quản lý chính là /quan-tri/
    path('django-admin/', admin.site.urls),
    re_path(r'^(admin|dashboard)(/.*)?$', RedirectView.as_view(url='/quan-tri/', permanent=False)),
    path('accounts/', include('allauth.urls')),
    path('quan-tri/', include('dashboard.urls')),
    path('', include('accounts.urls')),
    path('', include('cart.urls')),
    path('', include('orders.urls')),
    path('', include('payments.urls')),
    path('', include('reviews.urls')),
    path('', include('chatbot.urls')),
    path('', include('core.urls')),
    path('', include('products.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = 'core.views.error_403'
handler404 = 'core.views.error_404'
handler500 = 'core.views.error_500'
