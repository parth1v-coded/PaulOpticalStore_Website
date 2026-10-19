// Contact form: posts name + phone + message to /api/messages, which saves it in SQLite.
import { $ } from './api.js';

export function initContact() {
  const form = $('#contactForm'), status = $('#contactStatus'), btn = form.querySelector('button');
  const say = (msg, kind) => { status.textContent = msg; status.className = `form-status ${kind || ''}`; };
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    if (!data.name.trim() || !data.phone.trim() || !data.message.trim()) return say('Please fill in your name, phone number and message.', 'err');
    btn.disabled = true; say('Sending…');
    try {
      const res = await fetch('/api/messages', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
      const out = await res.json().catch(() => ({}));
      if (!res.ok) return say(out.error || 'Something went wrong. Please try again.', 'err');
      form.reset(); say('Thank you! Your message has been received — we\'ll call you soon.', 'ok');
    } catch { say('Could not reach the server. Please try again.', 'err'); }
    finally { btn.disabled = false; }
  });
}
