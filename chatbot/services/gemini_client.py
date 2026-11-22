"""Gọi Google Gemini qua thư viện google-genai với Function Calling.

Vòng xử lý: gửi hội thoại + khai báo tools -> mô hình yêu cầu gọi hàm -> backend thực thi (truy vấn DB thật)
-> trả kết quả cho mô hình -> mô hình viết câu trả lời dựa trên kết quả. Tối đa 4 vòng gọi công cụ.
"""

import logging

from django.conf import settings

from .tools import TOOL_DECLARATIONS, collect_product_ids, run_tool

logger = logging.getLogger('iparts')
MAX_TOOL_ROUNDS = 4


class GeminiUnavailable(Exception):
    """Lỗi tạm thời (timeout, mạng, quota, 5xx) -> chuyển sang chế độ dự phòng."""


class GeminiBlocked(Exception):
    """Nội dung bị chặn bởi bộ lọc an toàn."""


def is_configured() -> bool:
    return bool(settings.GEMINI_API_KEY)


def _client():
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=settings.GEMINI_TIMEOUT_SECONDS * 1000),
    )


def generate_reply(system_prompt: str, history: list[dict], user=None) -> dict:
    """history: [{'role': 'user'|'assistant', 'content': str}] (tối đa 10 tin gần nhất, tin cuối là câu hỏi).

    Trả về {'reply', 'tool_calls': [...], 'product_ids': [...], 'tool_results': [...]}.
    """
    from google.genai import errors, types

    client = _client()
    contents = [
        types.Content(role='user' if m['role'] == 'user' else 'model', parts=[types.Part.from_text(text=m['content'])])
        for m in history
    ]
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.3,
        tools=[types.Tool(function_declarations=[types.FunctionDeclaration(**d) for d in TOOL_DECLARATIONS])],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    tool_calls, product_ids, tool_results = [], [], []

    def call_model():
        for attempt in range(2):  # Thử lại 1 lần với lỗi tạm thời
            try:
                return client.models.generate_content(model=settings.GEMINI_MODEL, contents=contents, config=config)
            except errors.APIError as exc:
                code = getattr(exc, 'code', 0) or 0
                if code in (429, 500, 502, 503, 504) and attempt == 0:
                    continue
                logger.warning('Gemini APIError %s', code)
                raise GeminiUnavailable(str(code))
            except Exception as exc:  # timeout / lỗi mạng
                if attempt == 0:
                    continue
                logger.warning('Gemini lỗi kết nối: %s', type(exc).__name__)
                raise GeminiUnavailable(type(exc).__name__)
        raise GeminiUnavailable('retry')

    for _ in range(MAX_TOOL_ROUNDS + 1):
        response = call_model()
        candidate = response.candidates[0] if response.candidates else None
        if candidate is None or getattr(candidate, 'finish_reason', None) in ('SAFETY', 'PROHIBITED_CONTENT', 'BLOCKLIST'):
            raise GeminiBlocked()
        calls = response.function_calls or []
        if not calls or len(tool_calls) >= MAX_TOOL_ROUNDS * 3:
            text = (response.text or '').strip()
            if not text:
                raise GeminiUnavailable('empty')
            return {'reply': text, 'tool_calls': tool_calls, 'product_ids': product_ids, 'tool_results': tool_results}
        contents.append(candidate.content)
        parts = []
        for call in calls:
            args = dict(call.args or {})
            result = run_tool(call.name, args, user=user)
            tool_calls.append({'name': call.name, 'args': args})
            tool_results.append({'name': call.name, 'args': args, 'result': result})
            product_ids.extend(collect_product_ids(result))
            parts.append(types.Part.from_function_response(name=call.name, response={'result': result}))
        contents.append(types.Content(role='tool', parts=parts))
    # Hết số vòng cho phép: yêu cầu mô hình trả lời bằng dữ liệu đã có
    raise GeminiUnavailable('too_many_rounds')
