// Sổ địa chỉ: mở modal thêm/sửa, dùng bộ chọn Tỉnh/Thành -> Phường/Xã (2 cấp).
import { openModal } from '../core/modal.js';
import { initAddressPicker } from '../core/address-picker.js';

const form = document.querySelector('[data-address-form]');
const title = document.querySelector('[data-address-title]');
const picker = initAddressPicker(form.querySelector('[data-address-picker]'));
const FIELDS = ['full_name', 'phone', 'street_address'];

document.querySelector('[data-address-new]')?.addEventListener('click', () => {
  form.reset();
  picker.clear();
  form.action = form.dataset.addAction;
  title.textContent = 'Thêm địa chỉ';
  openModal('address-modal');
});

document.querySelectorAll('[data-address-edit]').forEach((btn) => btn.addEventListener('click', () => {
  const data = JSON.parse(btn.dataset.addressEdit);
  FIELDS.forEach((f) => { form[f].value = data[f] || ''; });
  form.is_default.checked = data.is_default;
  picker.set(data.province_code, data.ward_code);
  form.action = `/tai-khoan/dia-chi/${data.id}/sua/`;
  title.textContent = 'Sửa địa chỉ';
  openModal('address-modal');
}));
