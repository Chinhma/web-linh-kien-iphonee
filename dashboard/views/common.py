"""Tiện ích dùng chung cho Admin Panel: bảng dữ liệu, xuất CSV, CRUD đơn giản."""

import csv
from dataclasses import dataclass, field

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import ProtectedError, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

PER_PAGE = 20


def table(request, qs, search_fields=(), sort_fields=None, default_sort='-id', per_page=PER_PAGE):
    """Tìm kiếm + sắp xếp theo cột + phân trang 20 dòng. Tham số nằm trên URL."""
    q = (request.GET.get('q') or '').strip()[:100]
    if q and search_fields:
        cond = Q()
        for f in search_fields:
            cond |= Q(**{f'{f}__icontains': q})
        qs = qs.filter(cond)
    sort = request.GET.get('sort') or default_sort
    allowed = sort_fields or {}
    key = sort.lstrip('-')
    if key in allowed:
        qs = qs.order_by(('-' if sort.startswith('-') else '') + allowed[key], '-pk')
    else:
        sort = default_sort
        qs = qs.order_by(default_sort)
    size = request.GET.get('per_page')
    per_page = int(size) if size in ('20', '50', '100') else per_page
    page = Paginator(qs, per_page).get_page(request.GET.get('page'))
    return {'page_obj': page, 'q': q, 'sort': sort, 'total': page.paginator.count, 'per_page': per_page}


def csv_response(filename: str, header: list, rows) -> HttpResponse:
    """CSV UTF-8 có BOM để Excel đọc đúng tiếng Việt."""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}-{timezone.localdate():%Y%m%d}.csv"'
    response.write('﻿')
    writer = csv.writer(response)
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return response


@dataclass
class CrudConfig:
    """Cấu hình CRUD cho model đơn giản (danh mục, thương hiệu, dòng iPhone, banner, trang, FAQ, coupon)."""

    key: str
    model: type
    form_class: type
    title: str
    singular: str
    columns: list  # [(nhãn, thuộc tính/callable, sort_key|None)]
    search_fields: tuple = ()
    sort_fields: dict = field(default_factory=dict)
    default_sort: str = '-id'
    queryset: callable = None
    filters: list = field(default_factory=list)  # [(param, nhãn, [(value, label)], lookup)]
    delete_check: callable = None  # trả về thông báo lỗi nếu không được xóa
    menu: str = ''
    can_add: bool = True
    detail_url: callable = None
    sortable: str = ''  # khóa cho API sắp xếp kéo thả (banner, faq); rỗng = không kéo thả
    list_template: str = 'dashboard/crud_list.html'


def crud_list(request, cfg: CrudConfig):
    qs = cfg.queryset() if cfg.queryset else cfg.model.objects.all()
    active_filters = {}
    for param, _label, _choices, lookup in cfg.filters:
        value = request.GET.get(param)
        if value not in (None, ''):
            if callable(lookup):
                qs = qs.filter(lookup(value))
            else:
                qs = qs.filter(**{lookup: value if value not in ('1', '0') or 'is_' not in lookup else value == '1'})
            active_filters[param] = value
    ctx = table(request, qs, cfg.search_fields, cfg.sort_fields, cfg.default_sort)
    rows = []
    for obj in ctx['page_obj']:
        cells = []
        for _label, attr, _sort in cfg.columns:
            value = attr(obj) if callable(attr) else getattr(obj, attr)
            cells.append(value)
        rows.append({'obj': obj, 'cells': cells, 'detail_url': cfg.detail_url(obj) if cfg.detail_url else None})
    return render(request, cfg.list_template, {
        **ctx, 'cfg': cfg, 'rows': rows, 'active_filters': active_filters, 'menu': cfg.menu or cfg.key,
        'page_title': cfg.title,
    })


def crud_form(request, cfg: CrudConfig, pk=None):
    instance = get_object_or_404(cfg.model, pk=pk) if pk else None
    form = cfg.form_class(request.POST or None, request.FILES or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        messages.success(request, f'Đã lưu thành công {cfg.singular} "{obj}".')
        if request.POST.get('save_add'):
            return redirect(reverse(f'dashboard:{cfg.key}_add'))
        return redirect(reverse(f'dashboard:{cfg.key}_edit', args=[obj.pk]))  # Sửa xong ở lại trang sửa
    return render(request, 'dashboard/crud_form.html', {
        'form': form, 'cfg': cfg, 'instance': instance,
        'page_title': f'Sửa {cfg.singular}: {instance}' if instance else f'Thêm {cfg.singular}',
        'extra_crumb': str(instance) if instance else None,
    })


def crud_delete(request, cfg: CrudConfig, pk):
    obj = get_object_or_404(cfg.model, pk=pk)
    if request.method != 'POST':
        return redirect(reverse(f'dashboard:{cfg.key}_list'))
    error = cfg.delete_check(obj) if cfg.delete_check else ''
    if error:
        messages.error(request, error)
    else:
        try:
            obj.delete()
            messages.success(request, f'Đã xóa {cfg.singular} "{obj}".')
        except ProtectedError:
            messages.error(request, f'Không thể xóa {cfg.singular} vì đang được sử dụng.')
    return redirect(reverse(f'dashboard:{cfg.key}_list'))
