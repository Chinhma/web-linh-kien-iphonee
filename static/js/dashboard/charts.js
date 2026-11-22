// Biểu đồ Dashboard (Chart.js) – dữ liệu thật từ API /quan-tri/api/stats/... (chỉ staff).
import { apiFetch } from '../core/api.js';
import { openModal } from '../core/modal.js';
import { el, formatVnd } from '../core/utils.js';

const { Chart } = window;
const root = document.querySelector('[data-charts]');
const charts = {};
const PALETTE = ['#2563EB', '#16A34A', '#F59E0B', '#DC2626', '#7C3AED', '#0891B2', '#DB2777', '#65A30D', '#64748B', '#EA580C'];
Chart.defaults.font.family = '"Be Vietnam Pro", Inter, system-ui, sans-serif';
Chart.defaults.color = '#64748B';

// Trục Y dạng "1,2tr"
const short = (v) => {
  if (Math.abs(v) >= 1e9) return `${(v / 1e9).toFixed(1).replace('.', ',')} tỷ`;
  if (Math.abs(v) >= 1e6) return `${(v / 1e6).toFixed(1).replace('.', ',')}tr`;
  if (Math.abs(v) >= 1e3) return `${Math.round(v / 1e3)}k`;
  return v;
};

function wrapOf(kind) { return root.querySelector(`[data-chart-wrap="${kind}"]`); }

function setEmpty(kind, isEmpty) {
  const wrap = wrapOf(kind);
  wrap.querySelector('[data-skeleton]')?.remove();
  wrap.querySelector('[data-empty]')?.remove();
  wrap.querySelector('canvas').hidden = isEmpty;
  if (isEmpty) {
    const note = el('div', 'absolute inset-0 flex flex-col items-center justify-center text-sm text-muted', 'Chưa có dữ liệu trong kỳ này');
    note.dataset.empty = '1';
    wrap.appendChild(note);
  }
}

function draw(kind, config) {
  charts[kind]?.destroy();
  charts[kind] = new Chart(wrapOf(kind).querySelector('canvas'), config);
}

async function load(kind, extra = '') {
  try {
    return (await apiFetch(`/quan-tri/api/stats/${kind}/?${root.dataset.query}${extra}`, { silent: true })).data;
  } catch (e) {
    const wrap = wrapOf(kind);
    wrap.querySelector('[data-skeleton]')?.remove();
    wrap.appendChild(el('div', 'absolute inset-0 flex items-center justify-center text-sm text-danger', 'Không tải được dữ liệu biểu đồ'));
    return null;
  }
}

async function trend(period) {
  const d = await load('revenue-trend', `&period=${period}`);
  if (!d) return;
  setEmpty('revenue-trend', !d.datasets[0].data.some((v) => v > 0));
  draw('revenue-trend', {
    type: 'line',
    data: { labels: d.labels, datasets: [{ label: 'Doanh thu', data: d.datasets[0].data, borderColor: '#2563EB', backgroundColor: 'rgba(37,99,235,.14)', fill: true, tension: 0.35, pointRadius: 3 }] },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false },
      tooltip: { callbacks: { label: (c) => `${formatVnd(c.raw)} · ${d.orders[c.dataIndex]} đơn` } } },
      scales: { y: { beginAtZero: true, ticks: { callback: short } }, x: { grid: { display: false } } } },
  });
}

async function productsByCategory() {
  const d = await load('products-by-category');
  if (!d) return;
  setEmpty('products-by-category', !d.total);
  const center = wrapOf('products-by-category').querySelector('[data-doughnut-center]');
  center.hidden = !d.total;
  center.querySelector('[data-center-value]').textContent = d.total;
  draw('products-by-category', {
    type: 'doughnut',
    data: { labels: d.labels, datasets: [{ data: d.datasets[0].data, backgroundColor: PALETTE, borderWidth: 2 }] },
    options: {
      maintainAspectRatio: false, cutout: '68%',
      plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, generateLabels: (chart) => chart.data.labels.map((l, i) => ({
        text: `${l} (${chart.data.datasets[0].data[i]} · ${Math.round(chart.data.datasets[0].data[i] * 100 / d.total)}%)`,
        fillStyle: PALETTE[i % PALETTE.length], strokeStyle: '#fff', index: i })) } },
        tooltip: { callbacks: { label: (c) => `${c.raw} sản phẩm (${Math.round(c.raw * 100 / d.total)}%)` } } },
      onClick: (_e, elements) => { if (elements.length) window.location.href = `/quan-tri/san-pham/?category=${d.slugs[elements[0].index]}`; },
      onHover: (e, elements) => { e.native.target.style.cursor = elements.length ? 'pointer' : 'default'; },
    },
  });
}

async function revenueByCategory() {
  const d = await load('revenue-by-category');
  if (!d) return;
  const total = d.datasets[0].data.reduce((a, b) => a + b, 0);
  setEmpty('revenue-by-category', !total);
  draw('revenue-by-category', {
    type: 'doughnut',
    data: { labels: d.labels, datasets: [{ data: d.datasets[0].data, backgroundColor: PALETTE, borderWidth: 2 }] },
    options: { maintainAspectRatio: false, cutout: '60%', plugins: { legend: { position: 'bottom', labels: { boxWidth: 10 } },
      tooltip: { callbacks: { label: (c) => `${formatVnd(c.raw)} (${total ? (c.raw * 100 / total).toFixed(1) : 0}%)` } } } },
  });
}

async function topProducts() {
  const d = await load('top-products', '&limit=5');
  if (!d) return;
  setEmpty('top-products', !d.labels.length);
  draw('top-products', {
    type: 'bar',
    data: { labels: d.labels, datasets: [{ label: 'Số lượng bán', data: d.datasets[0].data, backgroundColor: '#16A34A', borderRadius: 6 }] },
    options: { indexAxis: 'y', maintainAspectRatio: false, plugins: { legend: { display: false },
      tooltip: { callbacks: { label: (c) => `${c.raw} sản phẩm · doanh thu ${formatVnd(d.revenue[c.dataIndex])}` } } },
      scales: { x: { beginAtZero: true, ticks: { precision: 0 } }, y: { grid: { display: false } } } },
  });
}

async function ordersByStatus() {
  const d = await load('orders-by-status');
  if (!d) return;
  setEmpty('orders-by-status', !d.datasets[0].data.some((v) => v > 0));
  draw('orders-by-status', {
    type: 'bar',
    data: { labels: d.labels, datasets: [{ label: 'Số đơn', data: d.datasets[0].data, backgroundColor: d.datasets[0].backgroundColor, borderRadius: 6 }] },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } }, x: { grid: { display: false } } } },
  });
}

if (root) {
  trend('7d');
  productsByCategory();
  revenueByCategory();
  topProducts();
  ordersByStatus();
  document.querySelectorAll('[data-trend-tabs] [data-period]').forEach((b) => b.addEventListener('click', () => {
    document.querySelectorAll('[data-trend-tabs] [data-period]').forEach((x) => x.classList.toggle('is-active', x === b));
    trend(b.dataset.period);
  }));
}

// Bộ lọc thời gian: chọn "Tùy chọn" mới hiện ô ngày
const rangeSelect = document.querySelector('[data-range-select]');
rangeSelect?.addEventListener('change', () => {
  const custom = rangeSelect.value === 'custom';
  document.querySelector('[data-custom-range]').classList.toggle('hidden', !custom);
  if (!custom) rangeSelect.form.requestSubmit();
});

// Nhập kho nhanh từ bảng sắp hết hàng
document.querySelectorAll('[data-quick-import]').forEach((b) => b.addEventListener('click', () => {
  document.querySelector('[data-qi-product]').value = b.dataset.quickImport;
  document.querySelector('[data-qi-name]').textContent = b.dataset.name;
  document.querySelector('[data-qi-cost]').value = b.dataset.cost;
  openModal('quick-import-modal');
}));
