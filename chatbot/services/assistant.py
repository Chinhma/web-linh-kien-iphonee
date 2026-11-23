"""Điều phối hội thoại iParts AI Assistant: lưu tin nhắn, gọi Gemini (hoặc dự phòng), dựng Product Card từ DB."""

import logging
import time

from django.core.cache import cache
from django.utils import timezone

from chatbot.models import ChatbotSetting, ChatConversation, ChatMessage
from chatbot.prompts import build_system_prompt
from core.utils import client_ip
from products.models import Product
from products.selectors import with_card_data
from products.services import resolve_category, resolve_iphone_model

from . import fallback, gemini_client, guard, tools

logger = logging.getLogger('iparts')
HISTORY_LIMIT = 10
MAX_MESSAGE_LENGTH = 1000


class RateLimited(Exception):
    pass


def check_rate_limit(request) -> None:
    """Giới hạn số tin nhắn mỗi giờ theo user/session + IP (cấu hình trong ChatbotSetting)."""
    setting = ChatbotSetting.get_solo()
    user = request.user
    if user.is_authenticated:
        identity, limit = f'u{user.pk}', setting.max_messages_per_hour_customer
    else:
        identity, limit = f's{request.session.session_key}', setting.max_messages_per_hour_guest
    for key in (f'chat-rate:{identity}', f'chat-rate-ip:{client_ip(request)}'):
        count = cache.get(key, 0)
        max_allowed = limit if 'ip' not in key else max(limit, setting.max_messages_per_hour_customer) * 2
        if count >= max_allowed:
            raise RateLimited()
    for key in (f'chat-rate:{identity}', f'chat-rate-ip:{client_ip(request)}'):
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, 3600)


def conversation_queryset(request):
    """Chỉ hội thoại thuộc user hoặc session hiện tại."""
    if request.user.is_authenticated:
        return ChatConversation.objects.filter(user=request.user)
    return ChatConversation.objects.filter(user__isnull=True, session_key=request.session.session_key or '-')


def get_or_create_conversation(request, conversation_id=None) -> ChatConversation:
    qs = conversation_queryset(request)
    conversation = qs.filter(pk=conversation_id).first() if conversation_id else None
    if conversation is None:
        conversation = ChatConversation.objects.create(
            user=request.user if request.user.is_authenticated else None,
            session_key=request.session.session_key or '',
        )
    return conversation


def product_cards(product_ids: list[int], notes: dict | None = None) -> list[dict]:
    """Dựng Product Card từ DB theo ID (không lấy từ chữ AI viết)."""
    unique_ids = list(dict.fromkeys(product_ids))[:8]
    products = {p.pk: p for p in with_card_data(Product.objects.filter(pk__in=unique_ids, status=Product.Status.ACTIVE))}
    cards = []
    for pid in unique_ids:
        p = products.get(pid)
        if p is None:
            continue
        cards.append({
            'id': p.pk, 'name': p.name, 'sku': p.sku, 'price': p.effective_price,
            'original_price': p.price if p.is_on_sale else None, 'image': p.image_url,
            'stock_status': p.stock_status, 'stock_label': p.stock_label, 'url': p.get_absolute_url(),
            'compatibility_note': (notes or {}).get(pid, ''),
        })
    return cards


def _notes_from_results(tool_results) -> dict:
    notes = {}
    for item in tool_results or []:
        result = item.get('result') or {}
        for product in result.get('products', []) if isinstance(result, dict) else []:
            if isinstance(product, dict) and product.get('compatibility_note'):
                notes[product['id']] = product['compatibility_note']
    return notes


def _context_model(history: list[dict], message: str):
    """Dòng máy của câu hiện tại, nếu không có thì lấy từ các tin nhắn trước của khách (nhớ ngữ cảnh)."""
    resolved = resolve_iphone_model(tools.normalize_query(message))
    if resolved['model'] and not resolved['ambiguous']:
        return resolved['model'].name, resolved
    for m in reversed(history[:-1]):
        if m['role'] == 'user':
            prev = resolve_iphone_model(tools.normalize_query(m['content']))
            if prev['model'] and not prev['ambiguous']:
                return prev['model'].name, resolved
    return (resolved['model'].name if resolved['model'] else ''), resolved


def _suggestions(result: dict, meta: dict, resolved: dict | None = None) -> list[str]:
    """Gợi ý câu hỏi tiếp theo theo đúng ngữ cảnh câu trả lời (không cố định)."""
    model = meta.get('iphone_model', '')
    category = meta.get('category', '')
    tool_results = result.get('tool_results') or []
    out: list[str] = []
    # Dòng máy mơ hồ -> gợi ý luôn từng phiên bản để khách bấm chọn
    candidates = []
    for item in tool_results:
        res = item.get('result') if isinstance(item.get('result'), dict) else {}
        info = res.get('iphone_model')
        if isinstance(info, dict) and info.get('ambiguous'):
            candidates = info.get('candidates', [])
    if not candidates and resolved and resolved.get('ambiguous') and not result.get('product_ids'):
        candidates = [m.name for m in resolved['candidates']]
    if candidates:
        label = category or 'Linh kiện'
        return [f'{label} {name}' for name in candidates[:4]]
    products = []
    for item in tool_results:
        res = item.get('result') if isinstance(item.get('result'), dict) else {}
        products.extend(p for p in res.get('products', []) if isinstance(p, dict))
    if len(products) >= 2:
        out.append(f'So sánh {products[0]["name"]} và {products[1]["name"]}')
    if products:
        out.append(f'{products[0]["name"]} bảo hành bao lâu?')
    if meta.get('no_result'):
        if model:
            out.append(f'{model} có những linh kiện nào?')
        out.append('Sản phẩm nào đang được giảm giá?')
    if model:
        for cat in ('Pin', 'Màn hình', 'Chân sạc', 'Camera sau'):
            if cat.lower() != category.lower() and len(out) < 3:
                out.append(f'{cat} {model} giá bao nhiêu?')
    intent = result.get('intent', '')
    if intent == 'store_policy':
        out += ['Phí vận chuyển bao nhiêu?', 'Chính sách đổi trả thế nào?']
    if category and not model:
        out.insert(0, f'{category} cho iPhone 13 Pro')
    unique = list(dict.fromkeys(x for x in out if x))
    return unique[:3] or ['Màn hình nào tương thích với iPhone 13 Pro?', 'Sản phẩm nào đang được giảm giá?',
                          'Pin iPhone 11 giá bao nhiêu?']


def handle_message(request, message: str, conversation_id=None) -> dict:
    """Xử lý một câu hỏi và trả về dữ liệu cho API: reply, products, actions, suggestions."""
    started = time.monotonic()
    user = request.user if request.user.is_authenticated else None
    conversation = get_or_create_conversation(request, conversation_id)
    ChatMessage.objects.create(conversation=conversation, role=ChatMessage.Role.USER, content=message)

    history = [{'role': m.role, 'content': m.content}
               for m in conversation.messages.filter(is_error=False).order_by('-created_at', '-id')[:HISTORY_LIMIT]][::-1]
    mode = 'ai'
    is_error = False
    context_model, resolved = _context_model(history, message)
    category = resolve_category(tools.normalize_query(message))
    try:
        if guard.is_injection(message):
            # Chặn ngay, không gửi cho Gemini
            result = {'reply': fallback.REFUSE_REPLY, 'intent': 'refuse', 'tool_calls': [], 'tool_results': [],
                      'product_ids': [], 'meta': {}}
        else:
            if not gemini_client.is_configured():
                raise gemini_client.GeminiUnavailable('not_configured')
            try:
                result = gemini_client.generate_reply(build_system_prompt(), history, user=user,
                                                      force_tools=guard.needs_store_data(message))
            except gemini_client.PriceMismatch as exc:
                # AI vẫn viết sai giá -> trả lời bằng dữ liệu tool, không dùng chữ của AI
                result = fallback.from_tool_results(exc.state['tool_results'], message, user=user)
            tool_results = result.get('tool_results') or []
            intent = result['tool_calls'][0]['name'] if result.get('tool_calls') else result.get('intent', 'general')
            intent = {'check_compatibility': 'compatibility_lookup', 'search_products': 'product_search',
                      'get_store_policy': 'store_policy', 'get_promotions': 'promotions'}.get(intent, intent)
            # Không có kết quả = đã tra dữ liệu nhưng mọi tool đều báo found=false (ghi vào "câu chưa trả lời được")
            no_result = bool(tool_results) and not any(
                isinstance(r.get('result'), dict) and r['result'].get('found', True) for r in tool_results)
            result.update({
                'intent': intent,
                'meta': {'iphone_model': context_model, 'category': category.name if category else '',
                         'no_result': no_result},
                'needs_login': any(r['result'].get('error') == 'LOGIN_REQUIRED' for r in tool_results
                                   if isinstance(r.get('result'), dict)),
            })
    except gemini_client.GeminiBlocked:
        result = {'reply': 'Xin lỗi, mình không thể hỗ trợ nội dung này. Bạn cần tìm linh kiện iPhone nào không?',
                  'intent': 'blocked', 'tool_calls': [], 'tool_results': [], 'product_ids': [], 'meta': {}}
    except gemini_client.GeminiUnavailable as exc:
        is_error = str(exc) != 'not_configured'
        mode = 'basic'
        result = fallback.answer(message, user=user)
    except Exception:  # Không để lỗi bất ngờ gây 500 cho widget
        logger.exception('Lỗi chatbot không mong muốn')
        is_error, mode = True, 'basic'
        try:
            result = fallback.answer(message, user=user)
        except Exception:
            logger.exception('Fallback cũng lỗi')
            result = {'reply': 'Xin lỗi, mình đang gặp chút trục trặc. Bạn thử lại sau ít phút hoặc gọi hotline giúp mình nhé.',
                      'intent': 'error', 'tool_calls': [], 'tool_results': [], 'product_ids': [], 'meta': {}}

    cards = product_cards(result.get('product_ids', []), _notes_from_results(result.get('tool_results')))
    actions = []
    is_customer = user is not None and not user.is_staff
    for card in cards[:3]:
        if is_customer:
            actions.append({'type': 'add_to_cart', 'product_id': card['id'], 'label': 'Thêm vào giỏ'})
    if cards and user is None:
        actions.append({'type': 'login', 'url': '/dang-nhap/', 'label': 'Đăng nhập để mua hàng'})
    if result.get('needs_login') and user is None and not cards:
        actions.append({'type': 'login', 'url': '/dang-nhap/', 'label': 'Đăng nhập'})
    if result.get('link'):
        actions.append({'type': 'open_url', 'url': result['link'], 'label': 'Xem tất cả kết quả tra cứu'})

    latency = int((time.monotonic() - started) * 1000)
    meta = {**result.get('meta', {}), 'mode': mode}
    if not meta.get('iphone_model') and context_model:
        meta['iphone_model'] = context_model
    reply_msg = ChatMessage.objects.create(
        conversation=conversation, role=ChatMessage.Role.ASSISTANT, content=result['reply'],
        products=[c['id'] for c in cards], intent=result.get('intent', '')[:50],
        tool_calls=result.get('tool_calls', []), meta=meta, latency_ms=latency, is_error=is_error,
    )
    conversation.message_count = conversation.messages.count()
    conversation.last_message_at = timezone.now()
    if not conversation.title:
        conversation.title = message[:60]
    if is_error:
        conversation.has_error = True
    if user and not conversation.user_id:
        conversation.user = user
    conversation.save()
    return {
        'conversation_id': conversation.pk,
        'message_id': reply_msg.pk,
        'reply': result['reply'],
        'products': cards,
        'actions': actions,
        'suggestions': _suggestions(result, meta, resolved),
        'mode': mode,
        'created_at': reply_msg.created_at.isoformat(),
    }


def history_payload(conversation: ChatConversation, user=None) -> list[dict]:
    is_customer = user is not None and user.is_authenticated and not user.is_staff
    messages = []
    for m in conversation.messages.order_by('created_at', 'id'):
        item = {'role': m.role, 'content': m.content, 'created_at': m.created_at.isoformat(), 'products': [], 'actions': []}
        if m.role == ChatMessage.Role.ASSISTANT and m.products:
            item['products'] = product_cards(m.products)
            if is_customer:
                item['actions'] = [{'type': 'add_to_cart', 'product_id': c['id'], 'label': 'Thêm vào giỏ'}
                                   for c in item['products'][:3]]
        messages.append(item)
    return messages


def attach_guest_conversations(request, user) -> None:
    """Khi Guest đăng nhập: gắn các hội thoại của session vào tài khoản."""
    key = request.session.session_key
    if key:
        ChatConversation.objects.filter(user__isnull=True, session_key=key).update(user=user)
