// apiFetch(): gắn CSRF + header AJAX, xử lý 401 (mở Login Required Modal), 429 và lỗi mạng.
import { toast } from './toast.js';
import { openLoginModal } from './modal.js';

export function getCookie(name) {
  const match = document.cookie.match(new RegExp('(^|;\\s*)' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[2]) : '';
}

export async function apiFetch(url, { method = 'GET', body = null, silent = false } = {}) {
  const headers = { 'X-Requested-With': 'XMLHttpRequest', Accept: 'application/json' };
  if (method !== 'GET') headers['X-CSRFToken'] = getCookie('csrftoken');
  if (body && !(body instanceof FormData)) headers['Content-Type'] = 'application/json';
  let response;
  try {
    response = await fetch(url, {
      method,
      headers,
      credentials: 'same-origin',
      body: body ? (body instanceof FormData ? body : JSON.stringify(body)) : null,
    });
  } catch (err) {
    if (!silent) toast('Không thể kết nối máy chủ. Vui lòng kiểm tra mạng và thử lại.', 'error');
    throw err;
  }
  let data = {};
  try { data = await response.json(); } catch (e) { data = { ok: false, message: 'Phản hồi không hợp lệ.' }; }
  if (response.status === 401) {
    openLoginModal();
    throw Object.assign(new Error('LOGIN_REQUIRED'), { data, status: 401 });
  }
  if (response.status === 429) {
    if (!silent) toast(data.message || 'Bạn thao tác hơi nhanh, vui lòng thử lại sau ít phút.', 'warning');
    throw Object.assign(new Error('RATE_LIMITED'), { data, status: 429 });
  }
  if (!response.ok || data.ok === false) {
    if (!silent) toast(data.message || 'Đã có lỗi xảy ra, vui lòng thử lại.', 'error');
    throw Object.assign(new Error(data.code || 'ERROR'), { data, status: response.status });
  }
  return data;
}
