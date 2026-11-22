// Kéo thả sắp xếp: container [data-sortable-url] chứa các phần tử [data-sort-id].
// Thả xong → POST {ids: [...]} về server để lưu display_order.
import { apiFetch } from '../core/api.js';
import { toast } from '../core/toast.js';

export function initSortable() {
  document.querySelectorAll('[data-sortable-url]').forEach((box) => {
    let dragging = null;
    const items = () => [...box.querySelectorAll(':scope > [data-sort-id]')];
    items().forEach((item) => {
      item.draggable = true;
      item.addEventListener('dragstart', (e) => {
        dragging = item;
        item.classList.add('opacity-50');
        e.dataTransfer.effectAllowed = 'move';
      });
      item.addEventListener('dragend', async () => {
        item.classList.remove('opacity-50');
        dragging = null;
        const ids = items().map((el) => Number(el.dataset.sortId));
        try {
          const res = await apiFetch(box.dataset.sortableUrl, { method: 'POST', body: { ids }, silent: true });
          toast(res.message || 'Đã lưu thứ tự.', 'success');
          box.querySelectorAll('[data-sort-index]').forEach((el, i) => { el.textContent = i + 1; });
        } catch (e) {
          toast('Không lưu được thứ tự, vui lòng thử lại.', 'error');
        }
      });
    });
    box.addEventListener('dragover', (e) => {
      if (!dragging) return;
      e.preventDefault();
      const grid = getComputedStyle(box).display === 'grid';
      const after = items().find((el) => {
        if (el === dragging) return false;
        const r = el.getBoundingClientRect();
        return grid ? (e.clientY < r.bottom && e.clientX < r.left + r.width / 2) || e.clientY < r.top
          : e.clientY < r.top + r.height / 2;
      });
      box.insertBefore(dragging, after || null);
    });
  });
}
