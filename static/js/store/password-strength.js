// Thanh đo độ mạnh mật khẩu.
const input = document.querySelector('input[data-strength], input[name="new_password1"]');
const bar = document.querySelector('[data-strength-bar]');
const label = document.querySelector('[data-strength-label]');

if (input && bar) {
  const levels = [
    ['w-1/5 bg-danger', 'Rất yếu'],
    ['w-2/5 bg-danger', 'Yếu'],
    ['w-3/5 bg-warning', 'Trung bình'],
    ['w-4/5 bg-success', 'Mạnh'],
    ['w-full bg-success', 'Rất mạnh'],
  ];
  input.addEventListener('input', () => {
    const v = input.value;
    let score = 0;
    if (v.length >= 8) score += 1;
    if (v.length >= 12) score += 1;
    if (/[a-z]/i.test(v) && /\d/.test(v)) score += 1;
    if (/[A-Z]/.test(v) && /[a-z]/.test(v)) score += 1;
    if (/[^A-Za-z0-9]/.test(v)) score += 1;
    const [cls, text] = levels[Math.max(0, Math.min(score, 5) - 1)] || levels[0];
    bar.className = `h-full rounded-full transition-all ${v ? cls : 'w-0'}`;
    if (label) label.textContent = v ? `Độ mạnh: ${text}` : 'Tối thiểu 8 ký tự, có cả chữ và số.';
  });
}
