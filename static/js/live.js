/* Live virtual try-on (camera). Opens from the product page's "Try On" button.
 *
 * - A friendly explainer comes first; the browser's own camera prompt appears only after the shopper taps "Allow camera".
 *   If permission is denied (or there's no camera / the page isn't a secure context) we explain how to fix it and offer
 *   a still-photo fallback that uses exactly the same fitting code.
 * - Every video frame is drawn to a canvas (mirrored, like a selfie camera). MediaPipe Face Landmarker (local WebAssembly,
 *   nothing is uploaded) returns the pupils; the frame drawing (an SVG in real millimetres from the server) is scaled from the
 *   pupil distance (average adult 63 mm), rotated with head roll, and narrowed slightly when the head turns. Position and size
 *   are smoothed between frames so the glasses stay locked on without jitter.
 * - Switch frames or colours while live; a size slider fine-tunes; the shutter saves a PNG snapshot.
 * - The camera stream is stopped whenever the view closes or the tab is hidden.
 */
import { $, el, getJSON, money, syncLayers } from './api.js';
import { getLandmarker, poseFromLandmarks } from './facefit.js';

const AVG_PD_MM = 63;
let built = false, frames = [], cache = new Map();           // frames: list rows; cache: id -> full product detail
let cur = null;                                               // {d (detail), ci, lw, tint}
let overlay = null, overlayMm = 150;                          // current drawing (Image) and its width in mm
let stream = null, raf = 0, mode = 'idle';                    // mode: idle | live | photo
let lmVideo = null, photoCanvas = null, lastTime = -1, lost = 0;
let session = 0, selToken = 0, ovToken = 0;                    // bumped to cancel work that finishes after the shopper has moved on
const pose = { cx: 0, cy: 0, pd: 0, rot: 0, yaw: 0, alpha: 0, has: false };
let userScale = 1, wasLive = false;
let canvas, ctx, video;

export async function openLive(opts = {}) {
  build();
  $('#live').hidden = false; syncLayers();
  $('#live .live-close').focus();
  if (!frames.length) frames = await getJSON('/api/products?category=frames');
  await select(opts.frameId || frames[0].id, opts);
  chips();
  // already allowed before? start straight away. Blocked before? say so. Otherwise explain first.
  let state = 'prompt';
  try { state = (await navigator.permissions.query({ name: 'camera' })).state; } catch { /* Safari/Firefox: not supported, just explain */ }
  if (state === 'granted') start(); else if (state === 'denied') panel('denied'); else panel('prompt');
}

export function closeLive() {
  stop(); $('#live').hidden = true; wasLive = false; syncLayers();
  document.querySelector('.pdp-tryon .btn')?.focus({ preventScroll: true });   // hand focus back to the Try On button
}

// ------------------------------------------------------------------ UI
function build() {
  if (built) return; built = true;
  const root = $('#live');
  video = el('video', { playsinline: '', muted: '', autoplay: '', class: 'live-video' });
  canvas = el('canvas', { class: 'live-canvas', 'aria-label': 'Live try-on view', role: 'img' }); ctx = canvas.getContext('2d');
  // clearing the value afterwards lets the shopper pick the same photo again (the browser only fires `change` when it differs)
  const file = el('input', { type: 'file', accept: 'image/*', hidden: true, id: 'liveFile', onchange: () => { const f = file.files[0]; file.value = ''; if (f) usePhoto(f); } });
  root.replaceChildren(
    el('header', { class: 'live-bar' }, el('button', { class: 'live-close', 'aria-label': 'Close try-on', onclick: closeLive }, '×'),
      el('div', { class: 'live-title' }, el('small', {}, 'Virtual try-on'), el('b', { id: 'liveName' })), el('span', { id: 'livePrice', class: 'live-price' })),
    el('div', { class: 'live-stage' }, canvas, video,
      el('div', { class: 'live-status', id: 'liveStatus', role: 'status', 'aria-live': 'polite' }),
      el('div', { class: 'live-flash', id: 'liveFlash' }),
      el('div', { class: 'live-panel', id: 'livePanel' })),
    el('div', { class: 'live-controls' },
      el('div', { class: 'live-row', id: 'liveChips', role: 'listbox', 'aria-label': 'Choose a frame' }),
      el('div', { class: 'live-row sw', id: 'liveSwatches', role: 'radiogroup', 'aria-label': 'Choose a colour' }),
      el('div', { class: 'live-actions' },
        el('label', { class: 'live-size' }, 'Size', el('input', { type: 'range', min: 80, max: 125, value: 100, 'aria-label': 'Frame size adjustment',
          oninput: (e) => { userScale = e.target.value / 100; if (mode === 'photo') paint(); } })),
        el('button', { class: 'shutter', id: 'shutter', 'aria-label': 'Take snapshot', disabled: true, onclick: snapshot }, el('i')),
        el('button', { class: 'btn btn-ghost-light btn-sm', onclick: () => file.click() }, 'Use a photo'))),
    el('div', { class: 'live-shot', id: 'liveShot', hidden: true }), file);
  addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('#live').hidden) { if (!$('#liveShot').hidden) $('#liveShot').hidden = true; else closeLive(); } });
  document.addEventListener('visibilitychange', () => {   // never leave the camera running in a background tab
    if (document.hidden && mode === 'live') { wasLive = true; stop(); panel('paused'); }
    else if (!document.hidden && wasLive && !$('#live').hidden) { wasLive = false; start(); }
  });
}

function panel(name, msg) {
  const p = $('#livePanel'), btn = (t, f, cls = 'btn-gold') => el('button', { class: `btn ${cls}`, onclick: f }, t);
  const photo = () => btn('Use a photo instead', () => $('#liveFile').click(), 'btn-ghost-light');
  const views = {
    prompt: [el('div', { class: 'ico' }, '📷'), el('h2', {}, 'Allow camera access'), el('p', {}, 'To show these frames on your face we need your camera. The video stays on your device: nothing is recorded, uploaded or shared.'),
      btn('Allow camera', start), photo()],
    starting: [el('div', { class: 'spin' }), el('p', {}, 'Starting camera and face tracking…')],
    paused: [el('p', {}, 'Camera paused while this tab was in the background.'), btn('Resume', start)],
    denied: [el('div', { class: 'ico' }, '🚫'), el('h2', {}, 'Camera access is blocked'), el('p', {}, 'You can still try frames on a photo. To use the live camera, allow camera access for this site (click the camera or lock icon in the address bar), then try again.'),
      btn('Try again', start), photo()],
    unavailable: [el('div', { class: 'ico' }, '⚠️'), el('h2', {}, 'Camera not available'), el('p', {}, msg || 'We couldn\'t find a camera, or this page isn\'t allowed to use it (live camera needs HTTPS or localhost).'), photo()],
    photoHelp: [],
  };
  p.replaceChildren(...(views[name] || [])); p.hidden = !(views[name] || []).length;
  $('#shutter').disabled = !(name === 'none');
}

const status = (t) => { $('#liveStatus').textContent = t || ''; $('#liveStatus').hidden = !t; };

// frame chips + colour swatches --------------------------------------------------------------
function chips() {
  $('#liveChips').replaceChildren(...frames.map((f) => el('button', { class: 'lchip', role: 'option', 'aria-selected': f.id === cur.d.id, title: f.name, onclick: () => select(f.id) },
    el('img', { src: f.tryon.overlay, alt: '', width: 96, height: 32 }), el('span', {}, f.name))));
  swatches();
  const row = $('#liveChips'), sel = row.querySelector('[aria-selected="true"]');   // bring the current frame into view (scroll the strip only, not the page)
  if (sel) row.scrollLeft = sel.offsetLeft - (row.clientWidth - sel.offsetWidth) / 2;
}
function swatches() {
  $('#liveSwatches').replaceChildren(...cur.d.options.colours.map((c, i) => el('button', { class: 'swatch', role: 'radio', 'aria-checked': i === cur.ci, 'aria-label': c.name, title: c.name, style: `--c:${c.hex}`,
    onclick: () => { cur.ci = i; swatches(); loadOverlay(); } })));
  $('#liveName').textContent = `${cur.d.name} · ${cur.d.options.colours[cur.ci].name}`;
  $('#livePrice').textContent = money(cur.d.price);
}

async function select(id, o = {}) {
  const my = ++selToken;
  let d = cache.get(id);
  if (!d) { d = await getJSON(`/api/products/${id}`); cache.set(id, d); }
  if (my !== selToken) return;                                  // the shopper tapped another frame meanwhile: keep the newer choice
  const ci = o.colourHex ? Math.max(0, d.options.colours.findIndex((c) => c.hex === o.colourHex)) : 0;
  cur = { d, ci, lw: o.lensWidth || d.options.default_width, tint: o.tint || d.options.default_tint };
  document.querySelectorAll('.lchip').forEach((c) => c.setAttribute('aria-selected', c.title === d.name));
  const row = $('#liveChips'), sel = row.querySelector('[aria-selected="true"]');
  if (sel) row.scrollLeft = sel.offsetLeft - (row.clientWidth - sel.offsetWidth) / 2;
  swatches(); await loadOverlay();
}

function loadOverlay() {
  const { d, ci, lw, tint } = cur, w = d.options.widths.find((x) => x.lens_width === lw) || d.options.widths[1];
  const img = new Image(), my = ++ovToken;
  img.src = `${d.options.overlay}?color=${d.options.colours[ci].hex.slice(1)}&lw=${w.lens_width}&tint=${tint}`;
  return img.decode().then(() => { if (my !== ovToken) return; overlay = img; overlayMm = w.width_mm; if (mode === 'photo') paint(); }).catch(() => { status('Could not load this frame.'); });
}

// camera ---------------------------------------------------------------------------------------
async function start() {
  stop(); const my = session; lastTime = -1; lost = 0; pose.has = false; pose.alpha = 0;
  if (!navigator.mediaDevices?.getUserMedia || !isSecureContext) { panel('unavailable'); return; }
  panel('starting');
  try {
    const s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
    if (my !== session) { s.getTracks().forEach((t) => t.stop()); return; }   // closed (or restarted) while the permission prompt was open: don't leave the camera on
    stream = s;
  } catch (e) {
    if (my !== session) return;
    if (['NotAllowedError', 'SecurityError', 'PermissionDeniedError'].includes(e.name)) panel('denied');
    else if (e.name === 'NotReadableError') panel('unavailable', 'Your camera is busy in another app. Close it and try again, or use a photo.');
    else panel('unavailable');
    return;
  }
  video.srcObject = stream;
  try { await video.play(); } catch { /* autoplay quirks: frames still arrive */ }
  await new Promise((r) => (video.readyState >= 2 ? r() : video.addEventListener('loadeddata', r, { once: true })));
  if (my !== session) return;
  canvas.width = video.videoWidth || 640; canvas.height = video.videoHeight || 480;
  panel('none'); $('#livePanel').hidden = true;
  mode = 'live'; $('#shutter').disabled = false;
  try { lmVideo ||= await getLandmarker('VIDEO'); if (my === session) status('Looking for your face…'); }
  catch (e) { console.warn('Face tracking unavailable', e); lmVideo = null; status('Face tracking isn\'t available here, so the frame stays centred. Move closer and use the size slider.'); }
  if (my !== session) return;
  loop();
}

function stop() {
  session++;                                                    // invalidates any start() still waiting on the camera or the model
  cancelAnimationFrame(raf); raf = 0;
  stream?.getTracks().forEach((t) => t.stop()); stream = null;
  if (video) video.srcObject = null;
  mode = 'idle'; if ($('#shutter')) $('#shutter').disabled = true;
}

function loop() {
  if (mode !== 'live') return;
  raf = requestAnimationFrame(loop);
  if (video.readyState < 2) return;
  if (lmVideo && video.currentTime !== lastTime) {                      // a new video frame has arrived: track the face
    lastTime = video.currentTime;
    const lm = lmVideo.detectForVideo(video, performance.now()).faceLandmarks?.[0];
    if (lm) { aim(poseFromLandmarks(lm, canvas.width, canvas.height)); lost = 0; status(''); }
    else if (++lost > 8) { pose.alpha = Math.max(0, pose.alpha - 0.2); status('Looking for your face… face the camera in good light.'); }
  } else if (!lmVideo && !pose.has) aim({ cx: canvas.width / 2, cy: canvas.height * 0.42, pd: canvas.width * 0.2, rot: 0, yaw: 0 });
  paint();
}

/** Ease towards the newest measurement so the frame follows smoothly instead of jittering. */
function aim(t) {
  const k = pose.has ? 0.5 : 1;   // first sighting: jump straight there
  for (const f of ['cx', 'cy', 'pd', 'rot', 'yaw']) pose[f] += (t[f] - pose[f]) * k;
  pose.alpha = Math.min(1, pose.alpha + 0.34); pose.has = true;
}

function paint() {
  const src = mode === 'photo' ? photoCanvas : video;
  if (!src) return;
  const W = canvas.width, H = canvas.height;
  ctx.save();
  if (mode === 'live') { ctx.translate(W, 0); ctx.scale(-1, 1); }       // mirror like a selfie camera (frame is symmetric, so it needs no flip)
  ctx.drawImage(src, 0, 0, W, H);
  if (overlay && pose.has && pose.alpha > 0.02) {
    const w = overlayMm * (pose.pd / AVG_PD_MM) * userScale, h = w * overlay.naturalHeight / overlay.naturalWidth;
    ctx.globalAlpha = pose.alpha; ctx.translate(pose.cx, pose.cy); ctx.rotate(pose.rot); ctx.scale(1 - 0.32 * pose.yaw, 1);
    ctx.shadowColor = 'rgba(0,0,0,.28)'; ctx.shadowBlur = w * 0.012; ctx.shadowOffsetY = w * 0.01;
    ctx.drawImage(overlay, -w / 2, -h / 2, w, h);
  }
  ctx.restore();
}

// still-photo fallback --------------------------------------------------------------------------
async function usePhoto(file) {
  if (!file.type.startsWith('image/')) { status('Please choose an image file.'); return; }
  stop();
  const bmp = await createImageBitmap(file).catch(() => null);
  if (!bmp) { status('That image could not be read. Try a JPG or PNG.'); return; }
  const k = Math.min(1, 1280 / Math.max(bmp.width, bmp.height));
  photoCanvas = el('canvas'); photoCanvas.width = canvas.width = Math.round(bmp.width * k); photoCanvas.height = canvas.height = Math.round(bmp.height * k);
  photoCanvas.getContext('2d').drawImage(bmp, 0, 0, photoCanvas.width, photoCanvas.height);
  mode = 'photo'; pose.has = false; pose.alpha = 1; $('#livePanel').hidden = true; $('#shutter').disabled = false;
  status('Finding your eyes…');
  try {
    const lm = (await (await getLandmarker('IMAGE')).detect(photoCanvas)).faceLandmarks?.[0];
    if (lm) { Object.assign(pose, poseFromLandmarks(lm, photoCanvas.width, photoCanvas.height), { has: true, alpha: 1 }); status('Frame fitted to your eyes. Switch frames or colours below.'); }
    else { Object.assign(pose, { cx: canvas.width / 2, cy: canvas.height * 0.42, pd: canvas.width * 0.22, rot: 0, yaw: 0, has: true, alpha: 1 }); status('No face found: the frame is centred. Use the size slider, or try another photo.'); }
  } catch { Object.assign(pose, { cx: canvas.width / 2, cy: canvas.height * 0.42, pd: canvas.width * 0.22, rot: 0, yaw: 0, has: true, alpha: 1 }); status('Face tracking is unavailable here. Use the size slider.'); }
  paint();
}

// snapshot ---------------------------------------------------------------------------------------
function snapshot() {
  const flash = $('#liveFlash'); flash.classList.add('on'); setTimeout(() => flash.classList.remove('on'), 160);
  canvas.toBlob((blob) => {
    if (!blob) return;
    const url = URL.createObjectURL(blob), name = `paul-optical-${cur.d.name.toLowerCase().replace(/\W+/g, '-')}.png`, shot = $('#liveShot');
    const close = () => { shot.hidden = true; URL.revokeObjectURL(url); };
    shot.replaceChildren(el('img', { src: url, alt: `Snapshot wearing ${cur.d.name}` }),
      el('div', { class: 'shot-actions' }, el('a', { class: 'btn btn-gold', href: url, download: name }, 'Save photo'), el('button', { class: 'btn btn-ghost-light', onclick: close }, 'Keep trying')));
    shot.hidden = false; shot.querySelector('a').focus();
  }, 'image/png');
}
