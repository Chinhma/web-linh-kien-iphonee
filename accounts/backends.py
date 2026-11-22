from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameBackend(ModelBackend):
    """Đăng nhập bằng email (không phân biệt hoa thường) hoặc tên đăng nhập."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = (username or kwargs.get('email') or '').strip()
        if not identifier or password is None:
            return None
        User = get_user_model()
        user = User.objects.filter(Q(email__iexact=identifier) | Q(username__iexact=identifier)).first()
        if user is None:
            User().set_password(password)  # Cân bằng thời gian xử lý, chống dò tài khoản
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
