// Bảng dữ liệu Admin: chọn nhiều + thanh thao tác hàng loạt, tìm kiếm debounce 400ms, toggle nhanh, cảnh báo rời form chưa lưu.
import { apiFetch } from '../core/api.js';
import { confirmDialog } from '../core/modal.js';
import { toast } from '../core/toast.js';
import { debounce } from '../core/utils.js';

// Form hàng loạt: <form id="bulk-form" data-bulk-form>; checkbox dòng: <input name="ids" form="bulk-form">
export function initBulk() {
  document.querySelectorAll('[data-bulk-form]').forEach((form) => {
    const boxes = () => [...document.querySelectorAll(`input[name="ids"][form="${form.id}"]`)];
    const bar = document.querySelector(`[data-bulk-bar="${form.id}"]`);
    const counter = bar?.querySelector('[data-bulk-count]');
    const refresh = () => {
      const n = boxes().filter((b) => b.checked).length;
      if (bar) bar.hidden = n === 0;
      if (counter) counter.textContent = n;
    };
    document.querySelectorAll(`[data-check-all="${form.id}"]`).forEach((all) => all.addEventListener('change', () => {
      boxes().forEach((cb) => { cb.checked = all.checked; });
      refresh();
    }));
    boxes().forEach((cb) => cb.addEventListener('change', refresh));
    refresh();
    form.addEventListener('submit', async (e) => {
      const checked = boxes().filter((b) => b.checked);
      const actionEl = e.submitter?.name === 'action' ? e.submitter : form.querySelector('[name="action"]');
      const action = actionEl?.value;
      if (!checked.length || !action) {
        e.preventDefault();
        toast(!checked.length ? 'Vui lòng chọn ít nhất một dòng.' : 'Vui lòng chọn thao tác.', 'warning');
        return;
      }
      if (form.dataset.bulkConfirmed === '1') return;
      e.preventDefault();
      const label = actionEl.tagName === 'SELECT' ? actionEl.selectedOptions[0].textContent : actionEl.textContent;
      const result = await confirmDialog({ title: 'Thao tác hàng loạt', message: `${label.trim()} cho ${checked.length} mục đã chọn?`, confirmText: 'Thực hiện', danger: action === 'delete' });
      if (result.confirmed) {
        if (actionEl.tagName !== 'SELECT') {
          const hidden = document.createElement('input');
          hidden.type = 'hidden';
          hidden.name = 'action';
          hidden.value = action;
          form.appendChild(hidden);
        }
        form.dataset.bulkConfirmed = '1';
        form.submit();
      }
    });
  });
}

// Ô tìm kiếm trong thanh công cụ tự gửi sau 400ms
export function initAutoSearch() {
  document.querySelectorAll('input[data-auto-search]').forEach((input) => {
    const submit = debounce(() => input.form.requestSubmit(), 400);
    input.addEventListener('input', submit);
    if (input.value) {
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);
    }
  });
  document.querySelectorAll('select[data-autosubmit], input[data-autosubmit]').forEach((s) => s.addEventListener('change', () => s.form.requestSubmit()));
}

// Toggle bật/tắt ngay (nổi bật, hoạt động...): <button data-toggle-url data-field="is_featured">
export function initToggles() {
  document.querySelectorAll('[data-toggle-url]').forEach((btn) => btn.addEventListener('click', async () => {
    try {
      const res = await apiFetch(btn.dataset.toggleUrl, { method: 'POST' });
      const on = res.data[btn.dataset.field || 'is_featured'];
      btn.setAttribute('aria-checked', String(on));
      btn.classList.toggle('is-on', on);
      toast(res.message || (on ? 'Đã bật.' : 'Đã tắt.'), 'success');
    } catch (e) { /* đã toast */ }
  }));
}

// Cảnh báo khi rời trang form mà chưa lưu: <form data-dirty-check>
export function initDirtyCheck() {
  document.querySelectorAll('form[data-dirty-check]').forEach((form) => {
    let dirty = false;
    form.addEventListener('input', () => { dirty = true; });
    form.addEventListener('change', () => { dirty = true; });
    form.addEventListener('submit', () => { dirty = false; });
    window.addEventListener('beforeunload', (e) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = '';
      }
    });
  });
}
