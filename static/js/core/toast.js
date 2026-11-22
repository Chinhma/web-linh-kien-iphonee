// Toast: success / error / warning / info – tự ẩn sau 4 giây, xếp chồng góc trên phải.
const ICONS = { success: 'check-circle-2', error: 'x-circle', warning: 'alert-triangle', info: 'info' };
const COLORS = {
  success: 'border-green-200 text-green-800',
  error: 'border-red-200 text-red-800',
  warning: 'border-amber-200 text-amber-800',
  info: 'border-blue-200 text-blue-800',
};

function container() {
  let box = document.getElementById('toast-stack');
  if (!box) {
    box = document.createElement('div');
    box.id = 'toast-stack';
    box.className = 'fixed right-4 top-4 z-[100] flex w-[calc(100%-2rem)] max-w-sm flex-col gap-2';
    box.setAttribute('aria-live', 'polite');
    document.body.appendChild(box);
  }
  return box;
}

export function toast(message, type = 'info') {
  if (type === 'danger') type = 'error';
  if (!ICONS[type]) type = 'info';
  const item = document.createElement('div');
  item.className = `flex items-start gap-3 rounded-xl border bg-white p-3.5 text-sm shadow-card-hover transition duration-200 ${COLORS[type]}`;
  item.setAttribute('role', 'status');
  const icon = document.createElement('i');
  icon.setAttribute('data-lucide', ICONS[type]);
  icon.className = 'mt-0.5 h-5 w-5 shrink-0';
  const text = document.createElement('div');
  text.className = 'flex-1 text-text';
  text.textContent = message;
  const close = document.createElement('button');
  close.type = 'button';
  close.className = 'text-muted hover:text-text';
  close.setAttribute('aria-label', 'Đóng');
  close.textContent = '×';
  close.addEventListener('click', () => item.remove());
  item.append(icon, text, close);
  container().appendChild(item);
  if (window.lucide) window.lucide.createIcons();
  setTimeout(() => {
    item.style.opacity = '0';
    setTimeout(() => item.remove(), 200);
  }, 4000);
}
