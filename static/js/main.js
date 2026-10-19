// Entry point: builds the data-driven parts of the page, then starts the motion layer.
import { $, el, getJSON, reducedMotion } from './api.js';
import { initCart } from './cart.js';
import { initChat } from './chat.js';
import { initPdp } from './pdp.js';
import { initContact } from './contact.js';
import { initFx, tiltGroup } from './fx.js';
import { initShop, selectCategory } from './shop.js';
import { initTryOn } from './tryon.js';

// Only hide [data-reveal] content when we're sure GSAP will bring it back.
if (window.gsap && window.ScrollTrigger && !reducedMotion) document.documentElement.classList.add('js');
$('#year').textContent = new Date().getFullYear();
initCart();
initPdp();   // after the cart, so a shared /product/<id> link opens straight to the detail screen
initChat();
initContact(); // independent of the catalogue, so it works even if that fails to load

const TILE = {
  frames: ['/static/img/site/tile-frames.jpg', 'Aviator sunglasses resting on a weathered wooden rail'],
  lenses: ['/static/img/site/tile-lenses.jpg', 'Case of trial lenses used by opticians'],
  accessories: ['/static/img/site/tile-accessories.jpg', 'Vintage wire glasses in an open velvet-lined case'],
  sprays: ['/static/img/site/tile-sprays.jpg', 'Gloved hand spraying a cleaning bottle'],
};

async function boot() {
  const cats = await getJSON('/api/categories');
  const all = await getJSON('/api/products');
  const brands = new Set(all.map((p) => p.brand)).size;
  const count = (k) => cats.find((c) => c.key === k).count;

  // collection tiles
  $('#tiles').replaceChildren(...cats.map((c, i) => el('a', { class: 'tile', href: '#shop', 'data-cat': c.key, 'aria-label': `Shop ${c.label}`,
      onclick: (e) => { e.preventDefault(); selectCategory(c.key, { scroll: true }); } },
    el('img', { src: TILE[c.key][0], alt: TILE[c.key][1], loading: 'lazy', decoding: 'async', width: 700, height: 980 }),
    el('span', { class: 'num' }, `0${i + 1}`), el('span', { class: 'glare' }),
    el('div', { class: 'tile-body' }, el('h3', {}, c.label), el('p', {}, `${c.blurb} ${c.count} products.`), el('span', { class: 'go' }, 'Shop now')))));
  tiltGroup($('#tiles'), '.tile', 9);

  // hero stats + numbers band (real counts from the database)
  const stat = (n, label, tag = 'li') => el(tag, {}, el('strong', { 'data-count': n }, '0'), el('span', {}, label));
  $('#heroStats').replaceChildren(stat(all.length, 'Products'), stat(count('frames'), 'Frames to try on'), stat(brands, 'Brands'));
  $('#numbers').replaceChildren(stat(all.length, 'Products in store'), stat(brands, 'Brands'), stat(count('frames'), 'Frames to try on'), stat(count('lenses'), 'Lens options'));

  const tryon = await initTryOn({ onShopFrame: () => selectCategory('frames') });
  await initShop({ onTryOn: (p) => tryon.selectFrame(p.id, { scroll: true }) });
  initFx();
  addEventListener('load', () => window.ScrollTrigger?.refresh());

  // 3D hero loads on the side so a slow GPU never delays the page
  import('./hero3d.js').then((m) => { if (!m.initHero($('#heroCanvas'), { reduced: reducedMotion })) throw new Error('no webgl'); })
    .catch((e) => { console.warn('3D hero disabled:', e.message); $('.hero-stage').hidden = true; });
}

boot().catch((e) => { console.error(e); $('#count').textContent = 'Could not load the catalogue. Is the server running?'; });

// image credits dialog (all photos are openly licensed; see static/img/credits.json)
$('#creditsBtn').addEventListener('click', async () => {
  const list = $('#creditsList');
  if (!list.children.length) {
    const credits = await getJSON('/static/img/credits.json');
    list.replaceChildren(...Object.entries(credits).map(([file, c]) => el('li', {},
      `${file.replace('img/', '')} — “${c.title}” by ${c.author}, ${c.license}. `, el('a', { href: c.source, target: '_blank', rel: 'noopener' }, 'Source'))));
  }
  $('#credits').showModal();
});
