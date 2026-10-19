// Shared face-fitting helpers for the live camera try-on (live.js). MediaPipe runs locally in WebAssembly: nothing is uploaded.
let vision;
const instances = {};

/** mode: 'VIDEO' (camera, one call per frame) or 'IMAGE' (a single still photo). Instances are created once and reused. */
export async function getLandmarker(mode) {
  if (instances[mode]) return instances[mode];
  const { FilesetResolver, FaceLandmarker } = await import('/static/vendor/mediapipe/vision_bundle.mjs');
  vision ??= await FilesetResolver.forVisionTasks('/static/vendor/mediapipe/wasm');
  return (instances[mode] = await FaceLandmarker.createFromOptions(vision, {
    baseOptions: { modelAssetPath: '/static/vendor/mediapipe/face_landmarker.task' }, runningMode: mode, numFaces: 1,
  }));
}

/** Landmarks -> where to put the frame, in pixels of a W x H picture.
 *  cx, cy : midpoint between the pupils;  pd : pupil distance in px;  rot : head roll in radians;
 *  yaw    : 0 = facing the camera ... ~1 = strongly turned (used to narrow the frame slightly). */
export function poseFromLandmarks(lm, W, H) {
  const px = (i) => ({ x: lm[i].x * W, y: lm[i].y * H });
  const mid = (a, b) => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });
  let a = lm.length > 473 ? px(468) : mid(px(33), px(133));  // iris centres (468 / 473), else the middle of each eye
  let b = lm.length > 473 ? px(473) : mid(px(362), px(263));
  if (a.x > b.x) [a, b] = [b, a];
  // yaw: how far the nose tip sits from the middle of the face width (cheek landmarks 234 / 454)
  const l = px(234), r = px(454), nose = px(1);
  const offset = (nose.x - (l.x + r.x) / 2) / Math.max(1, Math.abs(r.x - l.x));
  return { cx: (a.x + b.x) / 2, cy: (a.y + b.y) / 2, pd: Math.hypot(b.x - a.x, b.y - a.y), rot: Math.atan2(b.y - a.y, b.x - a.x), yaw: Math.min(1, Math.abs(offset) * 2.4) };
}
