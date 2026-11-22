"""Truy vấn đọc cho sản phẩm: danh sách có lọc, tra cứu tương thích. Tránh N+1 bằng select/prefetch."""

from django.db.models import Case, IntegerField, Prefetch, Q, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.utils import strip_accents, to_int

from .models import Category, Compatibility, IPhoneModel, Product, ProductImage

SORT_OPTIONS = {
    'newest': 'Mới nhất',
    'price_asc': 'Giá tăng dần',
    'price_desc': 'Giá giảm dần',
    'best_selling': 'Bán chạy',
    'rating': 'Đánh giá cao',
    'name': 'Tên A–Z',
}


def with_card_data(qs):
    """Prefetch đủ dữ liệu cho Product Card (ảnh, model tương thích verified)."""
    return qs.select_related('category', 'brand').prefetch_related(
        Prefetch('images', queryset=ProductImage.objects.order_by('-is_primary', 'display_order', 'id')),
        Prefetch('compatibilities', queryset=Compatibility.objects.filter(
            status=Compatibility.Status.VERIFIED, iphone_model__is_active=True).select_related('iphone_model')),
    )


def public_products():
    """Sản phẩm khách được thấy: đang bán và danh mục đang hoạt động."""
    return Product.objects.filter(status=Product.Status.ACTIVE, category__is_active=True)


def annotate_effective_price(qs):
    now = timezone.now()
    on_sale = (Q(sale_price__isnull=False) & (Q(sale_start__isnull=True) | Q(sale_start__lte=now))
               & (Q(sale_end__isnull=True) | Q(sale_end__gte=now)))
    return qs.annotate(
        eff_price=Case(When(on_sale, then='sale_price'), default='price', output_field=IntegerField()),
        on_sale_flag=Case(When(on_sale, then=Value(1)), default=Value(0), output_field=IntegerField()),
    )


def on_sale_products():
    return annotate_effective_price(public_products()).filter(on_sale_flag=1)


def search_filter(q: str) -> Q:
    """Tìm theo tên, SKU, mô tả ngắn, tên dòng iPhone tương thích; hỗ trợ gõ không dấu."""
    q = q.strip()
    plain = strip_accents(q).lower()
    condition = Q()
    for word in plain.split():
        condition &= (Q(search_text__icontains=word)
                      | Q(compatibilities__iphone_model__name__icontains=word,
                          compatibilities__status=Compatibility.Status.VERIFIED))
    return (Q(name__icontains=q) | Q(sku__icontains=q) | Q(short_description__icontains=q) | condition)


def filter_products(params, base_qs=None):
    """Áp dụng bộ lọc từ tham số URL. Tham số không hợp lệ bị bỏ qua (không gây lỗi 500)."""
    qs = annotate_effective_price(base_qs if base_qs is not None else public_products())
    applied = []
    q = (params.get('q') or '').strip()[:100]
    if q:
        qs = qs.filter(search_filter(q))
        applied.append(('q', q, f'Từ khóa: "{q}"'))
    categories = [c for c in params.getlist('category') if c]
    if categories:
        cats = list(Category.objects.filter(slug__in=categories, is_active=True))
        ids = set()
        for cat in cats:
            ids.update(cat.descendant_ids())
            applied.append(('category', cat.slug, cat.name))
        qs = qs.filter(category_id__in=ids)
    model_slug = params.get('model')
    if model_slug:
        iphone = IPhoneModel.objects.filter(slug=model_slug, is_active=True).first()
        if iphone:
            qs = qs.filter(compatibilities__iphone_model=iphone, compatibilities__status=Compatibility.Status.VERIFIED)
            applied.append(('model', iphone.slug, iphone.name))
    brands = [b for b in params.getlist('brand') if b]
    if brands:
        qs = qs.filter(brand__slug__in=brands)
        for brand in brands:
            applied.append(('brand', brand, f'Thương hiệu: {brand}'))
    qualities = [qv for qv in params.getlist('quality') if qv in Product.Quality.values]
    if qualities:
        qs = qs.filter(quality_grade__in=qualities)
        for qv in qualities:
            applied.append(('quality', qv, Product.Quality(qv).label))
    price_min = to_int(params.get('price_min'), minimum=0)
    price_max = to_int(params.get('price_max'), minimum=0)
    if price_min is not None:
        qs = qs.filter(eff_price__gte=price_min)
        applied.append(('price_min', None, f'Từ {price_min:,}₫'.replace(',', '.')))
    if price_max is not None:
        qs = qs.filter(eff_price__lte=price_max)
        applied.append(('price_max', None, f'Đến {price_max:,}₫'.replace(',', '.')))
    if params.get('in_stock') == '1':
        qs = qs.filter(stock_quantity__gt=0)
        applied.append(('in_stock', None, 'Còn hàng'))
    if params.get('on_sale') == '1':
        qs = qs.filter(on_sale_flag=1)
        applied.append(('on_sale', None, 'Đang giảm giá'))
    sort = params.get('sort') if params.get('sort') in SORT_OPTIONS else 'newest'
    ordering = {
        'newest': ['-created_at'], 'price_asc': ['eff_price'], 'price_desc': ['-eff_price'],
        'best_selling': ['-sold_count', '-created_at'], 'rating': ['-rating_avg', '-rating_count'], 'name': ['name'],
    }[sort]
    qs = qs.order_by(*ordering, 'id').distinct()
    return with_card_data(qs), applied, sort


def compatibility_lookup(iphone: IPhoneModel, category: Category | None = None):
    """Danh sách Compatibility verified cho một dòng iPhone (và danh mục, gồm cả danh mục con).

    Sắp xếp: còn hàng trước, sau đó chất lượng (chính hãng > OEM > thay thế), rồi giá.
    """
    qs = Compatibility.objects.filter(
        status=Compatibility.Status.VERIFIED, iphone_model=iphone,
        product__status=Product.Status.ACTIVE, product__category__is_active=True,
    )
    if category is not None:
        qs = qs.filter(product__category_id__in=category.descendant_ids())
    quality_rank = Case(
        When(product__quality_grade='original', then=Value(0)),
        When(product__quality_grade='oem', then=Value(1)),
        default=Value(2), output_field=IntegerField(),
    )
    in_stock_rank = Case(When(product__stock_quantity__gt=0, then=Value(0)), default=Value(1), output_field=IntegerField())
    return (qs.annotate(in_stock_rank=in_stock_rank, quality_rank=quality_rank,
                        price_rank=Coalesce('product__sale_price', 'product__price'))
            .order_by('in_stock_rank', 'quality_rank', 'price_rank')
            .select_related('product', 'product__category', 'product__brand', 'iphone_model')
            .prefetch_related('product__images'))


def iphone_models_grouped():
    groups: dict[int, dict] = {}
    for model in IPhoneModel.objects.filter(is_active=True).order_by('-series', 'display_order', 'name'):
        group = groups.setdefault(model.series, {'series': model.series, 'label': model.series_label, 'models': []})
        group['models'].append(model)
    return list(groups.values())


def product_compatibility_for(product: Product, iphone: IPhoneModel) -> tuple[str, str]:
    """Trả ('verified'|'incompatible'|'unknown', ghi chú). unverified coi như unknown với khách."""
    comp = Compatibility.objects.filter(product=product, iphone_model=iphone).first()
    if comp is None or comp.status == Compatibility.Status.UNVERIFIED:
        return 'unknown', ''
    return comp.status, comp.note
