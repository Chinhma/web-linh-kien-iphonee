"""Chế độ dự phòng (không có Gemini): nhận diện từ khóa rồi gọi trực tiếp các tool, trả lời theo mẫu câu.

Nhờ vậy demo vẫn chạy khi chưa có GEMINI_API_KEY hoặc khi Gemini lỗi. Dữ liệu vẫn 100% từ DB.
"""

import re

from core.models import StoreSetting
from core.templatetags.iparts import vnd
from products.services import resolve_category, resolve_iphone_model

from . import guard, tools

OFF_TOPIC = ['bai van', 'lam tho', 'giai toan', 'thoi tiet', 'bong da', 'viet code', 'lap trinh', 'chinh tri', 'nau an',
             'phuong trinh', 'dich sang', 'ke chuyen', 'viet van', 'chung khoan', 'xo so']
REFUSE_REPLY = ('Xin lỗi, mình không thể chia sẻ thông tin nội bộ của cửa hàng. Mình có thể giúp bạn tìm linh kiện '
                'hoặc kiểm tra tương thích với dòng iPhone của bạn nhé!')


def _product_lines(products: list[dict], limit: int = 5) -> str:
    lines = []
    for p in products[:limit]:
        price = vnd(p['price'])
        if p.get('is_on_sale'):
            price = f'{vnd(p["price"])} (giá gốc {vnd(p["original_price"])})'
        line = f'- **{p["name"]}** – {price} – {p["stock_label"]}'
        if p.get('compatibility_note'):
            line += f' – {p["compatibility_note"]}'
        lines.append(line)
    return '\n'.join(lines)


def answer(message: str, user=None) -> dict:
    message = tools.normalize_query(message) or message  # Bỏ dấu, mở rộng viết tắt: 'pin ip 11' -> 'pin iphone 11'
    text = message
    store = StoreSetting.get_solo()
    calls, results = [], []

    def call(name, **kwargs):
        result = tools.run_tool(name, kwargs, user=user)
        calls.append({'name': name, 'args': kwargs})
        results.append({'name': name, 'args': kwargs, 'result': result})
        return result

    if guard.is_injection(message):
        return _done(REFUSE_REPLY, 'refuse', calls, results)
    if any(k in text for k in OFF_TOPIC):
        return _done('Xin lỗi, mình chỉ hỗ trợ các câu hỏi về linh kiện iPhone và dịch vụ của iParts Store. '
                     'Bạn cần tìm linh kiện cho máy nào không?', 'off_topic', calls, results)

    if re.search(r'\bdon hang\b|\bdon cua toi\b|\bma don\b|\bips\d', text):
        code_match = re.search(r'ips\d{6}[a-z0-9]{5}', text)
        result = call('get_my_order_status', order_code=code_match.group(0).upper() if code_match else '')
        if result.get('error') == 'LOGIN_REQUIRED':
            return _done('Bạn vui lòng **đăng nhập** để mình kiểm tra trạng thái đơn hàng của bạn nhé.', 'order_status',
                         calls, results, needs_login=True)
        if result.get('code'):
            return _done(f'Đơn **{result["code"]}** đặt lúc {result["created_at"]}: trạng thái **{result["status"]}**, '
                         f'thanh toán: {result["payment_status"]}, tổng tiền {result["total"]}.', 'order_status', calls, results)
        return _done('Mình chưa tìm thấy đơn hàng nào của bạn.', 'order_status', calls, results)

    for topic, keys in {'warranty': ['bao hanh'], 'return': ['doi tra', 'hoan tra', 'tra hang'],
                        'shipping': ['van chuyen', 'phi ship', 'giao hang', 'ship'],
                        'contact': ['lien he', 'hotline', 'dia chi', 'gio lam viec']}.items():
        if any(k in text for k in keys) and not resolve_iphone_model(message)['model']:
            result = call('get_store_policy', topic=topic)
            if topic == 'contact':
                reply = (f'Bạn có thể liên hệ iParts Store qua hotline **{result["hotline"]}**, email {result["email"]}. '
                         f'Giờ làm việc: {result["working_hours"]}.')
            elif topic == 'shipping':
                reply = (f'Phí giao tiêu chuẩn {result["standard_fee"]} (miễn phí cho đơn từ {result["free_shipping_threshold"]}), '
                         f'giao nhanh {result["express_fee"]}.')
            else:
                reply = f'**{result.get("title", "Chính sách")}**\n{result.get("summary", "")[:500]}'
                if result.get('url'):
                    reply += f'\n\n[Xem đầy đủ]({result["url"]})'
            return _done(reply, 'store_policy', calls, results)

    if any(k in text for k in ['khuyen mai', 'giam gia', 'sale', 'ma giam', 'voucher', 'uu dai']):
        result = call('get_promotions')
        reply = 'Các sản phẩm đang giảm giá tại iParts Store:\n' + _product_lines(result['products']) if result['products'] \
            else 'Hiện chưa có sản phẩm giảm giá.'
        if result['coupons']:
            reply += '\n\nMã giảm giá đang áp dụng:\n' + '\n'.join(
                f'- **{c["code"]}**: {c["description"]} (đơn từ {c["min_order_value"]}, hết hạn {c["end_at"]})'
                for c in result['coupons'])
        return _done(reply, 'promotions', calls, results)

    resolved = resolve_iphone_model(message)
    category = resolve_category(message)
    meta = {'iphone_model': resolved['model'].name if resolved['model'] else '', 'category': category.name if category else ''}
    if resolved['model'] or resolved['ambiguous']:
        model = resolved['model']
        if model is None:
            names = ', '.join(m.name for m in resolved['candidates'])
            return _done(f'Bạn đang dùng phiên bản nào: {names}? Mình cần biết chính xác để kiểm tra linh kiện tương thích.',
                         'clarify_model', calls, results, meta=meta)
        result = call('check_compatibility', iphone_model=model.name, category=category.slug if category else '')
        products = result['products']
        if any(k in text for k in ['con hang', 'het hang', 'ton kho']):
            products = [p for p in products if p['stock_status'] != 'out_of_stock'] or products
        cat_label = category.name.lower() if category else 'linh kiện'
        if products:
            reply = f'Mình tìm thấy **{len(products)}** {cat_label} đã xác nhận tương thích với **{model.name}**:\n' + _product_lines(products)
        else:
            reply = (f'Hiện iParts Store chưa có {cat_label} đã xác nhận tương thích với **{model.name}**. '
                     f'Bạn có thể liên hệ hotline **{store.hotline}** để được hỗ trợ.')
        if resolved['ambiguous']:
            others = ', '.join(m.name for m in resolved['candidates'] if m != model)
            reply += f'\n\nLưu ý: kết quả trên dành cho **{model.name}**. Nếu máy bạn là {others}, hãy cho mình biết để kiểm tra lại nhé.'
        return _done(reply, 'compatibility_lookup', calls, results, meta=meta, no_result=not products,
                     link=result.get('lookup_url'))

    if re.search(r'iphone|\bip\s?\d', text):
        return _done(f'Hiện iParts Store chưa hỗ trợ dòng máy bạn hỏi. Bạn vui lòng liên hệ hotline **{store.hotline}** để được tư vấn thêm nhé.',
                     'unsupported_model', calls, results, no_result=True, meta=meta)

    if category:
        result = call('search_products', category=category.slug, in_stock_only=False)
        if result['products']:
            reply = f'Một số {category.name.lower()} đang có tại iParts Store:\n' + _product_lines(result['products']) + \
                    '\n\nBạn cho mình biết dòng iPhone để mình lọc đúng linh kiện tương thích nhé.'
            return _done(reply, 'product_search', calls, results, meta=meta)

    words = [w for w in re.findall(r'\w+', message) if len(w) > 2]
    if words:
        result = call('search_products', query=message[:80])
        if result['products']:
            return _done('Mình tìm thấy các sản phẩm sau:\n' + _product_lines(result['products']), 'product_search', calls, results)
    return _done('Mình là iParts AI Assistant. Bạn hãy cho mình biết **dòng iPhone** và **loại linh kiện** '
                 'cần tìm, ví dụ: "Màn hình iPhone 13 Pro" hoặc "Pin iPhone 11 giá bao nhiêu?".', 'unknown', calls, results,
                 no_result=True)


def _done(reply, intent, calls, results, needs_login=False, meta=None, no_result=False, link=None) -> dict:
    product_ids = []
    for item in results:
        product_ids.extend(tools.collect_product_ids(item['result']))
    return {'reply': reply, 'intent': intent, 'tool_calls': calls, 'tool_results': results,
            'product_ids': product_ids, 'needs_login': needs_login, 'meta': {**(meta or {}), 'no_result': no_result},
            'link': link}


def from_tool_results(tool_results: list[dict], message: str, user=None) -> dict:
    """Câu trả lời dựng hoàn toàn từ dữ liệu tool (khi chữ của AI có giá không khớp dữ liệu)."""
    products, seen = [], set()
    for item in tool_results or []:
        result = item.get('result') or {}
        for p in (result.get('products') or []) + ([result['product']] if isinstance(result.get('product'), dict) else []):
            if isinstance(p, dict) and p.get('id') and p['id'] not in seen and 'price' in p:
                seen.add(p['id'])
                products.append(p)
    if not products:
        return answer(message, user=user)
    reply = 'Đây là thông tin chính xác từ hệ thống iParts Store:\n' + _product_lines(products)
    return _done(reply, 'product_search', [{'name': i['name'], 'args': i.get('args', {})} for i in tool_results],
                 tool_results)
