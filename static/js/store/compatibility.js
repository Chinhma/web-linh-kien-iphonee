// Tra cứu linh kiện tương thích – 5 trạng thái: chưa chọn / đang tra cứu / có kết quả / không tìm thấy / lỗi.
import { apiFetch } from '../core/api.js';
import { el, formatVnd, refreshIcons, setLoading } from '../core/utils.js';
import { openChatWith } from '../chatbot/widget.js?v=4';

const app = document.querySelector('[data-compat-app]');
const results = app.querySelector('[data-compat-results]');
const submit = app.querySelector('[data-compat-submit]');
const label = app.querySelector('[data-selection-label]');
const select = app.querySelector('[data-model-select]');
const state = { model: '', modelName: '', category: '', categoryName: 'Tất cả linh kiện' };
const IS_STAFF = window.IPARTS?.isStaff;

function syncUi() {
  app.querySelectorAll('[data-model]').forEach((b) => b.classList.toggle('is-active', b.dataset.model === state.model));
  app.querySelectorAll('[data-category]').forEach((b) => b.classList.toggle('is-active', b.dataset.category === state.category));
  select.value = state.model;
  label.textContent = state.model ? `${state.modelName} · ${state.categoryName}` : '';
}

function setModel(slug) {
  const btn = app.querySelector(`[data-model="${CSS.escape(slug)}"]`);
  state.model = btn ? slug : '';
  state.modelName = btn ? btn.dataset.name : '';
  syncUi();
}

function setCategory(slug) {
  const btn = app.querySelector(`[data-category="${CSS.escape(slug)}"]`) || app.querySelector('[data-category=""]');
  state.category = btn.dataset.category;
  state.categoryName = btn.textContent.trim();
  syncUi();
}

function skeleton() {
  results.replaceChildren();
  for (let i = 0; i < 3; i += 1) {
    const card = el('div', 'card mb-3 flex gap-4 p-4');
    card.append(el('div', 'skeleton h-28 w-28 shrink-0'));
    const col = el('div', 'flex-1 space-y-3');
    col.append(el('div', 'skeleton h-4 w-2/3'), el('div', 'skeleton h-4 w-1/3'), el('div', 'skeleton h-8 w-40'));
    card.appendChild(col);
    results.appendChild(card);
  }
}

function itemCard(item) {
  const card = el('article', 'card flex flex-col gap-4 p-4 sm:flex-row');
  const imgLink = el('a', 'block shrink-0');
  imgLink.href = item.url;
  const img = el('img', 'h-40 w-full rounded-xl bg-slate-50 object-cover sm:h-32 sm:w-32');
  img.src = item.image;
  img.alt = item.name;
  img.loading = 'lazy';
  imgLink.appendChild(img);
  const body = el('div', 'min-w-0 flex-1');
  const title = el('a', 'font-semibold hover:text-primary', item.name);
  title.href = item.url;
  const meta = el('div', 'mt-1 flex flex-wrap items-center gap-2 text-xs text-muted');
  meta.append(el('span', '', `SKU: ${item.sku}`), el('span', 'badge-primary', item.quality), el('span', '', `Bảo hành ${item.warranty_months} tháng`));
  body.append(title, meta);
  if (item.specs.length) {
    const specs = el('ul', 'mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted');
    item.specs.forEach((s) => specs.appendChild(el('li', '', `${s.label}: ${s.value}`)));
    body.appendChild(specs);
  }
  if (item.note) {
    const note = el('p', 'mt-2 rounded-lg bg-amber-50 px-3 py-1.5 text-xs text-amber-800');
    note.textContent = `Ghi chú tương thích: ${item.note}`;
    body.appendChild(note);
  }
  const side = el('div', 'flex shrink-0 flex-col justify-between gap-3 sm:w-48 sm:items-end sm:text-right');
  const price = el('div');
  price.appendChild(el('div', 'text-lg font-bold text-primary', formatVnd(item.price)));
  if (item.original_price) price.appendChild(el('div', 'text-xs text-muted line-through', formatVnd(item.original_price)));
  const dot = item.stock_status === 'in_stock' ? 'bg-success' : item.stock_status === 'low_stock' ? 'bg-warning' : 'bg-danger';
  const stock = el('div', 'mt-1 flex items-center gap-1.5 text-xs text-muted sm:justify-end');
  stock.append(el('span', `h-2 w-2 rounded-full ${dot}`), document.createTextNode(item.stock_label));
  price.appendChild(stock);
  const actions = el('div', 'flex gap-2');
  const view = el('a', 'btn-secondary btn-sm', 'Xem chi tiết');
  view.href = item.url;
  actions.appendChild(view);
  if (IS_STAFF) {
    const edit = el('a', 'btn-primary btn-sm', 'Sửa');
    edit.href = `/quan-tri/san-pham/${item.id}/sua/`;
    actions.appendChild(edit);
  } else {
    const add = el('button', 'btn-primary btn-sm', item.purchasable ? 'Thêm vào giỏ' : 'Hết hàng');
    add.type = 'button';
    if (item.purchasable) {
      add.dataset.addToCart = item.id;
      add.dataset.productName = item.name;
    } else add.disabled = true;
    actions.appendChild(add);
  }
  side.append(price, actions);
  card.append(imgLink, body, side);
  return card;
}

function renderResults(data) {
  results.replaceChildren();
  if (!data.count) {
    const box = el('div', 'card flex flex-col items-center px-6 py-12 text-center');
    const icon = el('span', 'flex h-16 w-16 items-center justify-center rounded-full bg-amber-100 text-warning');
    icon.innerHTML = '<i data-lucide="search-x" class="h-8 w-8"></i>';
    const catText = data.category ? data.category.name.toLowerCase() : 'linh kiện';
    box.append(icon, el('h3', 'mt-4 text-lg font-semibold', `Chưa có ${catText} đã xác nhận tương thích với ${data.model.name}`));
    const btns = el('div', 'mt-5 flex flex-wrap justify-center gap-2');
    const ask = el('button', 'btn-primary', 'Hỏi iParts AI Assistant');
    ask.type = 'button';
    ask.addEventListener('click', () => openChatWith(`Có ${catText} nào cho ${data.model.name} không?`));
    const call = el('a', 'btn-secondary', `Liên hệ hotline ${app.dataset.hotlineDisplay}`);
    call.href = `tel:${app.dataset.hotline}`;
    btns.append(ask, call);
    box.appendChild(btns);
    if (data.other_categories?.length) {
      box.appendChild(el('p', 'mt-6 text-sm text-muted', `Linh kiện khác đang có cho ${data.model.name}:`));
      const chips = el('div', 'mt-2 flex flex-wrap justify-center gap-2');
      data.other_categories.forEach((c) => {
        const chip = el('button', 'chip', c.name);
        chip.type = 'button';
        chip.addEventListener('click', () => { setCategory(c.slug); lookup(); });
        chips.appendChild(chip);
      });
      box.appendChild(chips);
    }
    results.appendChild(box);
    refreshIcons();
    return;
  }
  const head = el('h2', 'mb-4 text-lg font-semibold');
  head.textContent = `Tìm thấy ${data.count} linh kiện tương thích với ${data.model.name}`;
  results.appendChild(head);
  if (!data.category) {
    const groups = {};
    data.items.forEach((i) => { (groups[i.category] = groups[i.category] || []).push(i); });
    Object.entries(groups).forEach(([name, items]) => {
      results.appendChild(el('h3', 'mb-3 mt-6 text-base font-semibold text-muted', `${name} (${items.length})`));
      const list = el('div', 'space-y-3');
      items.forEach((i) => list.appendChild(itemCard(i)));
      results.appendChild(list);
    });
  } else {
    const list = el('div', 'space-y-3');
    data.items.forEach((i) => list.appendChild(itemCard(i)));
    results.appendChild(list);
  }
  refreshIcons();
}

function renderError() {
  results.replaceChildren();
  const box = el('div', 'card flex flex-col items-center px-6 py-12 text-center');
  box.append(el('h3', 'text-lg font-semibold text-danger', 'Không thể tra cứu lúc này, vui lòng thử lại'));
  const retry = el('button', 'btn-primary mt-4', 'Thử lại');
  retry.type = 'button';
  retry.addEventListener('click', lookup);
  box.appendChild(retry);
  results.appendChild(box);
}

async function lookup() {
  if (!state.model) {
    label.textContent = 'Vui lòng chọn dòng iPhone trước.';
    label.className = 'text-sm font-medium text-danger';
    return;
  }
  label.className = 'text-sm text-muted';
  const params = new URLSearchParams({ model: state.model });
  if (state.category) params.set('category', state.category);
  history.replaceState(null, '', `${location.pathname}?${params}`);
  localStorage.setItem('iparts_my_model', state.model);
  setLoading(submit, true);
  skeleton();
  try {
    const res = await apiFetch(`${app.dataset.api}?${params}`, { silent: true });
    renderResults(res.data);
  } catch (e) {
    renderError();
  } finally {
    setLoading(submit, false);
    results.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

app.querySelectorAll('[data-model]').forEach((b) => b.addEventListener('click', () => setModel(b.dataset.model)));
app.querySelectorAll('[data-category]').forEach((b) => b.addEventListener('click', () => setCategory(b.dataset.category)));
select.addEventListener('change', () => setModel(select.value));
submit.addEventListener('click', lookup);
app.querySelector('[data-model-search]').addEventListener('input', (e) => {
  const q = e.target.value.trim().toLowerCase().replace(/\s+/g, '');
  app.querySelectorAll('[data-model]').forEach((b) => {
    b.hidden = q && !b.dataset.name.toLowerCase().replace(/\s+/g, '').includes(q);
  });
  app.querySelectorAll('[data-model-group]').forEach((g) => {
    g.hidden = ![...g.querySelectorAll('[data-model]')].some((b) => !b.hidden);
  });
});

const params = new URLSearchParams(location.search);
if (params.get('category')) setCategory(params.get('category'));
if (params.get('model')) {
  setModel(params.get('model'));
  if (state.model) lookup();
} else if (localStorage.getItem('iparts_my_model')) {
  setModel(localStorage.getItem('iparts_my_model'));
}
