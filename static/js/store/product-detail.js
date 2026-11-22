// Trang chi tiết: gallery + lightbox, tabs, kiểm tra tương thích theo máy.
import { apiFetch } from '../core/api.js';
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

// Kiểm tra máy của bạn
const check = document.querySelector('[data-compat-check]');
if (check) {
  const select = check.querySelector('select');
  const result = check.querySelector('[data-compat-result]');
  const saved = localStorage.getItem('iparts_my_model');
  if (saved && select.querySelector(`option[value="${CSS.escape(saved)}"]`)) select.value = saved;
  const run = async () => {
    if (!select.value) {
      result.classList.add('hidden');
      return;
    }
    localStorage.setItem('iparts_my_model', select.value);
    try {
      const res = await apiFetch(`${check.dataset.url}?model=${encodeURIComponent(select.value)}`, { silent: true });
      const { status, note, model } = res.data;
      const map = {
        verified: ['bg-green-100 text-green-800', `✔ Tương thích với ${model}`],
        incompatible: ['bg-red-100 text-red-800', `✖ Không tương thích với ${model}`],
        unknown: ['bg-amber-100 text-amber-800', `Chưa có thông tin xác nhận cho ${model}, vui lòng liên hệ hoặc hỏi iParts AI Assistant`],
      };
      const [cls, text] = map[status] || map.unknown;
      result.className = `mt-3 rounded-lg px-3 py-2 text-sm font-medium ${cls}`;
      result.textContent = note ? `${text}. ${note}` : text;
    } catch (e) {
      result.className = 'mt-3 rounded-lg bg-red-100 px-3 py-2 text-sm text-red-800';
      result.textContent = 'Không thể kiểm tra lúc này, vui lòng thử lại.';
    }
  };
  select.addEventListener('change', run);
  if (select.value) run();
}
