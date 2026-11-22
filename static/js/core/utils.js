// Tiện ích dùng chung phía trình duyệt.
export function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function formatVnd(value) {
  const number = Math.round(Number(value) || 0);
  return number.toLocaleString('vi-VN').replace(/,/g, '.') + '₫';
}

export function debounce(fn, wait = 300) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

export function setLoading(button, loading) {
  if (!button) return;
  button.disabled = loading;
  button.classList.toggle('is-loading', loading);
}

export function refreshIcons() {
  if (window.lucide) window.lucide.createIcons();
}

export function el(tag, className = '', text = '') {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

export function updateCounters({ cart_count: cart, wishlist_count: wishlist } = {}) {
  if (cart !== undefined) {
    document.querySelectorAll('[data-cart-count]').forEach((n) => {
      n.textContent = cart;
      n.hidden = !cart;
    });
  }
  if (wishlist !== undefined) {
    document.querySelectorAll('[data-wishlist-count]').forEach((n) => {
      n.textContent = wishlist;
      n.hidden = !wishlist;
    });
  }
}
