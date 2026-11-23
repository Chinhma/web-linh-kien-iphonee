// Biểu đồ đơn giản cho các trang Admin: đọc #chart-data {key: {labels, data}} và vẽ vào <canvas data-chart="key" data-type="line|bar|doughnut">.
import { el, formatVnd } from '../core/utils.js';

const data = JSON.parse(document.getElementById('chart-data')?.textContent || '{}');
const PALETTE = ['#D70019', '#16A34A', '#F59E0B', '#DC2626', '#7C3AED', '#0891B2', '#DB2777', '#65A30D', '#64748B', '#2563EB'];

document.querySelectorAll('canvas[data-chart]').forEach((canvas) => {
  const d = data[canvas.dataset.chart];
  const type = canvas.dataset.type || 'bar';
  if (!d || !d.data.some((v) => v)) {
    canvas.replaceWith(el('div', 'flex h-full items-center justify-center text-sm text-muted', 'Chưa có dữ liệu'));
    return;
  }
  const money = canvas.dataset.money === '1';
  new window.Chart(canvas, {
    type,
    data: {
      labels: d.labels,
      datasets: [{
        label: canvas.dataset.label || '',
        data: d.data,
        backgroundColor: type === 'doughnut' ? PALETTE : (type === 'line' ? 'rgba(215,0,25,.12)' : '#D70019'),
        borderColor: '#D70019',
        fill: type === 'line',
        tension: 0.35,
        borderRadius: type === 'bar' ? 6 : 0,
      }],
    },
    options: {
      maintainAspectRatio: false,
      indexAxis: canvas.dataset.horizontal === '1' ? 'y' : 'x',
      plugins: { legend: { display: type === 'doughnut', position: 'bottom' },
        tooltip: { callbacks: { label: (c) => (money ? formatVnd(c.raw) : String(c.raw)) } } },
      scales: type === 'doughnut' ? {} : { y: { beginAtZero: true, ticks: { precision: 0 } }, x: { grid: { display: false } } },
    },
  });
});
