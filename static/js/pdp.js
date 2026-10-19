// Product detail screen. Sections, in order:
//   1 image carousel  2 core info  3 purchase actions  4 key features  5 virtual try-on  6 customer reviews
// Opens as a full-screen layer over the catalogue at /product/<id> (shareable; the browser Back button closes it).
import { $, el, getJSON, money, reducedMotion, syncLayers } from './api.js';
import { cart, openCart } from './cart.js';
import { openLive } from './live.js';

const WISH_KEY = 'po_wish_v1';
const wished = () => { try { return new Set(JSON.parse(localStorage.getItem(WISH_KEY)) || []); } catch { return new Set(); } };
const setWished = (s) => { try { localStorage.setItem(WISH_KEY, JSON.stringify([...s])); } catch { /* ignore */ } };
const fmtDate = (iso) => new Date(iso + 'T00:00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
const stars = (n) => el('span', { class: 'stars', style: `--r:${n}`, role: 'img', 'aria-label': `${n} out of 5 stars` }, '★★★★★');
const PAGE = 5;

let S = null;            // state of the open product: {p, ci (colour), wi (width), li (lens), qty, pushed, opener}
let R = null;            // reviews state: {sort, stars, items, total, summary}
let io = null;           // IntersectionObserver for the sticky bar
const title0 = document.title;
const root = () => $('#pdp');
const isOpen = () => !root().hidden;

export function initPdp() {
  addEventListener('popstate', route);
  addEventListener('keydown', (e) => { if (e.key === 'Escape' && isOpen() && $('#cart').hidden && $('#live').hidden) closeProduct(); });
  route();
}

function route() {
  const m = location.pathname.match(/^\/product\/(\d+)\/?$/);
  if (m) openProduct(+m[1], { push: false }); else if (isOpen()) hide();
}

export async function openProduct(id, { push = true } = {}) {
  const opener = document.activeElement;
  let p;
  try { p = await getJSON(`/api/products/${id}`); } catch { p = null; }
  if (push) history.pushState({ pdp: id }, '', `/product/${id}`);
  S = { p, ci: 0, wi: 1, li: 0, qty: 1, pushed: push, opener };
  if (p) { S.wi = Math.max(0, (p.options?.widths || []).findIndex((w) => w.lens_width === p.options.default_width)); }
  root().hidden = false; syncLayers();
  p ? render() : renderMissing();
  document.title = p ? `${p.name} — Paul Optical` : title0;
  root().querySelector('.pdp-back').focus({ preventScroll: true });
}

export function closeProduct() {
  if (S?.pushed && history.state?.pdp) history.back(); else { hide(); if (/^\/product\//.test(location.pathname)) history.replaceState(null, '', '/'); }
}

function hide() {
  root().hidden = true; io?.disconnect(); syncLayers();
  document.title = title0;
  S?.opener?.focus?.({ preventScroll: true });
  S = null;
}

function renderMissing() {
  root().replaceChildren(topbar('Product not found'), el('div', { class: 'pdp-scroll' }, el('div', { class: 'pdp-missing' },
    el('p', {}, 'Sorry, we couldn\'t find that product.'), el('button', { class: 'btn btn-navy', onclick: closeProduct }, 'Back to the shop'))));
}

const topbar = (title) => el('header', { class: 'pdp-bar' },
  el('button', { class: 'pdp-back', 'aria-label': 'Back to products', onclick: closeProduct }, el('span', { 'aria-hidden': 'true' }, '←')),
  el('span', { class: 'pdp-bar-title' }, title),
  el('button', { class: 'pdp-bar-cart', 'aria-label': 'Open cart', onclick: () => openCart() }, 'Cart ', el('b', { class: 'pdp-cart-n' }, cart.count())));

// ---------------------------------------------------------------- derived values
const isFrame = () => S.p.category === 'frames';
const opt = () => S.p.options;
const colour = () => opt().colours[S.ci];
const width = () => opt().widths[S.wi];
const lens = () => opt().lenses[S.li];
const unit = () => S.p.price + (isFrame() ? lens().price_delta : 0);
const orig = () => (S.p.original_price && S.p.original_price > S.p.price ? S.p.original_price + (isFrame() ? lens().price_delta : 0) : null);
const label = () => (isFrame() ? `${colour().name}, ${width().label} lens, ${lens().name.replace(' (as shown)', '')}` : '');
const variantUrl = (view) => `${opt().overlay}?view=${view}&color=${colour().hex.slice(1)}&lw=${width().lens_width}` + (view === 'side' ? '' : `&tint=${lens().tint || opt().default_tint}`);

// ---------------------------------------------------------------- render
function render() {
  const { p } = S;
  // sections 1-5 share a grid (gallery sticks beside them on desktop); reviews follow below it
  const scroll = el('div', { class: 'pdp-scroll' },
    el('div', { class: 'pdp-top' }, gallerySection(), infoSection(), buySection(), featuresSection(), tryonSection()), reviewsSection());
  root().replaceChildren(topbar(p.name), scroll, stickyBar());
  scroll.scrollTop = 0;
  watchActions(scroll);
  loadReviews(true);
}

// 1 ---- image carousel
function gallerySection() {
  const p = S.p, slides = [{ kind: 'photo', src: p.image, alt: `${p.name} product photo` }];
  if (isFrame()) slides.push(...[['front', 'front view'], ['side', 'side view'], ['dims', 'measurements']].map(([view, w]) => ({ kind: 'svg', view, src: variantUrl(view), alt: `${p.name}, ${w}` })));
  const track = el('div', { class: 'g-track', tabindex: '0', role: 'group', 'aria-roledescription': 'carousel', 'aria-label': 'Product images, swipe to see more' },
    slides.map((s, i) => el('figure', { class: `g-slide ${s.kind}`, 'aria-label': `Image ${i + 1} of ${slides.length}` },
      el('img', { src: s.src, alt: s.alt, 'data-view': s.view || '', ...(i ? { loading: 'lazy' } : {}), decoding: 'async', draggable: 'false' }))));
  const counter = el('span', { class: 'g-count', 'aria-live': 'polite' }, `1 / ${slides.length}`);
  const dots = slides.map((s, i) => el('button', { class: 'g-dot', 'aria-label': `Show image ${i + 1}`, onclick: () => go(i) }));
  const go = (i) => track.scrollTo({ left: Math.max(0, Math.min(slides.length - 1, i)) * track.clientWidth, behavior: reducedMotion ? 'auto' : 'smooth' });
  const current = () => Math.round(track.scrollLeft / Math.max(1, track.clientWidth));
  const mark = () => { const i = current(); counter.textContent = `${i + 1} / ${slides.length}`; dots.forEach((d, k) => d.setAttribute('aria-current', k === i)); };
  let raf; track.addEventListener('scroll', () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(mark); }, { passive: true });
  track.addEventListener('keydown', (e) => { if (e.key === 'ArrowRight') { go(current() + 1); e.preventDefault(); } if (e.key === 'ArrowLeft') { go(current() - 1); e.preventDefault(); } });
  const multi = slides.length > 1;
  const sec = el('section', { class: 'pdp-gallery', 'aria-label': 'Product images' },
    el('div', { class: 'g-stage' }, track,
      multi && el('button', { class: 'g-arrow prev', 'aria-label': 'Previous image', onclick: () => go(current() - 1) }, '‹'),
      multi && el('button', { class: 'g-arrow next', 'aria-label': 'Next image', onclick: () => go(current() + 1) }, '›'),
      multi && counter, multi && el('div', { class: 'g-dots' }, dots)),
    isFrame() && el('p', { class: 'g-note' }, `Photo shows the ${S.p.options.colours[0].name.toLowerCase()} frame. The drawings update with your colour, size and lens choices.`));
  requestAnimationFrame(mark);
  return sec;
}

const refreshGallery = () => { if (isFrame()) root().querySelectorAll('.g-slide.svg img').forEach((img) => { img.src = variantUrl(img.dataset.view); }); };

// 2 ---- core info
function infoSection() {
  const p = S.p, r = p.rating;
  const low = p.stock > 0 && p.stock < 10;
  return el('section', { class: 'pdp-info' },
    el('p', { class: 'pdp-brand' }, p.brand),
    el('h1', {}, p.name),
    ratingLine(r),
    el('div', { class: 'pdp-price', 'aria-live': 'polite' }, el('strong', { class: 'now', id: 'pdpNow' }), el('s', { class: 'was', id: 'pdpWas' }), el('span', { class: 'off', id: 'pdpOff' })),
    el('p', { class: 'pdp-desc' }, p.description),
    el('p', { class: `pdp-stock ${p.stock === 0 ? 'out' : low ? 'low' : ''}` }, p.stock === 0 ? 'Out of stock' : low ? `Only ${p.stock} left` : 'In stock'),
    p.sku && el('p', { class: 'pdp-sku' }, `SKU ${p.sku}`));
}

/** The star line under the product name. A button (not a #link) so tapping it never touches the URL or the history. */
function ratingLine(r) {
  return r.count
    ? el('button', { class: 'pdp-rating', type: 'button', onclick: () => $('#pdp-reviews').scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth' }) },
      stars(r.average), el('span', {}, ` ${r.average.toFixed(1)} · ${r.count} review${r.count === 1 ? '' : 's'}`))
    : el('p', { class: 'pdp-rating none' }, 'No reviews yet');
}

function refreshPrice() {
  const now = unit(), was = orig();
  $('#pdpNow').textContent = money(now);
  $('#pdpWas').textContent = was ? money(was) : ''; $('#pdpWas').hidden = !was;
  const off = was ? Math.round((1 - now / was) * 100) : 0;
  $('#pdpOff').textContent = off ? `${off}% off` : ''; $('#pdpOff').hidden = !off;
  const sp = $('#stickyPrice'); if (sp) sp.textContent = money(now * S.qty);
  const sl = $('#stickyLabel'); if (sl) sl.textContent = S.qty > 1 ? `Total (${S.qty})` : 'Price';
}

// 3 ---- purchase actions
function buySection() {
  const p = S.p, out = p.stock === 0, maxQty = Math.max(1, Math.min(10, p.stock));
  const groups = [];
  if (isFrame()) {
    const o = opt();
    const colourName = el('span', { class: 'vg-val', id: 'vgColour' }, colour().name);
    groups.push(el('fieldset', { class: 'vg' }, el('legend', {}, 'Colour: ', colourName),
      el('div', { class: 'swatches', role: 'radiogroup', 'aria-label': 'Colour' }, o.colours.map((c, i) => el('button', {
        class: 'swatch', role: 'radio', 'aria-checked': i === S.ci, 'aria-label': c.name, title: c.name, style: `--c:${c.hex}`,
        onclick: (e) => { S.ci = i; colourName.textContent = c.name; pick(e.currentTarget, '.swatch'); changed(); } })))));
    groups.push(el('fieldset', { class: 'vg' }, el('legend', {}, 'Lens width'),
      el('div', { class: 'seg', role: 'radiogroup', 'aria-label': 'Lens width' }, o.widths.map((w, i) => el('button', {
        class: 'seg-b', role: 'radio', 'aria-checked': i === S.wi, onclick: (e) => { S.wi = i; pick(e.currentTarget, '.seg-b'); changed(); } },
        w.label, w.lens_width === o.default_width && el('small', {}, ' as listed'))))));
    groups.push(el('fieldset', { class: 'vg' }, el('legend', {}, 'Lens type'),
      el('div', { class: 'lens-opts', role: 'radiogroup', 'aria-label': 'Lens type' }, o.lenses.map((l, i) => el('button', {
        class: 'lens-b', role: 'radio', 'aria-checked': i === S.li, onclick: (e) => { S.li = i; pick(e.currentTarget, '.lens-b'); changed(); } },
        el('span', {}, l.name), el('small', {}, l.price_delta ? `+${money(l.price_delta)}` : 'Included'))))));
  }
  const qtyOut = el('output', { id: 'qtyOut' }, S.qty);
  const setQty = (n) => { S.qty = Math.max(1, Math.min(maxQty, n)); qtyOut.textContent = S.qty; $('#qtyMinus').disabled = S.qty <= 1; $('#qtyPlus').disabled = S.qty >= maxQty; refreshPrice(); };
  const w = wished(), heart = el('button', { class: 'wish', 'aria-pressed': w.has(p.id), 'aria-label': 'Save to wishlist', onclick: (e) => {
    const s = wished(); s.has(p.id) ? s.delete(p.id) : s.add(p.id); setWished(s);
    e.currentTarget.setAttribute('aria-pressed', s.has(p.id)); toast(s.has(p.id) ? 'Saved to your wishlist' : 'Removed from wishlist'); } }, el('span', { 'aria-hidden': 'true' }, '♥'));
  const add = () => { const capped = cart.add({ id: p.id, name: p.name, image: p.image, unit: unit(), qty: S.qty, label: label(), stock: p.stock }); updateCartN(); return capped; };
  const addBtn = (cls) => el('button', { class: `btn btn-navy big ${cls || ''}`, disabled: out,
    onclick: () => { toast(add() ? `Only ${p.stock} in stock: that's the most you can add` : 'Added to cart', 'View cart', () => openCart()); } }, out ? 'Sold out' : 'Add to Cart');
  const buyBtn = (cls) => el('button', { class: `btn btn-gold big ${cls || ''}`, disabled: out, onclick: () => { add(); openCart(true); } }, 'Buy Now');
  S.buttons = { addBtn, buyBtn };
  const sec = el('section', { class: 'pdp-buy', 'aria-label': 'Choose options and buy' }, ...groups,
    el('div', { class: 'buy-row' },
      el('div', { class: 'qty', role: 'group', 'aria-label': 'Quantity' },
        el('button', { id: 'qtyMinus', 'aria-label': 'Decrease quantity', onclick: () => setQty(S.qty - 1), disabled: true }, '−'), qtyOut,
        el('button', { id: 'qtyPlus', 'aria-label': 'Increase quantity', onclick: () => setQty(S.qty + 1), disabled: maxQty <= 1 }, '+')), heart),
    el('div', { class: 'pdp-actions', id: 'pdpActions' }, addBtn(), buyBtn()));
  requestAnimationFrame(() => { refreshPrice(); });
  return sec;
}

function pick(btn, sel) { btn.parentElement.querySelectorAll(sel).forEach((b) => b.setAttribute('aria-checked', b === btn)); }
function changed() { refreshPrice(); refreshGallery(); }
function updateCartN() { document.querySelectorAll('.pdp-cart-n').forEach((n) => { n.textContent = cart.count(); }); }

let toastTimer;
function toast(msg, actionLabel, action) {
  root().querySelector('.pdp-toast')?.remove();
  const t = el('div', { class: 'pdp-toast', role: 'status' }, msg, actionLabel && el('button', { onclick: () => { t.remove(); action(); } }, actionLabel));
  root().append(t); clearTimeout(toastTimer); toastTimer = setTimeout(() => t.remove(), 4000);
}

// sticky bar: appears once the in-page buttons scroll out of view, so Add to Cart / Buy Now are always reachable
function stickyBar() {
  const out = S.p.stock === 0;
  return el('div', { class: 'pdp-sticky', id: 'pdpSticky', hidden: true },
    el('div', { class: 'sp' }, el('small', { id: 'stickyLabel' }, 'Price'), el('strong', { id: 'stickyPrice' }, money(unit() * S.qty))),
    S.buttons.addBtn('sticky-b'), S.buttons.buyBtn('sticky-b'), out && null);
}

function watchActions(scroll) {
  io?.disconnect();
  io = new IntersectionObserver(([e]) => { $('#pdpSticky').hidden = e.isIntersecting; }, { root: scroll, threshold: 0.01 });
  io.observe($('#pdpActions'));
}

// 4 ---- key features
function featuresSection() {
  return el('section', { class: 'pdp-features', 'aria-labelledby': 'pdp-feat-h' }, el('h2', { id: 'pdp-feat-h' }, 'Key features'),
    el('ul', {}, (S.p.features.length ? S.p.features : ['Details coming soon']).map((f) => el('li', {}, f))));
}

// 5 ---- virtual try-on
function tryonSection() {
  const frame = isFrame();
  return el('section', { class: 'pdp-tryon', 'aria-labelledby': 'pdp-try-h' }, el('h2', { id: 'pdp-try-h' }, 'Virtual try-on'),
    el('p', {}, frame ? 'See how these look on you, live. Your camera stays on your device; nothing is recorded or uploaded.'
      : 'Virtual try-on is for eyewear frames. Pick any frame to try on with your camera, then come back here.'),
    el('button', { class: 'btn btn-gold big', onclick: () => openLive(frame ? { frameId: S.p.id, colourHex: colour().hex, lensWidth: width().lens_width, tint: lens().tint || opt().default_tint } : {}) },
      el('span', { 'aria-hidden': 'true' }, '📷 '), frame ? 'Try On' : 'Try frames on'));
}

// 6 ---- reviews
function reviewsSection() {
  return el('section', { class: 'pdp-reviews', id: 'pdp-reviews', 'aria-labelledby': 'pdp-rev-h' }, el('h2', { id: 'pdp-rev-h' }, 'Customer reviews'),
    el('div', { id: 'revBody' }, el('p', { class: 'muted' }, 'Loading reviews…')));
}

async function loadReviews(reset) {
  const pid = S.p.id;
  if (reset) R = { sort: R?.sort || 'recent', stars: 0, items: [], total: 0, summary: S.p.rating };
  const q = new URLSearchParams({ sort: R.sort, offset: R.items.length, limit: PAGE }); if (R.stars) q.set('stars', R.stars);
  let data;
  try { data = await getJSON(`/api/products/${pid}/reviews?${q}`); } catch { $('#revBody').replaceChildren(el('p', { class: 'err' }, 'Could not load reviews. Please try again later.')); return; }
  if (!S || S.p.id !== pid) return; // user moved on
  R.items.push(...data.items); R.total = data.total; R.summary = data.summary;
  drawReviews();
}

function drawReviews() {
  const { summary: s } = R, body = $('#revBody');
  const writeBtn = el('button', { class: 'btn btn-ghost', onclick: () => $('#revForm').toggleAttribute('hidden') }, 'Write a review');
  if (!s.count) {
    body.replaceChildren(el('div', { class: 'rev-empty' }, el('p', { class: 'big' }, 'No reviews yet'), el('p', {}, 'Be the first to share what you think of this product.'), writeBtn), reviewForm());
    return;
  }
  const summary = el('div', { class: 'rev-sum' },
    el('div', { class: 'avg' }, el('strong', {}, s.average.toFixed(1)), stars(s.average), el('span', {}, `${s.count} review${s.count === 1 ? '' : 's'}`)),
    el('div', { class: 'bars' }, [5, 4, 3, 2, 1].map((n) => el('button', { class: 'bar', 'aria-pressed': R.stars === n, 'aria-label': `Show ${n}-star reviews (${s.histogram[n]})`, onclick: () => { R.stars = R.stars === n ? 0 : n; R.items = []; loadReviews(false); } },
      el('span', {}, `${n}★`), el('i', {}, el('b', { style: `width:${(s.histogram[n] / s.count) * 100}%` })), el('em', {}, s.histogram[n])))));
  const sort = el('select', { 'aria-label': 'Sort reviews', onchange: (e) => { R.sort = e.target.value; R.items = []; loadReviews(false); } },
    [['recent', 'Most recent'], ['highest', 'Highest rated'], ['lowest', 'Lowest rated']].map(([v, t]) => el('option', { value: v, ...(v === R.sort ? { selected: true } : {}) }, t)));
  const filter = el('select', { 'aria-label': 'Filter by rating', onchange: (e) => { R.stars = +e.target.value; R.items = []; loadReviews(false); } },
    [[0, 'All ratings'], ...[5, 4, 3, 2, 1].map((n) => [n, `${n} star${n > 1 ? 's' : ''}`])].map(([v, t]) => el('option', { value: v, ...(v === R.stars ? { selected: true } : {}) }, t)));
  const list = R.items.length ? el('ul', { class: 'rev-list' }, R.items.map((r) => el('li', {},
    el('div', { class: 'rv-head' }, stars(r.rating), el('strong', {}, r.author), el('time', { datetime: r.date }, fmtDate(r.date)), r.sample && el('span', { class: 'tag' }, 'Sample review')),
    el('p', {}, r.text))))
    : el('p', { class: 'muted' }, `No ${R.stars}-star reviews. `, el('button', { class: 'linklike dark', onclick: () => { R.stars = 0; R.items = []; loadReviews(false); } }, 'Show all'));
  const more = R.items.length < R.total && el('button', { class: 'btn btn-ghost load-more', onclick: (e) => { e.currentTarget.disabled = true; loadReviews(false); } }, `Load more (${R.total - R.items.length} more)`);
  body.replaceChildren(summary, el('div', { class: 'rev-controls' }, el('label', {}, 'Sort', sort), el('label', {}, 'Filter', filter), writeBtn),
    reviewForm(), list, el('p', { class: 'muted small' }, `Showing ${R.items.length} of ${R.total}`), more);
}

function reviewForm() {
  let rating = 0;
  const status = el('p', { class: 'form-status', role: 'status' });
  const picker = el('div', { class: 'star-pick', role: 'radiogroup', 'aria-label': 'Your rating' }, [1, 2, 3, 4, 5].map((n) => el('button', { type: 'button', role: 'radio', 'aria-checked': 'false', 'aria-label': `${n} star${n > 1 ? 's' : ''}`,
    onclick: () => { rating = n; picker.querySelectorAll('button').forEach((b, i) => { b.setAttribute('aria-checked', i + 1 === n); b.classList.toggle('on', i < n); }); } }, '★')));
  const f = el('form', { id: 'revForm', class: 'rev-form', hidden: true, novalidate: true, onsubmit: async (e) => {
    e.preventDefault();
    const author = f.author.value.trim(), text = f.text.value.trim();
    if (!author || !rating || text.length < 5) { status.textContent = 'Please add your name, a star rating and a short review.'; status.className = 'form-status err'; return; }
    const res = await fetch(`/api/products/${S.p.id}/reviews`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ author, rating, text }) });
    const out = await res.json().catch(() => ({}));
    if (!res.ok) { status.textContent = out.error || 'Could not save your review.'; status.className = 'form-status err'; return; }
    S.p.rating = (await getJSON(`/api/products/${S.p.id}/reviews?limit=1`)).summary; R.sort = 'recent'; R.stars = 0; R.items = [];
    root().querySelector('.pdp-rating').replaceWith(ratingLine(S.p.rating));   // keep the headline rating in step with the new review
    await loadReviews(false); toast('Thanks! Your review was posted.');
  } },
    el('label', {}, 'Your name', el('input', { name: 'author', maxlength: 60, autocomplete: 'name' })), el('div', {}, el('span', { class: 'lbl' }, 'Your rating'), picker),
    el('label', {}, 'Your review', el('textarea', { name: 'text', rows: 3, maxlength: 600 })), status, el('button', { class: 'btn btn-navy', type: 'submit' }, 'Post review'));
  return f;
}

addEventListener('cart:change', () => { if (S) updateCartN(); }); // the bar's cart count follows changes made in the cart drawer
