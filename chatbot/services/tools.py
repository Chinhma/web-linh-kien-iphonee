"""Các công cụ (function calling) cho iParts AI Assistant.

Mỗi tool truy vấn DB thật và trả về dict GỌN chỉ gồm trường công khai (KHÔNG có cost_price),
tối đa 8 sản phẩm mỗi lần. Mọi kết quả đều có "found" (True/False) và "message" khi không có dữ liệu
để mô hình không phải đoán. Đây là cơ chế đảm bảo AI không bịa dữ liệu.
"""

from core.constants import WARRANTY_MONTHS
import re

from django.urls import reverse
from django.utils import timezone

from core.models import Page, StoreSetting
from core.templatetags.iparts import vnd
from core.utils import strip_accents
from products.models import Category, Compatibility, IPhoneModel, Product
from products.selectors import compatibility_lookup, on_sale_products, public_products, search_filter, with_card_data
from products.services import resolve_category, resolve_iphone_model
from promotions.services import public_active_coupons

MAX_PRODUCTS = 8

# Viết tắt / gõ sai phổ biến -> dạng chuẩn (không dấu). So khớp theo từ nguyên vẹn.
ABBREVIATIONS = {
    'ip': 'iphone', 'iphon': 'iphone', 'ipone': 'iphone', 'iphne': 'iphone', 'ifone': 'iphone', 'aiphone': 'iphone',
    'ipho': 'iphone', 'dt': '', 'đt': '', 'mh': 'man hinh', 'manhinh': 'man hinh', 'mhinh': 'man hinh',
    'pinn': 'pin', 'bin': 'pin', 'chansac': 'chan sac', 'congsac': 'cong sac', 'cam': 'camera', 'cmr': 'camera',
}
# Từ không mang nghĩa tìm kiếm (bỏ khi lọc theo từ khóa)
STOP_WORDS = {
    'cho', 'minh', 'toi', 'em', 'anh', 'chi', 'ban', 'gia', 'bao', 'nhieu', 'tien', 'con', 'hang', 'khong', 'ko', 'k',
    'co', 'can', 'tim', 'mua', 'thay', 'loai', 'nao', 'cua', 'la', 'voi', 'may', 'nhe', 'a', 'ah', 'vay', 'the',
    'shop', 'oi', 'giup', 'xem', 'cai', 'nay', 'do', 'duoc', 'hay', 'va', 'hoac', 'gi', 'muon', 'dang',
}
SORT_OPTIONS = {'price_asc', 'price_desc', 'best_selling', 'rating', 'relevance'}


def plain(text: str) -> str:
    """Bỏ dấu + chữ thường."""
    return strip_accents(text or '').lower()


def normalize_query(text: str) -> str:
    """Chuẩn hóa câu hỏi tiếng Việt: bỏ dấu, chữ thường, mở rộng viết tắt và lỗi gõ nhẹ.

    'pin ip 11' -> 'pin iphone 11'; 'mh 13pm' -> 'man hinh 13pm'.
    """
    text = re.sub(r'[^\w\s+]', ' ', plain(text))
    text = re.sub(r'\b(ip|iphone|i)(\d{1,2}|x|xs|xr|se)\b', r'iphone \2', text)  # ip13 -> iphone 13
    words = []
    for word in text.split():
        words.append(ABBREVIATIONS.get(word, word))
    return re.sub(r'\s+', ' ', ' '.join(words)).strip()


def product_dict(product: Product, note: str = '') -> dict:
    return {
        'id': product.pk,
        'name': product.name,
        'sku': product.sku,
        'category': product.category.name,
        'quality': product.get_quality_grade_display(),
        'price': product.effective_price,
        'original_price': product.price,
        'is_on_sale': product.is_on_sale,
        'stock_status': product.stock_status,
        'stock_label': product.stock_label,
        'stock_quantity': product.stock_quantity,
        'warranty_months': WARRANTY_MONTHS,  # Bảo hành cố định, miễn phí
        'rating_avg': float(product.rating_avg),
        'rating_count': product.rating_count,
        'sold_count': product.sold_count,
        'compatible_models': [m.name for m in product.verified_models][:10],
        'url': product.get_absolute_url(),
        'compatibility_note': note,
        # Các lựa chọn có giá riêng (vd. Zin bóc máy / GX / Incell...). 'price' ở trên là giá thấp nhất.
        # Biến thể loại màn × màu, mỗi tổ hợp một giá. 'price' ở trên là giá tổ hợp mặc định.
        'variants': [{'name': v.label, 'price': v.effective_price, 'in_stock': v.stock > 0} for v in product.active_variants],
    }


def _model_info(text: str) -> tuple[IPhoneModel | None, dict]:
    resolved = resolve_iphone_model(normalize_query(text))
    info = {'query': text}
    if resolved['ambiguous']:
        info['ambiguous'] = True
        info['candidates'] = [m.name for m in resolved['candidates']]
        info['hint'] = 'Có nhiều phiên bản, hãy hỏi lại khách dùng phiên bản nào trước khi khẳng định.'
    if resolved['model']:
        info['model'] = resolved['model'].name
        info['model_slug'] = resolved['model'].slug
    return resolved['model'], info


def _resolve_cat(text: str) -> Category | None:
    return (resolve_category(normalize_query(text))
            or Category.objects.filter(slug=text, is_active=True).first())


def _keywords(query: str, model: IPhoneModel | None, category: Category | None) -> str:
    """Bỏ phần tên máy / danh mục / từ vô nghĩa khỏi query để lọc thêm theo từ khóa còn lại."""
    text = normalize_query(query)
    if model or category:
        # Đã lọc bằng model/danh mục -> bỏ mọi token liên quan tên máy và tên danh mục
        text = re.sub(r'\biphone\b|\b(1[0-9]|[6-9]|xs|xr|x|se)\b|\b(pro\s*max|promax|prm|pm|pro|plus|mini|max)\b', ' ', text)
        if category:
            for word in plain(category.name).split():
                text = re.sub(rf'\b{re.escape(word)}\b', ' ', text)
    words = [w for w in text.split() if w not in STOP_WORDS and len(w) > 1]
    return ' '.join(words)


def search_products(query: str = '', category: str = '', iphone_model: str = '', min_price: int | None = None,
                    max_price: int | None = None, in_stock_only: bool = False, sort_by: str = 'relevance') -> dict:
    """Tìm sản phẩm: không phân biệt dấu/hoa thường, hiểu viết tắt (ip, 13pm, prm, màn, pin, cam...)."""
    qs = public_products()
    result: dict = {'query': query}
    # Tự suy ra danh mục / dòng máy từ query nếu mô hình chưa tách riêng
    cat = _resolve_cat(category) if category else (_resolve_cat(query) if query else None)
    if category and cat is None:
        result['category_warning'] = f'Không có loại linh kiện "{category}".'
    if cat:
        qs = qs.filter(category_id__in=cat.descendant_ids())
        result['category'] = cat.name
    model = None
    model_text = iphone_model
    if not model_text and query:
        guess = resolve_iphone_model(normalize_query(query))
        if guess['model'] or guess['ambiguous']:
            model_text = query
    if model_text:
        model, info = _model_info(model_text)
        result['iphone_model'] = info
        if model:
            qs = qs.filter(compatibilities__iphone_model=model, compatibilities__status=Compatibility.Status.VERIFIED)
        elif iphone_model:
            return {**result, 'found': False, 'products': [], 'total_found': 0,
                    'message': f'Hệ thống chưa có dòng máy "{iphone_model}".'}
    keywords = _keywords(query, model, cat) if query else ''
    if keywords:
        qs = qs.filter(search_filter(keywords))
    items = list(with_card_data(qs.distinct()))
    if min_price:
        items = [p for p in items if p.effective_price >= int(min_price)]
    if max_price:
        items = [p for p in items if p.effective_price <= int(max_price)]
    if in_stock_only:
        items = [p for p in items if p.stock_quantity > 0]
    sort_by = sort_by if sort_by in SORT_OPTIONS else 'relevance'
    sorters = {
        'price_asc': lambda p: p.effective_price,
        'price_desc': lambda p: -p.effective_price,
        'best_selling': lambda p: -p.sold_count,
        'rating': lambda p: (-float(p.rating_avg), -p.rating_count),
        'relevance': lambda p: (p.stock_quantity <= 0, -p.sold_count, p.effective_price),
    }
    items.sort(key=sorters[sort_by])
    result.update({
        'found': bool(items),
        'total_found': len(items),
        'sort_by': sort_by,
        'products': [product_dict(p) for p in items[:MAX_PRODUCTS]],
    })
    if not items:
        result['message'] = 'Không tìm thấy sản phẩm phù hợp trong cửa hàng.'
    return result


def check_compatibility(iphone_model: str, category: str = '') -> dict:
    model, info = _model_info(iphone_model)
    if model is None:
        if info.get('ambiguous'):
            return {'found': False, 'iphone_model': info, 'products': [],
                    'message': 'Cần hỏi lại khách phiên bản máy cụ thể.'}
        return {'found': False, 'iphone_model': info, 'products': [], 'message': 'Hệ thống chưa hỗ trợ dòng máy này.'}
    cat = _resolve_cat(category) if category else None
    comps = list(compatibility_lookup(model, cat)[:MAX_PRODUCTS])
    return {
        'found': bool(comps),
        'iphone_model': info,
        'category': cat.name if cat else 'Tất cả linh kiện',
        'products': [product_dict(c.product, c.note) for c in comps],
        'lookup_url': reverse('products:compatibility') + f'?model={model.slug}' + (f'&category={cat.slug}' if cat else ''),
        'message': '' if comps else f'Chưa có linh kiện đã xác nhận tương thích với {model.name}.',
    }


def _find_product(product_id=None, sku: str = '') -> Product | None:
    qs = with_card_data(public_products())
    if product_id:
        return qs.filter(pk=int(product_id)).first()
    if sku:
        return qs.filter(sku__iexact=sku.strip()).first()
    return None


def check_product_compatibility(iphone_model: str, product_id: int | None = None, sku: str = '') -> dict:
    product = _find_product(product_id, sku)
    if product is None:
        return {'found': False, 'result': 'unknown', 'message': 'Không tìm thấy sản phẩm.'}
    model, info = _model_info(iphone_model)
    if model is None:
        return {'found': True, 'result': 'unknown', 'iphone_model': info, 'product': product_dict(product)}
    comp = Compatibility.objects.filter(product=product, iphone_model=model).first()
    status = comp.status if comp and comp.status != Compatibility.Status.UNVERIFIED else 'unknown'
    return {'found': True, 'result': status, 'note': comp.note if comp and status != 'unknown' else '',
            'iphone_model': info, 'product': product_dict(product)}


def get_product_detail(product_id: int | None = None, sku: str = '') -> dict:
    product = _find_product(product_id, sku)
    if product is None:
        return {'found': False, 'message': 'Không tìm thấy sản phẩm.'}
    data = product_dict(product)
    data.update({
        'found': True,
        'short_description': product.short_description,
        'specifications': product.specifications[:10] if isinstance(product.specifications, list) else [],
        'usage_guide': product.usage_guide[:500],
    })
    return data


def compare_products(product_ids: list | None = None) -> dict:
    """So sánh 2–4 sản phẩm: giá, chất lượng, bảo hành, tồn kho, đánh giá, dòng máy tương thích."""
    ids = []
    for pid in product_ids or []:
        try:
            ids.append(int(pid))
        except (TypeError, ValueError):
            continue
    ids = list(dict.fromkeys(ids))[:4]
    if len(ids) < 2:
        return {'found': False, 'products': [], 'message': 'Cần ít nhất 2 mã sản phẩm (id) để so sánh.'}
    found = {p.pk: p for p in with_card_data(public_products().filter(pk__in=ids))}
    products = [product_dict(found[i]) for i in ids if i in found]
    result = {'found': len(products) >= 2, 'products': products}
    if len(products) < 2:
        result['message'] = 'Không đủ sản phẩm hợp lệ để so sánh.'
    else:
        result['cheapest_id'] = min(products, key=lambda p: p['price'])['id']
        result['longest_warranty_id'] = max(products, key=lambda p: p['warranty_months'] or 0)['id']
    return result


def get_product_reviews(product_id: int | None = None) -> dict:
    """Điểm trung bình, số đánh giá và tối đa 5 nhận xét đã duyệt gần nhất."""
    product = _find_product(product_id)
    if product is None:
        return {'found': False, 'message': 'Không tìm thấy sản phẩm.'}
    from reviews.models import Review

    reviews = list(Review.objects.filter(product=product, status=Review.Status.APPROVED)
                   .select_related('user').order_by('-created_at')[:5])
    data = {'found': bool(reviews), 'product_id': product.pk, 'product_name': product.name,
            'rating_avg': float(product.rating_avg), 'rating_count': product.rating_count,
            'recent_reviews': [{'rating': r.rating, 'author': r.author_display, 'content': r.content[:300],
                                'date': timezone.localtime(r.created_at).strftime('%d/%m/%Y')} for r in reviews]}
    if not reviews:
        data['message'] = 'Sản phẩm chưa có đánh giá nào.'
    return data


def list_iphone_models() -> dict:
    models = [m.name for m in IPhoneModel.objects.filter(is_active=True).order_by('series', 'display_order')]
    return {'found': bool(models), 'models': models}


def list_categories() -> dict:
    cats = [{'name': c.name, 'slug': c.slug} for c in Category.objects.filter(is_active=True).order_by('display_order')]
    return {'found': bool(cats), 'categories': cats}


def get_promotions() -> dict:
    products = list(with_card_data(on_sale_products().order_by('-sold_count')[:MAX_PRODUCTS]))
    coupons = [{'code': c.code, 'description': c.description or c.value_label,
                'min_order_value': vnd(c.min_order_value), 'end_at': timezone.localtime(c.end_at).strftime('%d/%m/%Y')}
               for c in public_active_coupons()[:5]]
    data = {'found': bool(products or coupons), 'products': [product_dict(p) for p in products], 'coupons': coupons}
    if not data['found']:
        data['message'] = 'Hiện chưa có chương trình khuyến mãi hay mã giảm giá nào.'
    return data


POLICY_PAGES = {
    'warranty': 'chinh-sach-bao-hanh', 'return': 'chinh-sach-doi-tra',
    'shipping': 'chinh-sach-van-chuyen', 'payment': 'huong-dan-mua-hang',
}


def get_store_policy(topic: str = 'contact') -> dict:
    store = StoreSetting.get_solo()
    if topic == 'contact' or topic not in POLICY_PAGES:
        return {'found': True, 'hotline': store.hotline, 'email': store.email, 'working_hours': store.working_hours,
                'address': store.address or 'Chưa cập nhật'}
    page = Page.objects.filter(slug=POLICY_PAGES[topic], is_published=True).first()
    data = {'topic': topic, 'found': bool(page), 'hotline': store.hotline}
    if page:
        data.update({'title': page.title, 'summary': page.content[:1500], 'url': page.get_absolute_url()})
    if topic == 'shipping':
        data.update({'found': True, 'standard_fee': vnd(store.shipping_fee_standard),
                     'express_fee': vnd(store.shipping_fee_express),
                     'free_shipping_threshold': vnd(store.free_shipping_threshold)})
    if not data['found']:
        data['message'] = 'Chưa có nội dung chính sách này, hãy mời khách liên hệ hotline.'
    return data


def get_my_order_status(user=None, order_code: str = '') -> dict:
    """Chỉ trả đơn của CHÍNH user đang đăng nhập (lọc theo user, không bao giờ theo mã đơn đơn thuần)."""
    if user is None or not user.is_authenticated:
        return {'found': False, 'error': 'LOGIN_REQUIRED', 'message': 'Khách cần đăng nhập để xem đơn hàng.'}
    from orders.models import Order

    orders = Order.objects.filter(user=user)
    order = orders.filter(code__iexact=order_code.strip()).first() if order_code else orders.order_by('-created_at').first()
    if order is None:
        return {'found': False, 'message': 'Không tìm thấy đơn hàng.'}
    return {'found': True, 'code': order.code, 'status': order.get_status_display(),
            'payment_status': order.get_payment_status_display(), 'total': vnd(order.total),
            'created_at': timezone.localtime(order.created_at).strftime('%d/%m/%Y %H:%M'), 'url': order.get_absolute_url()}


# ------------------------------------------------------------------ Khai báo cho Gemini
TOOL_DECLARATIONS = [
    {
        'name': 'search_products',
        'description': ('Tìm linh kiện trong cửa hàng. Hiểu tiếng Việt không dấu và viết tắt (ip, 13pm, prm, màn, pin, '
                        'cam, chân sạc...). Có thể truyền nguyên câu khách vào query. Hỗ trợ lọc khoảng giá, chỉ hàng còn, '
                        'sắp xếp.'),
        'parameters': {'type': 'OBJECT', 'properties': {
            'query': {'type': 'STRING', 'description': 'Từ khóa tự do, ví dụ "pin ip 11", "màn 13 pro max zin"'},
            'category': {'type': 'STRING', 'description': 'Loại linh kiện, ví dụ "màn hình", "pin", "chân sạc"'},
            'iphone_model': {'type': 'STRING', 'description': 'Dòng iPhone, ví dụ "iPhone 13 Pro"'},
            'min_price': {'type': 'INTEGER', 'description': 'Giá tối thiểu (VND)'},
            'max_price': {'type': 'INTEGER', 'description': 'Giá tối đa (VND)'},
            'in_stock_only': {'type': 'BOOLEAN', 'description': 'Chỉ lấy sản phẩm còn hàng'},
            'sort_by': {'type': 'STRING', 'enum': sorted(SORT_OPTIONS),
                        'description': 'price_asc (rẻ trước), price_desc, best_selling, rating, relevance'},
        }},
    },
    {
        'name': 'check_compatibility',
        'description': 'Tra cứu các linh kiện ĐÃ XÁC NHẬN tương thích với một dòng iPhone (có thể lọc theo loại linh kiện).',
        'parameters': {'type': 'OBJECT', 'properties': {
            'iphone_model': {'type': 'STRING', 'description': 'Dòng iPhone'},
            'category': {'type': 'STRING', 'description': 'Loại linh kiện (tùy chọn)'},
        }, 'required': ['iphone_model']},
    },
    {
        'name': 'check_product_compatibility',
        'description': 'Kiểm tra một sản phẩm cụ thể có tương thích với dòng iPhone không.',
        'parameters': {'type': 'OBJECT', 'properties': {
            'product_id': {'type': 'INTEGER'}, 'sku': {'type': 'STRING'},
            'iphone_model': {'type': 'STRING'},
        }, 'required': ['iphone_model']},
    },
    {
        'name': 'get_product_detail',
        'description': 'Lấy thông tin chi tiết công khai của sản phẩm theo id hoặc SKU (mô tả, thông số, bảo hành, đánh giá).',
        'parameters': {'type': 'OBJECT', 'properties': {'product_id': {'type': 'INTEGER'}, 'sku': {'type': 'STRING'}}},
    },
    {
        'name': 'compare_products',
        'description': 'So sánh 2–4 sản phẩm theo id (lấy id từ kết quả search_products/check_compatibility).',
        'parameters': {'type': 'OBJECT', 'properties': {
            'product_ids': {'type': 'ARRAY', 'items': {'type': 'INTEGER'}, 'description': 'Danh sách 2–4 id sản phẩm'},
        }, 'required': ['product_ids']},
    },
    {
        'name': 'get_product_reviews',
        'description': 'Điểm đánh giá trung bình, số đánh giá và vài nhận xét gần nhất của khách về một sản phẩm.',
        'parameters': {'type': 'OBJECT', 'properties': {'product_id': {'type': 'INTEGER'}}, 'required': ['product_id']},
    },
    {'name': 'list_iphone_models', 'description': 'Danh sách dòng iPhone cửa hàng hỗ trợ.',
     'parameters': {'type': 'OBJECT', 'properties': {}}},
    {'name': 'list_categories', 'description': 'Danh sách loại linh kiện.',
     'parameters': {'type': 'OBJECT', 'properties': {}}},
    {'name': 'get_promotions', 'description': 'Sản phẩm đang giảm giá và mã giảm giá công khai còn hiệu lực.',
     'parameters': {'type': 'OBJECT', 'properties': {}}},
    {
        'name': 'get_store_policy',
        'description': 'Chính sách cửa hàng: warranty (bảo hành), return (đổi trả), shipping (vận chuyển, phí ship), payment (thanh toán), contact (liên hệ).',
        'parameters': {'type': 'OBJECT', 'properties': {
            'topic': {'type': 'STRING', 'enum': ['warranty', 'return', 'shipping', 'payment', 'contact']}},
            'required': ['topic']},
    },
    {
        'name': 'get_my_order_status',
        'description': 'Trạng thái đơn hàng của CHÍNH khách đang chat (đơn gần nhất nếu không có mã). Khách chưa đăng nhập sẽ nhận lỗi.',
        'parameters': {'type': 'OBJECT', 'properties': {'order_code': {'type': 'STRING'}}},
    },
]

TOOL_FUNCTIONS = {
    'search_products': search_products,
    'check_compatibility': check_compatibility,
    'check_product_compatibility': check_product_compatibility,
    'get_product_detail': get_product_detail,
    'compare_products': compare_products,
    'get_product_reviews': get_product_reviews,
    'list_iphone_models': list_iphone_models,
    'list_categories': list_categories,
    'get_promotions': get_promotions,
    'get_store_policy': get_store_policy,
    'get_my_order_status': get_my_order_status,
}


def run_tool(name: str, args: dict, user=None) -> dict:
    """Thực thi tool theo tên với tham số do mô hình cung cấp (chỉ nhận tham số đã khai báo)."""
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return {'found': False, 'error': f'Không có công cụ {name}'}
    declared = next(d for d in TOOL_DECLARATIONS if d['name'] == name)['parameters'].get('properties', {})
    clean_args = {k: v for k, v in (args or {}).items() if k in declared}
    if isinstance(clean_args.get('product_ids'), (list, tuple)):
        clean_args['product_ids'] = list(clean_args['product_ids'])
    try:
        if name == 'get_my_order_status':
            return func(user=user, **clean_args)
        return func(**clean_args)
    except (TypeError, ValueError) as exc:
        return {'found': False, 'error': f'Tham số không hợp lệ: {type(exc).__name__}'}


def collect_product_ids(result) -> list[int]:
    """Lấy ID sản phẩm từ kết quả tool (để backend tự dựng Product Card, không dựa vào chữ AI viết)."""
    ids = []
    if isinstance(result, dict):
        for product in result.get('products', []) or []:
            if isinstance(product, dict) and product.get('id'):
                ids.append(product['id'])
        if isinstance(result.get('product'), dict) and result['product'].get('id'):
            ids.append(result['product']['id'])
        if result.get('id') and result.get('sku'):
            ids.append(result['id'])
    return ids
