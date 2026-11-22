"""Chuẩn hóa tên dòng iPhone và loại linh kiện từ văn bản tự do (dùng cho chatbot và tìm kiếm)."""

import re

from core.utils import strip_accents

from .models import Category, IPhoneModel

# Từ đồng nghĩa -> slug danh mục (slug sinh từ tên danh mục seed)
CATEGORY_SYNONYMS = {
    'man-hinh': ['man hinh', 'manhinh', 'mh', 'lcd', 'oled', 'screen', 'display', 'cam ung', 'man'],
    'pin': ['pin', 'battery', 'bin', 'pinn'],
    'camera-sau': ['camera sau', 'cam sau', 'rear camera', 'back camera'],
    'camera-truoc': ['camera truoc', 'cam truoc', 'front camera', 'selfie', 'face id camera'],
    'camera': ['camera', 'cam'],
    'chan-sac': ['chan sac', 'cong sac', 'dock', 'charging port', 'sac', 'lightning', 'usb-c', 'usb c', 'charge'],
    'loa-trong': ['loa trong', 'loa thoai', 'loa nghe', 'earpiece'],
    'loa-ngoai': ['loa ngoai', 'loa chuong', 'loudspeaker'],
    'loa': ['loa', 'speaker'],
    'micro': ['micro', 'mic', 'microphone'],
    'vo-may': ['vo may', 'vo', 'nap lung', 'kinh lung', 'back glass', 'housing'],
    'khung-may': ['khung may', 'khung', 'suon', 'frame'],
    'nut-nguon-am-luong': ['nut nguon', 'nut am luong', 'nut', 'phim', 'button', 'power button'],
    'cap-va-linh-kien-khac': ['cap', 'flex', 'linh kien khac', 'ic', 'rung', 'taptic'],
}

_SUFFIXES = [
    (r'pro\s*max|promax|pm|prm', 'pro max'),
    (r'pro', 'pro'),
    (r'plus|\+', 'plus'),
    (r'mini', 'mini'),
    (r'max', 'max'),
]


def _normalize(text: str) -> str:
    return re.sub(r'\s+', ' ', strip_accents(text or '').lower()).strip()


def _canonical_key(name: str) -> str:
    return _normalize(name).replace('iphone', '').replace(' ', '')


def resolve_iphone_model(text: str) -> dict:
    """Nhận các cách viết như 'ip13 pro', 'iphone 13pro', '13 promax', 'i13 pm', 'xs max'.

    Trả về {'model': IPhoneModel | None, 'candidates': [IPhoneModel], 'ambiguous': bool, 'query': str}.
    - Khớp chính xác một model có hậu tố (Pro, Pro Max, mini, Plus) -> model.
    - Chỉ có số thế hệ mà có nhiều phiên bản (13, 13 mini, 13 Pro...) -> ambiguous=True, candidates là các
      phiên bản để hỏi lại khách; model là bản tiêu chuẩn (nếu có) để tham khảo.
    """
    raw = _normalize(text)
    models = list(IPhoneModel.objects.filter(is_active=True))
    result = {'model': None, 'candidates': [], 'ambiguous': False, 'query': text}
    if not raw:
        return result
    match = re.search(r'(?:iphone|ip|i)?\s*(1[0-9]|[6-9]|xs|xr|x|se)\s*((?:pro\s*max|promax|prm|pm|pro|plus|\+|mini|max)?)\b', raw)
    if not match:
        return result
    gen, suffix_raw = match.group(1), (match.group(2) or '').strip()
    suffix = ''
    for pattern, value in _SUFFIXES:
        if suffix_raw and re.fullmatch(pattern, suffix_raw):
            suffix = value
            break
    if gen == 'xs' and suffix == 'max':
        suffix = 'max'
    key = (gen + suffix.replace(' ', ''))
    by_key = {_canonical_key(m.name): m for m in models}
    if key in by_key and (suffix or gen in ('x', 'xr', 'xs', 'se') or not _has_variants(models, gen)):
        result['model'] = by_key[key]
        return result
    if not suffix:
        candidates = [m for m in models if re.fullmatch(rf'{gen}(mini|pro|promax|plus|max)?', _canonical_key(m.name))]
        if len(candidates) == 1:
            result['model'] = candidates[0]
        elif candidates:
            result['candidates'] = sorted(candidates, key=lambda m: (m.display_order, m.name))
            result['ambiguous'] = True
            result['model'] = by_key.get(key)
    return result


def _has_variants(models, gen: str) -> bool:
    return sum(1 for m in models if re.fullmatch(rf'{gen}(mini|pro|promax|plus|max)?', _canonical_key(m.name))) > 1


def resolve_category(text: str) -> Category | None:
    """Ánh xạ từ đồng nghĩa ('màn', 'lcd', 'cổng sạc'...) sang danh mục. Ưu tiên cụm từ dài hơn."""
    raw = f' {_normalize(text)} '
    pairs = sorted(((syn, slug) for slug, syns in CATEGORY_SYNONYMS.items() for syn in syns), key=lambda x: -len(x[0]))
    for synonym, slug in pairs:
        if f' {synonym} ' in raw:
            category = Category.objects.filter(slug=slug, is_active=True).first()
            if category:
                return category
    category_by_name = {_normalize(c.name): c for c in Category.objects.filter(is_active=True)}
    for name, category in sorted(category_by_name.items(), key=lambda x: -len(x[0])):
        if f' {name} ' in raw:
            return category
    return None
