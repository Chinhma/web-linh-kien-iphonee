// API của iParts AI Assistant – gọi backend Django (KHÔNG gọi Gemini trực tiếp từ trình duyệt).
import { apiFetch } from '../core/api.js';

export const sendMessage = (message, conversationId) =>
  apiFetch('/api/chatbot/message/', { method: 'POST', body: { message, conversation_id: conversationId }, silent: true });

export const loadHistory = (conversationId) =>
  apiFetch(`/api/chatbot/history/${conversationId ? `?conversation_id=${conversationId}` : ''}`, { silent: true });

export const resetConversation = () => apiFetch('/api/chatbot/reset/', { method: 'POST', silent: true });
