/** Cấu hình Tailwind cho iParts Store – màu theo Design System (Phần 5.2). */
module.exports = {
  content: ['./templates/**/*.html', './**/templates/**/*.html', './static/js/**/*.js', './core/templatetags/*.py'],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: '#2563EB', dark: '#1D4ED8', light: '#DBEAFE' },
        background: '#F8FAFC',
        surface: '#FFFFFF',
        text: '#0F172A',
        muted: '#64748B',
        border: '#E2E8F0',
        success: '#16A34A',
        warning: '#F59E0B',
        danger: '#DC2626',
        'footer-bg': '#0F172A',
      },
      fontFamily: { sans: ['"Be Vietnam Pro"', 'Inter', 'system-ui', 'sans-serif'] },
      borderRadius: { btn: '10px', card: '16px', modal: '20px' },
      boxShadow: {
        card: '0 1px 3px rgba(15,23,42,.06)',
        'card-hover': '0 8px 24px rgba(15,23,42,.08)',
      },
      maxWidth: { container: '1280px' },
    },
  },
  plugins: [],
};
