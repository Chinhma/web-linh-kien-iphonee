// Ô chọn sản phẩm có gợi ý (ảnh + SKU + tồn kho) cho các trang Admin: nhập kho, kiểm kê, thêm tương thích.
import { apiFetch } from '../core/api.js';
import { debounce, el, formatVnd } from '../core/utils.js';

export function initProductPicker(root, { onSelect } = {}) {
  if (root.dataset.bound) return;
  root.dataset.bound = '1';
  const hidden = root.querySelector('input[type="hidden"]');
  const input = root.querySelector('[data-picker-input]');
  const box = root.querySelector('[data-picker-results]');
  const info = root.querySelector('[data-picker-info]');
  let items = [];

  const choose = (p) => {
    hidden.value = p.id;
    input.value = `${p.sku} – ${p.name}`;
    info.textContent = '';
    info.append('Tồn hiện tại: ', el('strong', '', String(p.stock)), ` · Giá nhập: ${formatVnd(p.cost_price)} · ${p.status}`);
    box.hidden = true;
    root.dispatchEvent(new CustomEvent('product:selected', { detail: p, bubbles: true }));
    if (onSelect) onSelect(p);
  };

  const search = debounce(async () => {
    try {
      const res = await apiFetch(`${root.dataset.url}?q=${encodeURIComponent(input.value.trim())}`, { silent: true });
      items = res.data.products;
      box.replaceChildren();
      if (!items.length) box.appendChild(el('p', 'px-4 py-3 text-sm text-muted', 'Không tìm thấy sản phẩm.'));
      items.forEach((p) => {
        const row = el('button', 'flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-slate-50');
        row.type = 'button';
        const img = el('img', 'h-10 w-10 shrink-0 rounded-lg object-cover');
        img.src = p.image;
        img.alt = '';
        const text = el('div', 'min-w-0 flex-1');
        text.append(el('div', 'truncate text-sm font-medium', p.name), el('div', 'text-xs text-muted', `${p.sku} · Tồn ${p.stock}`));
        row.append(img, text);
        row.addEventListener('mousedown', (e) => { e.preventDefault(); choose(p); });
        box.appendChild(row);
      });
      box.hidden = false;
    } catch (e) { /* bỏ qua */ }
  }, 250);

  input.addEventListener('input', () => { hidden.value = ''; search(); });
  input.addEventListener('focus', search);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (items[0]) choose(items[0]);
    }
    if (e.key === 'Escape') box.hidden = true;
  });
  document.addEventListener('click', (e) => { if (!root.contains(e.target)) box.hidden = true; });
}

export function initProductPickers(scope = document) {
  scope.querySelectorAll('[data-product-picker]').forEach((r) => initProductPicker(r));
}

document.addEventListener('DOMContentLoaded', () => initProductPickers());
