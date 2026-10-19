// Tiny helpers shared by every module.
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} -> ${res.status}`);
  return res.json();
}

// Change the currency for the whole shop here.
const fmt = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 0, maximumFractionDigits: 0 });
export const money = (n) => fmt.format(n);

/** Call after opening or closing the product screen, live try-on or cart. While one is open, everything behind it is made
 *  `inert` (can't be tabbed to or clicked by assistive tech) and the page can't scroll; a screen under another one is inert too. */
export function syncLayers() {
  const open = (id) => !document.getElementById(id).hidden;
  const pdp = open('pdp'), live = open('live'), cart = open('cart'), any = pdp || live || cart;
  document.querySelectorAll('#header, main, footer, #chatOpen, #chat, .skip').forEach((e) => { e.inert = any; });
  document.getElementById('pdp').inert = live || cart;
  document.getElementById('live').inert = cart;
  document.body.classList.toggle('no-scroll', any);
}

export const reducedMotion =matchMedia('(prefers-reduced-motion: reduce)').matches;

export function el(tag, attrs = {}, ...kids) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k.startsWith('aria-') && typeof v === 'boolean') { node.setAttribute(k, String(v)); continue; } // aria-* needs "true"/"false", not ""
    if (v === false || v == null) continue;
    if (k === 'class') node.className = v;
    else if (k === 'html') node.innerHTML = v;
    else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? '' : v);
  }
  node.append(...kids.flat().filter((x) => x != null && x !== false));
  return node;
}
