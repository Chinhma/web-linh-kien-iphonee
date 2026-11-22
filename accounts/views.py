from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import PasswordResetForm
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST

from core.permissions import customer_required, safe_next_url
from core.utils import client_ip

from .forms import AddressForm, IPartsPasswordChangeForm, IPartsSetPasswordForm, LoginForm, ProfileForm, RegisterForm
from .models import MAX_ADDRESSES, Address
from .services import ensure_profile, login_locked_seconds, register_login_failure, reset_login_failures

BACKEND = 'accounts.backends.EmailOrUsernameBackend'


def _finish_login(request, user, remember: bool):
    from chatbot.services.assistant import attach_guest_conversations

    old_session_key = request.session.session_key
    login(request, user, backend=BACKEND)
    request.session.set_expiry(60 * 60 * 24 * 30 if remember else 0)
    if old_session_key and not user.is_staff:
        from chatbot.models import ChatConversation

        ChatConversation.objects.filter(user__isnull=True, session_key=old_session_key).update(user=user)
    attach_guest_conversations(request, user)


def authenticate_with_limit(request, form, staff_only: bool = False):
    """Xác thực có giới hạn đăng nhập sai (5 lần / 15 phút theo cặp IP + tài khoản). Trả về user hoặc None."""
    from django.contrib.auth import authenticate, get_user_model

    identifier = form.cleaned_data['identifier'].strip()
    ip = client_ip(request)
    locked = login_locked_seconds(ip, identifier)
    if locked:
        form.add_error(None, f'Bạn đã nhập sai quá nhiều lần. Vui lòng thử lại sau {locked // 60 + 1} phút.')
        return None
    User = get_user_model()
    candidate = User.objects.filter(Q(email__iexact=identifier) | Q(username__iexact=identifier)).first()
    if candidate and not candidate.is_active and candidate.check_password(form.cleaned_data['password']):
        form.add_error(None, 'Tài khoản đã bị khóa, vui lòng liên hệ cửa hàng.')
        return None
    user = authenticate(request, username=identifier, password=form.cleaned_data['password'])
    if user is None:
        register_login_failure(ip, identifier)
        form.add_error(None, 'Email/tên đăng nhập hoặc mật khẩu không đúng.')
        return None
    if staff_only and not user.is_staff:
        form.add_error(None, 'Tài khoản không có quyền quản trị.')
        return None
    reset_login_failures(ip, identifier)
    return user


def login_view(request):
    if request.user.is_authenticated:
        return redirect('products:home')
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = authenticate_with_limit(request, form)
        if user is not None:
            _finish_login(request, user, form.cleaned_data['remember'])
            messages.success(request, f'Xin chào {user.display_name}!')
            return redirect(safe_next_url(request, '/'))  # Admin đăng nhập ở trang khách thì ở lại website
    return render(request, 'accounts/login.html', {'form': form, 'next': safe_next_url(request, '')})


def register_view(request):
    if request.user.is_authenticated:
        return redirect('products:home')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        _finish_login(request, user, remember=False)
        messages.success(request, 'Chào mừng bạn đến với iParts Store!')
        from django.core.mail import send_mail

        send_mail('Chào mừng bạn đến với iParts Store',
                  f'Xin chào {user.display_name},\n\nCảm ơn bạn đã đăng ký tài khoản tại iParts Store.',
                  None, [user.email], fail_silently=True)
        return redirect(safe_next_url(request, '/'))
    return render(request, 'accounts/register.html', {'form': form, 'next': safe_next_url(request, '')})


@require_POST
def logout_view(request):
    """Đăng xuất chỉ bằng POST có CSRF token."""
    logout(request)
    messages.success(request, 'Bạn đã đăng xuất.')
    return redirect('products:home')


class IPartsPasswordResetView(auth_views.PasswordResetView):
    template_name = 'accounts/password_reset.html'
    email_template_name = 'emails/password_reset.txt'
    html_email_template_name = 'emails/password_reset.html'
    subject_template_name = 'emails/password_reset_subject.txt'
    success_url = reverse_lazy('accounts:password_reset_done')
    form_class = PasswordResetForm

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['email'].widget.attrs.update({'class': 'form-input', 'placeholder': 'ban@example.com'})
        return form


class IPartsPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')
    form_class = IPartsSetPasswordForm


# ------------------------------------------------------------------ Khu vực tài khoản
def _account_context(request, active: str, **extra):
    return {'account_active': active, **extra}


@customer_required
def overview(request):
    from cart.models import WishlistItem
    from orders.models import Order

    orders = Order.objects.filter(user=request.user)
    stats = orders.aggregate(
        total=Count('id'),
        processing=Count('id', filter=Q(status__in=['pending', 'confirmed', 'preparing', 'shipping'])),
        done=Count('id', filter=Q(status='delivered')),
    )
    return render(request, 'customer/overview.html', _account_context(
        request, 'overview', stats=stats, wishlist_count_total=WishlistItem.objects.filter(user=request.user).count(),
        recent_orders=orders.prefetch_related('items').order_by('-created_at')[:5],
    ))


@customer_required
def profile_view(request):
    ensure_profile(request.user)
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Đã cập nhật thông tin cá nhân.')
        return redirect('accounts:profile')
    return render(request, 'customer/profile.html', _account_context(request, 'profile', form=form))


@customer_required
def addresses(request):
    items = Address.objects.filter(user=request.user)
    return render(request, 'customer/addresses.html', _account_context(
        request, 'addresses', addresses=items, form=AddressForm(), max_addresses=MAX_ADDRESSES))


@customer_required
def address_save(request, pk=None):
    instance = get_object_or_404(Address, pk=pk, user=request.user) if pk else None
    if request.method != 'POST':
        return redirect('accounts:addresses')
    if instance is None and Address.objects.filter(user=request.user).count() >= MAX_ADDRESSES:
        messages.error(request, f'Mỗi tài khoản lưu tối đa {MAX_ADDRESSES} địa chỉ.')
        return redirect('accounts:addresses')
    form = AddressForm(request.POST, instance=instance)
    if form.is_valid():
        address = form.save(commit=False)
        address.user = request.user
        address.save()
        messages.success(request, 'Đã lưu địa chỉ.')
    else:
        errors = '; '.join(f'{form.fields[f].label if f in form.fields else ""}: {e[0]}' for f, e in form.errors.items())
        messages.error(request, f'Địa chỉ chưa hợp lệ – {errors}')
    return redirect(safe_next_url(request, reverse('accounts:addresses')))


@customer_required
@require_POST
def address_delete(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    was_default = address.is_default
    address.delete()
    if was_default:
        first = Address.objects.filter(user=request.user).first()
        if first:
            first.is_default = True
            first.save()
    messages.success(request, 'Đã xóa địa chỉ.')
    return redirect('accounts:addresses')


@customer_required
@require_POST
def address_default(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    address.is_default = True
    address.save()
    messages.success(request, 'Đã đặt làm địa chỉ mặc định.')
    return redirect('accounts:addresses')


def change_password(request):
    """Đổi mật khẩu (Customer và Admin). Tài khoản Google chưa có mật khẩu -> "Đặt mật khẩu"."""
    if not request.user.is_authenticated:
        return redirect(f"{reverse('accounts:login')}?next={request.path}")
    has_password = request.user.has_usable_password()
    form_class = IPartsPasswordChangeForm if has_password else IPartsSetPasswordForm
    form = form_class(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'Đổi mật khẩu thành công.' if has_password else 'Đặt mật khẩu thành công.')
        return redirect('dashboard:profile' if user.is_staff else 'accounts:change_password')
    template = 'dashboard/change_password.html' if request.user.is_staff else 'customer/change_password.html'
    return render(request, template, _account_context(request, 'password', form=form, has_password=has_password))


@customer_required
def chat_history(request):
    from chatbot.models import ChatConversation

    conversations = ChatConversation.objects.filter(user=request.user, message_count__gt=0)
    page = Paginator(conversations, 10).get_page(request.GET.get('page'))
    selected = None
    if request.GET.get('id'):
        selected = conversations.filter(pk=request.GET.get('id')).first()
        if selected is None:
            raise Http404
    return render(request, 'customer/chat_history.html', _account_context(
        request, 'chat', page_obj=page, selected=selected,
        chat_messages=selected.messages.all() if selected else []))
