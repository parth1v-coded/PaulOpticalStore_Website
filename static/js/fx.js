// Motion layer: GSAP + ScrollTrigger scroll animation, pointer-driven 3D tilt, counters, magnetic buttons.
// Everything animates transform/opacity only (compositor-friendly) and degrades to static content
// when the user prefers reduced motion or GSAP is unavailable.
import { $, $$, reducedMotion } from './api.js';

/** Pointer-driven 3D tilt for every `selector` inside `container` (mouse only; touch just scrolls). */
export function tiltGroup(container, selector, max = 8) {
  if (reducedMotion) return;
  let raf;
  const reset = (t) => { t.classList.remove('is-tilting'); ['--rx', '--ry', '--px', '--py'].forEach((v) => t.style.removeProperty(v)); };
  container.addEventListener('pointermove', (e) => {
    if (e.pointerType !== 'mouse') return;
    const t = e.target.closest(selector);
    if (!t) return;
    const { clientX, clientY } = e;
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      const r = t.getBoundingClientRect();
      const x = (clientX - r.left) / r.width, y = (clientY - r.top) / r.height;
      t.classList.add('is-tilting');
      t.style.setProperty('--ry', `${(x - .5) * 2 * max}deg`);
      t.style.setProperty('--rx', `${(.5 - y) * 2 * max}deg`);
      t.style.setProperty('--px', `${(.5 - x) * 26}px`);   // inner image drifts opposite the tilt: depth
      t.style.setProperty('--py', `${(.5 - y) * 26}px`);
      t.style.setProperty('--gx', `${x * 100}%`); t.style.setProperty('--gy', `${y * 100}%`);
    });
  });
  container.addEventListener('pointerout', (e) => {
    const t = e.target.closest(selector);
    if (t && !t.contains(e.relatedTarget)) reset(t);
  });
}

export function initFx() {
  initHeader();
  if (!window.gsap || !window.ScrollTrigger) { document.documentElement.classList.remove('js'); return; }
  gsap.registerPlugin(ScrollTrigger);
  heroIntro();
  scrollReveals();
  parallax();
  magnetic();
  if (!reducedMotion) setTimeout(story, 0);
}

function initHeader() {
  const header = $('#header'), bar = $('#progress'), nav = $('#nav'), btn = $('#menuBtn');
  let ticking = false;
  const update = () => {
    const max = document.documentElement.scrollHeight - innerHeight;
    header.classList.toggle('scrolled', scrollY > 30);
    bar.style.transform = `scaleX(${max > 0 ? scrollY / max : 0})`;
    ticking = false;
  };
  addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
  update();
  // smooth in-page links (done here, not in CSS - see the note in style.css)
  document.addEventListener('click', (e) => {
    if (e.defaultPrevented) return;                              // another handler already dealt with this click
    const a = e.target.closest('a[href^="#"]');
    if (a?.closest('#pdp, #live, #cart')) return;               // links inside the overlay screens manage their own scrolling
    const target = a && a.getAttribute('href').length > 1 && document.querySelector(a.getAttribute('href'));
    if (!target) return;
    e.preventDefault();
    target.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth' });
    history.replaceState(null, '', a.getAttribute('href'));
  });
  btn.addEventListener('click', () => { const open = nav.classList.toggle('open'); btn.setAttribute('aria-expanded', open); });
  nav.addEventListener('click', (e) => { if (e.target.closest('a')) { nav.classList.remove('open'); btn.setAttribute('aria-expanded', 'false'); } });
}

function heroIntro() {
  // split the headline into words so each can slide up from behind a mask
  const h1 = $('[data-split]');
  h1.innerHTML = h1.textContent.trim().split(/\s+/).map((w) => `<span class="w"><span>${w}</span></span>`).join(' ');
  if (reducedMotion) return;
  const tl = gsap.timeline({ defaults: { ease: 'power4.out' } });
  tl.from('.hero h1 .w > span', { yPercent: 115, rotate: 5, duration: 1.1, stagger: .07 }, .15)
    .from('[data-hero]', { y: 30, autoAlpha: 0, duration: .9, stagger: .1 }, .35)
    .from('.hero-stage', { autoAlpha: 0, scale: .92, duration: 1.4 }, .2);
}

function scrollReveals() {
  if (!reducedMotion) {
    ScrollTrigger.batch('[data-reveal]', {
      start: 'top 90%', once: true,
      onEnter: (els) => gsap.to(els, { opacity: 1, y: 0, duration: .9, stagger: .12, ease: 'power3.out', overwrite: true }),
    });
    gsap.from('.tile', { scrollTrigger: { trigger: '#tiles', start: 'top 82%', once: true }, y: 90, rotateY: -28, autoAlpha: 0, transformPerspective: 1000,
      duration: 1.1, stagger: .14, ease: 'power3.out', clearProps: 'transform,opacity,visibility' });
    gsap.from('.numbers-grid li', { scrollTrigger: { trigger: '#numbers', start: 'top 85%', once: true }, y: 50, autoAlpha: 0, rotateX: -40, transformPerspective: 800, duration: 1, stagger: .12, ease: 'back.out(1.4)' });
  }
  // counters: count up once when scrolled into view
  $$('[data-count]').forEach((n) => {
    const target = +n.dataset.count, o = { v: 0 };
    ScrollTrigger.create({ trigger: n, start: 'top 92%', once: true, onEnter: () =>
      gsap.to(o, { v: target, duration: reducedMotion ? .01 : 1.6, ease: 'power2.out', onUpdate: () => { n.textContent = Math.round(o.v); } }) });
  });
}

function parallax() {
  if (reducedMotion) return;
  $$('[data-parallax]').forEach((n) => gsap.to(n, { y: () => parseFloat(n.dataset.parallax) * innerHeight * .6, ease: 'none',
    scrollTrigger: { trigger: n.parentElement, start: 'top bottom', end: 'bottom top', scrub: true } }));
  gsap.to('.hero-copy', { yPercent: -14, ease: 'none', scrollTrigger: { trigger: '.hero', start: 'top top', end: 'bottom top', scrub: true } });
  gsap.to('.hero-stage', { yPercent: 10, ease: 'none', scrollTrigger: { trigger: '.hero', start: 'top top', end: 'bottom top', scrub: true } });
  // collection photos slowly pan inside their frames as you scroll past
  $$('.tile img').forEach((img) => gsap.fromTo(img, { objectPosition: '30% 25%' }, { objectPosition: '70% 75%', ease: 'none',
    scrollTrigger: { trigger: img.closest('.tile'), start: 'top bottom', end: 'bottom top', scrub: true } }));
  $$('.numbers-grid strong').forEach((n) => gsap.from(n, { yPercent: 20, ease: 'none', scrollTrigger: { trigger: n, start: 'top bottom', end: 'top 40%', scrub: true } }));
}

function magnetic() {
  if (reducedMotion) return;
  $$('[data-magnetic]').forEach((b) => {
    const x = gsap.quickTo(b, 'x', { duration: .4, ease: 'power3' }), y = gsap.quickTo(b, 'y', { duration: .4, ease: 'power3' });
    b.addEventListener('pointermove', (e) => {
      if (e.pointerType !== 'mouse') return;
      const r = b.getBoundingClientRect();
      x((e.clientX - r.left - r.width / 2) * .28); y((e.clientY - r.top - r.height / 2) * .4);
    });
    b.addEventListener('pointerleave', () => { x(0); y(0); });
  });
}

/** Pinned 3-step story: scrolling flips the photos around in 3D while the matching step lights up. */
function story() {
  if (innerWidth < 961) return; // small screens keep the simple stacked layout
  const sec = $('#craft'), steps = $$('.step'), shots = $$('.shot'), bar = $('#craftBar');
  sec.classList.add('is-pinned');
  gsap.set(shots, { transformPerspective: 1400 });
  gsap.set(shots.slice(1), { autoAlpha: 0, rotateY: 55, x: 140, scale: .86 });
  let current = 0;
  const show = (i) => { if (i === current) return; current = i; steps.forEach((s, k) => s.classList.toggle('is-on', k === i)); };
  const tl = gsap.timeline({ defaults: { ease: 'power2.inOut' }, scrollTrigger: {
    trigger: '.craft-pin', start: 'top top', end: '+=240%', pin: true, scrub: .6, anticipatePin: 1,
    onUpdate: (s) => { bar.style.transform = `scaleX(${s.progress})`; show(s.progress < .34 ? 0 : s.progress < .68 ? 1 : 2); } } });
  tl.to({}, { duration: 3 }, 0); // fixes the timeline at 3 units so the transitions sit at ~1/3 and ~2/3
  [1, 2].forEach((i) => {
    const at = i * 1 - .35;
    tl.to(shots[i - 1], { autoAlpha: 0, rotateY: -55, x: -140, scale: .86, duration: .7 }, at)
      .to(shots[i], { autoAlpha: 1, rotateY: 0, x: 0, scale: 1, duration: .7 }, at);
  });
}
