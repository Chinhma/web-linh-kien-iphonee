// Tìm nhanh trên topbar Admin: phím tắt "/" hoặc Ctrl+K, gợi ý theo nhóm (Đơn hàng / Sản phẩm / Khách hàng), Enter mở kết quả đầu.
import { apiFetch } from '../core/api.js';
import { debounce, el } from '../core/utils.js';

export function initQuickSearch() {
  const wrap = document.querySelector('[data-quick-search]');
  if (!wrap) return;
  const input = wrap.querySelector('input');
  const box = wrap.querySelector('[data-quick-results]');
  let results = [];
  let active = 0;

  const render = () => {
    box.replaceChildren();
    if (!results.length) {
      box.appendChild(el('p', 'px-4 py-3 text-muted', 'Không tìm thấy kết quả.'));
      box.hidden = false;
      return;
    }
    let lastType = '';
    results.forEach((r, i) => {
      if (r.type !== lastType) {
        box.appendChild(el('div', 'px-4 pb-1 pt-3 text-[11px] font-semibold uppercase tracking-wider text-muted', r.type));
        lastType = r.type;
      }
      const a = el('a', `block px-4 py-2 hover:bg-slate-50 ${i === active ? 'bg-primary-light' : ''}`, r.text);
      a.href = r.url;
      box.appendChild(a);
    });
    box.hidden = false;
  };

  input.addEventListener('input', debounce(async () => {
    const q = input.value.trim();
    if (q.length < 2) { box.hidden = true; results = []; return; }
    try {
      const res = await apiFetch(`/quan-tri/api/tim-kiem/?q=${encodeURIComponent(q)}`, { silent: true });
      results = res.data.results;
      active = 0;
      render();
    } catch (e) { /* bỏ qua */ }
  }, 300));
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' && results.length) { active = Math.min(active + 1, results.length - 1); render(); e.preventDefault(); }
    if (e.key === 'ArrowUp' && results.length) { active = Math.max(active - 1, 0); render(); e.preventDefault(); }
    if (e.key === 'Enter' && results[active]) { window.location.href = results[active].url; e.preventDefault(); }
    if (e.key === 'Escape') { box.hidden = true; input.blur(); }
  });
  document.addEventListener('keydown', (e) => {
    const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName) || document.activeElement?.isContentEditable;
    if ((e.key === '/' && !typing) || ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k')) {
      e.preventDefault();
      input.focus();
      input.select();
    }
  });
  document.addEventListener('click', (e) => { if (!wrap.contains(e.target)) box.hidden = true; });
}
