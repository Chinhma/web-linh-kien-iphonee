// Checkout: chọn địa chỉ đã lưu, cập nhật phí ship/tổng tiền (chỉ để xem), validate nhanh, chống bấm 2 lần.
import { toast } from '../core/toast.js';
import { formatVnd, setLoading } from '../core/utils.js';
import { initAddressPicker } from '../core/address-picker.js';

const form = document.querySelector('[data-checkout-form]');
const data = JSON.parse(document.getElementById('checkout-data').textContent);
const PHONE = /^(0|\+84)(3|5|7|8|9)\d{8}$/;
const picker = initAddressPicker(form.querySelector('[data-address-picker]'));

function updateTotal() {
  const method = form.querySelector('input[name="shipping_method"]:checked')?.value || 'standard';
  const fee = data.fees[method] || 0;
  form.querySelector('[data-shipping-fee]').textContent = fee ? formatVnd(fee) : 'Miễn phí';
  form.querySelector('[data-grand-total]').textContent = formatVnd(data.subtotal - data.discount + fee);
}

form.querySelectorAll('input[name="shipping_method"]').forEach((r) => r.addEventListener('change', updateTotal));
updateTotal();

form.querySelectorAll('input[name="address_choice"]').forEach((radio) => radio.addEventListener('change', () => {
  if (radio.value === 'new') {
    ['recipient_name', 'recipient_phone', 'street_address'].forEach((n) => { form[n].value = ''; });
    picker.clear();
    form.recipient_name.focus();
    return;
  }
  const addr = JSON.parse(radio.dataset.address);
  ['recipient_name', 'recipient_phone', 'street_address'].forEach((k) => { form[k].value = addr[k] || ''; });
  picker.set(addr.province_code, addr.ward_code);
}));

function fieldError(name, message) {
  const input = form[name];
  const wrap = input.closest('div');
  wrap.classList.toggle('is-invalid', !!message);
  let p = wrap.querySelector('[data-client-error]');
  if (!p) {
    p = document.createElement('p');
    p.className = 'form-error';
    p.dataset.clientError = '1';
    wrap.appendChild(p);
  }
  p.textContent = message || '';
}

form.addEventListener('submit', (e) => {
  if (form.dataset.submitting) {
    e.preventDefault();
    return;
  }
  let ok = true;
  const required = { recipient_name: 'Vui lòng nhập họ tên', street_address: 'Vui lòng nhập số nhà, tên đường' };
  Object.entries(required).forEach(([name, msg]) => {
    const bad = !form[name].value.trim();
    fieldError(name, bad ? msg : '');
    if (bad) ok = false;
  });
  const phoneBad = !PHONE.test(form.recipient_phone.value.replace(/\s/g, ''));
  fieldError('recipient_phone', phoneBad ? 'Số điện thoại không hợp lệ' : '');
  const emailBad = !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.recipient_email.value.trim());
  fieldError('recipient_email', emailBad ? 'Email không hợp lệ' : '');
  if (phoneBad || emailBad) ok = false;
  ['province_code', 'ward_code'].forEach((name) => {
    const combo = form.querySelector(`[data-combo="${name === 'province_code' ? 'province' : 'ward'}"]`);
    const bad = !form[name].value;
    combo.classList.toggle('is-invalid', bad);
    let p = combo.querySelector('[data-client-error]');
    if (!p) {
      p = document.createElement('p');
      p.className = 'form-error';
      p.dataset.clientError = '1';
      combo.appendChild(p);
    }
    p.textContent = bad ? (name === 'province_code' ? 'Vui lòng chọn Tỉnh/Thành phố' : 'Vui lòng chọn Phường/Xã') : '';
    if (bad) ok = false;
  });
  if (!form.agree.checked) {
    toast('Bạn cần đồng ý với điều khoản mua hàng.', 'warning');
    ok = false;
  }
  if (!form.querySelector('input[name="payment_method"]:checked')) {
    toast('Vui lòng chọn phương thức thanh toán.', 'warning');
    ok = false;
  }
  if (!ok) {
    e.preventDefault();
    form.querySelector('.is-invalid input:not([type=hidden]), .is-invalid button')?.focus();
    return;
  }
  form.dataset.submitting = '1';
  setLoading(form.querySelector('[data-place-order]'), true);
});
