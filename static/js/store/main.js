// Script chung cho mọi trang khách hàng: header, tìm kiếm gợi ý, thêm giỏ, yêu thích, newsletter.
import { apiFetch } from '../core/api.js';
import { initConfirmForms, initModals, openLoginModal } from '../core/modal.js';
import { toast } from '../core/toast.js';
import { debounce, el, formatVnd, refreshIcons, setLoading, updateCounters } from '../core/utils.js';

const IP = window.IPARTS || {};
const PENDING_KEY = 'iparts_pending_action';

// ---------- Django messages -> toast ----------
function flushMessages() {
  const node = document.getElementById('django-messages');
  if (!node) return;
  JSON.parse(node.textContent || '[]').forEach((m) => toast(m.message, m.level));
}

// ---------- Header ----------
function initAdminToolbar() {
  const bar = document.querySelector('[data-admin-toolbar]');
  if (!bar) return;
  const KEY = 'iparts_admin_toolbar_collapsed';
  const text = bar.querySelector('[data-admin-toolbar-text]');
  const btn = bar.querySelector('[data-admin-toolbar-toggle]');
  const apply = (collapsed) => {
    text.hidden = collapsed;
    btn.style.transform = collapsed ? 'rotate(180deg)' : '';
    btn.setAttribute('aria-label', collapsed ? 'Mở rộng thanh quản trị' : 'Thu gọn thanh quản trị');
  };
  apply(localStorage.getItem(KEY) === '1');
  btn.addEventListener('click', () => {
    const collapsed = !text.hidden;
    localStorage.setItem(KEY, collapsed ? '1' : '0');
    apply(collapsed);
  });
}

function initHeader() {
  const header = document.getElementById('site-header');
  if (header) {
    const onScroll = () => header.classList.toggle('shadow-card-hover', window.scrollY > 8);
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }
  const bar = document.getElementById('announcement-bar');
  if (bar) {
    const key = 'iparts_announcement_' + (bar.dataset.hash || '');
    if (localStorage.getItem(key)) bar.remove();
    bar.querySelector('[data-close]')?.addEventListener('click', () => {
      localStorage.setItem(key, '1');
      bar.remove();
    });
  }
  // Dropdown (tài khoản, mega menu)
  document.querySelectorAll('[data-dropdown]').forEach((wrap) => {
    const trigger = wrap.querySelector('[data-dropdown-trigger]');
    const menu = wrap.querySelector('[data-dropdown-menu]');
    trigger?.addEventListener('click', (e) => {
      e.stopPropagation();
      const willOpen = menu.hidden;
      document.querySelectorAll('[data-dropdown-menu]').forEach((m) => { m.hidden = true; });
      menu.hidden = !willOpen;
      trigger.setAttribute('aria-expanded', String(willOpen));
    });
  });
  document.addEventListener('click', (e) => {
    if (!e.target.closest('[data-dropdown]')) document.querySelectorAll('[data-dropdown-menu]').forEach((m) => { m.hidden = true; });
  });
  // Drawer mobile
  document.querySelectorAll('[data-drawer-open]').forEach((btn) => btn.addEventListener('click', () => {
    const drawer = document.getElementById(btn.dataset.drawerOpen);
    drawer.hidden = false;
    document.body.classList.add('overflow-hidden');
  }));
  document.querySelectorAll('[data-drawer]').forEach((drawer) => drawer.addEventListener('click', (e) => {
    if (e.target === drawer || e.target.closest('[data-drawer-close]')) {
      drawer.hidden = true;
      document.body.classList.remove('overflow-hidden');
    }
  }));
  document.querySelector('[data-mobile-search-toggle]')?.addEventListener('click', () => {
    const bar = document.getElementById('mobile-search');
    bar.hidden = !bar.hidden;
    if (!bar.hidden) bar.querySelector('input')?.focus();
  });
}

// ---------- Tìm kiếm gợi ý ----------
function initSearchSuggest() {
  document.querySelectorAll('[data-search-suggest]').forEach((form) => {
    const input = form.querySelector('input[name="q"]');
    const box = form.querySelector('[data-suggest-box]');
    let items = [];
    let active = -1;
    const render = () => {
      box.replaceChildren();
      if (!items.length) {
        box.hidden = true;
        return;
      }
      items.forEach((p, i) => {
        const a = el('a', `flex items-center gap-3 px-3 py-2 hover:bg-slate-50 ${i === active ? 'bg-slate-100' : ''}`);
        a.href = p.url;
        const img = el('img', 'h-10 w-10 rounded-lg object-cover bg-slate-100');
        img.src = p.image;
        img.alt = '';
        const info = el('div', 'min-w-0 flex-1');
        info.append(el('div', 'truncate text-sm font-medium', p.name), el('div', 'text-xs font-semibold text-primary', formatVnd(p.price)));
        a.append(img, info);
        box.appendChild(a);
      });
      const all = el('button', 'w-full border-t border-border px-3 py-2 text-left text-sm text-primary hover:bg-slate-50', `Xem tất cả kết quả cho "${input.value}"`);
      all.type = 'submit';
      box.appendChild(all);
      box.hidden = false;
    };
    const load = debounce(async () => {
      const q = input.value.trim();
      if (q.length < 2) {
        items = [];
        render();
        return;
      }
      try {
        const res = await apiFetch(`/api/search/suggest/?q=${encodeURIComponent(q)}`, { silent: true });
        items = res.data.products;
        active = -1;
        render();
      } catch (e) { /* bỏ qua */ }
    }, 300);
    input.addEventListener('input', load);
    input.addEventListener('keydown', (e) => {
      if (box.hidden || !items.length) return;
      if (e.key === 'ArrowDown') { active = Math.min(active + 1, items.length - 1); render(); e.preventDefault(); }
      if (e.key === 'ArrowUp') { active = Math.max(active - 1, -1); render(); e.preventDefault(); }
      if (e.key === 'Enter' && active >= 0) { window.location.href = items[active].url; e.preventDefault(); }
      if (e.key === 'Escape') box.hidden = true;
    });
    document.addEventListener('click', (e) => { if (!form.contains(e.target)) box.hidden = true; });
  });
}

// ---------- Giỏ hàng / Mua ngay ----------
export async function addToCart(productId, quantity = 1, { buyNow = false, button = null } = {}) {
  if (!IP.isAuthenticated) {
    sessionStorage.setItem(PENDING_KEY, JSON.stringify({ type: 'add_to_cart', product_id: productId, qty: quantity, name: button?.dataset.productName || '', path: location.pathname }));
    openLoginModal();
    return null;
  }
  if (IP.isStaff) {
    toast('Tài khoản quản trị không dùng để mua hàng.', 'warning');
    return null;
  }
  setLoading(button, true);
  try {
    const res = await apiFetch('/api/cart/add/', { method: 'POST', body: { product_id: productId, quantity, buy_now: buyNow } });
    updateCounters(res.data);
    if (buyNow) {
      window.location.href = '/thanh-toan/';
      return res;
    }
    toast(res.message || 'Đã thêm vào giỏ hàng.', res.data.limited ? 'warning' : 'success');
    return res;
  } catch (e) {
    return null;
  } finally {
    setLoading(button, false);
  }
}

function initCartButtons() {
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-add-to-cart]');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    const qtyInput = btn.dataset.qtyInput ? document.querySelector(btn.dataset.qtyInput) : null;
    addToCart(Number(btn.dataset.addToCart), qtyInput ? Number(qtyInput.value) || 1 : 1, { buyNow: btn.hasAttribute('data-buy-now'), button: btn });
  });
}

// ---------- Yêu thích ----------
function initWishlist() {
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-wishlist-toggle]');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    if (!IP.isAuthenticated) {
      openLoginModal();
      return;
    }
    if (IP.isStaff) {
      toast('Tài khoản quản trị không dùng chức năng yêu thích.', 'warning');
      return;
    }
    btn.disabled = true;
    try {
      const res = await apiFetch('/api/wishlist/toggle/', { method: 'POST', body: { product_id: Number(btn.dataset.wishlistToggle) } });
      document.querySelectorAll(`[data-wishlist-toggle="${btn.dataset.wishlistToggle}"]`).forEach((b) => {
        b.classList.toggle('is-wishlisted', res.data.in_wishlist);
        b.setAttribute('aria-pressed', String(res.data.in_wishlist));
      });
      updateCounters(res.data);
      toast(res.message, 'success');
      if (!res.data.in_wishlist && btn.dataset.removeCard !== undefined) btn.closest('[data-product-card]')?.remove();
    } catch (err) { /* đã toast */ } finally {
      btn.disabled = false;
    }
  });
}

// ---------- Hành động dang dở sau khi đăng nhập ----------
async function resumePendingAction() {
  const raw = sessionStorage.getItem(PENDING_KEY);
  if (!raw || !IP.isAuthenticated || IP.isStaff) return;
  sessionStorage.removeItem(PENDING_KEY);
  let action;
  try { action = JSON.parse(raw); } catch (e) { return; }
  if (action.type !== 'add_to_cart') return;
  const { confirmDialog } = await import('../core/modal.js');
  const result = await confirmDialog({
    title: 'Tiếp tục mua hàng?',
    message: `Bạn có muốn thêm sản phẩm ${action.name ? `"${action.name}" ` : ''}vào giỏ hàng không?`,
    confirmText: 'Thêm vào giỏ',
    danger: false,
  });
  if (result.confirmed) addToCart(action.product_id, action.qty || 1);
}

// ---------- Newsletter ----------
function initNewsletter() {
  document.querySelectorAll('[data-newsletter-form]').forEach((form) => form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    setLoading(btn, true);
    try {
      const res = await apiFetch('/api/newsletter/', { method: 'POST', body: { email: form.email.value } });
      toast(res.message, 'success');
      form.reset();
    } catch (err) { /* đã toast */ } finally {
      setLoading(btn, false);
    }
  }));
}

// ---------- Tiện ích form: hiện/ẩn mật khẩu, chặn submit 2 lần, accordion ----------
function initFormHelpers() {
  document.querySelectorAll('[data-toggle-password]').forEach((btn) => btn.addEventListener('click', () => {
    const input = document.getElementById(btn.dataset.togglePassword);
    input.type = input.type === 'password' ? 'text' : 'password';
    btn.setAttribute('aria-label', input.type === 'password' ? 'Hiện mật khẩu' : 'Ẩn mật khẩu');
  }));
  document.querySelectorAll('form[data-once]').forEach((form) => form.addEventListener('submit', (e) => {
    if (form.dataset.submitting) {
      e.preventDefault();
      return;
    }
    if (e.defaultPrevented) return;
    form.dataset.submitting = '1';
    setLoading(form.querySelector('button[type="submit"]'), true);
  }));
  document.querySelectorAll('[data-accordion] [data-accordion-trigger]').forEach((btn) => btn.addEventListener('click', () => {
    const panel = btn.nextElementSibling;
    const isOpen = !panel.classList.toggle('hidden');
    btn.setAttribute('aria-expanded', String(isOpen));
    btn.querySelector('[data-accordion-icon]')?.classList.toggle('rotate-180', isOpen);
  }));
  document.querySelectorAll('[data-google-disabled]').forEach((btn) => btn.addEventListener('click', (e) => {
    e.preventDefault();
    toast('Đăng nhập Google chưa được cấu hình. Quản trị viên vui lòng xem README mục Google OAuth.', 'warning');
  }));
  document.querySelectorAll('[data-copy]').forEach((btn) => btn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(btn.dataset.copy);
      toast('Đã sao chép.', 'success');
    } catch (e) { toast('Không sao chép được, vui lòng chọn và sao chép thủ công.', 'warning'); }
  }));
  document.querySelectorAll('select[data-autosubmit], input[data-autosubmit]').forEach((s) => s.addEventListener('change', () => s.form.submit()));
}

// ---------- Quantity stepper ----------
export function initSteppers(root = document) {
  root.querySelectorAll('[data-stepper]').forEach((wrap) => {
    if (wrap.dataset.bound) return;
    wrap.dataset.bound = '1';
    const input = wrap.querySelector('input');
    const clamp = () => {
      const max = Number(input.max) || 10;
      let v = Math.round(Number(input.value) || 1);
      v = Math.min(Math.max(v, 1), max);
      input.value = v;
      input.dispatchEvent(new CustomEvent('stepper:change', { bubbles: true }));
    };
    wrap.querySelector('[data-step="-1"]').addEventListener('click', () => { input.value = Number(input.value) - 1; clamp(); });
    wrap.querySelector('[data-step="1"]').addEventListener('click', () => {
      if (Number(input.value) >= (Number(input.max) || 10)) toast(`Chỉ còn ${input.max} sản phẩm có thể mua.`, 'warning');
      input.value = Number(input.value) + 1;
      clamp();
    });
    input.addEventListener('change', clamp);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  refreshIcons();
  initModals();
  initConfirmForms();
  flushMessages();
  initAdminToolbar();
  initHeader();
  initSearchSuggest();
  initCartButtons();
  initWishlist();
  initNewsletter();
  initFormHelpers();
  initSteppers();
  resumePendingAction();
});
