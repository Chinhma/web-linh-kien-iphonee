// Django admin – Sản phẩm: tự tính "% giảm" ngay khi gõ Giá bán / Giá khuyến mãi
// (dòng Loại màn và khung Giá chung). Giá KM = giá bán -> 0% (không khuyến mãi); lớn hơn giá bán -> cảnh báo.
(function () {
  const num = (v) => Number(String(v || '').replace(/[^\d]/g, '')) || 0;

  function text(priceRaw, saleRaw) {
    const price = num(priceRaw);
    const sale = num(saleRaw);
    if (!String(saleRaw || '').trim() || !price) return ['—', ''];
    if (sale > price) return ['Giá KM lớn hơn giá bán!', '#DC2626'];
    if (sale === price) return ['0% (không khuyến mãi)', '#64748B'];
    return [`-${Math.round((price - sale) * 100 / price)}%`, '#D70019'];
  }

  function outputFor(prefix, saleInput) {
    if (prefix) {  // Dòng Loại màn: ô "% giảm" có sẵn (readonly)
      return saleInput.closest('.inline-related')?.querySelector('.field-discount .readonly');
    }
    let out = document.getElementById('product-discount-preview');  // Khung Giá chung: thêm nhãn cạnh ô giá KM
    if (!out) {
      out = document.createElement('strong');
      out.id = 'product-discount-preview';
      out.style.marginLeft = '12px';
      saleInput.insertAdjacentElement('afterend', out);
    }
    return out;
  }

  function recalc(prefix) {
    const price = document.querySelector(`[name="${prefix}price"]`);
    const sale = document.querySelector(`[name="${prefix}sale_price"]`);
    if (!price || !sale) return;
    const out = outputFor(prefix, sale);
    if (!out) return;
    const [label, color] = text(price.value, sale.value);
    out.textContent = label;
    out.style.color = color;
    out.style.fontWeight = '700';
  }

  document.addEventListener('input', (e) => {
    const m = (e.target.name || '').match(/^((?:options-\d+-)?)(price|sale_price)$/);
    if (m) recalc(m[1]);
  });
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[name$="sale_price"]').forEach((el) => {
      const m = el.name.match(/^((?:options-\d+-)?)sale_price$/);
      if (m && !m[1].includes('__prefix__')) recalc(m[1]);
    });
  });
})();
