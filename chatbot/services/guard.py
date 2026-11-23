"""Lớp bảo vệ cho chatbot: phân loại câu hỏi, chặn prompt injection, kiểm tra giá tiền AI viết ra.

- needs_store_data(): câu hỏi LOẠI A (giá, tồn kho, tương thích, khuyến mãi, đơn hàng, chính sách) -> buộc gọi tool.
- is_injection(): yêu cầu lộ prompt/API key/giá nhập, "bỏ qua hướng dẫn" -> từ chối ngay, không gửi cho Gemini.
- unverified_prices(): mọi giá trong câu trả lời phải khớp giá có trong kết quả tool của lượt đó.
"""

import re

from products.services import resolve_category, resolve_iphone_model

from .tools import normalize_query, plain

INJECTION = [
    'bo qua huong dan', 'bo qua moi huong dan', 'bo qua cac huong dan', 'quen huong dan', 'ignore previous',
    'ignore all', 'ignore your instructions', 'disregard', 'system prompt', 'prompt he thong', 'huong dan he thong',
    'api key', 'apikey', 'api_key', 'gemini key', 'secret key', 'gia nhap', 'cost price', 'cost_price',
    'developer mode', 'jailbreak', 'dan mode', 'in ra prompt', 'tiet lo prompt',
]

# Từ khóa cho thấy khách hỏi dữ liệu cửa hàng (loại A)
STORE_DATA_KEYWORDS = [
    'gia', 'bao nhieu tien', 'bao tien', 'nhieu tien', 'con hang', 'het hang', 'ton kho', 'con khong', 'co ban',
    'ban khong', 'mua', 'dat hang', 'khuyen mai', 'giam gia', 'sale', 'ma giam', 'voucher', 'coupon', 'uu dai',
    'ship', 'van chuyen', 'giao hang', 'phi giao', 'bao hanh', 'doi tra', 'hoan tien', 'tra hang', 'don hang',
    'ma don', 'tuong thich', 'vua khong', 'lap duoc', 'dung duoc', 'co loai nao', 'loai nao', 'nhung loai',
    'san pham', 'linh kien nao', 'goi y', 'tu van', 'so sanh', 'danh gia', 'review', 'hotline', 'lien he', 'dia chi',
    'thanh toan', 're nhat', 'dat nhat', 'ban chay',
]
# Câu hỏi kiến thức chung (loại B1) – không ép gọi tool nếu không kèm từ khóa mua bán
KNOWLEDGE_HINTS = ['khac gi', 'khac nhau', 'la gi', 'tai sao', 'vi sao', 'dau hieu', 'cach kiem tra', 'co nen',
                   'co mat', 'co bi', 'nhu the nao', 'the nao la', 'nguyen nhan', 'meo', 'kinh nghiem']

# Giá tiền: 1.234.000đ | 1,234,000 ₫ | 1234000 vnd | 500k | 1,2 triệu
_PRICE_PATTERNS = [
    (re.compile(r'(?<![\d.,])(\d{1,3}(?:[.,]\d{3})+|\d{4,})\s*(?:đồng|dong|vnđ|vnd|đ|₫)(?!\w)', re.I), 1),
    (re.compile(r'(?<![\d.,])(\d+(?:[.,]\d+)?)\s*(?:nghìn|ngàn|k)(?!\w)', re.I), 1000),
    (re.compile(r'(?<![\d.,])(\d+(?:[.,]\d+)?)\s*(?:triệu|tr)(?!\w)', re.I), 1_000_000),
]


def is_injection(message: str) -> bool:
    text = plain(message)
    return any(k in text for k in INJECTION)


def needs_store_data(message: str) -> bool:
    """True nếu câu hỏi cần dữ liệu thật của cửa hàng (loại A)."""
    text = f' {normalize_query(message)} '
    if any(f' {k} ' in text or (' ' in k and k in text) for k in STORE_DATA_KEYWORDS):
        return True
    has_model = bool(resolve_iphone_model(text)['model'] or resolve_iphone_model(text)['ambiguous'])
    has_category = resolve_category(text) is not None
    is_knowledge = any(k in text for k in KNOWLEDGE_HINTS)
    # "màn hình 13 pro", "pin ip 11" (dòng máy + linh kiện, không phải câu hỏi kiến thức) -> loại A
    return has_model and has_category and not is_knowledge


def _to_int(raw: str, factor: int) -> int | None:
    raw = raw.strip()
    if factor == 1:
        digits = re.sub(r'[.,]', '', raw)
        return int(digits) if digits.isdigit() else None
    try:
        return int(round(float(raw.replace(',', '.')) * factor))
    except ValueError:
        return None


def extract_prices(text: str) -> set[int]:
    """Lấy mọi số tiền (VND) xuất hiện trong văn bản."""
    found = set()
    for pattern, factor in _PRICE_PATTERNS:
        for match in pattern.finditer(text or ''):
            value = _to_int(match.group(1), factor)
            if value and value >= 1000:
                found.add(value)
    return found


def _numbers_in(obj, bucket: set[int]) -> None:
    """Gom mọi số nguyên / chuỗi tiền trong kết quả tool."""
    if isinstance(obj, bool):
        return
    if isinstance(obj, int):
        if obj >= 1000:
            bucket.add(obj)
    elif isinstance(obj, str):
        bucket.update(extract_prices(obj))
    elif isinstance(obj, dict):
        # Số tiền được giảm của cùng 1 sản phẩm (giá gốc - giá bán) cũng là con số hợp lệ
        if isinstance(obj.get('price'), int) and isinstance(obj.get('original_price'), int):
            if obj['original_price'] - obj['price'] >= 1000:
                bucket.add(obj['original_price'] - obj['price'])
        for value in obj.values():
            _numbers_in(value, bucket)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            _numbers_in(value, bucket)


def allowed_prices(tool_results: list[dict], extra_texts: list[str] | None = None) -> set[int]:
    """Giá hợp lệ = giá có trong kết quả tool (kèm số tiền được giảm) + giá đã có trong hội thoại/cấu hình cửa hàng."""
    values: set[int] = set()
    for item in tool_results or []:
        _numbers_in(item.get('result'), values)
    for text in extra_texts or []:
        values.update(extract_prices(text))
    return values


def unverified_prices(reply: str, tool_results: list[dict], extra_texts: list[str] | None = None) -> set[int]:
    """Các giá trong câu trả lời KHÔNG khớp dữ liệu tool -> nghi bịa."""
    return extract_prices(reply) - allowed_prices(tool_results, extra_texts)
