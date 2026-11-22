// Biểu đồ cho các trang báo cáo: đọc dữ liệu từ json_script #report-chart.
import { formatVnd } from '../core/utils.js';

const node = document.getElementById('report-chart');
const canvas = document.querySelector('[data-report-chart]');
if (node && canvas && window.Chart) {
  const data = JSON.parse(node.textContent);
  const type = canvas.dataset.type || 'bar';
  const palette = ['#2563EB', '#16A34A', '#F59E0B', '#DC2626', '#7C3AED', '#0891B2', '#DB2777', '#65A30D', '#64748B'];
  new window.Chart(canvas, {
    type,
    data: {
      labels: data.labels,
      datasets: [{
        label: canvas.dataset.label || '', data: data.data,
        backgroundColor: type === 'doughnut' ? palette : '#2563EB', borderRadius: type === 'bar' ? 6 : 0,
      }],
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { display: type === 'doughnut', position: 'bottom' }, tooltip: { callbacks: { label: (c) => formatVnd(c.raw) } } },
      scales: type === 'doughnut' ? {} : { y: { beginAtZero: true }, x: { grid: { display: false } } },
    },
  });
}
