// Trang yêu thích: thêm tất cả sản phẩm còn hàng vào giỏ.
import { apiFetch } from '../core/api.js';
import { toast } from '../core/toast.js';
import { setLoading, updateCounters } from '../core/utils.js';

document.querySelector('[data-add-all]')?.addEventListener('click', async (e) => {
  const btn = e.currentTarget;
  setLoading(btn, true);
  try {
    const res = await apiFetch('/api/wishlist/add-all/', { method: 'POST' });
    updateCounters(res.data);
    toast(res.message, 'success');
  } catch (err) { /* đã toast */ } finally {
    setLoading(btn, false);
  }
});
