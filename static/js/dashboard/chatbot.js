// Trang cấu hình chatbot (Admin): trình sửa câu hỏi gợi ý (thêm/xóa/kéo thả) + kiểm tra kết nối Gemini.
import { apiFetch } from '../core/api.js';
import { setLoading } from '../core/utils.js';

const MAX_SUGGESTIONS = 10;

function initSuggestions() {
  const list = document.querySelector('[data-sugg-list]');
  const store = document.querySelector('[data-sugg-store]');
  const addBtn = document.querySelector('[data-sugg-add]');
  if (!list || !store) return;

  const sync = () => {
    store.value = [...list.querySelectorAll('input')].map((i) => i.value.trim()).filter(Boolean).join('\n');
    if (addBtn) addBtn.disabled = list.children.length >= MAX_SUGGESTIONS;
    store.dispatchEvent(new Event('input', { bubbles: true }));
  };

  const addRow = (text = '', focus = false) => {
    const li = document.createElement('li');
    li.className = 'flex items-center gap-2 rounded-lg border border-border bg-white p-1.5';
    li.draggable = true;
    li.innerHTML = `<span class="cursor-grab select-none px-1 text-muted" title="Kéo để sắp xếp">⋮⋮</span>
      <input type="text" maxlength="120" class="form-input flex-1 py-1.5" placeholder="Ví dụ: Pin iPhone 13 giá bao nhiêu?" aria-label="Câu hỏi gợi ý">
      <button type="button" class="btn-ghost btn-sm text-danger" aria-label="Xóa câu này">✕</button>`;
    const input = li.querySelector('input');
    input.value = text;
    input.addEventListener('input', sync);
    li.querySelector('button').addEventListener('click', () => { li.remove(); sync(); });
    li.addEventListener('dragstart', () => li.classList.add('opacity-50'));
    li.addEventListener('dragend', () => { li.classList.remove('opacity-50'); sync(); });
    list.appendChild(li);
    if (focus) input.focus();
  };

  list.addEventListener('dragover', (e) => {
    e.preventDefault();
    const dragging = list.querySelector('.opacity-50');
    if (!dragging) return;
    const after = [...list.children].find((el) => el !== dragging && e.clientY < el.getBoundingClientRect().top + el.offsetHeight / 2);
    list.insertBefore(dragging, after || null);
  });

  store.value.split('\n').map((s) => s.trim()).filter(Boolean).forEach((q) => addRow(q));
  if (!list.children.length) addRow();
  addBtn?.addEventListener('click', () => { if (list.children.length < MAX_SUGGESTIONS) { addRow('', true); sync(); } });
  sync();
}

function initGeminiTest() {
  const btn = document.querySelector('[data-test-url]');
  btn?.addEventListener('click', async () => {
    const out = document.querySelector('[data-test-result]');
    setLoading(btn, true);
    out.textContent = 'Đang kiểm tra...';
    try {
      const res = await apiFetch(btn.dataset.testUrl, { method: 'POST', silent: true });
      out.textContent = res.message;
      out.className = 'mt-2 text-xs text-success';
    } catch (e) {
      out.textContent = e?.data?.message || 'Không kiểm tra được.';
      out.className = 'mt-2 text-xs text-danger';
    } finally {
      setLoading(btn, false);
    }
  });
}

initSuggestions();
initGeminiTest();
