"""Các công cụ (function calling) cho iParts AI Assistant.

Mỗi tool truy vấn DB thật và trả về dict GỌN chỉ gồm trường công khai (KHÔNG có cost_price),
tối đa 8 sản phẩm mỗi lần. Đây là cơ chế đảm bảo AI không bịa dữ liệu.
"""

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
        'warranty_months': product.warranty_months,
        'compatible_models': [m.name for m in product.verified_models][:10],
        'url': product.get_absolute_url(),
        'compatibility_note': note,
    }


def _model_info(text: str) -> tuple[IPhoneModel | None, dict]:
    resolved = resolve_iphone_model(text)
    info = {'query': text}
    if resolved['ambiguous']:
        info['ambiguous'] = True
        info['candidates'] = [m.name for m in resolved['candidates']]
        info['hint'] = 'Có nhiều phiên bản, hãy hỏi lại khách dùng phiên bản nào trước khi khẳng định.'
    if resolved['model']:
        info['model'] = resolved['model'].name
        info['model_slug'] = resolved['model'].slug
    return resolved['model'], info


def search_products(query: str = '', category: str = '', iphone_model: str = '', max_price: int | None = None,
                    in_stock_only: bool = False) -> dict:
    qs = public_products()
    result: dict = {}
    if category:
        cat = resolve_category(category) or Category.objects.filter(slug=category, is_active=True).first()
        if cat:
            qs = qs.filter(category_id__in=cat.descendant_ids())
            result['category'] = cat.name
    if iphone_model:
        model, info = _model_info(iphone_model)
        result['iphone_model'] = info
        if model:
            qs = qs.filter(compatibilities__iphone_model=model, compatibilities__status=Compatibility.Status.VERIFIED)
        else:
            return {**result, 'products': [], 'message': 'Hệ thống chưa có dòng máy này.'}
    if query:
        cleaned = query
        if iphone_model or category:  # Tránh lọc trùng khi query chứa lại tên máy/danh mục
            cleaned = ''
        if cleaned:
            qs = qs.filter(search_filter(cleaned))
    if max_price:
        qs = [p for p in with_card_data(qs.distinct()) if p.effective_price <= int(max_price)]
    else:
        qs = list(with_card_data(qs.distinct().order_by('-stock_quantity', 'price')[:40]))
    if in_stock_only:
        qs = [p for p in qs if p.stock_quantity > 0]
    products = qs[:MAX_PRODUCTS]
    result['products'] = [product_dict(p) for p in products]
    result['total_found'] = len(qs)
    return result


def check_compatibility(iphone_model: str, category: str = '') -> dict:
    model, info = _model_info(iphone_model)
    if model is None:
        if info.get('ambiguous'):
            return {'iphone_model': info, 'products': []}
        return {'iphone_model': info, 'products': [], 'message': 'Hệ thống chưa hỗ trợ dòng máy này.'}
    cat = None
    if category:
        cat = resolve_category(category) or Category.objects.filter(slug=category).first()
    comps = list(compatibility_lookup(model, cat)[:MAX_PRODUCTS])
    return {
        'iphone_model': info,
        'category': cat.name if cat else 'Tất cả linh kiện',
        'products': [product_dict(c.product, c.note) for c in comps],
        'lookup_url': reverse('products:compatibility') + f'?model={model.slug}' + (f'&category={cat.slug}' if cat else ''),
        'message': '' if comps else f'Chưa có linh kiện đã xác nhận tương thích với {model.name}.',
    }


def _find_product(product_id=None, sku: str = '') -> Product | None:
    qs = with_card_data(public_products())
    if product_id:
        return qs.filter(pk=product_id).first()
    if sku:
        return qs.filter(sku__iexact=sku.strip()).first()
    return None


def check_product_compatibility(iphone_model: str, product_id: int | None = None, sku: str = '') -> dict:
    product = _find_product(product_id, sku)
    if product is None:
        return {'result': 'unknown', 'message': 'Không tìm thấy sản phẩm.'}
    model, info = _model_info(iphone_model)
    if model is None:
        return {'result': 'unknown', 'iphone_model': info, 'product': product_dict(product)}
    comp = Compatibility.objects.filter(product=product, iphone_model=model).first()
    status = comp.status if comp and comp.status != Compatibility.Status.UNVERIFIED else 'unknown'
    return {'result': status, 'note': comp.note if comp and status != 'unknown' else '',
            'iphone_model': info, 'product': product_dict(product)}


def get_product_detail(product_id: int | None = None, sku: str = '') -> dict:
    product = _find_product(product_id, sku)
    if product is None:
        return {'message': 'Không tìm thấy sản phẩm.'}
    data = product_dict(product)
    data.update({
        'short_description': product.short_description,
        'specifications': product.specifications[:10] if isinstance(product.specifications, list) else [],
        'rating_avg': float(product.rating_avg), 'rating_count': product.rating_count,
        'brand': product.brand.name if product.brand else '',
        'usage_guide': product.usage_guide[:500],
    })
    return data


def list_iphone_models() -> dict:
    return {'models': [m.name for m in IPhoneModel.objects.filter(is_active=True).order_by('series', 'display_order')]}


def list_categories() -> dict:
    return {'categories': [{'name': c.name, 'slug': c.slug}
                           for c in Category.objects.filter(is_active=True).order_by('display_order')]}


def get_promotions() -> dict:
    products = list(with_card_data(on_sale_products().order_by('-sold_count')[:MAX_PRODUCTS]))
    coupons = [{'code': c.code, 'description': c.description or c.value_label,
                'min_order_value': vnd(c.min_order_value), 'end_at': timezone.localtime(c.end_at).strftime('%d/%m/%Y')}
               for c in public_active_coupons()[:5]]
    return {'products': [product_dict(p) for p in products], 'coupons': coupons}


POLICY_PAGES = {
    'warranty': 'chinh-sach-bao-hanh', 'return': 'chinh-sach-doi-tra',
    'shipping': 'chinh-sach-van-chuyen', 'payment': 'huong-dan-mua-hang',
}


def get_store_policy(topic: str = 'contact') -> dict:
    store = StoreSetting.get_solo()
    if topic == 'contact' or topic not in POLICY_PAGES:
        return {'hotline': store.hotline, 'email': store.email, 'working_hours': store.working_hours,
                'address': store.address or 'Chưa cập nhật'}
    page = Page.objects.filter(slug=POLICY_PAGES[topic], is_published=True).first()
    data = {'topic': topic}
    if page:
        data.update({'title': page.title, 'summary': page.content[:1200], 'url': page.get_absolute_url()})
    if topic == 'shipping':
        data.update({'standard_fee': vnd(store.shipping_fee_standard), 'express_fee': vnd(store.shipping_fee_express),
                     'free_shipping_threshold': vnd(store.free_shipping_threshold)})
    return data


def get_my_order_status(user=None, order_code: str = '') -> dict:
    if user is None or not user.is_authenticated:
        return {'error': 'LOGIN_REQUIRED', 'message': 'Khách cần đăng nhập để xem đơn hàng.'}
    from orders.models import Order

    orders = Order.objects.filter(user=user)
    order = orders.filter(code__iexact=order_code.strip()).first() if order_code else orders.order_by('-created_at').first()
    if order is None:
        return {'message': 'Không tìm thấy đơn hàng.'}
    return {'code': order.code, 'status': order.get_status_display(), 'payment_status': order.get_payment_status_display(),
            'total': vnd(order.total), 'created_at': timezone.localtime(order.created_at).strftime('%d/%m/%Y %H:%M'),
            'url': order.get_absolute_url()}


# ------------------------------------------------------------------ Khai báo cho Gemini
TOOL_DECLARATIONS = [
    {
        'name': 'search_products',
        'description': 'Tìm sản phẩm linh kiện iPhone trong cửa hàng theo từ khóa, loại linh kiện, dòng iPhone, giá tối đa.',
        'parameters': {'type': 'OBJECT', 'properties': {
            'query': {'type': 'STRING', 'description': 'Từ khóa tự do'},
            'category': {'type': 'STRING', 'description': 'Loại linh kiện, ví dụ "màn hình", "pin", "chân sạc"'},
            'iphone_model': {'type': 'STRING', 'description': 'Dòng iPhone khách nhắc tới, ví dụ "iPhone 13 Pro"'},
            'max_price': {'type': 'INTEGER', 'description': 'Giá tối đa (VND)'},
            'in_stock_only': {'type': 'BOOLEAN', 'description': 'Chỉ lấy sản phẩm còn hàng'},
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
        'description': 'Lấy thông tin chi tiết công khai của sản phẩm theo id hoặc SKU.',
        'parameters': {'type': 'OBJECT', 'properties': {'product_id': {'type': 'INTEGER'}, 'sku': {'type': 'STRING'}}},
    },
    {'name': 'list_iphone_models', 'description': 'Danh sách dòng iPhone cửa hàng hỗ trợ.',
     'parameters': {'type': 'OBJECT', 'properties': {}}},
    {'name': 'list_categories', 'description': 'Danh sách loại linh kiện.',
     'parameters': {'type': 'OBJECT', 'properties': {}}},
    {'name': 'get_promotions', 'description': 'Sản phẩm đang giảm giá và mã giảm giá công khai còn hiệu lực.',
     'parameters': {'type': 'OBJECT', 'properties': {}}},
    {
        'name': 'get_store_policy',
        'description': 'Chính sách cửa hàng: warranty (bảo hành), return (đổi trả), shipping (vận chuyển), payment (thanh toán), contact (liên hệ).',
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
        return {'error': f'Không có công cụ {name}'}
    declared = next(d for d in TOOL_DECLARATIONS if d['name'] == name)['parameters'].get('properties', {})
    clean_args = {k: v for k, v in (args or {}).items() if k in declared}
    try:
        if name == 'get_my_order_status':
            return func(user=user, **clean_args)
        return func(**clean_args)
    except (TypeError, ValueError) as exc:
        return {'error': f'Tham số không hợp lệ: {type(exc).__name__}'}


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


def plain(text: str) -> str:
    return strip_accents(text or '').lower()
