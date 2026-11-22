// Hiển thị tin nhắn chatbot. Markdown cơ bản được xử lý SAU KHI escape HTML (chống XSS).
import { escapeHtml, formatVnd, el } from '../core/utils.js';

export function renderMarkdown(text) {
  const lines = escapeHtml(text).split('\n');
  const out = [];
  let inList = false;
  for (const raw of lines) {
    let line = raw.trim()
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\[([^\]]+)\]\((\/[^)\s]*|https?:\/\/[^)\s]+)\)/g, '<a href="$2" class="underline text-primary">$1</a>');
    if (/^[-*•] /.test(line)) {
      if (!inList) { out.push('<ul class="list-disc space-y-1 pl-4">'); inList = true; }
      out.push(`<li>${line.slice(2)}</li>`);
      continue;
    }
    if (inList) { out.push('</ul>'); inList = false; }
    line = line.replace(/^#{1,4} /, '');
    if (line) out.push(`<p>${line}</p>`);
  }
  if (inList) out.push('</ul>');
  return out.join('');
}

function timeLabel(iso) {
  const d = iso ? new Date(iso) : new Date();
  return d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
}

export function userBubble(text, createdAt) {
  const wrap = el('div', 'flex flex-col items-end');
  const bubble = el('div', 'chat-bubble-user whitespace-pre-wrap break-words');
  bubble.textContent = text;
  wrap.append(bubble, el('span', 'mt-1 text-[10px] text-muted', timeLabel(createdAt)));
  return wrap;
}

function productCard(p, actions, isGuest) {
  const card = el('div', 'w-48 shrink-0 overflow-hidden rounded-xl border border-border bg-white');
  const img = el('img', 'h-24 w-full object-cover bg-slate-50');
  img.src = p.image;
  img.alt = '';
  img.loading = 'lazy';
  const body = el('div', 'p-2.5');
  const name = el('a', 'line-clamp-2 text-xs font-semibold hover:text-primary', p.name);
  name.href = p.url;
  const price = el('div', 'mt-1 text-sm font-bold text-primary', formatVnd(p.price));
  if (p.original_price) {
    const old = el('span', 'ml-1 text-[10px] font-normal text-muted line-through', formatVnd(p.original_price));
    price.appendChild(old);
  }
  const dot = p.stock_status === 'in_stock' ? 'bg-success' : p.stock_status === 'low_stock' ? 'bg-warning' : 'bg-danger';
  const stock = el('div', 'mt-1 flex items-center gap-1 text-[11px] text-muted');
  stock.append(el('span', `h-1.5 w-1.5 rounded-full ${dot}`), document.createTextNode(p.stock_label));
  body.append(name, price, stock);
  if (p.compatibility_note) body.appendChild(el('div', 'mt-1 line-clamp-2 text-[10px] italic text-muted', p.compatibility_note));
  const row = el('div', 'mt-2 flex gap-1.5');
  const view = el('a', 'btn-secondary btn-sm flex-1', 'Xem');
  view.href = p.url;
  row.appendChild(view);
  const canAdd = actions.some((a) => a.type === 'add_to_cart' && a.product_id === p.id);
  if (window.IPARTS?.isStaff) {
    const edit = el('a', 'btn-primary btn-sm flex-1', 'Sửa');
    edit.href = `/quan-tri/san-pham/${p.id}/sua/`;
    row.appendChild(edit);
  } else if (canAdd && p.stock_status !== 'out_of_stock') {
    const add = el('button', 'btn-primary btn-sm flex-1', 'Thêm vào giỏ');
    add.type = 'button';
    add.dataset.addToCart = p.id;
    add.dataset.productName = p.name;
    row.appendChild(add);
  } else if (isGuest) {
    const login = el('button', 'btn-primary btn-sm flex-1 text-[11px]', 'Đăng nhập để mua');
    login.type = 'button';
    login.dataset.chatLogin = '1';
    row.appendChild(login);
  }
  body.appendChild(row);
  card.append(img, body);
  return card;
}

export function botBubble(data, { isGuest = false, onSuggestion = null } = {}) {
  const wrap = el('div', 'flex gap-2');
  const avatar = el('img', 'mt-1 h-8 w-8 shrink-0 rounded-full bg-white object-cover');
  avatar.src = '/static/images/brand/chatbot-avatar-sm.png?v=1';
  avatar.alt = '';
  const col = el('div', 'min-w-0 flex-1');
  const bubble = el('div', 'chat-bubble-bot space-y-1.5 break-words');
  bubble.innerHTML = renderMarkdown(data.reply ?? data.content ?? ''); // đã escape trong renderMarkdown
  col.appendChild(bubble);
  const products = data.products || [];
  const actions = data.actions || [];
  if (products.length) {
    const scroller = el('div', 'no-scrollbar mt-2 flex gap-2 overflow-x-auto pb-1');
    products.forEach((p) => scroller.appendChild(productCard(p, actions, isGuest)));
    col.appendChild(scroller);
  }
  actions.filter((a) => a.type === 'open_url' || (a.type === 'login' && !products.length)).forEach((a) => {
    const link = el('a', 'mt-2 inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline', `${a.label} →`);
    link.href = a.type === 'login' ? `${a.url}?next=${encodeURIComponent(location.pathname)}` : a.url;
    col.appendChild(link);
  });
  col.appendChild(el('div', 'mt-1 text-[10px] text-muted', timeLabel(data.created_at)));
  if (onSuggestion && data.suggestions?.length) {
    const chips = el('div', 'mt-2 flex flex-wrap gap-1.5');
    data.suggestions.forEach((s) => {
      const chip = el('button', 'rounded-full border border-primary/30 bg-primary-light/60 px-2.5 py-1 text-[11px] text-primary-dark hover:bg-primary-light', s);
      chip.type = 'button';
      chip.addEventListener('click', () => onSuggestion(s));
      chips.appendChild(chip);
    });
    col.appendChild(chips);
  }
  wrap.append(avatar, col);
  return wrap;
}
