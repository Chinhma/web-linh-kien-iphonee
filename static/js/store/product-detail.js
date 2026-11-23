// Trang chi tiết: gallery + lightbox, tabs, chọn loại màn / màu (gọi API, server tính giá).
import { apiFetch } from '../core/api.js';
import { toast } from '../core/toast.js';
import { refreshIcons } from '../core/utils.js';
import { openModal } from '../core/modal.js';

const gallery = document.querySelector('[data-gallery]');
const mainImg = gallery?.querySelector('[data-gallery-image]');
const thumbs = [...(gallery?.querySelectorAll('[data-gallery-thumb]') || [])];
const sources = thumbs.length ? thumbs.map((t) => t.dataset.galleryThumb) : [mainImg?.src];
let current = 0;

function show(index) {
  current = (index + sources.length) % sources.length;
  mainImg.src = sources[current];
  thumbs.forEach((t, i) => {
    t.classList.toggle('border-primary', i === current);
    t.classList.toggle('border-border', i !== current);
  });
  const lb = document.querySelector('[data-lightbox-image]');
  if (lb) lb.src = sources[current];
}

thumbs.forEach((t, i) => t.addEventListener('click', () => show(i)));
gallery?.querySelector('[data-gallery-main]')?.addEventListener('click', () => {
  document.querySelector('[data-lightbox-image]').src = sources[current];
  openModal('lightbox');
});
document.querySelector('[data-lightbox-prev]')?.addEventListener('click', (e) => { e.stopPropagation(); show(current - 1); });
document.querySelector('[data-lightbox-next]')?.addEventListener('click', (e) => { e.stopPropagation(); show(current + 1); });
document.addEventListener('keydown', (e) => {
  if (document.getElementById('lightbox')?.hidden) return;
  if (e.key === 'ArrowLeft') show(current - 1);
  if (e.key === 'ArrowRight') show(current + 1);
});
let touchX = null;
mainImg?.addEventListener('touchstart', (e) => { touchX = e.touches[0].clientX; }, { passive: true });
mainImg?.addEventListener('touchend', (e) => {
  if (touchX === null) return;
  const dx = e.changedTouches[0].clientX - touchX;
  if (Math.abs(dx) > 40) show(current + (dx < 0 ? 1 : -1));
  touchX = null;
});

// Tabs
const tabs = document.querySelector('[data-tabs]');
function openTab(name) {
  tabs.querySelectorAll('[data-tab]').forEach((b) => b.classList.toggle('is-active', b.dataset.tab === name));
  tabs.querySelectorAll('[data-tab-panel]').forEach((p) => { p.hidden = p.dataset.tabPanel !== name; });
}
tabs?.querySelectorAll('[data-tab]').forEach((b) => b.addEventListener('click', () => openTab(b.dataset.tab)));
document.querySelectorAll('[data-open-tab]').forEach((a) => a.addEventListener('click', () => openTab(a.dataset.openTab)));
if (location.hash === '#tab-reviews' || new URLSearchParams(location.search).has('sao') || new URLSearchParams(location.search).has('trang_dg')) {
  openTab('reviews');
}

// ---------- Chọn LOẠI MÀN / MÀU: "load lại một nhịp" ----------
// Bấm 1 ô -> loading ngắn ở khối giá + ảnh, khoá các ô -> gọi API (server tính giá) -> thay khối chọn mua,
// thanh mua ở đáy, ảnh -> cập nhật URL ?loai=&mau= (F5 / gửi link vẫn đúng tổ hợp, nút Back quay lại tổ hợp trước).
const panel = document.querySelector('[data-purchase-panel]');
const buyBar = document.querySelector('[data-buy-bar]');
const imageLoading = document.querySelector('[data-image-loading]');
const MIN_LOADING_MS = 350;

function bindStepper(root) {  // Stepper nằm trong khối được thay mới -> gắn lại sự kiện
  root.querySelectorAll('[data-stepper]').forEach((wrap) => {
    const input = wrap.querySelector('input');
    const clamp = () => {
      const max = Number(input.max) || 10;
      input.value = Math.min(Math.max(Math.round(Number(input.value) || 1), 1), max);
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

function setLoading(on) {
  panel.classList.toggle('pointer-events-none', on);
  panel.setAttribute('aria-busy', String(on));
  panel.querySelectorAll('[data-loading-zone]').forEach((z) => z.classList.toggle('animate-pulse', on));
  panel.querySelectorAll('[data-variant-picker]').forEach((z) => z.classList.toggle('opacity-60', on));
  buyBar?.classList.toggle('opacity-60', on);
  if (imageLoading) {
    imageLoading.classList.toggle('hidden', !on);
    imageLoading.classList.toggle('flex', on);
  }
}

let busy = false;
async function loadVariant(query, { push = true } = {}) {
  if (!panel || busy) return;
  busy = true;
  setLoading(true);
  const qty = document.getElementById('detail-qty')?.value;
  try {
    const [res] = await Promise.all([
      apiFetch(`${panel.dataset.api}${query}`, { silent: true }),
      new Promise((r) => { setTimeout(r, MIN_LOADING_MS); }),
    ]);
    const d = res.data;
    panel.innerHTML = d.panel_html;
    if (buyBar) buyBar.innerHTML = d.bar_html;
    const qtyInput = document.getElementById('detail-qty');
    if (qtyInput && qty) qtyInput.value = Math.min(Number(qty), Number(qtyInput.max) || 1);
    bindStepper(panel);
    if (mainImg && d.image) {
      mainImg.src = d.image;
      const lb = document.querySelector('[data-lightbox-image]');
      if (lb) lb.src = d.image;
    }
    const badge = document.querySelector('[data-image-badge]');
    if (badge) {
      badge.classList.toggle('hidden', !d.discount_percent);
      badge.textContent = `-${d.discount_percent}%`;
    }
    const url = new URL(location.href);
    url.search = d.query;
    url.hash = '';
    history[push ? 'pushState' : 'replaceState']({ variantQuery: d.query }, '', url);
    if (d.notice) toast(d.notice, 'warning');
    refreshIcons();
  } catch (e) {
    toast('Không tải được giá của lựa chọn này, vui lòng thử lại.', 'error');
  } finally {
    busy = false;
    setLoading(false);
  }
}

if (panel) {
  panel.addEventListener('click', (e) => {
    const link = e.target.closest('[data-variant-link]');
    if (!link || e.metaKey || e.ctrlKey || e.shiftKey) return;  // mở tab mới thì để trình duyệt xử lý
    e.preventDefault();
    if (link.getAttribute('aria-current') === 'true') return;
    loadVariant(new URL(link.href, location.href).search);
  });
  window.addEventListener('popstate', () => loadVariant(location.search, { push: false }));
}
