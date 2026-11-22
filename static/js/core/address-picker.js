// Bộ chọn địa chỉ 2 cấp (sau 01/07/2025): Tỉnh/Thành phố -> Phường/Xã.
// Dữ liệu đọc từ file tĩnh /static/data/vn-address-2025.json (không gọi API ngoài).
// Dùng: <div data-address-picker data-src="..."> ... (xem templates/includes/components/address_picker.html)

let dataPromise = null;

function loadData(src) {
  if (!dataPromise) {
    dataPromise = fetch(src, { credentials: 'same-origin' }).then((r) => {
      if (!r.ok) throw new Error('ADDRESS_DATA');
      return r.json();
    });
  }
  return dataPromise;
}

/** Bỏ dấu + chữ thường: "Thành phố Hà Nội" -> "thanh pho ha noi". */
export function normalize(text) {
  return String(text || '').replace(/đ/g, 'd').replace(/Đ/g, 'D')
    .normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
}

const PREFIX = /^(thanh pho|tinh|phuong|xa|dac khu)\s+/;

class Combo {
  constructor(root, { placeholder, onSelect }) {
    this.root = root;
    this.trigger = root.querySelector('[data-combo-trigger]');
    this.label = root.querySelector('[data-combo-label]');
    this.panel = root.querySelector('[data-combo-panel]');
    this.search = root.querySelector('[data-combo-search]');
    this.list = root.querySelector('[data-combo-list]');
    this.backdrop = root.querySelector('[data-combo-backdrop]');
    this.placeholder = placeholder;
    this.onSelect = onSelect;
    this.items = [];
    this.filtered = [];
    this.active = -1;
    this.value = '';

    this.trigger.addEventListener('click', () => (this.panel.hidden ? this.open() : this.close()));
    this.trigger.addEventListener('keydown', (e) => {
      if (['ArrowDown', 'Enter', ' '].includes(e.key)) {
        e.preventDefault();
        this.open();
      }
    });
    this.search.addEventListener('input', () => this.filter());
    this.search.addEventListener('keydown', (e) => this.onKey(e));
    this.backdrop?.addEventListener('click', () => this.close());
    document.addEventListener('click', (e) => {
      if (!this.panel.hidden && !root.contains(e.target)) this.close();
    });
  }

  setItems(items) {
    this.items = items.map((it) => ({ ...it, key: normalize(it.name), short: normalize(it.name).replace(PREFIX, '') }));
  }

  setDisabled(disabled, hint) {
    this.trigger.disabled = disabled;
    this.trigger.classList.toggle('opacity-60', disabled);
    this.trigger.classList.toggle('cursor-not-allowed', disabled);
    if (disabled) this.setValue('', hint);
  }

  setValue(code, emptyText) {
    const item = this.items.find((it) => it.code === code);
    this.value = item ? item.code : '';
    this.label.textContent = item ? item.name : (emptyText || this.placeholder);
    this.label.classList.toggle('text-muted', !item);
    return item;
  }

  open() {
    if (this.trigger.disabled) return;
    this.panel.hidden = false;
    if (this.backdrop) this.backdrop.hidden = window.innerWidth >= 640;
    this.trigger.setAttribute('aria-expanded', 'true');
    this.search.value = '';
    this.filter();
    const idx = this.filtered.findIndex((it) => it.code === this.value);
    this.highlight(idx >= 0 ? idx : 0, true);
    setTimeout(() => this.search.focus(), 10);
  }

  close(focusTrigger = false) {
    this.panel.hidden = true;
    if (this.backdrop) this.backdrop.hidden = true;
    this.trigger.setAttribute('aria-expanded', 'false');
    if (focusTrigger) this.trigger.focus();
  }

  filter() {
    const q = normalize(this.search.value);
    this.filtered = q ? this.items.filter((it) => it.key.includes(q) || it.short.startsWith(q)) : this.items;
    this.render();
    this.highlight(this.filtered.length ? 0 : -1);
  }

  render() {
    this.list.replaceChildren();
    if (!this.filtered.length) {
      const li = document.createElement('li');
      li.className = 'px-4 py-3 text-sm text-muted';
      li.textContent = 'Không tìm thấy kết quả phù hợp';
      this.list.appendChild(li);
      return;
    }
    this.filtered.forEach((it, i) => {
      const li = document.createElement('li');
      li.setAttribute('role', 'option');
      li.dataset.index = i;
      li.className = 'cursor-pointer px-4 py-2.5 text-sm hover:bg-slate-50';
      li.textContent = it.name;
      if (it.code === this.value) li.classList.add('font-semibold', 'text-primary');
      li.addEventListener('mousedown', (e) => {
        e.preventDefault();
        this.choose(i);
      });
      this.list.appendChild(li);
    });
  }

  highlight(i, scroll = true) {
    this.active = i;
    [...this.list.children].forEach((li, n) => {
      const on = n === i;
      li.classList.toggle('bg-primary-light', on);
      li.setAttribute('aria-selected', String(on));
      if (on && scroll) li.scrollIntoView({ block: 'nearest' });
    });
  }

  onKey(e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      this.highlight(Math.min(this.active + 1, this.filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      this.highlight(Math.max(this.active - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (this.active >= 0) this.choose(this.active);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation(); // Chỉ đóng danh sách, không đóng modal chứa nó
      this.close(true);
    } else if (e.key === 'Tab') {
      this.close();
    }
  }

  choose(i) {
    const item = this.filtered[i];
    if (!item) return;
    this.setValue(item.code);
    this.close(true);
    this.onSelect(item);
  }
}

export function initAddressPicker(root) {
  if (root.addressPicker) return root.addressPicker;
  const provinceInput = root.querySelector('input[name="province_code"]');
  const wardInput = root.querySelector('input[name="ward_code"]');
  let provinces = [];

  const wardCombo = new Combo(root.querySelector('[data-combo="ward"]'), {
    placeholder: 'Chọn Phường/Xã',
    onSelect: (w) => {
      wardInput.value = w.code;
      root.dispatchEvent(new CustomEvent('address:change', { bubbles: true }));
    },
  });

  const setProvince = (code, wardCode = '') => {
    const item = provinceCombo.setValue(code);
    provinceInput.value = item ? item.code : '';
    const p = provinces.find((x) => x.code === provinceInput.value);
    wardCombo.setItems(p ? p.wards : []);
    wardCombo.setDisabled(!p, p ? '' : 'Chọn Tỉnh/Thành phố trước');
    const w = p ? wardCombo.setValue(wardCode) : null;
    wardInput.value = w ? w.code : '';
  };

  const provinceCombo = new Combo(root.querySelector('[data-combo="province"]'), {
    placeholder: 'Chọn Tỉnh/Thành phố',
    onSelect: (p) => {
      // Đổi tỉnh -> xóa phường/xã đã chọn
      setProvince(p.code, '');
      root.dispatchEvent(new CustomEvent('address:change', { bubbles: true }));
      setTimeout(() => wardCombo.open(), 50);
    },
  });

  provinceCombo.setDisabled(true, 'Đang tải dữ liệu...');
  wardCombo.setDisabled(true, 'Chọn Tỉnh/Thành phố trước');

  const api = {
    ready: loadData(root.dataset.src).then((data) => {
      provinces = data;
      provinceCombo.setItems(data);
      provinceCombo.setDisabled(false);
      setProvince(provinceInput.value, wardInput.value);
    }).catch(() => {
      provinceCombo.setDisabled(true, 'Không tải được dữ liệu địa chỉ');
    }),
    set(provinceCode, wardCode) {
      api.ready.then(() => setProvince(provinceCode || '', wardCode || ''));
    },
    clear() { api.set('', ''); },
    get value() { return { province_code: provinceInput.value, ward_code: wardInput.value }; },
  };
  root.addressPicker = api;
  return api;
}

export function initAddressPickers(scope = document) {
  return [...scope.querySelectorAll('[data-address-picker]')].map(initAddressPicker);
}
