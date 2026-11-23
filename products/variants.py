"""Chọn tổ hợp LOẠI MÀN × MÀU trên trang chi tiết – dùng chung cho lần render đầu và API đổi lựa chọn.

Giá cuối = giá của biến thể (loại màn + màu). Không cộng thêm gì; bảo hành cố định 12 tháng miễn phí.
"""

from urllib.parse import urlencode

from core.constants import WARRANTY_LABEL, WARRANTY_MONTHS, WARRANTY_SHORT


def _pick(items, slug, default):
    if slug:
        found = next((x for x in items if x.slug == slug), None)
        if found:
            return found
    return default


def resolve_selection(product, loai_slug: str | None = None, mau_slug: str | None = None) -> dict:
    """Trả về toàn bộ dữ liệu khối giá + nhóm chọn cho 1 tổ hợp.

    Quy tắc:
    - Lần đầu (không có tham số): loại màn mặc định + màu mặc định còn hàng.
      Loại mặc định hết sạch hàng -> loại đầu tiên còn hàng.
    - Đổi loại màn: luôn chọn được. Nếu màu đang chọn của loại đó hết hàng / không có -> tự chuyển sang
      màu còn hàng gần nhất (theo thứ tự) và trả `notice`, vd "Màu Trắng tạm hết, đã chuyển sang Đen".
    - Thẻ loại màn: giá của loại đó với màu đang chọn; mờ "Hết hàng" khi mọi màu của loại đó hết hàng.
    - Thẻ màu: giá của màu đó với loại màn đang chọn; mờ "Hết hàng" khi tổ hợp đó hết hàng.
    """
    options = product.active_options
    colors = product.active_colors
    variants = product.active_variants
    vmap = {(v.option_id, v.color_id): v for v in variants}

    def get(o, c):
        return vmap.get((o.pk if o else None, c.pk if c else None))

    def in_stock(o, c):
        v = get(o, c)
        return v is not None and v.stock > 0

    # Chỉ hiện nhóm có dữ liệu biến thể
    options = [o for o in options if any(v.option_id == o.pk for v in variants)]
    colors = [c for c in colors if any(v.color_id == c.pk for v in variants)]
    first_visit = not loai_slug and not mau_slug
    notice = ''

    # ---- Loại màn
    option = None
    if options:
        default_opt = next((o for o in options if o.is_default), options[0])
        option = _pick(options, loai_slug, default_opt)
        if first_visit and not any(in_stock(option, c) for c in (colors or [None])):
            option = next((o for o in options if any(in_stock(o, c) for c in (colors or [None]))), option)

    # ---- Màu
    color = None
    if colors:
        default_col = next((c for c in colors if c.is_default), colors[0])
        requested = _pick(colors, mau_slug, default_col)
        color = requested
        if not in_stock(option, color):
            # Màu còn hàng gần nhất theo thứ tự hiển thị
            idx = colors.index(requested)
            ordered = sorted(range(len(colors)), key=lambda i: (abs(i - idx), i))
            alt = next((colors[i] for i in ordered if in_stock(option, colors[i])), None)
            if alt is not None and alt != requested:
                color = alt
                if mau_slug or not first_visit:
                    notice = f'Màu {requested.name} tạm hết, đã chuyển sang {alt.name}.'
            elif get(option, requested) is None:
                color = next((c for c in colors if get(option, c) is not None), requested)

    variant = get(option, color) if variants else None
    has_variants = bool(variants)

    # ---- Ô giá
    if variant is not None:
        price, original, discount = variant.effective_price, variant.original_price, variant.discount_percent
        opt = variant.priced_option
        promo_end = opt.sale_end if opt is not None and opt.is_on_sale else None
        stock, stock_status, stock_label = variant.stock, variant.stock_status, variant.stock_label
        sku = variant.sku or product.sku
        image = ((variant.image.url if variant.image else '') or (color.image.url if color and color.image else '')
                 or product.image_url)
    else:
        price = product.effective_price
        original = product.price if product.is_on_sale else None
        discount = product.discount_percent
        promo_end = product.sale_end if product.is_on_sale else None
        stock = 0 if has_variants else product.stock_quantity
        stock_status = 'out_of_stock' if has_variants else product.stock_status
        stock_label = 'Hết hàng' if has_variants else product.stock_label
        sku, image = product.sku, product.image_url

    def query(o, c) -> str:
        q = {}
        if o:
            q['loai'] = o.slug
        if c:
            q['mau'] = c.slug
        return '?' + urlencode(q) if q else ''

    option_cards = []
    for o in options:
        v = get(o, color) or next((get(o, c) for c in colors if get(o, c)), None) if colors else get(o, None)
        option_cards.append({
            'slug': o.slug, 'name': o.name, 'selected': option is not None and o.pk == option.pk,
            'price': v.effective_price if v else None, 'original_price': v.original_price if v else None,
            'disabled': not any(in_stock(o, c) for c in (colors or [None])), 'query': query(o, color),
        })
    color_cards = []
    for c in colors:
        v = get(option, c)
        color_cards.append({
            'slug': c.slug, 'name': c.name, 'hex': c.hex_code, 'image': c.image.url if c.image else '',
            'selected': color is not None and c.pk == color.pk, 'price': v.effective_price if v else None,
            'disabled': not in_stock(option, c), 'query': query(option, c),
        })

    label_parts = [x.name for x in (option, color) if x is not None]
    can_buy = product.is_purchasable and (not has_variants or (variant is not None and variant.stock > 0))
    return {
        'has_variants': has_variants,
        'option_label': product.option_label or 'Loại màn hình',
        'option': option, 'color': color, 'variant': variant,
        'variant_id': variant.pk if variant else None,
        'option_cards': option_cards, 'color_cards': color_cards,
        'option_description': option.description if option else '',
        'price': price, 'original_price': original, 'discount_percent': discount, 'promo_end': promo_end,
        'stock_status': stock_status, 'stock_label': stock_label, 'max_qty': max(0, min(stock, 10)),
        'sku': sku, 'image': image, 'can_buy': can_buy, 'notice': notice,
        'label': ' · '.join(label_parts),
        'summary': ' · '.join(label_parts + [f'{WARRANTY_SHORT} miễn phí']),
        'query': query(option, color),
        'warranty_months': WARRANTY_MONTHS, 'warranty_label': WARRANTY_LABEL,
    }
