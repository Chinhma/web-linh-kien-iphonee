// Modal dùng chung: đóng bằng nút X, phím Esc, click nền; khóa cuộn trang khi mở.
let openCount = 0;

export function openModal(id) {
  const modal = document.getElementById(id);
  if (!modal || !modal.hidden) return modal;
  modal.hidden = false;
  openCount += 1;
  document.body.classList.add('overflow-hidden');
  const focusable = modal.querySelector('input, select, textarea, button:not([data-modal-close])');
  if (focusable) setTimeout(() => focusable.focus(), 30);
  return modal;
}

export function closeModal(modalOrId) {
  const modal = typeof modalOrId === 'string' ? document.getElementById(modalOrId) : modalOrId;
  if (!modal || modal.hidden) return;
  modal.hidden = true;
  openCount = Math.max(0, openCount - 1);
  if (!openCount) document.body.classList.remove('overflow-hidden');
  modal.dispatchEvent(new CustomEvent('modal:closed'));
}

export function initModals(root = document) {
  root.querySelectorAll('[data-modal]').forEach((modal) => {
    if (modal.dataset.bound) return;
    modal.dataset.bound = '1';
    modal.addEventListener('click', (e) => {
      if (e.target === modal || e.target.closest('[data-modal-close]')) closeModal(modal);
    });
  });
  root.querySelectorAll('[data-modal-open]').forEach((btn) => {
    if (btn.dataset.boundOpen) return;
    btn.dataset.boundOpen = '1';
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      openModal(btn.dataset.modalOpen);
    });
  });
}

document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape') return;
  const opened = [...document.querySelectorAll('[data-modal]')].filter((m) => !m.hidden);
  if (opened.length) closeModal(opened[opened.length - 1]);
});

export function openLoginModal() {
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  document.querySelectorAll('[data-login-link]').forEach((a) => {
    a.href = `${a.dataset.loginLink}?next=${next}`;
  });
  openModal('login-required-modal');
}

/**
 * Confirm modal thay cho confirm() mặc định. Trả về Promise<{confirmed, note}>.
 */
export function confirmDialog({ title = 'Xác nhận', message = '', confirmText = 'Đồng ý', danger = true,
  withNote = false, notePlaceholder = 'Ghi chú', noteRequired = false } = {}) {
  return new Promise((resolve) => {
    const modal = document.getElementById('confirm-modal');
    modal.querySelector('[data-confirm-title]').textContent = title;
    modal.querySelector('[data-confirm-message]').textContent = message;
    const okBtn = modal.querySelector('[data-confirm-ok]');
    okBtn.textContent = confirmText;
    okBtn.className = danger ? 'btn-danger' : 'btn-primary';
    const noteWrap = modal.querySelector('[data-confirm-note-wrap]');
    const note = modal.querySelector('[data-confirm-note]');
    const noteError = modal.querySelector('[data-confirm-note-error]');
    noteWrap.hidden = !withNote;
    note.value = '';
    note.placeholder = notePlaceholder;
    noteError.hidden = true;
    let done = false;
    const finish = (confirmed) => {
      if (done) return;
      done = true;
      okBtn.removeEventListener('click', onOk);
      modal.removeEventListener('modal:closed', onClose);
      closeModal(modal);
      resolve({ confirmed, note: note.value.trim() });
    };
    const onOk = () => {
      if (withNote && noteRequired && !note.value.trim()) {
        noteError.hidden = false;
        note.focus();
        return;
      }
      finish(true);
    };
    const onClose = () => finish(false);
    okBtn.addEventListener('click', onOk);
    modal.addEventListener('modal:closed', onClose);
    openModal('confirm-modal');
  });
}

/** Gắn confirm modal cho form có data-confirm (thay confirm()). */
export function initConfirmForms(root = document) {
  root.querySelectorAll('form[data-confirm]').forEach((form) => {
    if (form.dataset.confirmBound) return;
    form.dataset.confirmBound = '1';
    form.addEventListener('submit', async (e) => {
      if (form.dataset.confirmed === '1' || e.defaultPrevented) return;
      e.preventDefault();
      const result = await confirmDialog({
        title: form.dataset.confirmTitle || 'Xác nhận thao tác',
        message: form.dataset.confirm,
        confirmText: form.dataset.confirmOk || 'Đồng ý',
        danger: form.dataset.confirmDanger !== '0',
        withNote: form.dataset.confirmNote === '1' || form.dataset.confirmNote === 'required',
        noteRequired: form.dataset.confirmNote === 'required',
        notePlaceholder: form.dataset.confirmNotePlaceholder || 'Nhập ghi chú / lý do',
      });
      if (!result.confirmed) return;
      if (result.note) {
        let input = form.querySelector('input[name="note"]');
        if (!input) {
          input = document.createElement('input');
          input.type = 'hidden';
          input.name = 'note';
          form.appendChild(input);
        }
        input.value = result.note;
      }
      form.dataset.confirmed = '1';
      form.requestSubmit ? form.requestSubmit() : form.submit();
    });
  });
}
