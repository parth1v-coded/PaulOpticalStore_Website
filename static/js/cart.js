// Shopping cart: kept in the browser (localStorage), shown in a slide-over drawer.
// There is no payment system: "Place order request" sends the order as a message to the shop (it appears in /admin) and the shop calls to confirm.
import { $, el, money, syncLayers } from './api.js';

const KEY = 'po_cart_v1';
let mem = [];                                   // fallback when localStorage is blocked (private mode etc.)
const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || []; } catch { return mem; } };
const save = (items) => { mem = items; try { localStorage.setItem(KEY, JSON.stringify(items)); } catch { /* keep in memory */ } update(); };

export const cart = {
  items: load,
  count: () => load().reduce((n, i) => n + i.qty, 0),
  total: () => load().reduce((n, i) => n + i.qty * i.unit, 0),
  /** item: {id, name, image, unit, qty, label, stock}. Same product + same options merges into one line; a line can't
   *  exceed 10 or the product's stock. Returns true if the quantity had to be capped. */
  add(item) {
    const items = load(), key = `${item.id}|${item.label}`, hit = items.find((i) => i.key === key), cap = Math.min(10, item.stock || 10);
    const want = (hit ? hit.qty : 0) + item.qty;
    if (hit) hit.qty = Math.min(cap, want); else items.push({ ...item, key, qty: Math.min(cap, want) });
    save(items);
    return want > cap;
  },
  setQty(key, qty) { save(load().map((i) => (i.key === key ? { ...i, qty: Math.max(1, Math.min(Math.min(10, i.stock || 10), qty)) } : i))); },
  remove(key) { save(load().filter((i) => i.key !== key)); },
  clear() { save([]); },
};

function update() {
  const n = cart.count(), badge = $('#cartCount');
  badge.textContent = n; badge.hidden = n === 0;
  $('#cartBtn').setAttribute('aria-label', `Open cart, ${n} item${n === 1 ? '' : 's'}`);
  if (!$('#cart').hidden) render();
  dispatchEvent(new Event('cart:change'));
}

let step = 'cart', note = '';                   // 'cart' | 'checkout' | 'done'
let opener = null;

export function openCart(startAtCheckout = false) {
  opener = document.activeElement;
  step = startAtCheckout && cart.count() ? 'checkout' : 'cart'; note = '';
  $('#cart').hidden = false; syncLayers();
  render();
  $('#cart .cart-close').focus();
}

export function closeCart() {
  $('#cart').hidden = true; syncLayers();
  opener?.focus?.();
}

function render() {
  const root = $('#cart'), items = cart.items();
  const head = el('header', {}, el('h2', {}, step === 'checkout' ? 'Checkout' : step === 'done' ? 'Thank you' : `Your cart (${cart.count()})`),
    el('button', { class: 'cart-close', 'aria-label': 'Close cart', onclick: closeCart }, '×'));
  if (step === 'done') {
    root.replaceChildren(head, el('div', { class: 'cart-done' }, el('p', { class: 'big' }, '✓ Order request sent'), el('p', {}, note),
      el('button', { class: 'btn btn-navy', onclick: closeCart }, 'Continue shopping')));
    return;
  }
  if (!items.length) {
    root.replaceChildren(head, el('div', { class: 'cart-empty' }, el('p', {}, 'Your cart is empty.'), el('button', { class: 'btn btn-navy', onclick: closeCart }, 'Keep browsing')));
    return;
  }
  const list = el('ul', { class: 'cart-list' }, items.map((i) => el('li', {},
    el('img', { src: i.image, alt: '', width: 72, height: 72 }),
    el('div', { class: 'cl-info' }, el('strong', {}, i.name), el('span', {}, i.label || ' '),
      step === 'cart' && el('div', { class: 'qty sm' },
        el('button', { 'aria-label': `Fewer ${i.name}`, onclick: () => cart.setQty(i.key, i.qty - 1), disabled: i.qty <= 1 }, '−'), el('output', {}, i.qty),
        el('button', { 'aria-label': `More ${i.name}`, onclick: () => cart.setQty(i.key, i.qty + 1), disabled: i.qty >= 10 }, '+'),
        el('button', { class: 'linklike dark', onclick: () => cart.remove(i.key) }, 'Remove')),
      step === 'checkout' && el('span', {}, `Qty ${i.qty}`)),
    el('div', { class: 'cl-price' }, money(i.qty * i.unit)))));
  const total = el('div', { class: 'cart-total' }, el('span', {}, 'Total'), el('strong', {}, money(cart.total())));
  if (step === 'cart') {
    root.replaceChildren(head, list, el('footer', {}, total,
      el('p', { class: 'fine-dark' }, 'Demo store: no payment is taken. Checkout sends an order request and we call you to confirm.'),
      el('button', { class: 'btn btn-gold', onclick: () => { step = 'checkout'; render(); } }, 'Checkout'),
      el('button', { class: 'btn btn-ghost', onclick: () => cart.clear() }, 'Empty cart')));
    return;
  }
  const status = el('p', { class: 'form-status', role: 'status' }, note);
  const form = el('form', { class: 'cart-form', novalidate: true, onsubmit: async (e) => {
    e.preventDefault();
    const name = form.name.value.trim(), phone = form.phone.value.trim();
    if (!name || !phone) { status.textContent = 'Please enter your name and phone number.'; status.className = 'form-status err'; return; }
    const lines = cart.items().map((i) => `- ${i.qty} x ${i.name}${i.label ? ` (${i.label})` : ''} @ ${money(i.unit)}`);
    const message = `ORDER REQUEST\n${lines.join('\n')}\nTotal: ${money(cart.total())}`;   // server accepts up to 2000 chars: ~20 cart lines
    const btn = form.querySelector('button[type=submit]'); btn.disabled = true; status.textContent = 'Sending…'; status.className = 'form-status';
    try {
      const res = await fetch('/api/messages', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, phone, message }) });
      const out = await res.json().catch(() => ({}));
      if (!res.ok) { status.textContent = out.error || 'Something went wrong. Please try again.'; status.className = 'form-status err'; btn.disabled = false; return; }
      cart.clear(); step = 'done'; note = `Thanks ${name}! We'll call ${phone} shortly to confirm your order. (Demo store: nothing was charged.)`; render();
    } catch { status.textContent = 'Could not reach the server. Please try again.'; status.className = 'form-status err'; btn.disabled = false; }
  } },
    el('label', {}, 'Your name', el('input', { name: 'name', required: true, maxlength: 100, autocomplete: 'name' })),
    el('label', {}, 'Phone number', el('input', { name: 'phone', type: 'tel', required: true, maxlength: 30, autocomplete: 'tel' })),
    status,
    el('button', { class: 'btn btn-gold', type: 'submit' }, `Place order request · ${money(cart.total())}`),
    el('button', { class: 'btn btn-ghost', type: 'button', onclick: () => { step = 'cart'; note = ''; render(); } }, '← Back to cart'),
    el('p', { class: 'fine-dark' }, 'Demo store: no payment is taken. We will call you to confirm.'));
  root.replaceChildren(head, list, total, form);
  form.name.focus();
}

export function initCart() {
  $('#cartBtn').addEventListener('click', () => openCart());
  // Escape closes only the top-most layer: stop the event here so the product screen underneath doesn't also close
  addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('#cart').hidden) { e.stopImmediatePropagation(); closeCart(); } });
  update();
}
