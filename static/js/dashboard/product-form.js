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

// ---------- Biến thể: a) Loại màn  b) Màu sắc  c) Bảng biến thể tự sinh = loại × màu ----------
const SCREEN_TYPES = [
  ['Màn zin bóc máy', 'Màn Apple tháo máy, màu sắc – độ sáng – cảm ứng gần như nguyên bản.'],
  ['Màn zin ép kính', 'Tấm màn zin Apple, ép lại mặt kính mới – hiển thị chuẩn, giá mềm hơn zin bóc máy.'],
  ['Màn GX', 'Màn OLED/LCD hãng GX chất lượng cao, màu sắc tươi, cảm ứng nhạy.'],
  ['Màn JK', 'Màn JK incell phổ thông, hiển thị ổn định, giá tốt.'],
  ['Màn Incell', 'Màn Incell giá rẻ, phù hợp nhu cầu sử dụng cơ bản.'],
  ['Màn linh kiện thường (màn lô)', 'Màn linh kiện phổ thông, giá tiết kiệm nhất.'],
];
const editor = readJson('variant-editor-data');
const optInput = form.querySelector('input[name="options_data"]');
const colorInput = form.querySelector('input[name="colors_data"]');
const variantInput = form.querySelector('input[name="variants_data"]');
const optBox = form.querySelector('[data-option-rows]');
const colorBox = form.querySelector('[data-color-rows]');
const variantBody = form.querySelector('[data-variant-rows]');
const priceNote = form.querySelector('[data-price-note]');
let newKey = 0;
const nextKey = (p) => `${p}${Date.now().toString(36)}${newKey++}`;

const mkInput = (key, placeholder, value, type = 'text', cls = 'form-input py-2') => {
  const i = el('input', cls);
  i.type = type; i.placeholder = placeholder; i.dataset.k = key; i.value = value ?? '';
  if (type === 'number') { i.min = '0'; i.step = '1000'; }
  return i;
};
const mkCheck = (key, checked, label, type = 'checkbox', name = '') => {
  const wrap = el('label', 'flex shrink-0 cursor-pointer items-center gap-1.5 text-xs');
  const c = el('input', 'form-check'); c.type = type; c.dataset.k = key; c.checked = Boolean(checked);
  if (name) c.name = name;
  wrap.append(c, el('span', type === 'radio' ? 'font-semibold text-primary' : '', label));
  return wrap;
};
const mkDel = (onClick) => {
  const d = el('button', 'icon-btn shrink-0 text-danger', '✕'); d.type = 'button'; d.setAttribute('aria-label', 'Xóa');
  d.addEventListener('click', onClick);
  return d;
};
const rowVal = (r, k) => r.querySelector(`[data-k="${k}"]`);

// ---- a) Loại màn
function addOptionRow(o = {}) {
  const row = el('div', 'grid items-center gap-2 rounded-lg bg-slate-50 p-2 md:grid-cols-[auto_1fr_2fr_auto_36px]');
  row.dataset.id = o.id || '';
  row.dataset.key = o.key || (o.id ? String(o.id) : nextKey('o'));
  const name = mkInput('name', 'Tên loại, vd. Màn zin bóc máy', o.name); name.maxLength = 100;
  const desc = mkInput('description', 'Mô tả ngắn 2–3 dòng hiện dưới nhóm chọn', o.description); desc.maxLength = 300;
  row.append(mkCheck('is_default', o.is_default, 'Mặc định', 'radio', 'option_default_ui'), name, desc,
    mkCheck('is_active', o.is_active !== false, 'Hiển thị'), mkDel(() => { row.remove(); renderVariants(); }));
  name.addEventListener('input', renderVariants);
  rowVal(row, 'is_active').addEventListener('change', renderVariants);
  optBox.appendChild(row);
  return row;
}

// ---- b) Màu sắc
function addColorRow(c = {}) {
  const row = el('div', 'grid items-center gap-2 rounded-lg bg-slate-50 p-2 md:grid-cols-[auto_44px_1.2fr_1.6fr_auto_36px]');
  row.dataset.id = c.id || '';
  row.dataset.key = c.key || (c.id ? String(c.id) : nextKey('c'));
  const hex = el('input', 'h-10 w-11 cursor-pointer rounded-lg border border-border'); hex.type = 'color';
  hex.dataset.k = 'hex_code'; hex.value = (c.hex_code || '#e2e8f0').toLowerCase(); hex.title = 'Mã màu';
  const name = mkInput('name', 'Tên màu, vd. Trắng', c.name); name.maxLength = 60;
  const imgWrap = el('div', 'flex items-center gap-2 text-xs');
  const thumb = el('img', 'h-9 w-9 rounded-md object-cover'); thumb.alt = ''; thumb.hidden = !c.image; if (c.image) thumb.src = c.image;
  const file = el('input', 'w-40 text-xs'); file.type = 'file'; file.accept = 'image/jpeg,image/png,image/webp';
  file.name = `color_image_${row.dataset.key}`;
  file.addEventListener('change', () => { if (file.files[0]) { thumb.src = URL.createObjectURL(file.files[0]); thumb.hidden = false; } });
  imgWrap.append(thumb, file);
  if (c.image) imgWrap.append(mkCheck('remove_image', false, 'Xóa ảnh'));
  row.append(mkCheck('is_default', c.is_default, 'Mặc định', 'radio', 'color_default_ui'), hex, name, imgWrap,
    mkCheck('is_active', c.is_active !== false, 'Hiển thị'), mkDel(() => { row.remove(); renderVariants(); }));
  name.addEventListener('input', renderVariants);
  rowVal(row, 'is_active').addEventListener('change', renderVariants);
  colorBox.appendChild(row);
  return row;
}

// ---- c) Bảng biến thể: sinh lại khi đổi loại/màu, giữ nguyên giá đã nhập theo cặp key
const variantState = new Map();  // `${optionKey}|${colorKey}` -> dữ liệu dòng
(editor.variants || []).forEach((v) => variantState.set(`${v.option_key || ''}|${v.color_key || ''}`, { ...v }));

function readVariantRows() {
  variantBody.querySelectorAll('tr[data-pair]').forEach((tr) => {
    const st = variantState.get(tr.dataset.pair) || {};
    ['price', 'compare_price', 'stock', 'sku'].forEach((k) => { st[k] = rowVal(tr, k).value; });
    st.is_active = rowVal(tr, 'is_active').checked;
    st.remove_image = Boolean(rowVal(tr, 'remove_image')?.checked);
    variantState.set(tr.dataset.pair, st);
  });
}

function renderVariants() {
  readVariantRows();
  const opts = [...optBox.children].filter((r) => rowVal(r, 'name').value.trim());
  const cols = [...colorBox.children].filter((r) => rowVal(r, 'name').value.trim());
  form.querySelector('[data-option-empty]').hidden = opts.length > 0;
  form.querySelector('[data-color-empty]').hidden = cols.length > 0;
  const optList = opts.length ? opts : [null];
  const colList = cols.length ? cols : [null];
  // Giữ lại input file đã chọn (không tạo lại được) theo cặp
  const files = new Map([...variantBody.querySelectorAll('tr[data-pair]')].map((tr) => [tr.dataset.pair, tr.querySelector('input[type="file"]')]));
  variantBody.replaceChildren();
  const hasAny = opts.length || cols.length;
  form.querySelector('[data-variant-empty]').hidden = Boolean(hasAny);
  priceNote.hidden = !hasAny;
  if (!hasAny) return;
  optList.forEach((o) => {
    colList.forEach((c, ci) => {
      const pair = `${o ? o.dataset.key : ''}|${c ? c.dataset.key : ''}`;
      const st = variantState.get(pair) || { is_active: true };
      if (!st.key) st.key = st.id ? `v${st.id}` : nextKey('v');
      variantState.set(pair, st);
      const tr = el('tr', `border-t border-border ${ci === 0 && cols.length > 1 ? 'border-t-2 border-t-primary/30' : ''}`);
      tr.dataset.pair = pair;
      const off = (o && !rowVal(o, 'is_active').checked) || (c && !rowVal(c, 'is_active').checked);
      const label = el('td', 'whitespace-nowrap px-2 py-1.5');
      label.append(el('div', 'font-semibold', [o && rowVal(o, 'name').value.trim(), c && rowVal(c, 'name').value.trim()].filter(Boolean).join(' – ')));
      if (off) label.append(el('div', 'text-[11px] text-warning', 'Loại/màu đang ẩn'));
      const price = mkInput('price', 'Để trống = không bán', st.price, 'number', 'form-input w-32 py-1.5');
      const compare = mkInput('compare_price', 'Giá gốc', st.compare_price, 'number', 'form-input w-28 py-1.5');
      const pct = el('td', 'px-2 text-sm font-bold text-danger');
      const upd = () => {
        const p = Number(price.value) || 0; const cp = Number(compare.value) || 0;
        pct.textContent = p && cp > p ? `-${Math.round((cp - p) * 100 / cp)}%` : '—';
        compare.classList.toggle('border-danger', Boolean(cp) && cp <= p);
      };
      price.addEventListener('input', upd); compare.addEventListener('input', upd); upd();
      const stock = mkInput('stock', '0', st.stock ?? 0, 'number', 'form-input w-20 py-1.5'); stock.step = '1';
      const sku = mkInput('sku', 'Tùy chọn', st.sku, 'text', 'form-input w-32 py-1.5'); sku.maxLength = 50;
      const imgTd = el('td', 'px-2');
      const imgWrap = el('div', 'flex items-center gap-1.5');
      const thumb = el('img', 'h-8 w-8 rounded object-cover'); thumb.alt = ''; thumb.hidden = !st.image; if (st.image) thumb.src = st.image;
      let file = files.get(pair);
      if (!file) {
        file = el('input', 'w-36 text-xs'); file.type = 'file'; file.accept = 'image/jpeg,image/png,image/webp';
        file.addEventListener('change', () => { if (file.files[0]) { thumb.src = URL.createObjectURL(file.files[0]); thumb.hidden = false; } });
      }
      file.name = `variant_image_${st.key}`;
      imgWrap.append(thumb, file);
      if (st.image) imgWrap.append(mkCheck('remove_image', st.remove_image, 'Xóa'));
      imgTd.append(imgWrap);
      const active = el('input', 'form-check'); active.type = 'checkbox'; active.dataset.k = 'is_active'; active.checked = st.is_active !== false;
      const td = (child) => { const t = el('td', 'px-2 py-1.5'); t.append(child); return t; };
      const priceTd = td(price);
      if (cols.length > 1 && o) {  // Áp giá cho tất cả màu của loại này
        const apply = el('button', 'mt-1 block text-[11px] font-semibold text-primary hover:underline', 'Áp giá cho tất cả màu');
        apply.type = 'button';
        apply.addEventListener('click', () => {
          variantBody.querySelectorAll(`tr[data-pair^="${o.dataset.key}|"]`).forEach((other) => {
            rowVal(other, 'price').value = price.value;
            rowVal(other, 'compare_price').value = compare.value;
            rowVal(other, 'price').dispatchEvent(new Event('input'));
          });
          toast('Đã áp giá cho tất cả màu của loại này.', 'success');
        });
        priceTd.append(apply);
      }
      tr.append(label, priceTd, td(compare), pct, td(stock), td(sku), imgTd, td(active));
      variantBody.appendChild(tr);
    });
  });
}

(editor.options || []).forEach((o) => addOptionRow(o));
(editor.colors || []).forEach((c) => addColorRow(c));
form.querySelector('[data-option-add]').addEventListener('click', () => { addOptionRow().querySelector('[data-k="name"]').focus(); renderVariants(); });
form.querySelector('[data-color-add]').addEventListener('click', () => { addColorRow().querySelector('[data-k="name"]').focus(); renderVariants(); });
const namesIn = (box) => new Set([...box.querySelectorAll('[data-k="name"]')].map((i) => i.value.trim().toLowerCase()));
function addScreenTypes() {
  const names = namesIn(optBox);
  const empty = !optBox.children.length;
  SCREEN_TYPES.filter(([n]) => !names.has(n.toLowerCase())).forEach(([n, d], i) => addOptionRow({ name: n, description: d, is_default: empty && i === 0 }));
  if (!form.option_label.value.trim()) form.option_label.value = 'Loại màn hình';
  renderVariants();
}
form.querySelector('[data-option-template="screen"]').addEventListener('click', () => {
  addScreenTypes();
  toast('Đã thêm 6 loại màn – nhập giá cho từng tổ hợp ở bảng biến thể.', 'info');
});
form.querySelector('[data-option-template="models"]').addEventListener('click', () => {
  const models = [...form.querySelectorAll('input[name="compat_models"]:checked')].map((c) => c.parentElement.textContent.trim());
  if (!models.length) { toast('Tick các dòng máy ở khung "Tương thích" trước.', 'warning'); return; }
  const names = namesIn(optBox);
  models.filter((m) => !names.has(m.toLowerCase())).forEach((m) => addOptionRow({ name: m }));
  if (!form.option_label.value.trim()) form.option_label.value = 'Dòng máy';
  renderVariants();
});
form.querySelector('[data-color-template]').addEventListener('click', () => {
  const names = namesIn(colorBox);
  const empty = !colorBox.children.length;
  [['Trắng', '#ffffff'], ['Đen', '#111111']].filter(([n]) => !names.has(n.toLowerCase()))
    .forEach(([n, h], i) => addColorRow({ name: n, hex_code: h, is_default: empty && i === 0 }));
  renderVariants();
});
// Danh mục Màn hình mà chưa có loại màn: tự điền sẵn 6 loại
const isScreenCategory = () => {
  const v = form.category.value;
  if (!v) return false;
  const text = (form.category.selectedOptions[0]?.textContent || '').toLowerCase();
  return CATEGORY_CODES[v] === 'SCR' || text.includes('màn hình');
};
const autoScreenTypes = () => {
  if (isScreenCategory() && !optBox.children.length) {
    addScreenTypes();
    toast('Sản phẩm màn hình: đã điền sẵn 6 loại màn – thêm màu (nếu có) rồi nhập giá ở bảng biến thể.', 'info');
  }
};
form.category.addEventListener('change', autoScreenTypes);
renderVariants();
autoScreenTypes();

function serializeVariants() {
  readVariantRows();
  const group = (box, extra) => {
    const rows = [...box.children];
    if (rows.length && !rows.some((r) => rowVal(r, 'is_default').checked)) rowVal(rows[0], 'is_default').checked = true;
    return rows.map((r) => ({
      id: r.dataset.id ? Number(r.dataset.id) : null, key: r.dataset.key, name: rowVal(r, 'name').value.trim(),
      is_default: rowVal(r, 'is_default').checked, is_active: rowVal(r, 'is_active').checked, ...extra(r),
    })).filter((x) => x.name);
  };
  optInput.value = JSON.stringify(group(optBox, (r) => ({ description: rowVal(r, 'description').value.trim() })));
  colorInput.value = JSON.stringify(group(colorBox, (r) => ({
    hex_code: rowVal(r, 'hex_code').value, remove_image: Boolean(rowVal(r, 'remove_image')?.checked),
  })));
  const nameOf = (box, key) => (key ? rowVal(box.querySelector(`[data-key="${CSS.escape(key)}"]`) || el('div'), 'name')?.value.trim() : '');
  const variants = [...variantBody.querySelectorAll('tr[data-pair]')].map((tr) => {
    const [optionKey, colorKey] = tr.dataset.pair.split('|');
    const st = variantState.get(tr.dataset.pair);
    return {
      id: st.id || null, key: st.key, option_key: optionKey, color_key: colorKey,
      option_name: nameOf(optBox, optionKey), color_name: nameOf(colorBox, colorKey),
      price: st.price, compare_price: st.compare_price, stock: st.stock, sku: st.sku,
      is_active: st.is_active, remove_image: st.remove_image,
    };
  });
  variantInput.value = JSON.stringify(variants);
  // Giá sản phẩm là trường bắt buộc: có biến thể thì lấy tạm theo tổ hợp đầu tiên có giá (server tự đồng bộ khi lưu)
  const first = variants.find((v) => Number(v.price) > 0);
  if (first && !Number(form.price.value)) form.price.value = first.price;
}

form.addEventListener('submit', () => {
  serializeVariants();
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
  if (sale && sale > price) box.appendChild(el('div', 'font-semibold text-danger', 'Giá khuyến mãi không được lớn hơn giá bán'));
  if (sale && sale === price) box.appendChild(el('div', 'text-muted', 'Giảm 0% – không khuyến mãi'));
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
