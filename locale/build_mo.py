"""Sinh file dịch tiếng Việt bổ sung cho các chuỗi admin Django còn thiếu.

Chạy: python locale/build_mo.py  (không cần cài gettext). Tạo locale/vi/LC_MESSAGES/django.po và django.mo.
Muốn dịch thêm câu nào: thêm vào SINGLE rồi chạy lại lệnh trên và khởi động lại server.
"""

import struct
from pathlib import Path

OUT = Path(__file__).resolve().parent / 'vi' / 'LC_MESSAGES'

SINGLE = {
    'Show counts': 'Hiện số lượng',
    'Hide counts': 'Ẩn số lượng',
    'By %(filter_title)s': 'Theo %(filter_title)s',
    'Toggle theme (current theme: auto)': 'Đổi giao diện (hiện tại: tự động)',
    'Toggle theme (current theme: light)': 'Đổi giao diện (hiện tại: sáng)',
    'Toggle theme (current theme: dark)': 'Đổi giao diện (hiện tại: tối)',
    'Toggle navigation': 'Ẩn/hiện menu',
    'Skip to main content': 'Bỏ qua tới nội dung chính',
    'Run the selected action': 'Thực hiện thao tác đã chọn',
    'Action:': 'Thao tác:',
    'Go': 'Thực hiện',
    'History': 'Lịch sử',
    'Currently:': 'Hiện tại:',
}
PLURAL = {
    ('Please correct the error below.', 'Please correct the errors below.'): 'Vui lòng sửa lỗi bên dưới.',
}
HEADER = 'Content-Type: text/plain; charset=UTF-8\nLanguage: vi\nPlural-Forms: nplurals=1; plural=0;\n'


def esc(text: str) -> str:
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    entries = {'': HEADER, **SINGLE}
    for (singular, plural), tr in PLURAL.items():
        entries[singular + '\x00' + plural] = tr

    po = ['# Bản dịch bổ sung cho chuỗi admin Django còn thiếu tiếng Việt (sinh bởi locale/build_mo.py).',
          'msgid ""', 'msgstr ""'] + [f'"{esc(line)}\\n"' for line in HEADER.strip().split('\n')] + ['']
    for k, v in SINGLE.items():
        po += [f'msgid "{esc(k)}"', f'msgstr "{esc(v)}"', '']
    for (s, p), tr in PLURAL.items():
        po += [f'msgid "{esc(s)}"', f'msgid_plural "{esc(p)}"', f'msgstr[0] "{esc(tr)}"', '']
    (OUT / 'django.po').write_text('\n'.join(po), encoding='utf-8')

    # Định dạng .mo của GNU gettext
    keys = sorted(entries)
    ids = [k.encode('utf-8') for k in keys]
    strs = [entries[k].encode('utf-8') for k in keys]
    n = len(keys)
    key_table, val_table = 7 * 4, 7 * 4 + n * 8
    data_start = val_table + n * 8
    offsets, blob = [], b''
    for b in ids + strs:
        offsets.append((len(b), data_start + len(blob)))
        blob += b + b'\0'
    out = struct.pack('<7I', 0x950412DE, 0, n, key_table, val_table, 0, 0)
    for length, offset in offsets:
        out += struct.pack('<2I', length, offset)
    (OUT / 'django.mo').write_bytes(out + blob)
    print(f'Đã tạo bản dịch: {n - 1} chuỗi')


if __name__ == '__main__':
    main()
