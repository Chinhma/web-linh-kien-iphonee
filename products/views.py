from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from core.constants import WARRANTY_MONTHS
from core.models import FAQ, Banner, Page, StoreSetting
from core.utils import api_error, api_ok
from reviews.models import Review

from .models import Category, Compatibility, IPhoneModel, Product
from .variants import resolve_selection
from .selectors import (SORT_OPTIONS, compatibility_lookup, filter_products, iphone_models_grouped, on_sale_products,
                        product_compatibility_for, public_products, search_filter, with_card_data)

PER_PAGE = 12


def wishlist_ids(request) -> set:
    if request.user.is_authenticated and not request.user.is_staff:
        return set(request.user.wishlist_items.values_list('product_id', flat=True))
    return set()


def home(request):
    categories = (Category.objects.filter(is_active=True, parent__isnull=True)
                  .annotate(product_total=Count('products', filter=Q(products__status='active'), distinct=True)
                            + Count('children__products', filter=Q(children__products__status='active'), distinct=True)))
    base = with_card_data(public_products())
    on_sale = list(with_card_data(on_sale_products()).order_by('-sold_count')[:24])
    on_sale.sort(key=lambda p: -p.discount_percent)
    from chatbot.models import ChatbotSetting

    return render(request, 'store/home.html', {
        'banners': Banner.objects.filter(is_active=True),
        'categories': categories,
        'iphone_groups': iphone_models_grouped(),
        'featured': base.filter(is_featured=True)[:8],
        'on_sale': on_sale[:8],
        'best_sellers': base.filter(sold_count__gt=0).order_by('-sold_count')[:8],
        'new_products': base.order_by('-created_at')[:8],
        'reviews': Review.objects.filter(status='approved', rating__gte=4).select_related('user', 'product')[:6],
        'faqs': FAQ.objects.filter(is_active=True)[:8],
        'chat_questions': ChatbotSetting.get_solo().suggested_questions[:3],
        'wishlist_ids': wishlist_ids(request),
    })


def _listing(request, template_ctx: dict, base_qs=None):
    qs, applied, sort = filter_products(request.GET, base_qs)
    page = Paginator(qs, PER_PAGE).get_page(request.GET.get('page'))
    selected_categories = request.GET.getlist('category')
    context = {
        'page_obj': page,
        'products': page.object_list,
        'applied_filters': applied,
        'sort': sort,
        'sort_options': SORT_OPTIONS,
        'filter_categories': Category.objects.filter(is_active=True, parent__isnull=True).prefetch_related('children'),
        'iphone_groups': iphone_models_grouped(),
        'quality_choices': Product.Quality.choices,
        'selected_categories': selected_categories,
        'selected_brands': request.GET.getlist('brand'),
        'selected_qualities': request.GET.getlist('quality'),
        'wishlist_ids': wishlist_ids(request),
        **template_ctx,
    }
    return render(request, 'store/product_list.html', context)


def product_list(request):
    return _listing(request, {'page_title': 'Tất cả sản phẩm', 'breadcrumbs': [('Sản phẩm', None)]})


def sale_list(request):
    return _listing(request, {'page_title': 'Sản phẩm đang khuyến mãi', 'breadcrumbs': [('Khuyến mãi', None)],
                              'fixed_on_sale': True}, base_qs=on_sale_products())


def new_list(request):
    since = timezone.now() - timezone.timedelta(days=60)
    return _listing(request, {'page_title': 'Sản phẩm mới', 'breadcrumbs': [('Sản phẩm mới', None)]},
                    base_qs=public_products().filter(created_at__gte=since))


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    crumbs = [(category.parent.name, category.parent.get_absolute_url())] if category.parent_id else []
    crumbs.append((category.name, None))
    return _listing(request, {'page_title': category.name, 'category': category, 'breadcrumbs': crumbs},
                    base_qs=public_products().filter(category_id__in=category.descendant_ids()))


def _detail_queryset():
    return (with_card_data(Product.objects.all())
            .prefetch_related('compatibilities__iphone_model', 'colors', 'variants__option', 'variants__color'))


def _purchase_context(request, product, sel) -> dict:
    """Ngữ cảnh chung cho khối chọn mua + thanh mua dính ở đáy (render lần đầu và trả qua API)."""
    return {'product': product, 'sel': sel, 'can_buy': sel['can_buy'], 'max_qty': sel['max_qty'],
            'in_wishlist': product.pk in wishlist_ids(request)}


def product_detail(request, slug):
    product = _detail_queryset().filter(slug=slug).first()
    if product is None:
        raise Http404
    preview_warning = ''
    if product.status != Product.Status.ACTIVE or not product.category.is_active:
        if not request.user.is_staff:
            raise Http404
        preview_warning = f'Sản phẩm đang ở trạng thái "{product.get_status_display()}" – chỉ Admin xem được trang này.'
    Product.objects.filter(pk=product.pk).update(view_count=F('view_count') + 1)
    all_comps = list(Compatibility.objects.filter(product=product, iphone_model__is_active=True).select_related('iphone_model'))
    verified = [c for c in all_comps if c.status == Compatibility.Status.VERIFIED]
    incompatible = [c for c in all_comps if c.status == Compatibility.Status.INCOMPATIBLE]

    reviews = Review.objects.filter(product=product, status=Review.Status.APPROVED).select_related('user')
    star_filter = request.GET.get('sao')
    distribution = {i: 0 for i in range(5, 0, -1)}
    for row in reviews.values('rating').annotate(c=Count('id')):
        distribution[row['rating']] = row['c']
    if star_filter in {'1', '2', '3', '4', '5'}:
        reviews = reviews.filter(rating=int(star_filter))
    review_page = Paginator(reviews, 5).get_page(request.GET.get('trang_dg'))

    sel = resolve_selection(product, request.GET.get('loai'), request.GET.get('mau'))

    model_ids = [c.iphone_model_id for c in verified]
    related = (with_card_data(public_products().exclude(pk=product.pk)
                              .filter(Q(category=product.category) | Q(compatibilities__iphone_model_id__in=model_ids,
                                                                       compatibilities__status='verified')))
               .distinct().order_by('-sold_count')[:8])
    bought_together = []
    if model_ids:
        bought_together = (with_card_data(public_products().exclude(category=product.category)
                                          .filter(compatibilities__iphone_model_id=model_ids[0], compatibilities__status='verified'))
                           .distinct().order_by('-sold_count')[:4])
    from reviews.services import can_review_product

    store = StoreSetting.get_solo()
    warranty_page = Page.objects.filter(slug='chinh-sach-bao-hanh', is_published=True).first()
    crumbs = [('Sản phẩm', '/san-pham/')]
    if product.category.parent_id:
        crumbs.append((product.category.parent.name, product.category.parent.get_absolute_url()))
    crumbs += [(product.category.name, product.category.get_absolute_url()), (product.name, None)]
    return render(request, 'store/product_detail.html', {
        'product': product,
        'images': list(product.images.all()),
        'verified_comps': verified,
        'incompatible_comps': incompatible,
        'iphone_groups': iphone_models_grouped(),
        'reviews_page': review_page,
        'distribution': distribution,
        'star_filter': star_filter,
        'review_item': can_review_product(request.user, product),
        'related': related,
        'bought_together': bought_together,
        'in_wishlist': product.pk in wishlist_ids(request),
        'wishlist_ids': wishlist_ids(request),
        'max_qty': sel['max_qty'],
        'sel': sel,
        'can_buy': sel['can_buy'],
        'store': store,
        'warranty_page': warranty_page,
        'preview_warning': preview_warning,
        'breadcrumbs': crumbs,
    })


def compatibility_page(request):
    from django.urls import reverse

    return render(request, 'store/compatibility.html', {
        'iphone_groups': iphone_models_grouped(),
        'categories': Category.objects.filter(is_active=True, parent__isnull=True).prefetch_related('children'),
        'breadcrumbs': [('Tra cứu linh kiện tương thích', None)],
        'api_url': reverse('products:api_compatibility'),
    })


# ------------------------------------------------------------------ API JSON
def _compat_item(c: Compatibility) -> dict:
    p = c.product
    specs = p.specifications if isinstance(p.specifications, list) else []
    return {
        'id': p.pk, 'name': p.name, 'sku': p.sku, 'url': p.get_absolute_url(), 'image': p.image_url,
        'quality': p.get_quality_grade_display(), 'quality_code': p.quality_grade,
        'price': p.effective_price, 'original_price': p.price if p.is_on_sale else None,
        'discount_percent': p.discount_percent, 'stock_status': p.stock_status, 'stock_label': p.stock_label,
        'warranty_months': WARRANTY_MONTHS, 'specs': specs[:3], 'note': c.note,
        'category': p.category.parent.name if p.category.parent_id else p.category.name,
        'category_slug': p.category.slug,
        'purchasable': p.stock_quantity > 0,
    }


@require_GET
def api_compatibility(request):
    """GET /api/compatibility/?model=<slug>&category=<slug> – chỉ trả quan hệ VERIFIED, sản phẩm đang bán."""
    model = IPhoneModel.objects.filter(slug=request.GET.get('model', ''), is_active=True).first()
    if model is None:
        return api_error('INVALID_MODEL', 'Vui lòng chọn dòng iPhone hợp lệ.', status=400)
    category = None
    if request.GET.get('category'):
        category = Category.objects.filter(slug=request.GET['category'], is_active=True).first()
        if category is None:
            return api_error('INVALID_CATEGORY', 'Loại linh kiện không hợp lệ.', status=400)
    items = [_compat_item(c) for c in compatibility_lookup(model, category)]
    available = []
    if not items and category is not None:
        available = list(Category.objects.filter(
            is_active=True, products__compatibilities__iphone_model=model,
            products__compatibilities__status='verified', products__status='active').distinct().values('name', 'slug'))
    return api_ok({
        'model': {'name': model.name, 'slug': model.slug},
        'category': {'name': category.name, 'slug': category.slug} if category else None,
        'count': len(items), 'items': items, 'other_categories': available,
        'sample_notice': StoreSetting.get_solo().show_sample_data_notice,
    })


@require_GET
def api_product_variant(request, pk):
    """GET /api/products/<pk>/variant/?loai=&mau= – giá + tồn kho + HTML khối chọn mua của tổ hợp (server tính giá)."""
    from django.template.loader import render_to_string

    product = _detail_queryset().filter(pk=pk).first()
    if product is None or (product.status != Product.Status.ACTIVE and not request.user.is_staff):
        return api_error('NOT_FOUND', 'Sản phẩm không tồn tại.', status=404)
    sel = resolve_selection(product, request.GET.get('loai'), request.GET.get('mau'))
    ctx = _purchase_context(request, product, sel)
    return api_ok({
        'variant_id': sel['variant_id'], 'price': sel['price'], 'original_price': sel['original_price'],
        'discount_percent': sel['discount_percent'], 'stock_status': sel['stock_status'], 'sku': sel['sku'],
        'image': sel['image'], 'query': sel['query'], 'notice': sel['notice'], 'summary': sel['summary'],
        'panel_html': render_to_string('store/_purchase_panel.html', ctx, request),
        'bar_html': render_to_string('store/_buy_bar.html', ctx, request),
    })


@require_GET
def api_product_check(request, pk):
    """Ô "Kiểm tra máy của bạn" trên trang chi tiết."""
    product = get_object_or_404(public_products(), pk=pk)
    model = IPhoneModel.objects.filter(slug=request.GET.get('model', ''), is_active=True).first()
    if model is None:
        return api_error('INVALID_MODEL', 'Vui lòng chọn dòng iPhone.', status=400)
    status, note = product_compatibility_for(product, model)
    return api_ok({'status': status, 'note': note, 'model': model.name})


@require_GET
def api_iphone_models(request):
    return api_ok({'groups': [{'series': g['series'], 'label': g['label'],
                               'models': [{'name': m.name, 'slug': m.slug} for m in g['models']]}
                              for g in iphone_models_grouped()]})


@require_GET
def api_categories(request):
    return api_ok({'categories': [{'name': c.name, 'slug': c.slug, 'icon': c.icon, 'parent': c.parent.slug if c.parent_id else None}
                                  for c in Category.objects.filter(is_active=True).select_related('parent')]})


@require_GET
def api_search_suggest(request):
    q = (request.GET.get('q') or '').strip()[:100]
    if len(q) < 2:
        return api_ok({'products': []})
    products = with_card_data(public_products().filter(search_filter(q)).distinct().order_by('-sold_count'))[:6]
    return api_ok({'products': [{'name': p.name, 'url': p.get_absolute_url(), 'image': p.image_url,
                                 'price': p.effective_price} for p in products]})
