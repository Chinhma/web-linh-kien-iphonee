// Xem trước ảnh đại diện trước khi lưu (kiểm tra nhanh dung lượng ≤ 5 MB).
import { toast } from '../core/toast.js';

const input = document.querySelector('input[name="avatar"]');
const preview = document.querySelector('[data-avatar-preview]');
input?.classList.add('sr-only');
input?.addEventListener('change', () => {
  const file = input.files[0];
  if (!file) return;
  if (file.size > 5 * 1024 * 1024) {
    toast('Ảnh vượt quá 5 MB.', 'error');
    input.value = '';
    return;
  }
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    toast('Chỉ chấp nhận ảnh JPG, PNG hoặc WEBP.', 'error');
    input.value = '';
    return;
  }
  preview.src = URL.createObjectURL(file);
});
