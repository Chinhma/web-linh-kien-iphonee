// Giỏ hàng: cập nhật số lượng / chọn / xóa / mã giảm giá bằng AJAX. Tổng tiền luôn do backend tính lại.
import { apiFetch } from '../core/api.js';
import { toast } from '../core/toast.js';
import { debounce, formatVnd, setLoading, updateCounters } from '../core/utils.js';

const page = document.querySelector('[data-cart-page]');

function applySummary(data) {
  updateCounters(data);
  page.querySelector('[data-subtotal]').textContent = formatVnd(data.subtotal);
  page.querySelector('[data-discount]').textContent = `-${formatVnd(data.discount)}`;
  page.querySelector('[data-total]').textContent = formatVnd(data.total);
  page.querySelector('[data-selected-count]').textContent = data.selected_count;
  const btn = page.querySelector('[data-checkout-btn]');
  btn.classList.toggle('pointer-events-none', !data.can_checkout);
  btn.classList.toggle('opacity-50', !data.can_checkout);
  btn.setAttribute('aria-disabled', String(!data.can_checkout));
  Object.entries(data.lines || {}).forEach(([id, line]) => {
    const row = page.querySelector(`[data-cart-line="${id}"]`);
    if (!row) return;
    row.querySelector('[data-line-total]').textContent = formatVnd(line.line_total);
    row.querySelector('[data-unit-price]').textContent = formatVnd(line.unit_price);
    const input = row.querySelector('input[type="number"]');
    if (input) input.value = line.quantity;
    const warn = row.querySelector('[data-line-warning]');
    warn.textContent = line.warning;
    warn.classList.toggle('hidden', !line.warning);
  });
  const couponApplied = page.querySelector('[data-coupon-applied]');
  couponApplied.classList.toggle('hidden', !data.coupon_code);
  page.querySelector('[data-coupon-form]').classList.toggle('hidden', !!data.coupon_code);
  page.querySelector('[data-coupon-label]').textContent = data.coupon_code;
}

async function withRow(id, fn) {
  const row = page.querySelector(`[data-cart-line="${id}"]`);
  const loader = row?.querySelector('[data-line-loading]');
  if (loader) loader.hidden = false;
  try {
    return await fn();
  } catch (e) {
    return null;
  } finally {
    if (loader) loader.hidden = true;
  }
}

if (page) {
  const updateQty = debounce((id, quantity) => withRow(id, async () => {
    const res = await apiFetch('/api/cart/update/', { method: 'POST', body: { item_id: Number(id), quantity } });
    applySummary(res.data);
    if (res.message && res.message.startsWith('Chỉ còn')) toast(res.message, 'warning');
  }), 400);

  page.addEventListener('stepper:change', (e) => {
    const input = e.target;
    if (input.dataset.itemId) updateQty(input.dataset.itemId, Number(input.value));
  });

  page.querySelectorAll('[data-select-item]').forEach((cb) => cb.addEventListener('change', () => withRow(cb.dataset.selectItem, async () => {
    const res = await apiFetch('/api/cart/select/', { method: 'POST', body: { item_ids: [Number(cb.dataset.selectItem)], selected: cb.checked } });
    applySummary(res.data);
  })));

  page.querySelector('[data-select-all]')?.addEventListener('change', async (e) => {
    const boxes = [...page.querySelectorAll('[data-select-item]:not(:disabled)')];
    boxes.forEach((b) => { b.checked = e.target.checked; });
    try {
      const res = await apiFetch('/api/cart/select/', { method: 'POST', body: { item_ids: boxes.map((b) => Number(b.dataset.selectItem)), selected: e.target.checked } });
      applySummary(res.data);
    } catch (err) { /* đã toast */ }
  });

  // Xóa dòng: form có data-confirm -> confirm modal -> submit -> chặn và gọi API
  page.querySelectorAll('form[data-remove-item]').forEach((form) => form.addEventListener('submit', (e) => {
    if (form.dataset.confirmed !== '1') return;
    e.preventDefault();
    form.dataset.confirmed = '';
    const id = form.dataset.removeItem;
    withRow(id, async () => {
      const res = await apiFetch('/api/cart/remove/', { method: 'POST', body: { item_id: Number(id) } });
      page.querySelector(`[data-cart-line="${id}"]`)?.remove();
      applySummary(res.data);
      toast(res.message, 'success');
      if (!page.querySelector('[data-cart-line]')) window.location.reload();
    });
  }));

  page.querySelector('[data-coupon-form]').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target;
    const btn = form.querySelector('button');
    setLoading(btn, true);
    try {
      const res = await apiFetch('/api/cart/coupon/', { method: 'POST', body: { code: form.code.value } });
      applySummary(res.data);
      toast(res.message, 'success');
      form.reset();
    } catch (err) { /* đã toast */ } finally {
      setLoading(btn, false);
    }
  });

  page.querySelector('[data-coupon-remove]').addEventListener('click', async () => {
    try {
      const res = await apiFetch('/api/cart/coupon/', { method: 'DELETE' });
      applySummary(res.data);
      toast(res.message, 'info');
    } catch (err) { /* đã toast */ }
  });
}
