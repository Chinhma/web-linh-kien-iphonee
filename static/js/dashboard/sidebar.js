// Sidebar Admin: accordion mục con, nhớ trạng thái mở/đóng + thu gọn trong localStorage, drawer trên mobile.
const OPEN_KEY = 'iparts_admin_open_menus';
const COLLAPSE_KEY = 'iparts_admin_sidebar_collapsed';

export function initSidebar() {
  const sidebar = document.getElementById('admin-sidebar');
  const main = document.getElementById('admin-main');
  const backdrop = document.getElementById('sidebar-backdrop');
  if (!sidebar) return;
  const isDesktop = () => window.matchMedia('(min-width: 1024px)').matches;
  let saved = [];
  try { saved = JSON.parse(localStorage.getItem(OPEN_KEY) || '[]'); } catch (e) { saved = []; }

  const setOpen = (parent, open, animate = true) => {
    const panel = parent.querySelector('[data-side-children]');
    parent.classList.toggle('is-open', open);
    parent.querySelector('[data-side-toggle]').setAttribute('aria-expanded', String(open));
    if (!animate) panel.style.transition = 'none';
    panel.style.maxHeight = open ? `${panel.scrollHeight}px` : '0px';
    if (!animate) requestAnimationFrame(() => { panel.style.transition = ''; });
  };
  const persist = () => {
    const open = [...sidebar.querySelectorAll('[data-side-parent].is-open')].map((p) => p.dataset.sideParent);
    localStorage.setItem(OPEN_KEY, JSON.stringify(open));
  };

  sidebar.querySelectorAll('[data-side-parent]').forEach((parent) => {
    // Mục cha của trang đang mở luôn mở sẵn; các mục khác theo trạng thái đã lưu
    const open = parent.hasAttribute('data-open-initial') || saved.includes(parent.dataset.sideParent);
    setOpen(parent, open, false);
    parent.querySelector('[data-side-toggle]').addEventListener('click', () => {
      if (sidebar.classList.contains('is-collapsed')) return; // Thu gọn: dùng menu nổi khi hover
      setOpen(parent, !parent.classList.contains('is-open'));
      persist();
    });
  });

  const setCollapsed = (collapsed) => {
    sidebar.classList.toggle('is-collapsed', collapsed);
    main.classList.toggle('is-collapsed', collapsed);
    localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0');
  };
  if (localStorage.getItem(COLLAPSE_KEY) === '1' && isDesktop()) setCollapsed(true);

  const openDrawer = () => {
    sidebar.classList.remove('-translate-x-full', 'is-collapsed');
    backdrop.hidden = false;
    document.body.classList.add('overflow-hidden');
  };
  const closeDrawer = () => {
    sidebar.classList.add('-translate-x-full');
    backdrop.hidden = true;
    document.body.classList.remove('overflow-hidden');
  };
  document.querySelector('[data-sidebar-toggle]')?.addEventListener('click', () => {
    if (isDesktop()) setCollapsed(!sidebar.classList.contains('is-collapsed'));
    else if (sidebar.classList.contains('-translate-x-full')) openDrawer();
    else closeDrawer();
  });
  sidebar.querySelector('[data-sidebar-collapse]')?.addEventListener('click', () => {
    if (isDesktop()) setCollapsed(true);
    else closeDrawer();
  });
  backdrop.addEventListener('click', closeDrawer);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !backdrop.hidden) closeDrawer(); });
}
