// Pricing chatbot widget. Sends the conversation to /api/chat; the server answers only from pricing.md.
import { $, el } from './api.js';

export function initChat() {
  const box = $('#chat'), log = $('#chatLog'), form = $('#chatForm'), open = $('#chatOpen'), history = [];
  const add = (cls, text) => { const p = el('p', { class: cls }, text); log.append(p); log.scrollTop = log.scrollHeight; return p; };
  const toggle = (show) => { box.hidden = !show; open.hidden = show; open.setAttribute('aria-expanded', show); if (show) form.q.focus(); };
  open.addEventListener('click', () => toggle(true));
  $('#chatClose').addEventListener('click', () => { toggle(false); open.focus(); });
  addEventListener('keydown', (e) => { if (e.key === 'Escape' && !box.hidden) toggle(false); });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const q = form.q.value.trim();
    if (!q) return;
    form.q.value = ''; add('me', q); history.push({ role: 'user', content: q });
    const wait = add('bot', '…'), btn = form.querySelector('button');
    btn.disabled = true;
    try {
      const res = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ messages: history }) });
      const out = await res.json().catch(() => ({}));
      if (!res.ok) { wait.textContent = out.error || 'Something went wrong. Please try again.'; wait.classList.add('err'); history.pop(); }
      else { wait.textContent = out.reply; history.push({ role: 'assistant', content: out.reply }); }
    } catch { wait.textContent = 'Could not reach the server. Please try again.'; wait.classList.add('err'); history.pop(); }
    finally { btn.disabled = false; log.scrollTop = log.scrollHeight; form.q.focus(); }
  });
}
