from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from core.permissions import customer_required, safe_next_url
from core.utils import to_int

from .models import Review
from .services import ReviewError, create_review, reviewable_items


@customer_required
@require_POST
def review_create(request):
    try:
        create_review(request.user, to_int(request.POST.get('order_item_id')), to_int(request.POST.get('rating'), 0),
                      request.POST.get('content', ''))
        messages.success(request, 'Cảm ơn bạn! Đánh giá sẽ hiển thị sau khi được cửa hàng duyệt.')
    except (ReviewError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect(safe_next_url(request, '/tai-khoan/danh-gia/'))


@customer_required
def my_reviews(request):
    return render(request, 'customer/reviews.html', {
        'account_active': 'reviews',
        'reviews': Review.objects.filter(user=request.user).select_related('product', 'order_item__order'),
        'pending_items': reviewable_items(request.user).order_by('-order__delivered_at'),
    })
