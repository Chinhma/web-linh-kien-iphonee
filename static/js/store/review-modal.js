// Mở modal viết đánh giá cho từng sản phẩm của đơn đã giao.
import { openModal } from '../core/modal.js';

document.querySelectorAll('[data-review-item]').forEach((btn) => btn.addEventListener('click', () => {
  document.querySelector('[data-review-input]').value = btn.dataset.reviewItem;
  document.querySelector('[data-review-product]').textContent = btn.dataset.reviewName;
  openModal('review-modal');
}));
