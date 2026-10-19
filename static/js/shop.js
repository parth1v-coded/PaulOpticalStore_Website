// Catalogue: category tabs, attribute filters (built from /api/facets), product grid with 3D flip cards.
import { $, el, getJSON, money, reducedMotion } from './api.js';
import { tiltGroup } from './fx.js';
import { openProduct } from './pdp.js';

const LABEL = {
  shape: 'Shape', material: 'Material', size: 'Size', color: 'Colour', rim_type: 'Rim', gender: 'For', lens_tint: 'Lens tint',
  lens_type: 'Lens type', lens_index: 'Index', coating: 'Coating', uv_protection: 'UV protection',
  accessory_type: 'Type', compatibility: 'Fits', volume_ml: 'Volume', formula: 'Formula', scent: 'Scent',
  safe_for: 'Safe for', includes_cloth: 'Includes wipes / cloth',
};
const TAGS = { frames: ['shape', 'material', 'size'], lenses: ['lens_type', 'lens_index', 'coating'],
  accessories: ['accessory_type', 'material', 'color'], sprays: ['volume_ml', 'formula', 'scent'] };
const HIDDEN = new Set(['color_hex', 'lens_width', 'bridge', 'temple']);

const fmtVal = (key, v) => typeof v === 'boolean' ? (v ? 'Yes' : 'No')
  : key === 'lens_index' ? Number(v).toFixed(2) : key === 'volume_ml' ? `${v} ml` : String(v);

const state = { cat: 'all', picked: {}, q: '', sort: '', inStock: false, maxPrice: null, priceRange: null };
let categories = [], seq = 0, onTryOn = () => {};

export async function initShop(opts) {
  onTryOn = opts.onTryOn;
  categories = await getJSON('/api/categories');
  renderTabs();
  tiltGroup($('#grid'), '.card', 7);
  $('#sort').addEventListener('change', (e) => { state.sort = e.target.value; load(); });
  $('#clearEmpty').addEventListener('click', clearFilters);
  $('#filtersToggle').addEventListener('click', () => { const open = $('#filters').classList.toggle('open'); $('#filtersToggle').setAttribute('aria-expanded', open); });
  addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDrawer(); });
  await selectCategory('all');
  return categories;
}

let catSeq = 0;
export async function selectCategory(cat, { scroll = false } = {}) {
  const my = ++catSeq;                                          // if the shopper taps another tab while this one is loading, drop this result
  state.cat = cat; state.picked = {}; state.maxPrice = null; state.priceRange = null;
  document.querySelectorAll('.tab').forEach((t) => t.setAttribute('aria-selected', t.dataset.cat === cat));
  if (cat !== 'all') {
    const { facets, price } = await getJSON(`/api/facets?category=${cat}`);
    if (my !== catSeq) return;
    state.facets = facets; state.priceRange = price; state.maxPrice = price.max;
  } else state.facets = [];
  renderFilters();
  if (scroll) $('#shop').scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth' });
  await load();
}

function renderTabs() {
  const tabs = $('#tabs');
  const total = categories.reduce((n, c) => n + c.count, 0);
  const mk = (key, label, count) => el('button', { class: 'tab', role: 'tab', 'data-cat': key, 'aria-selected': key === 'all', onclick: () => selectCategory(key) }, label, el('small', {}, count));
  tabs.replaceChildren(mk('all', 'All products', total), ...categories.map((c) => mk(c.key, c.label, c.count)));
}

function clearFilters() {
  state.picked = {}; state.q = ''; state.inStock = false; state.maxPrice = state.priceRange?.max ?? null;
  renderFilters(); load();
}

function renderFilters() {
  const root = $('#filters');
  let debounce;
  const search = el('input', { class: 'field', type: 'search', placeholder: 'Search name or brand…', 'aria-label': 'Search products', value: state.q,
    oninput: (e) => { clearTimeout(debounce); debounce = setTimeout(() => { state.q = e.target.value.trim(); load(); }, 250); } });
  const parts = [el('h3', {}, 'Search'), search];

  if (state.cat === 'all') {
    parts.push(el('p', { class: 'tip', style: 'color:var(--muted);margin-top:16px;font-size:.82rem' }, 'Choose a collection above to filter by its own attributes — shape and material for frames, index and coating for lenses, and so on.'));
  }
  for (const f of state.facets) {
    parts.push(el('h3', {}, f.label), el('div', { class: 'chips', role: 'group', 'aria-label': f.label },
      f.options.map((o) => el('label', { class: 'chip' },
        el('input', { type: 'checkbox', checked: !!state.picked[f.key]?.has(o.value), onchange: (e) => togglePick(f.key, o.value, e.target.checked) }),
        el('span', {}, fmtVal(f.key, o.value), el('em', {}, o.count))))));
  }
  if (state.priceRange && state.priceRange.min !== state.priceRange.max) {
    const out = el('output', {}, money(state.maxPrice));
    parts.push(el('h3', {}, 'Max price'),
      el('input', { class: 'range', type: 'range', min: state.priceRange.min, max: state.priceRange.max, step: 1, value: state.maxPrice, 'aria-label': 'Maximum price',
        oninput: (e) => { state.maxPrice = +e.target.value; out.textContent = money(state.maxPrice); clearTimeout(debounce); debounce = setTimeout(load, 150); } }),
      el('div', { class: 'range-out' }, el('span', {}, money(state.priceRange.min)), out));
  }
  parts.push(el('label', { class: 'check' }, el('input', { type: 'checkbox', checked: state.inStock, onchange: (e) => { state.inStock = e.target.checked; load(); } }), 'In stock only'),
    el('button', { class: 'btn btn-ghost btn-sm clear', onclick: clearFilters }, 'Clear filters'),
    el('button', { class: 'btn btn-navy filters-done', onclick: closeDrawer }, 'Show results'));
  root.replaceChildren(...parts);
}

function closeDrawer() { // the filters become a bottom sheet on phones
  $('#filters').classList.remove('open'); $('#filtersToggle').setAttribute('aria-expanded', 'false');
}

function togglePick(key, value, on) {
  const set = (state.picked[key] ??= new Set());
  on ? set.add(value) : set.delete(value);
  if (!set.size) delete state.picked[key];
  load();
}

async function load() {
  const mine = ++seq;
  const p = new URLSearchParams();
  if (state.cat !== 'all') p.set('category', state.cat);
  if (state.q) p.set('q', state.q);
  if (state.sort) p.set('sort', state.sort);
  if (state.inStock) p.set('in_stock', '1');
  if (state.priceRange && state.maxPrice < state.priceRange.max) p.set('max_price', state.maxPrice);
  for (const [k, set] of Object.entries(state.picked)) set.forEach((v) => p.append(k, v));
  let items;
  try { items = await getJSON(`/api/products?${p}`); } catch (e) { $('#count').textContent = 'Could not load products. Is the server running?'; return; }
  if (mine !== seq) return; // a newer request superseded this one
  renderGrid(items);
}

function renderGrid(items) {
  const grid = $('#grid');
  $('#count').textContent = `${items.length} ${items.length === 1 ? 'product' : 'products'}`;
  $('#empty').hidden = items.length > 0;
  const cards = items.map(card);
  grid.replaceChildren(...cards);
  if (window.gsap && !reducedMotion && items.length) {
    // animate the wrappers (not .card, which the 3D tilt owns) and hand control back when done
    gsap.fromTo(cards, { autoAlpha: 0, y: 46, rotateX: -14, transformPerspective: 900 },
      { autoAlpha: 1, y: 0, rotateX: 0, duration: .8, ease: 'power3.out', stagger: { each: .045, from: 'start' }, clearProps: 'all', overwrite: true });
  }
  window.ScrollTrigger?.refresh();
}

function card(p) {
  const tags = (TAGS[p.category] || []).map((k) => el('li', {}, fmtVal(k, p.specs[k])));
  const rows = Object.entries(p.specs).filter(([k]) => !HIDDEN.has(k)).map(([k, v]) => [LABEL[k] || k, fmtVal(k, v)]);
  if (p.category === 'frames') rows.push(['Fit', `${p.specs.lens_width}-${p.specs.bridge}-${p.specs.temple} mm`]);
  const isFrame = p.category === 'frames';
  const tryBtn = (cls) => isFrame && el('button', { class: `btn btn-sm ${cls}`, onclick: () => onTryOn(p) }, 'Try on');
  const badge = p.discount_pct ? el('span', { class: 'badge sale' }, `${p.discount_pct}% off`)
    : p.stock < 10 ? el('span', { class: 'badge low' }, `Only ${p.stock} left`) : p.featured && el('span', { class: 'badge' }, 'Featured');
  // real links (open in a new tab / copy address work); a plain tap opens the detail screen
  const open = (e) => { if (e.metaKey || e.ctrlKey || e.shiftKey || e.button) return; e.preventDefault(); openProduct(p.id); };
  const href = `/product/${p.id}`;

  const front = el('div', { class: 'face front' },
    el('a', { class: 'media', href, 'aria-label': `View ${p.name}`, tabindex: '-1', onclick: open }, badge, el('img', { src: p.image, alt: p.name, loading: 'lazy', decoding: 'async', width: 560, height: 588 })),
    el('div', { class: 'info' },
      el('p', { class: 'brand-line' }, p.brand), el('h3', {}, el('a', { href, onclick: open }, p.name)),
      el('p', { class: 'price' }, money(p.price), p.discount_pct ? el('s', {}, money(p.original_price)) : null),
      el('ul', { class: 'tags' }, tags),
      el('div', { class: 'actions' },
        el('a', { class: 'btn btn-sm btn-navy', href, onclick: open }, 'View details'), tryBtn('btn-ghost-card'),
        el('button', { class: 'btn btn-sm btn-ghost-card flip', 'aria-expanded': 'false', onclick: () => flip(root, true) }, 'Quick specs'))));
  const back = el('div', { class: 'face back', inert: true },
    el('h3', {}, p.name), el('p', {}, p.description),
    el('dl', {}, rows.map(([k, v]) => [el('dt', {}, k), el('dd', {}, v)]).flat()),
    el('p', { class: 'price', style: 'color:var(--gold-2)' }, `${money(p.price)} · SKU ${p.sku}`),
    el('div', { class: 'actions' }, el('button', { class: 'btn btn-sm btn-ghost-light', onclick: () => flip(root, false) }, '← Back'), tryBtn('btn-gold')),
    el('p', { class: 'credit' }, `Photo: ${p.image_credit}`));
  const root = el('div', { class: 'card', 'data-id': p.id }, el('div', { class: 'card-inner' }, front, back));
  return el('li', { class: 'card-wrap' }, root);
}

function flip(card, to) {
  card.classList.toggle('flipped', to);
  const [front, back] = card.querySelectorAll('.face');
  front.inert = to; back.inert = !to; // the hidden side must not be tabbable
  card.querySelector(to ? '.back .btn' : '.front .flip').focus({ preventScroll: true });
}

