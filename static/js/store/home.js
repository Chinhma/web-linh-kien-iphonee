// Trang chủ: slider banner (tự chuyển 5 giây, chấm điều hướng, vuốt trên mobile).
document.querySelectorAll('[data-slider]').forEach((slider) => {
  const track = slider.querySelector('[data-slider-track]');
  const dots = [...slider.querySelectorAll('[data-slider-dots] button')];
  const total = track.children.length;
  if (total < 2) return;
  let index = 0;
  let timer;
  const go = (i) => {
    index = (i + total) % total;
    track.style.transform = `translateX(-${index * 100}%)`;
    dots.forEach((d, n) => d.classList.toggle('is-active', n === index));
  };
  const start = () => {
    clearInterval(timer);
    timer = setInterval(() => go(index + 1), 5000);
  };
  dots.forEach((d, n) => d.addEventListener('click', () => { go(n); start(); }));
  let startX = null;
  track.addEventListener('touchstart', (e) => { startX = e.touches[0].clientX; }, { passive: true });
  track.addEventListener('touchend', (e) => {
    if (startX === null) return;
    const dx = e.changedTouches[0].clientX - startX;
    if (Math.abs(dx) > 40) { go(index + (dx < 0 ? 1 : -1)); start(); }
    startX = null;
  });
  go(0);
  start();
});
