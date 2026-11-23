"""Quản lý sản phẩm, linh kiện tương thích và kho hàng."""

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.permissions import staff_required
from core.utils import to_int
from inventory.models import InventoryTransaction
from inventory.services import adjust_stock
from products.models import Category, Compatibility, IPhoneModel, Product, ProductImage
from products.selectors import annotate_effective_price, iphone_models_grouped

from ..forms import CompatibilityAddForm, CompatibilityEditForm, ProductForm, ProductImagesForm
from .common import csv_response, table


# ------------------------------------------------------------------ Sản phẩm
def _category_tree():
    return Category.objects.filter(parent__isnull=True).prefetch_related('children').order_by('display_order')


def _product_csv(qs):
    return csv_response('san-pham', ['SKU', 'Mã linh kiện', 'Tên', 'Danh mục', 'Chất lượng', 'Giá bán', 'Giá KM', 'Giá nhập',
                                     'Tồn kho', 'Đã bán', 'Trạng thái'],
                        ([p.sku, p.part_code, p.name, p.category.name, p.get_quality_grade_display(), p.price, p.sale_price or '',
                          p.cost_price, p.stock_quantity, p.sold_count, p.get_status_display()] for p in qs))


@staff_required
def product_list(request):
    qs = annotate_effective_price(Product.objects.select_related('category').prefetch_related('images'))
    g = request.GET
    if g.get('category'):
        cat = Category.objects.filter(slug=g['category']).first()
        qs = qs.filter(category_id__in=cat.descendant_ids()) if cat else qs.none()
    if g.get('quality') in Product.Quality.values:
        qs = qs.filter(quality_grade=g['quality'])
    if g.get('status'):
        qs = qs.filter(status=g['status'])
    if g.get('stock') == 'out':
        qs = qs.filter(stock_quantity=0)
    elif g.get('stock') == 'low':
        qs = qs.filter(stock_quantity__gt=0, stock_quantity__lte=F('low_stock_threshold'))
    elif g.get('stock') == 'in':
        qs = qs.filter(stock_quantity__gt=F('low_stock_threshold'))
    if g.get('model'):
        qs = qs.filter(compatibilities__iphone_model__slug=g['model']).distinct()
    if g.get('on_sale') == '1':
        qs = qs.filter(on_sale_flag=1)
    if g.get('export') == 'csv':
        return _product_csv(qs.order_by('name'))
    ctx = table(request, qs, ('name', 'sku', 'part_code'), {'name': 'name', 'price': 'eff_price', 'stock': 'stock_quantity',
                                                           'sold': 'sold_count', 'created': 'created_at'}, '-created_at')
    allp = Product.objects.all()
    stats = {'total': allp.count(), 'active': allp.filter(status='active').count(),
             'low': allp.filter(stock_quantity__gt=0, stock_quantity__lte=F('low_stock_threshold')).count(),
             'out': allp.filter(stock_quantity=0).count()}
    low_view = g.get('stock') == 'low'
    return render(request, 'dashboard/products.html', {
        **ctx, 'page_title': 'Sản phẩm sắp hết hàng' if low_view else 'Sản phẩm',
        'page_description': 'Nhập kho nhanh cho từng dòng.' if low_view else 'Quản lý linh kiện đang kinh doanh.',
        'stats': stats, 'category_tree': _category_tree(),
        'statuses': Product.Status.choices, 'qualities': Product.Quality.choices, 'iphone_groups': iphone_models_grouped(),
        'has_filters': any(g.get(k) for k in ('q', 'category', 'quality', 'status', 'stock', 'model', 'on_sale')),
    })


@staff_required
@require_POST
def product_bulk(request):
    ids = [to_int(i) for i in request.POST.getlist('ids') if to_int(i)]
    action = request.POST.get('action')
    qs = Product.objects.filter(pk__in=ids)
    if action == 'export':
        return _product_csv(qs.select_related('category').order_by('name'))
    if action in Product.Status.values:
        count = qs.update(status=action)
    elif action in ('feature', 'unfeature'):
        count = qs.update(is_featured=action == 'feature')
    else:
        messages.error(request, 'Thao tác không hợp lệ.')
        return redirect('dashboard:product_list')
    messages.success(request, f'Đã cập nhật {count} sản phẩm.')
    return redirect(request.POST.get('next') or 'dashboard:product_list')


@staff_required
@require_POST
def product_toggle_featured(request, pk):
    product = get_object_or_404(Product, pk=pk)
    Product.objects.filter(pk=pk).update(is_featured=not product.is_featured)
    return JsonResponse({'ok': True, 'data': {'is_featured': not product.is_featured}})


def _save_images(request, product):
    form = ProductImagesForm(request.POST, request.FILES)
    if not form.is_valid():
        for errors in form.errors.values():
            for e in errors:
                messages.error(request, f'Ảnh không hợp lệ: {e}')
        return
    start = product.images.count()
    for i, f in enumerate(form.cleaned_data['images']):
        ProductImage.objects.create(product=product, image=f, alt_text=product.name, display_order=start + i,
                                    is_primary=not product.images.exists())
    primary = to_int(request.POST.get('primary_image'))
    if primary:
        img = product.images.filter(pk=primary).first()
        if img:
            img.is_primary = True
            img.save()
    for img_id in request.POST.getlist('delete_images'):
        img = product.images.filter(pk=to_int(img_id)).first()
        if img:
            img.image.delete(save=False)
            img.delete()
    for img in product.images.all():
        order = to_int(request.POST.get(f'order_{img.pk}'))
        if order is not None and order != img.display_order:
            ProductImage.objects.filter(pk=img.pk).update(display_order=order)
    if not product.images.filter(is_primary=True).exists() and product.images.exists():
        first = product.images.order_by('display_order').first()
        first.is_primary = True
        first.save()


def _save_compat(request, product):
    selected = {to_int(i) for i in request.POST.getlist('compat_models') if to_int(i)}
    default_status = request.POST.get('compat_status') or Compatibility.Status.VERIFIED
    note = request.POST.get('compat_note', '').strip()[:300]
    existing = {c.iphone_model_id: c for c in product.compatibilities.all()}
    for model_id in selected - existing.keys():
        comp = Compatibility(product=product, iphone_model_id=model_id, note=note, source='Admin nhập')
        comp.set_status(default_status, request.user)
        comp.save()
    Compatibility.objects.filter(product=product, iphone_model_id__in=existing.keys() - selected).delete()


def _variant_editor_data(form, product) -> dict:
    """Dữ liệu 3 bảng: loại màn, màu sắc, biến thể. Form lỗi thì lấy lại dữ liệu vừa gửi (ảnh mới phải chọn lại)."""
    if form.is_bound:
        def val(name):
            v = form[name].value()
            return v if isinstance(v, list) else []
        return {'options': val('options_data'), 'colors': val('colors_data'), 'variants': val('variants_data')}
    if product is None:
        return {'options': [], 'colors': [], 'variants': []}
    return {
        'options': [{'id': o.pk, 'key': str(o.pk), 'name': o.name, 'description': o.description,
                     'is_default': o.is_default, 'is_active': o.is_active} for o in product.options.all()],
        'colors': [{'id': c.pk, 'key': str(c.pk), 'name': c.name, 'hex_code': c.hex_code,
                    'image': c.image.url if c.image else '', 'is_default': c.is_default, 'is_active': c.is_active}
                   for c in product.colors.all()],
        'variants': [{'id': v.pk, 'key': f'v{v.pk}', 'option_key': str(v.option_id or ''), 'color_key': str(v.color_id or ''),
                      'price': v.price, 'compare_price': v.compare_price, 'stock': v.stock, 'sku': v.sku,
                      'image': v.image.url if v.image else '', 'is_active': v.is_active}
                     for v in product.variants.all()],
    }


@staff_required
def product_form(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None
    form = ProductForm(request.POST or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            obj = form.save()
            if product is None and form.cleaned_data.get('initial_stock'):
                adjust_stock(obj, form.cleaned_data['initial_stock'], InventoryTransaction.Type.INITIAL, request.user,
                             'Tồn kho ban đầu khi tạo sản phẩm', unit_cost=obj.cost_price or None)
            _save_compat(request, obj)
            form.save_variants(obj, request.FILES, request.user)
        _save_images(request, obj)
        messages.success(request, f'Đã lưu thành công sản phẩm "{obj.name}".')
        if request.POST.get('save_add'):
            return redirect('dashboard:product_add')
        return redirect('dashboard:product_edit', pk=obj.pk)  # Sửa xong ở lại trang sửa
    compat_ids = set(product.compatibilities.values_list('iphone_model_id', flat=True)) if product else set()
    return render(request, 'dashboard/product_form.html', {
        'page_title': f'Sửa: {product.name}' if product else 'Thêm sản phẩm mới', 'form': form, 'product': product,
        'images': product.images.all() if product else [], 'iphone_groups': iphone_models_grouped(),
        'compat_ids': compat_ids, 'compat_statuses': Compatibility.Status.choices,
        'category_codes': {c.pk: (c.parent.code if c.parent_id else c.code) for c in Category.objects.select_related('parent')},
        'specs_json': product.specifications if product else [],
        'highlights_json': product.highlights if product else [],
        'variant_editor': _variant_editor_data(form, product),
        'has_orders': product.order_items.exists() if product else False,
    })


@staff_required
def product_suggest_sku(request):
    from ..forms import generate_sku

    category = Category.objects.filter(pk=to_int(request.GET.get('category'))).first()
    if category is None:
        return JsonResponse({'ok': False, 'message': 'Chọn danh mục trước.'}, status=400)
    return JsonResponse({'ok': True, 'data': {'sku': generate_sku(category, request.GET.get('model', ''))}})


@staff_required
@require_POST
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if product.order_items.exists():
        Product.objects.filter(pk=pk).update(status=Product.Status.DISCONTINUED)
        messages.warning(request, f'"{product.name}" đã có trong đơn hàng nên không thể xóa – đã chuyển sang "Ngừng kinh doanh".')
    else:
        with transaction.atomic():
            InventoryTransaction.objects.filter(product=product).delete()
            for img in product.images.all():
                img.image.delete(save=False)
            product.delete()
        messages.success(request, f'Đã xóa sản phẩm "{product.name}".')
    return redirect('dashboard:product_list')


@staff_required
@require_POST
def product_duplicate(request, pk):
    """Nhân bản sản phẩm sang dòng máy khác: tạo bản Nháp, tồn kho 0, tương thích thay bằng dòng máy mới chọn."""
    from ..forms import generate_sku

    source = get_object_or_404(Product, pk=pk)
    target = IPhoneModel.objects.filter(pk=to_int(request.POST.get('iphone_model'))).first()
    old_models = [c.iphone_model for c in source.compatibilities.select_related('iphone_model').order_by('iphone_model__series')]
    product = Product.objects.get(pk=pk)
    product.pk = None
    product.slug = ''
    product.name = f'{source.name} (bản sao)'
    if target:
        for m in sorted(old_models, key=lambda x: -len(x.name)):
            if m.name in source.name:
                product.name = source.name.replace(m.name, target.name)
                break
        else:
            product.name = f'{source.name} – {target.name}'
    product.sku = generate_sku(source.category, target.name if target else 'COPY')
    product.status = Product.Status.DRAFT
    product.stock_quantity = product.sold_count = product.rating_count = product.view_count = 0
    product.rating_avg = 0
    product.save()
    # Nhân bản loại màn, màu, biến thể (giữ giá, tồn kho về 0 như sản phẩm)
    option_map, color_map = {}, {}
    for option in source.options.all():
        old = option.pk
        option.pk = None
        option.product = product
        option.save()
        option_map[old] = option
    for color in source.colors.all():
        old = color.pk
        color.pk = None
        color.product = product
        color.save()
        color_map[old] = color
    for variant in source.variants.all():
        variant.pk = None
        variant.product = product
        variant.option = option_map.get(variant.option_id)
        variant.color = color_map.get(variant.color_id)
        variant.stock = 0
        variant.save()
    if target:
        comp = Compatibility(product=product, iphone_model=target, source='Nhân bản – cần kiểm tra')
        comp.set_status(Compatibility.Status.UNVERIFIED, request.user)
        comp.save()
    else:
        for c in source.compatibilities.all():
            Compatibility.objects.create(product=product, iphone_model_id=c.iphone_model_id, status=c.status, note=c.note,
                                         source=c.source, is_sample_data=c.is_sample_data)
    messages.success(request, f'Đã nhân bản thành "{product.name}" (Nháp, tồn kho 0). Hãy kiểm tra giá, ảnh và xác nhận tương thích.')
    return redirect('dashboard:product_edit', pk=product.pk)


# ------------------------------------------------------------------ Tương thích
@staff_required
def compat_list(request):
    qs = Compatibility.objects.select_related('product', 'product__category', 'iphone_model', 'verified_by').prefetch_related('product__images')
    g = request.GET
    if g.get('model'):
        qs = qs.filter(iphone_model__slug=g['model'])
    if g.get('category'):
        cat = Category.objects.filter(slug=g['category']).first()
        if cat:
            qs = qs.filter(product__category_id__in=cat.descendant_ids())
    if g.get('status'):
        qs = qs.filter(status=g['status'])
    if g.get('sample') in ('1', '0'):
        qs = qs.filter(is_sample_data=g['sample'] == '1')
    ctx = table(request, qs, ('product__name', 'product__sku', 'iphone_model__name'),
                {'product': 'product__name', 'model': 'iphone_model__series', 'status': 'status', 'verified': 'verified_at'},
                'iphone_model__series')
    # Thống kê: số dòng iPhone chưa có linh kiện verified cho mỗi danh mục gốc
    total_models = IPhoneModel.objects.filter(is_active=True).count()
    gaps = []
    for cat in Category.objects.filter(parent__isnull=True, is_active=True):
        covered = (IPhoneModel.objects.filter(is_active=True, compatibilities__status='verified',
                                              compatibilities__product__category_id__in=cat.descendant_ids()).distinct().count())
        gaps.append({'name': cat.name, 'missing': total_models - covered})
    return render(request, 'dashboard/compat_list.html', {
        **ctx, 'page_title': 'Linh kiện tương thích', 'iphone_groups': iphone_models_grouped(),
        'page_description': 'Nguồn dữ liệu duy nhất cho trang tra cứu, trang sản phẩm và chatbot – chỉ "Đã xác nhận" hiển thị cho khách.',
        'categories': Category.objects.all(), 'statuses': Compatibility.Status.choices, 'gaps': gaps,
    })


@staff_required
def compat_add(request):
    """Thêm tương thích: 1 sản phẩm + NHIỀU dòng iPhone. Cặp đã tồn tại thì bỏ qua và báo."""
    if request.method == 'POST':
        form = CompatibilityAddForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Vui lòng chọn sản phẩm, ít nhất một dòng iPhone và trạng thái.')
            return redirect(request.get_full_path())
        product = form.cleaned_data['product']
        created, skipped = 0, []
        for model in form.cleaned_data['iphone_models']:
            if Compatibility.objects.filter(product=product, iphone_model=model).exists():
                skipped.append(model.name)
                continue
            comp = Compatibility(product=product, iphone_model=model, note=form.cleaned_data['note'],
                                 source=form.cleaned_data['source'])
            comp.set_status(form.cleaned_data['status'], request.user)
            comp.save()
            created += 1
        if created:
            messages.success(request, f'Đã thêm {created} quan hệ tương thích cho "{product.name}".')
        if skipped:
            messages.warning(request, f'Bỏ qua cặp đã tồn tại: {", ".join(skipped)}.')
        return redirect(f"{reverse('dashboard:compat_list')}?q={product.sku}")
    return render(request, 'dashboard/compat_add.html', {
        'page_title': 'Thêm tương thích', 'page_description': 'Chọn 1 sản phẩm và một hoặc nhiều dòng iPhone tương thích.',
        'iphone_groups': iphone_models_grouped(), 'statuses': Compatibility.Status.choices,
        'preset': Product.objects.filter(pk=to_int(request.GET.get('product'))).first(),
        'preset_model': to_int(request.GET.get('model'))})


@staff_required
def compat_edit(request, pk):
    comp = get_object_or_404(Compatibility.objects.select_related('product', 'iphone_model'), pk=pk)
    old_status = comp.status
    form = CompatibilityEditForm(request.POST or None, instance=comp)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        if obj.status != old_status:
            obj.set_status(obj.status, request.user)
        obj.save()
        messages.success(request, 'Đã cập nhật quan hệ tương thích.')
        return redirect('dashboard:compat_list')
    return render(request, 'dashboard/compat_edit.html', {'menu': 'compat', 'page_title': 'Sửa tương thích', 'form': form, 'comp': comp})


@staff_required
@require_POST
def compat_bulk(request):
    ids = [to_int(i) for i in request.POST.getlist('ids') if to_int(i)]
    action = request.POST.get('action')
    comps = Compatibility.objects.filter(pk__in=ids)
    if action == 'delete':
        count = comps.count()
        comps.delete()
    elif action in Compatibility.Status.values:
        count = 0
        for comp in comps:
            comp.set_status(action, request.user)
            comp.save()
            count += 1
    else:
        messages.error(request, 'Thao tác không hợp lệ.')
        return redirect('dashboard:compat_list')
    messages.success(request, f'Đã cập nhật {count} quan hệ tương thích.')
    return redirect(request.POST.get('next') or 'dashboard:compat_list')


@staff_required
def compat_matrix(request):
    """Chế độ ma trận: hàng = sản phẩm, cột = dòng iPhone, ô = trạng thái (bấm để đổi)."""
    categories = Category.objects.filter(is_active=True)
    category = Category.objects.filter(slug=request.GET.get('category')).first() or categories.first()
    products = list(Product.objects.filter(category_id__in=category.descendant_ids()).order_by('name')) if category else []
    models = list(IPhoneModel.objects.filter(is_active=True).order_by('-series', 'display_order'))
    cells = {(c.product_id, c.iphone_model_id): c.status for c in Compatibility.objects.filter(product__in=products)}
    rows = [{'product': p, 'cells': [(m, cells.get((p.pk, m.pk), '')) for m in models]} for p in products]
    return render(request, 'dashboard/compat_matrix.html', {
        'menu': 'compat', 'page_title': 'Ma trận tương thích', 'categories': categories, 'category': category,
        'models': models, 'rows': rows})


@staff_required
@require_POST
def compat_matrix_toggle(request):
    """Bấm ô: trống -> verified -> unverified -> incompatible -> trống."""
    product = get_object_or_404(Product, pk=to_int(request.POST.get('product')))
    model = get_object_or_404(IPhoneModel, pk=to_int(request.POST.get('model')))
    comp = Compatibility.objects.filter(product=product, iphone_model=model).first()
    cycle = ['verified', 'unverified', 'incompatible', '']
    current = comp.status if comp else ''
    nxt = cycle[(cycle.index(current) + 1) % len(cycle)] if current in cycle else 'verified'
    if not nxt:
        comp.delete()
    else:
        comp = comp or Compatibility(product=product, iphone_model=model, source='Admin – ma trận')
        comp.set_status(nxt, request.user)
        comp.save()
    return JsonResponse({'ok': True, 'data': {'status': nxt}})


# ------------------------------------------------------------------ Kho hàng
@staff_required
def inventory_overview(request):
    qs = Product.objects.select_related('category').prefetch_related('images').annotate(stock_value=F('stock_quantity') * F('cost_price'))
    state = request.GET.get('state')
    if state == 'low':
        qs = qs.filter(stock_quantity__gt=0, stock_quantity__lte=F('low_stock_threshold'))
    elif state == 'out':
        qs = qs.filter(stock_quantity=0)
    if request.GET.get('product'):
        qs = qs.filter(pk=to_int(request.GET.get('product')))
    totals = Product.objects.aggregate(value=Sum(F('stock_quantity') * F('cost_price')), qty=Sum('stock_quantity'),
                                       low=Count('id', filter=Q(stock_quantity__gt=0, stock_quantity__lte=F('low_stock_threshold'))),
                                       out=Count('id', filter=Q(stock_quantity=0)))
    ctx = table(request, qs, ('name', 'sku'), {'name': 'name', 'stock': 'stock_quantity', 'value': 'stock_value'}, 'stock_quantity')
    return render(request, 'dashboard/inventory.html', {
        **ctx, 'page_title': 'Tổng quan tồn kho', 'totals': totals,
        'page_description': 'Tồn kho chỉ thay đổi qua Nhập kho, Điều chỉnh kiểm kê hoặc đơn hàng – mọi thay đổi đều có lịch sử.',
    })


@staff_required
def inventory_history(request):
    qs = InventoryTransaction.objects.select_related('product', 'order', 'created_by')
    g = request.GET
    if g.get('product'):
        qs = qs.filter(product_id=to_int(g['product']))
    if g.get('type'):
        qs = qs.filter(type=g['type'])
    if g.get('from'):
        qs = qs.filter(created_at__date__gte=g['from'])
    if g.get('to'):
        qs = qs.filter(created_at__date__lte=g['to'])
    if g.get('export') == 'csv':
        return csv_response('lich-su-kho', ['Thời gian', 'SKU', 'Sản phẩm', 'Loại', 'Thay đổi', 'Tồn trước', 'Tồn sau', 'Đơn hàng', 'Người thực hiện', 'Ghi chú'],
                            ([timezone.localtime(t.created_at).strftime('%d/%m/%Y %H:%M'), t.product.sku, t.product.name, t.get_type_display(),
                              t.quantity_change, t.stock_before, t.stock_after, t.order.code if t.order else '',
                              t.created_by.display_name if t.created_by else 'Hệ thống', t.note] for t in qs.order_by('-created_at')))
    ctx = table(request, qs, ('product__name', 'product__sku', 'note'), {'time': 'created_at', 'change': 'quantity_change'}, '-created_at')
    return render(request, 'dashboard/inventory_history.html', {
        **ctx, 'menu': 'inventory', 'page_title': 'Lịch sử nhập xuất kho', 'types': InventoryTransaction.Type.choices,
        'products': Product.objects.order_by('name').only('pk', 'name')})


# ------------------------------------------------------------------ Cây danh mục & dòng iPhone
@staff_required
def category_tree(request):
    """Cây danh mục 2 cấp: cấp 1 (icon, in đậm, thu/mở được), cấp 2 thụt vào."""
    counts = dict(Product.objects.values_list('category_id').annotate(n=Count('id')))
    tree = []
    for parent in Category.objects.filter(parent__isnull=True).prefetch_related('children').order_by('display_order', 'name'):
        children = list(parent.children.order_by('display_order', 'name'))
        for c in children:
            c.product_total = counts.get(c.pk, 0)
        parent.product_total = counts.get(parent.pk, 0) + sum(c.product_total for c in children)
        tree.append({'node': parent, 'children': children})
    return render(request, 'dashboard/category_tree.html', {
        'page_title': 'Cây danh mục', 'tree': tree,
        'page_description': 'Danh mục cấp 1 là nhóm linh kiện; cấp 2 là loại cụ thể. Khi xóa danh mục còn sản phẩm, bạn chọn danh mục để chuyển sản phẩm sang (sản phẩm không bị xóa).'})


@staff_required
def category_delete(request, pk):
    """Xóa danh mục an toàn: sản phẩm còn lại được CHUYỂN sang danh mục khác (không xóa sản phẩm),
    danh mục con được chuyển sang danh mục cha khác hoặc thành cấp 1."""
    category = get_object_or_404(Category, pk=pk)
    children = list(category.children.order_by('display_order', 'name'))
    products_count = category.products.count()
    excluded = [category.pk] + [c.pk for c in children]
    # Đích cho sản phẩm: chỉ danh mục lá (không phải danh mục đang xóa / con của nó)
    leaf_targets = (Category.objects.exclude(pk__in=excluded).annotate(n_children=Count('children'))
                    .filter(n_children=0).select_related('parent').order_by('parent__display_order', 'display_order', 'name'))
    parent_targets = Category.objects.filter(parent__isnull=True).exclude(pk=category.pk).order_by('display_order', 'name')
    if request.method == 'POST':
        target = None
        if products_count:
            target = leaf_targets.filter(pk=to_int(request.POST.get('move_products_to'))).first()
            if not target:
                messages.error(request, f'Vui lòng chọn danh mục để chuyển {products_count} sản phẩm sang.')
                return redirect('dashboard:category_delete', pk=pk)
        new_parent = None
        if children and request.POST.get('move_children_to'):
            new_parent = parent_targets.filter(pk=to_int(request.POST['move_children_to'])).first()
        with transaction.atomic():
            if target:
                category.products.update(category=target)
            if children:
                category.children.update(parent=new_parent)
            name = category.name
            category.delete()
        msg = f'Đã xóa danh mục "{name}".'
        if target:
            msg += f' {products_count} sản phẩm đã chuyển sang "{target.name}".'
        if children:
            msg += f' {len(children)} danh mục con đã chuyển sang ' + (f'"{new_parent.name}".' if new_parent else 'cấp 1.')
        messages.success(request, msg)
        return redirect('dashboard:category_list')
    return render(request, 'dashboard/category_delete.html', {
        'page_title': f'Xóa danh mục: {category.name}', 'extra_crumb': 'Xóa', 'category': category,
        'children': children, 'products_count': products_count, 'leaf_targets': leaf_targets,
        'parent_targets': parent_targets})


@staff_required
def iphone_list(request):
    counts = dict(Compatibility.objects.filter(status='verified').values_list('iphone_model_id').annotate(n=Count('id')))
    groups = {}
    for m in IPhoneModel.objects.order_by('-series', 'display_order', 'name'):
        m.verified_total = counts.get(m.pk, 0)
        groups.setdefault(m.series, {'label': m.series_label, 'models': []})['models'].append(m)
    return render(request, 'dashboard/iphone_list.html', {
        'page_title': 'Dòng iPhone', 'groups': list(groups.values()),
        'page_description': 'Nhóm theo thế hệ. Dòng máy đã có dữ liệu tương thích chỉ được tắt, không xóa.'})


@staff_required
def iphone_detail(request, pk):
    model = get_object_or_404(IPhoneModel, pk=pk)
    comps = (Compatibility.objects.filter(iphone_model=model).select_related('product', 'product__category', 'product__category__parent')
             .prefetch_related('product__images').order_by('product__category__display_order', 'product__name'))
    groups = {}
    for c in comps:
        g = c.product.category.parent or c.product.category
        groups.setdefault(g.pk, {'category': g, 'items': []})['items'].append(c)
    return render(request, 'dashboard/iphone_detail.html', {
        'page_title': model.name, 'extra_crumb': model.name, 'model': model, 'groups': list(groups.values()),
        'verified': sum(1 for c in comps if c.status == 'verified')})
