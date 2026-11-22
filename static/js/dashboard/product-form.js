// Form sản phẩm (Admin): thông số + điểm nổi bật dạng bảng động, mẫu thông số theo loại, gợi ý SKU,
// xem trước % giảm/lợi nhuận, ảnh kéo thả + sắp xếp + chọn ảnh chính, lọc tương thích.
import { apiFetch } from '../core/api.js';
import { toast } from '../core/toast.js';
import { el, formatVnd, refreshIcons } from '../core/utils.js';

const form = document.querySelector('[data-product-form]');
const readJson = (id) => JSON.parse(document.getElementById(id)?.textContent || '[]');
const CATEGORY_CODES = JSON.parse(document.getElementById('category-codes').textContent || '{}');

// Mẫu thông số theo mã danh mục cấp 1
const SPEC_TEMPLATES = {
  SCR: ['Công nghệ', 'Kích thước', 'Độ phân giải', 'Tần số quét', 'True Tone', 'Cảm ứng'],
  BAT: ['Dung lượng', 'Điện áp', 'Loại cell', 'Chu kỳ sạc', 'Hiển thị tình trạng pin'],
  CAM: ['Độ phân giải', 'Khẩu độ', 'Chống rung', 'Loại camera'],
  CHG: ['Cổng kết nối', 'Tốc độ sạc', 'Kèm micro', 'Chất liệu cáp'],
  SPK: ['Loại loa', 'Công suất', 'Trở kháng'],
  MIC: ['Loại micro', 'Vị trí'],
  HSG: ['Màu sắc', 'Chất liệu', 'Kèm linh kiện'],
  FRM: ['Màu sắc', 'Chất liệu'],
  BTN: ['Loại nút', 'Kèm cáp'],
  OTH: ['Loại linh kiện', 'Ghi chú'],
};

// ---------- Bảng động: thông số (Tên – Giá trị) ----------
const specInput = form.querySelector('input[name="specifications"]');
const specBox = form.querySelector('[data-spec-rows]');
function addSpecRow(label = '', value = '') {
  const row = el('div', 'grid gap-2 md:grid-cols-[1fr_1fr_40px]');
  const l = el('input', 'form-input py-2'); l.placeholder = 'Tên thông số'; l.value = label; l.dataset.k = 'label';
  const v = el('input', 'form-input py-2'); v.placeholder = 'Giá trị'; v.value = value; v.dataset.k = 'value';
  const del = el('button', 'icon-btn text-danger', '✕'); del.type = 'button'; del.setAttribute('aria-label', 'Xóa dòng');
  del.addEventListener('click', () => row.remove());
  row.append(l, v, del);
  specBox.appendChild(row);
  return row;
}
const specs = readJson('specs-data');
(specs.length ? specs : [{ label: '', value: '' }]).forEach((s) => addSpecRow(s.label, s.value));
form.querySelector('[data-spec-add]').addEventListener('click', () => addSpecRow().querySelector('input').focus());
form.querySelector('[data-spec-template]').addEventListener('click', () => {
  const code = CATEGORY_CODES[form.category.value];
  const tpl = SPEC_TEMPLATES[code];
  if (!tpl) { toast('Chọn danh mục trước để dùng mẫu thông số.', 'warning'); return; }
  const existing = new Set([...specBox.querySelectorAll('[data-k="label"]')].map((i) => i.value.trim().toLowerCase()));
  [...specBox.children].forEach((r) => { if (!r.querySelector('[data-k="label"]').value.trim()) r.remove(); });
  tpl.filter((t) => !existing.has(t.toLowerCase())).forEach((t) => addSpecRow(t, ''));
  toast('Đã thêm mẫu thông số – hãy điền giá trị.', 'info');
});

// ---------- Bảng động: điểm nổi bật ----------
const hlInput = form.querySelector('input[name="highlights"]');
const hlBox = form.querySelector('[data-highlight-rows]');
function addHighlight(text = '') {
  const row = el('div', 'flex gap-2');
  const i = el('input', 'form-input py-2'); i.placeholder = 'Điểm nổi bật'; i.value = text; i.maxLength = 200;
  const del = el('button', 'icon-btn shrink-0 text-danger', '✕'); del.type = 'button'; del.setAttribute('aria-label', 'Xóa dòng');
  del.addEventListener('click', () => row.remove());
  row.append(i, del);
  hlBox.appendChild(row);
  return i;
}
readJson('highlights-data').forEach((h) => addHighlight(h));
form.querySelector('[data-highlight-add]').addEventListener('click', () => addHighlight().focus());

form.addEventListener('submit', () => {
  specInput.value = JSON.stringify([...specBox.children].map((r) => ({
    label: r.querySelector('[data-k="label"]').value.trim(), value: r.querySelector('[data-k="value"]').value.trim(),
  })).filter((s) => s.label));
  hlInput.value = JSON.stringify([...hlBox.querySelectorAll('input')].map((i) => i.value.trim()).filter(Boolean));
});

// ---------- Gợi ý SKU ----------
form.querySelector('[data-suggest-sku]').addEventListener('click', async (e) => {
  const category = form.category.value;
  const firstModel = form.querySelector('input[name="compat_models"]:checked')?.parentElement.textContent.trim() || '';
  if (!category) { toast('Vui lòng chọn danh mục trước.', 'warning'); return; }
  try {
    const res = await apiFetch(`${e.currentTarget.dataset.suggestSku}?category=${category}&model=${encodeURIComponent(firstModel)}`);
    form.sku.value = res.data.sku;
  } catch (err) { /* đã toast */ }
});

// ---------- Xem trước % giảm và lợi nhuận ----------
function pricePreview() {
  const price = Number(form.price.value) || 0;
  const sale = Number(form.sale_price.value) || 0;
  const cost = Number(form.cost_price.value) || 0;
  const box = form.querySelector('[data-price-preview]');
  box.replaceChildren();
  const effective = sale && sale < price ? sale : price;
  if (sale && sale >= price) box.appendChild(el('div', 'font-semibold text-danger', 'Giá khuyến mãi phải nhỏ hơn giá bán'));
  if (sale && sale < price) box.appendChild(el('div', 'font-semibold text-danger', `Giảm ${Math.round((price - sale) * 100 / price)}%`));
  if (price) box.appendChild(el('div', '', `Lợi nhuận dự kiến: ${formatVnd(effective - cost)} (${effective ? Math.round((effective - cost) * 100 / effective) : 0}%)`));
  if (!box.children.length) box.textContent = 'Nhập giá để xem % giảm và lợi nhuận.';
}
['price', 'sale_price', 'cost_price'].forEach((n) => form[n].addEventListener('input', pricePreview));
pricePreview();

// ---------- Ảnh: kéo thả upload + xem trước ----------
const drop = form.querySelector('[data-dropzone]');
const fileInput = drop.querySelector('input[type="file"]');
const preview = form.querySelector('[data-image-preview]');
function showFiles() {
  preview.replaceChildren();
  [...fileInput.files].forEach((f) => {
    if (f.size > 5 * 1024 * 1024) toast(`${f.name} vượt quá 5 MB.`, 'error');
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(f.type)) toast(`${f.name}: chỉ nhận JPG/PNG/WEBP.`, 'error');
    const img = el('img', 'aspect-square w-full rounded-lg object-cover');
    img.src = URL.createObjectURL(f);
    img.alt = f.name;
    preview.appendChild(img);
  });
}
fileInput.addEventListener('change', showFiles);
['dragenter', 'dragover'].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add('border-primary'); }));
['dragleave', 'drop'].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove('border-primary'); }));
drop.addEventListener('drop', (e) => { fileInput.files = e.dataTransfer.files; showFiles(); });

// ---------- Ảnh hiện có: kéo để sắp xếp, ★ chọn ảnh chính ----------
const sortBox = form.querySelector('[data-image-sort]');
if (sortBox) {
  let dragged = null;
  const renumber = () => sortBox.querySelectorAll('[data-image-item]').forEach((item, i) => { item.querySelector('[data-order-input]').value = i; });
  sortBox.querySelectorAll('[data-image-item]').forEach((item) => {
    item.addEventListener('dragstart', () => { dragged = item; item.classList.add('opacity-50'); });
    item.addEventListener('dragend', () => { item.classList.remove('opacity-50'); dragged = null; renumber(); });
    item.addEventListener('dragover', (e) => {
      e.preventDefault();
      if (!dragged || dragged === item) return;
      const rect = item.getBoundingClientRect();
      sortBox.insertBefore(dragged, e.clientX < rect.left + rect.width / 2 ? item : item.nextSibling);
    });
  });
  sortBox.querySelectorAll('input[name="primary_image"]').forEach((r) => r.addEventListener('change', () => {
    sortBox.querySelectorAll('[data-image-item]').forEach((i) => i.classList.toggle('is-primary', i.contains(r) && r.checked));
  }));
}

// ---------- Tương thích: tìm nhanh + chọn cả nhóm ----------
form.querySelector('[data-compat-search]').addEventListener('input', (e) => {
  const q = e.target.value.trim().toLowerCase();
  form.querySelectorAll('[data-compat-item]').forEach((item) => { item.hidden = q && !item.dataset.compatItem.includes(q); });
});
form.querySelectorAll('[data-group-toggle]').forEach((btn) => btn.addEventListener('click', () => {
  const boxes = [...btn.closest('[data-compat-group]').querySelectorAll('input[type="checkbox"]')];
  const all = boxes.every((b) => b.checked);
  boxes.forEach((b) => { b.checked = !all; });
}));

// Thanh nút cố định: canh theo sidebar thu gọn
const bar = document.querySelector('[data-save-bar]');
const sidebar = document.getElementById('admin-sidebar');
const syncBar = () => {
  const desktop = window.matchMedia('(min-width: 1024px)').matches;
  bar.style.left = desktop ? (sidebar.classList.contains('is-collapsed') ? '72px' : '260px') : '0';
};
new MutationObserver(syncBar).observe(sidebar, { attributes: true, attributeFilter: ['class'] });
window.addEventListener('resize', syncBar);
syncBar();
refreshIcons();
