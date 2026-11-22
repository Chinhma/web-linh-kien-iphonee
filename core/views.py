import json

from django import forms
from django.contrib import messages
from django.core.cache import cache
from django.core.validators import validate_email
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import FAQ, ContactMessage, NewsletterSubscriber, Page
from .utils import api_error, api_ok, client_ip


def page_view(request, slug):
    page = get_object_or_404(Page, slug=slug, is_published=True)
    return render(request, 'pages/page.html', {'page': page, 'breadcrumbs': [(page.title, None)]})


def faq_view(request):
    return render(request, 'pages/faq.html', {'faqs': FAQ.objects.filter(is_active=True),
                                              'breadcrumbs': [('Câu hỏi thường gặp', None)]})


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'phone', 'message']
        widgets = {'message': forms.Textarea(attrs={'rows': 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-input'


def contact_view(request):
    initial = {}
    if request.user.is_authenticated:
        initial = {'name': request.user.display_name, 'email': request.user.email, 'phone': request.user.phone}
    form = ContactForm(request.POST or None, initial=initial)
    if request.method == 'POST':
        key = f'contact-rate:{client_ip(request)}'
        if cache.get(key, 0) >= 5:
            messages.error(request, 'Bạn đã gửi quá nhiều tin nhắn, vui lòng thử lại sau.')
        elif form.is_valid():
            form.save()
            cache.set(key, cache.get(key, 0) + 1, 3600)
            messages.success(request, 'Cảm ơn bạn! iParts Store sẽ phản hồi sớm nhất.')
            return redirect('core:contact')
    return render(request, 'pages/contact.html', {'form': form, 'breadcrumbs': [('Liên hệ', None)]})


@require_POST
def api_newsletter(request):
    key = f'newsletter-rate:{client_ip(request)}'
    if cache.get(key, 0) >= 5:
        return api_error('RATE_LIMITED', 'Bạn thao tác quá nhanh, vui lòng thử lại sau.', status=429)
    cache.set(key, cache.get(key, 0) + 1, 600)
    try:
        email = str(json.loads(request.body or '{}').get('email', '')).strip().lower()
        validate_email(email)
    except (ValueError, forms.ValidationError):
        return api_error('INVALID_EMAIL', 'Email không hợp lệ.', errors={'email': 'Email không hợp lệ.'})
    _, created = NewsletterSubscriber.objects.get_or_create(email=email)
    if not created:
        return api_error('DUPLICATE', 'Email này đã đăng ký nhận tin trước đó.', status=409)
    return api_ok(message='Đăng ký nhận tin thành công. Cảm ơn bạn!')


def error_403(request, exception=None):
    return render(request, '403.html', status=403)


def error_404(request, exception=None):
    return render(request, '404.html', status=404)


def error_500(request):
    # Không dùng context processor phức tạp để tránh lỗi lồng nhau
    from django.http import HttpResponseServerError
    from django.template import loader

    return HttpResponseServerError(loader.get_template('500.html').render({}))
