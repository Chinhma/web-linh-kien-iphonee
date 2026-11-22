import json

from django.views.decorators.http import require_GET, require_POST

from core.utils import api_error, api_ok, to_int

from .models import ChatbotSetting
from .services import gemini_client
from .services.assistant import (MAX_MESSAGE_LENGTH, RateLimited, check_rate_limit, conversation_queryset,
                                 handle_message, history_payload)


def _ensure_session(request):
    """Đảm bảo khách vãng lai có session ổn định (để lưu hội thoại và giới hạn tần suất).

    Đánh dấu session đã thay đổi để SessionMiddleware luôn gửi cookie về trình duyệt.
    """
    if not request.session.session_key:
        request.session['chatbot'] = True
        request.session.save()
        request.session.modified = True


@require_POST
def api_message(request):
    """POST /api/chatbot/message/ – view mỏng: kiểm tra đầu vào, rate limit, gọi service."""
    _ensure_session(request)
    setting = ChatbotSetting.get_solo()
    if not setting.is_enabled:
        return api_error('CHATBOT_DISABLED', 'iParts AI Assistant đang tạm ngưng, vui lòng liên hệ hotline.', status=503)
    try:
        data = json.loads(request.body or '{}')
    except (ValueError, UnicodeDecodeError):
        return api_error('INVALID', 'Dữ liệu không hợp lệ.')
    message = str(data.get('message', '')).strip()
    if not message:
        return api_error('EMPTY_MESSAGE', 'Vui lòng nhập câu hỏi.')
    if len(message) > MAX_MESSAGE_LENGTH:
        return api_error('TOO_LONG', f'Câu hỏi tối đa {MAX_MESSAGE_LENGTH} ký tự.')
    try:
        check_rate_limit(request)
    except RateLimited:
        return api_error('RATE_LIMITED', 'Bạn gửi hơi nhanh, vui lòng thử lại sau ít phút.', status=429)
    return api_ok(handle_message(request, message, to_int(data.get('conversation_id'))))


@require_GET
def api_history(request):
    """Chỉ trả hội thoại thuộc user/session hiện tại."""
    _ensure_session(request)
    setting = ChatbotSetting.get_solo()
    qs = conversation_queryset(request)
    conversation_id = to_int(request.GET.get('conversation_id'))
    conversation = qs.filter(pk=conversation_id).first() if conversation_id else None
    if conversation is None and request.user.is_authenticated and not conversation_id:
        conversation = qs.filter(message_count__gt=0).order_by('-last_message_at').first()
    return api_ok({
        'enabled': setting.is_enabled,
        'mode': 'ai' if gemini_client.is_configured() else 'basic',
        'greeting': setting.greeting_message,
        'suggestions': setting.suggested_questions or [],
        'conversation_id': conversation.pk if conversation else None,
        'messages': history_payload(conversation, request.user) if conversation else [],
    })


@require_POST
def api_reset(request):
    _ensure_session(request)
    return api_ok(message='Đã bắt đầu cuộc trò chuyện mới.')
