// Widget iParts AI Assistant: mở/đóng, gửi câu hỏi, nạp lại lịch sử, gợi ý câu hỏi.
import { openLoginModal } from '../core/modal.js';
import { refreshIcons } from '../core/utils.js';
import { loadHistory, resetConversation, sendMessage } from './api.js';
import { botBubble, userBubble } from './render.js?v=3';

const STORE_KEY = 'iparts_chat';
const state = { conversationId: null, busy: false, enabled: true, greeting: '', suggestions: [], loaded: false };
const $ = (id) => document.getElementById(id);
const isGuest = !window.IPARTS?.isAuthenticated;

function saveState(extra = {}) {
  const prev = JSON.parse(sessionStorage.getItem(STORE_KEY) || '{}');
  sessionStorage.setItem(STORE_KEY, JSON.stringify({ ...prev, conversationId: state.conversationId, ...extra }));
}

function scrollBottom() {
  const box = $('chat-messages');
  box.scrollTop = box.scrollHeight;
}

function renderWelcome() {
  const box = $('chat-messages');
  box.replaceChildren();
  box.appendChild(botBubble({ reply: state.greeting, suggestions: state.enabled ? state.suggestions : [] }, { isGuest, onSuggestion: ask }));
  if (!state.enabled) {
    const hotline = $('chat-root').dataset.hotline;
    box.appendChild(botBubble({ reply: `iParts AI Assistant đang tạm ngưng. Bạn vui lòng liên hệ hotline **${hotline}** để được hỗ trợ.` }, { isGuest }));
  }
  refreshIcons();
}

function setStatus(enabled, mode) {
  const status = $('chat-status');
  status.replaceChildren();
  const dot = document.createElement('span');
  dot.className = `h-2 w-2 rounded-full ${enabled ? 'bg-green-400' : 'bg-slate-300'}`;
  const text = document.createElement('span');
  text.textContent = enabled ? 'Đang hoạt động' : 'Tạm ngưng';
  status.append(dot, text);
}

async function ensureLoaded() {
  if (state.loaded) return;
  state.loaded = true;
  try {
    const res = await loadHistory(state.conversationId);
    const d = res.data;
    state.enabled = d.enabled;
    state.greeting = d.greeting;
    state.suggestions = d.suggestions || [];
    state.conversationId = d.conversation_id || null;
    setStatus(d.enabled, d.mode);
    renderWelcome();
    const box = $('chat-messages');
    (d.messages || []).forEach((m) => box.appendChild(m.role === 'user' ? userBubble(m.content, m.created_at) : botBubble(m, { isGuest })));
    saveState();
    refreshIcons();
    scrollBottom();
  } catch (e) {
    state.greeting = 'Xin chào! Mình là iParts AI Assistant.';
    renderWelcome();
  }
}

async function ask(text) {
  const message = (text || '').trim();
  if (!message || state.busy || !state.enabled) return;
  const box = $('chat-messages');
  box.appendChild(userBubble(message));
  $('chat-input').value = '';
  onInput();
  scrollBottom();
  state.busy = true;
  $('chat-send').disabled = true;
  $('chat-typing').hidden = false;
  try {
    const res = await sendMessage(message, state.conversationId);
    state.conversationId = res.data.conversation_id;
    saveState();
    setStatus(true, res.data.mode);
    box.appendChild(botBubble(res.data, { isGuest, onSuggestion: ask }));
    if ($('chat-window').hidden) $('chat-unread').hidden = false;
  } catch (err) {
    const msg = err?.data?.message || 'Không thể kết nối iParts AI Assistant lúc này, vui lòng thử lại.';
    box.appendChild(botBubble({ reply: msg }, { isGuest }));
    if (err?.data?.code === 'CHATBOT_DISABLED') { state.enabled = false; setStatus(false); }
  } finally {
    state.busy = false;
    $('chat-typing').hidden = true;
    onInput();
    refreshIcons();
    scrollBottom();
  }
}

function onInput() {
  const input = $('chat-input');
  input.style.height = 'auto';
  input.style.height = `${Math.min(input.scrollHeight, 112)}px`;
  $('chat-count').textContent = `${input.value.length}/1000`;
  $('chat-send').disabled = !input.value.trim() || state.busy || !state.enabled;
}

function openChat() {
  $('chat-window').hidden = false;
  $('chat-unread').hidden = true;
  $('chat-launcher').classList.remove('pulse-ring');
  saveState({ open: true });
  ensureLoaded().then(() => $('chat-input').focus());
}

function closeChat() {
  $('chat-window').hidden = true;
  saveState({ open: false });
}

export function openChatWith(question) {
  openChat();
  ensureLoaded().then(() => ask(question));
}

document.addEventListener('DOMContentLoaded', () => {
  if (!$('chat-root')) return;
  const saved = JSON.parse(sessionStorage.getItem(STORE_KEY) || '{}');
  state.conversationId = saved.conversationId || null;
  if (saved.seen) $('chat-launcher').classList.remove('pulse-ring');
  saveState({ seen: true });
  // Bấm avatar: đang mở chat -> đóng chat; ngược lại bật/tắt bảng "Liên hệ hỗ trợ"
  const menu = $('contact-menu');
  const closeMenu = () => { menu.hidden = true; };
  $('chat-launcher').addEventListener('click', (e) => {
    e.stopPropagation();
    $('chat-launcher').classList.remove('pulse-ring');
    if (!$('chat-window').hidden) {
      closeChat();
      return;
    }
    menu.hidden = !menu.hidden;
  });
  $('contact-menu-close').addEventListener('click', closeMenu);
  $('contact-open-chatbot').addEventListener('click', () => {
    closeMenu();
    openChat();
  });
  menu.querySelectorAll('a').forEach((a) => a.addEventListener('click', closeMenu));
  document.addEventListener('click', (e) => {
    if (!menu.hidden && !menu.contains(e.target)) closeMenu();
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeMenu(); });
  $('chat-close').addEventListener('click', closeChat);
  $('chat-minimize').addEventListener('click', closeChat);
  $('chat-new').addEventListener('click', async () => {
    try { await resetConversation(); } catch (e) { /* bỏ qua */ }
    state.conversationId = null;
    saveState();
    renderWelcome();
  });
  $('chat-input').addEventListener('input', onInput);
  $('chat-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      ask($('chat-input').value);
    }
  });
  $('chat-form').addEventListener('submit', (e) => {
    e.preventDefault();
    ask($('chat-input').value);
  });
  $('chat-messages').addEventListener('click', (e) => {
    if (e.target.closest('[data-chat-login]')) openLoginModal();
  });
  document.querySelectorAll('[data-chat-ask]').forEach((btn) => btn.addEventListener('click', () => openChatWith(btn.dataset.chatAsk)));
  document.querySelectorAll('[data-open-chat]').forEach((btn) => btn.addEventListener('click', openChat));
  if (saved.open) openChat();
});
