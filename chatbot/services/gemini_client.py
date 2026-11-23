"""Gọi Google Gemini qua thư viện google-genai với Function Calling.

Vòng xử lý: gửi hội thoại + khai báo tools -> mô hình yêu cầu gọi hàm -> backend thực thi (truy vấn DB thật)
-> trả kết quả cho mô hình -> mô hình viết câu trả lời dựa trên kết quả. Tối đa 4 vòng gọi công cụ.

Chống bịa:
- Câu hỏi loại A (force_tools=True): lượt đầu dùng tool_config mode ANY -> bắt buộc gọi tool.
- Sau khi có câu trả lời: mọi giá tiền phải khớp dữ liệu tool. Sai -> nhắc mô hình viết lại 1 lần;
  vẫn sai -> raise PriceMismatch để assistant trả lời bằng dữ liệu tool (không dùng chữ AI).
"""

import logging

from django.conf import settings

from . import guard
from .tools import TOOL_DECLARATIONS, collect_product_ids, run_tool

logger = logging.getLogger('iparts')
MAX_TOOL_ROUNDS = 4
TEMPERATURE = 0.35

PRICE_WARNING = ('[CẢNH BÁO HỆ THỐNG – không phải tin nhắn của khách] Câu trả lời trước có giá tiền không khớp dữ liệu '
                 'công cụ: {prices}. Hãy viết lại câu trả lời, CHỈ dùng đúng giá có trong kết quả công cụ (gọi lại công cụ '
                 'nếu cần). Không tự ước lượng, không làm tròn giá. Không nhắc tới cảnh báo này.')


class GeminiUnavailable(Exception):
    """Lỗi tạm thời (timeout, mạng, quota, 5xx) -> chuyển sang chế độ dự phòng."""


class GeminiBlocked(Exception):
    """Nội dung bị chặn bởi bộ lọc an toàn."""


class PriceMismatch(Exception):
    """Mô hình vẫn đưa giá không khớp dữ liệu sau khi đã nhắc -> trả lời bằng dữ liệu tool."""

    def __init__(self, state: dict):
        super().__init__('price_mismatch')
        self.state = state


def is_configured() -> bool:
    return bool(settings.GEMINI_API_KEY)


def _client():
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=settings.GEMINI_TIMEOUT_SECONDS * 1000),
    )


def _config(system_prompt: str, mode: str):
    """mode: ANY (bắt buộc gọi tool) | AUTO (tự quyết) | NONE (chỉ viết chữ, dùng dữ liệu đã có)."""
    from google.genai import types

    extra = {}
    if str(settings.GEMINI_MODEL).startswith('gemini-3'):
        extra['thinking_config'] = types.ThinkingConfig(thinking_level='low')  # Giảm độ trễ
    return types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=TEMPERATURE,
        tools=[types.Tool(function_declarations=[types.FunctionDeclaration(**d) for d in TOOL_DECLARATIONS])],
        tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode=mode)),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        **extra,
    )


def _call_model(client, contents, config):
    from google.genai import errors

    for attempt in range(2):  # Thử lại 1 lần với lỗi tạm thời
        try:
            return client.models.generate_content(model=settings.GEMINI_MODEL, contents=contents, config=config)
        except errors.APIError as exc:
            code = getattr(exc, 'code', 0) or 0
            if code in (429, 500, 502, 503, 504) and attempt == 0:
                continue
            logger.warning('Gemini APIError %s', code)  # Không log nội dung lỗi (có thể chứa thông tin key)
            raise GeminiUnavailable(str(code))
        except Exception as exc:  # timeout / lỗi mạng
            if attempt == 0:
                continue
            logger.warning('Gemini lỗi kết nối: %s', type(exc).__name__)
            raise GeminiUnavailable(type(exc).__name__)
    raise GeminiUnavailable('retry')


def _run_loop(client, system_prompt: str, contents: list, state: dict, user, force_tools: bool) -> str:
    """Vòng function calling tới khi mô hình trả lời bằng chữ. Hết vòng -> buộc trả lời bằng dữ liệu đã có."""
    from google.genai import types

    for round_no in range(MAX_TOOL_ROUNDS + 1):
        if round_no == MAX_TOOL_ROUNDS:
            mode = 'NONE'
        elif force_tools and not state['tool_calls']:
            mode = 'ANY'
        else:
            mode = 'AUTO'
        response = _call_model(client, contents, _config(system_prompt, mode))
        candidate = response.candidates[0] if response.candidates else None
        finish = str(getattr(candidate, 'finish_reason', '') or '')
        if candidate is None or any(x in finish for x in ('SAFETY', 'PROHIBITED_CONTENT', 'BLOCKLIST')):
            raise GeminiBlocked()
        calls = response.function_calls or []
        if not calls:
            text = (response.text or '').strip()
            if not text:
                raise GeminiUnavailable('empty')
            return text
        contents.append(candidate.content)
        parts = []
        for call in calls:
            args = dict(call.args or {})
            result = run_tool(call.name, args, user=user)
            state['tool_calls'].append({'name': call.name, 'args': args})
            state['tool_results'].append({'name': call.name, 'args': args, 'result': result})
            state['product_ids'].extend(collect_product_ids(result))
            # Gửi kèm id của lời gọi để Gemini ghép đúng kết quả (bắt buộc với model mới)
            parts.append(types.Part(function_response=types.FunctionResponse(
                id=getattr(call, 'id', None), name=call.name, response={'result': result})))
        contents.append(types.Content(role='user', parts=parts))
    raise GeminiUnavailable('too_many_rounds')


def generate_reply(system_prompt: str, history: list[dict], user=None, force_tools: bool = False) -> dict:
    """history: [{'role': 'user'|'assistant', 'content': str}] (tối đa 10 tin gần nhất, tin cuối là câu hỏi).

    Trả về {'reply', 'tool_calls': [...], 'product_ids': [...], 'tool_results': [...], 'price_retry': bool}.
    """
    from google.genai import types

    client = _client()
    contents = [
        types.Content(role='user' if m['role'] == 'user' else 'model', parts=[types.Part.from_text(text=m['content'])])
        for m in history
    ]
    state = {'tool_calls': [], 'product_ids': [], 'tool_results': []}
    # Giá khách tự nêu và giá trong các câu trả lời trước (đã kiểm tra) cũng được phép nhắc lại
    # (kèm system prompt vì có phí ship lấy từ cấu hình cửa hàng)
    known_texts = [m['content'] for m in history] + [system_prompt]

    text = _run_loop(client, system_prompt, contents, state, user, force_tools)
    bad = guard.unverified_prices(text, state['tool_results'], known_texts)
    price_retry = False
    if bad:
        price_retry = True
        logger.warning('Gemini trả giá không khớp dữ liệu tool: %s – yêu cầu viết lại', sorted(bad))
        contents.append(types.Content(role='model', parts=[types.Part.from_text(text=text)]))
        warning = PRICE_WARNING.format(prices=', '.join(f'{p:,}'.replace(',', '.') + 'đ' for p in sorted(bad)))
        contents.append(types.Content(role='user', parts=[types.Part.from_text(text=warning)]))
        text = _run_loop(client, system_prompt, contents, state, user, force_tools=False)
        bad = guard.unverified_prices(text, state['tool_results'], known_texts)
        if bad:
            logger.warning('Gemini vẫn trả giá sai %s – dùng câu trả lời từ dữ liệu tool', sorted(bad))
            raise PriceMismatch(state)
    if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY in text:  # Phòng hờ: không bao giờ lộ key
        text = 'Xin lỗi, mình không thể chia sẻ thông tin nội bộ của cửa hàng.'
    return {'reply': text, 'price_retry': price_retry, **state}
