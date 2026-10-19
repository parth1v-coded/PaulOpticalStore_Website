// Hero: a procedurally modelled pair of glasses rendered with three.js (no model file or texture needed).
// Responds to the cursor and to scroll, pauses when off-screen, and renders a single still frame for
// visitors who prefer reduced motion. Returns false if WebGL is unavailable (the page works without it).
import * as THREE from 'three';
import { RoomEnvironment } from '/static/vendor/RoomEnvironment.js';

export function initHero(canvas, { reduced = false } = {}) {
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
  } catch (e) { return false; }
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;

  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture; // soft studio reflections for the metal
  const key = new THREE.DirectionalLight(0xffffff, 1.6); key.position.set(4, 6, 8); scene.add(key);

  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 80);
  const rig = new THREE.Group();            // moves with pointer / scroll
  scene.add(rig);
  const glasses = buildGlasses();
  rig.add(glasses);

  // thin "focus rings" and drifting dust give depth and an optics feel
  const rings = new THREE.Group();
  [[3.1, 0xc9a24b, .6], [3.6, 0x2f5aaa, .4], [4.1, 0xc9a24b, .28]].forEach(([r, c, o], i) => { // radii stay inside the canvas so nothing is clipped
    const ring = new THREE.Mesh(new THREE.TorusGeometry(r, 0.014, 8, 160), new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: o }));
    ring.rotation.set(1.25 - i * .22, 0, i * .7);
    rings.add(ring);
  });
  scene.add(rings);
  const dust = (() => {
    const n = 160, pos = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const r = 4.5 + Math.random() * 4, a = Math.random() * Math.PI * 2, b = Math.acos(2 * Math.random() - 1);
      pos.set([r * Math.sin(b) * Math.cos(a), r * Math.sin(b) * Math.sin(a), r * Math.cos(b)], i * 3);
    }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    return new THREE.Points(g, new THREE.PointsMaterial({ color: 0xc9a24b, size: 0.07, transparent: true, opacity: .8, depthWrite: false }));
  })();
  scene.add(dust);

  // ---- interaction state ----
  const target = { x: 0, y: 0 }, cur = { x: 0, y: 0 };
  addEventListener('pointermove', (e) => {
    if (e.pointerType === 'touch') return;
    target.x = (e.clientX / innerWidth - .5) * 2; target.y = (e.clientY / innerHeight - .5) * 2;
  }, { passive: true });

  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.position.set(0, 0.2, Math.max(12.5, 11.2 / camera.aspect)); // always fit the full width of the glasses
    camera.lookAt(0, 0, 0);
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(canvas);
  resize();

  let visible = true, raf = 0;
  const clock = new THREE.Clock();
  function frame() {
    raf = visible ? requestAnimationFrame(frame) : 0;
    const t = clock.getElapsedTime();
    cur.x += (target.x - cur.x) * .06; cur.y += (target.y - cur.y) * .06; // eased follow
    const heroProgress = Math.min(1, scrollY / innerHeight);              // 0 at the top -> 1 when hero has scrolled away
    rig.rotation.y = -0.55 + cur.x * .55 + heroProgress * Math.PI * .9;
    rig.rotation.x = cur.y * .25 + heroProgress * .3;
    rig.position.y = Math.sin(t * 1.1) * .12;
    rig.scale.setScalar(1 - heroProgress * .25);
    rings.rotation.z = t * .08 + heroProgress; rings.rotation.y = t * .05;
    dust.rotation.y = t * .03; dust.rotation.x = Math.sin(t * .1) * .1;
    renderer.render(scene, camera);
  }
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible && !raf) { clock.getDelta(); frame(); } }).observe(canvas);
  if (reduced) { rig.rotation.y = -0.55; renderer.render(scene, camera); visible = false; } else frame();
  return true;
}

function buildGlasses() {
  const g = new THREE.Group();
  const gold = new THREE.MeshPhysicalMaterial({ color: 0xd9b45f, metalness: 1, roughness: .2, clearcoat: .5, clearcoatRoughness: .15, envMapIntensity: 1.3 });
  // glossy translucent lens. (Real transmission would sample a black backdrop on a transparent canvas, so we fake it with reflections.)
  const glass = new THREE.MeshPhysicalMaterial({ color: 0x9fc4ff, metalness: 0, roughness: .02, transparent: true, opacity: .2, clearcoat: 1, clearcoatRoughness: 0,
    envMapIntensity: 2.2, side: THREE.DoubleSide, depthWrite: false });
  const pad = new THREE.MeshPhysicalMaterial({ color: 0xffffff, transparent: true, opacity: .55, roughness: .1 });
  const sx = 1.28, sy = .86; // lens centre offset and height squash

  for (const s of [-1, 1]) {
    const rim = new THREE.Mesh(new THREE.TorusGeometry(1, .055, 32, 160), gold);
    rim.scale.y = sy; rim.position.x = s * sx; g.add(rim);
    const lens = new THREE.Mesh(new THREE.CircleGeometry(.995, 96), glass);
    lens.scale.y = sy; lens.position.set(s * sx, 0, 0); g.add(lens);
    // temple arm: out from the hinge, along the head, curling down behind the ear
    const arm = new THREE.CatmullRomCurve3([
      new THREE.Vector3(s * (sx + 1.0), .42, 0), new THREE.Vector3(s * (sx + 1.08), .42, -.3),
      new THREE.Vector3(s * (sx + 1.1), .38, -2.2), new THREE.Vector3(s * (sx + 1.02), .25, -3.6), new THREE.Vector3(s * (sx + .92), -.2, -4.2),
    ]);
    g.add(new THREE.Mesh(new THREE.TubeGeometry(arm, 64, .042, 12), gold));
    const hinge = new THREE.Mesh(new THREE.BoxGeometry(.12, .2, .14), gold); hinge.position.set(s * (sx + 1.02), .42, -.05); g.add(hinge);
    const nose = new THREE.Mesh(new THREE.SphereGeometry(.11, 24, 16), pad); nose.scale.set(.7, 1.5, .5); nose.position.set(s * .36, -.26, .12); g.add(nose);
  }
  // double-curve bridge
  const bridge = new THREE.CatmullRomCurve3([new THREE.Vector3(-.28, .1, 0), new THREE.Vector3(-.14, .36, .02), new THREE.Vector3(.14, .36, .02), new THREE.Vector3(.28, .1, 0)]);
  g.add(new THREE.Mesh(new THREE.TubeGeometry(bridge, 32, .05, 12), gold));
  g.position.z = 1.6; // centre of mass so it rotates about its middle
  const holder = new THREE.Group(); holder.add(g);
  return holder;
}
