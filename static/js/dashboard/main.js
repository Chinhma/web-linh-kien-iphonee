// Script chung Admin Panel: sidebar, dropdown, thông báo, tìm nhanh, bảng dữ liệu, confirm modal, toast.
import { apiFetch } from '../core/api.js';
import { initConfirmForms, initModals } from '../core/modal.js';
import { toast } from '../core/toast.js';
import { el, refreshIcons } from '../core/utils.js';
import { initQuickSearch } from './quick-search.js';
import { initSidebar } from './sidebar.js';
import { initSortable } from './sortable.js';
import { initAutoSearch, initBulk, initDirtyCheck, initToggles } from './tables.js';

function initDropdowns() {
  document.querySelectorAll('[data-dropdown]').forEach((wrap) => {
    wrap.querySelector('[data-dropdown-trigger]').addEventListener('click', (e) => {
      e.stopPropagation();
      const menu = wrap.querySelector('[data-dropdown-menu]');
      const willOpen = menu.hidden;
      document.querySelectorAll('[data-dropdown-menu]').forEach((m) => { m.hidden = true; });
      menu.hidden = !willOpen;
    });
  });
  document.addEventListener('click', (e) => {
    if (!e.target.closest('[data-dropdown]')) document.querySelectorAll('[data-dropdown-menu]').forEach((m) => { m.hidden = true; });
  });
}

async function loadNotifications() {
  try {
    const res = await apiFetch('/quan-tri/api/thong-bao/', { silent: true });
    const badge = document.querySelector('[data-notif-count]');
    badge.textContent = res.data.count > 99 ? '99+' : res.data.count;
    badge.hidden = !res.data.count;
    const list = document.querySelector('[data-notif-list]');
    list.replaceChildren();
    if (!res.data.items.length) list.appendChild(el('p', 'px-4 py-3 text-muted', 'Không có thông báo mới.'));
    res.data.items.forEach((item) => {
      const a = el('a', 'flex items-start gap-3 px-4 py-2.5 hover:bg-slate-50');
      a.href = item.url;
      const icon = el('i', 'mt-0.5 h-4 w-4 shrink-0 text-primary');
      icon.setAttribute('data-lucide', item.icon);
      a.append(icon, el('span', '', item.text));
      list.appendChild(a);
    });
    refreshIcons();
  } catch (e) { /* bỏ qua */ }
}

document.addEventListener('DOMContentLoaded', () => {
  refreshIcons();
  initModals();
  initConfirmForms();
  initSidebar();
  initDropdowns();
  initQuickSearch();
  initBulk();
  initAutoSearch();
  initToggles();
  initDirtyCheck();
  initSortable();
  loadNotifications();
  const node = document.getElementById('django-messages');
  if (node) JSON.parse(node.textContent || '[]').forEach((m) => toast(m.message, m.level));
  document.querySelectorAll('[data-copy]').forEach((b) => b.addEventListener('click', () => navigator.clipboard?.writeText(b.dataset.copy).then(() => toast('Đã sao chép.', 'success'))));
  document.querySelectorAll('[data-print]').forEach((b) => b.addEventListener('click', () => window.print()));
});
