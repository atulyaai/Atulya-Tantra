// Atulya's face: a holographic particle humanoid (three.js).
//
// It opens as a comet-like stream of particles rising from a bright point,
// then the particles fly into a glowing bust with contour lines and a warm face.
// The opening is directed rather than animated: four hard camera cuts — the
// chest point, a three-quarter, a close on the head, then a settle to front —
// with an `ASSEMBLING... n%` readout counting the sequence off. Once she is
// up, a `STATUS: <state> INTENSITY: <band>` line tracks the live signal.
// Everything pulses with the live sound level (your voice while it
// listens, its own voice while it speaks).
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';

const HEAD = { x: 0, y: 0.45, rx: 0.3, ry: 0.4 };
const CHEST_POINT = { x: 0, y: -1.08 };
const KIND = { body: 0, core: 3 };
const BLUE = [0.08, 0.38, 0.82];
const DIM = [0.13, 0.36, 0.7]; // contour lines: dimmer, so the many particles don't wash out
const ICE = [0.22, 0.62, 0.95];
const GOLD = [0.82, 0.39, 0.08];
const ORANGE = [1.0, 0.2, 0.015];

function rand(a = 0, b = 1) { return a + Math.random() * (b - a); }
function gauss() { return (Math.random() + Math.random() + Math.random() - 1.5) / 1.5; }
function smooth(e0, e1, x) { const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0))); return t * t * (3 - 2 * t); }

// Half-width of the bust silhouette at height y (front view).
function halfWidth(y) {
  if (y >= HEAD.y - HEAD.ry && y <= HEAD.y + HEAD.ry) {
    const k = (y - HEAD.y) / HEAD.ry;
    const jaw = y < HEAD.y ? 1 - 0.25 * smooth(HEAD.y, HEAD.y - HEAD.ry, y) : 1; // narrower chin
    return HEAD.rx * Math.sqrt(Math.max(0, 1 - k * k)) * jaw;
  }
  if (y > -0.16) return 0.12; // neck
  return 0.12 + 0.74 * smooth(-0.16, -0.62, y); // shoulders sloping out
}

// Where a particle starts: a curling comet trail rising from the bright point.
function cometStart(s) {
  const spread = 0.04 + s * 0.22;
  return [
    CHEST_POINT.x + Math.sin(s * 3.4) * 0.95 * s + gauss() * spread,
    CHEST_POINT.y + s * 1.9 + gauss() * spread * 0.6,
    gauss() * spread,
  ];
}

const MOUTH_Y = 0.04; // face center in the video-derived head coordinates
async function loadReference() {
  const res = await fetch('/hologram-points.bin');
  if (!res.ok) throw new Error(`Hologram reference missing (${res.status})`);
  const buf = await res.arrayBuffer();
  const count = new DataView(buf).getUint32(0, true);
  return { count, data: new Float32Array(buf, 4, count * 7) };
}

function buildParticles(reference) {
  const deform = []; // per particle: jaw xyz, "aa" xyz, blink xyz (zero for non-face particles)
  const target = [];
  const start = [];
  const color = [];
  const size = [];
  const kind = [];
  const phase = [];
  function add(p, c, sz, k, s = Math.random()) {
    target.push(p[0], p[1], p[2]);
    start.push(...cometStart(s));
    color.push(c[0], c[1], c[2]);
    size.push(sz);
    kind.push(k);
    phase.push(Math.random());
    deform.push(0, 0, 0, 0, 0, 0, 0, 0, 0);
  }

  // Coordinates and colors are sampled from the user's reference video, so the
  // scanline silhouette, face glow, shoulder curves and gold veins stay faithful.
  for (let i = 0; i < reference.count; i += 1) {
    const o = i * 7;
    add([reference.data[o], reference.data[o + 1], reference.data[o + 2]],
      [reference.data[o + 3], reference.data[o + 4], reference.data[o + 5]],
      reference.data[o + 6], KIND.body, i / reference.count);
  }

  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(target, 3));
  g.setAttribute('aStart', new THREE.Float32BufferAttribute(start, 3));
  g.setAttribute('aColor', new THREE.Float32BufferAttribute(color, 3));
  g.setAttribute('aSize', new THREE.Float32BufferAttribute(size, 1));
  g.setAttribute('aKind', new THREE.Float32BufferAttribute(kind, 1));
  g.setAttribute('aPhase', new THREE.Float32BufferAttribute(phase, 1));
  const d = new Float32Array(deform);
  const view = (offset) => new THREE.InterleavedBufferAttribute(new THREE.InterleavedBuffer(d, 9), 3, offset);
  g.setAttribute('aJaw', view(0));
  g.setAttribute('aAa', view(3));
  g.setAttribute('aBlink', view(6));
  return g;
}

const vertexShader = /* glsl */`
  uniform float uTime;
  uniform float uMorph;
  uniform float uLevel;
  uniform float uScale;
  uniform float uSpin;
  uniform float uJaw;
  uniform float uBlink;
  uniform float uScatter;
  uniform float uBreath;
  attribute vec3 aStart;
  attribute vec3 aJaw;
  attribute vec3 aAa;
  attribute vec3 aBlink;
  attribute vec3 aColor;
  attribute float aSize;
  attribute float aKind;
  attribute float aPhase;
  varying vec3 vColor;
  varying float vAlpha;
  const vec2 HEAD = vec2(${HEAD.x.toFixed(2)}, ${(HEAD.y - 0.05).toFixed(2)});
  const vec2 POINT = vec2(${CHEST_POINT.x.toFixed(2)}, ${CHEST_POINT.y.toFixed(2)});

  void main() {
    vec3 p = position;
    float alpha = 1.0;

    if (aKind < 0.5) {            // body: talks, blinks, breathes, shimmers; fades out at the bottom
      p += aJaw * uJaw * 0.7 + aAa * uJaw + aBlink * uBlink;
      p.y += uBreath * (p.y + 1.2) * 0.012;
      // Thinking: the face dissolves into a drifting cloud, then pulls back together.
      vec3 dir = normalize(vec3(sin(aPhase * 91.0), cos(aPhase * 57.0), sin(aPhase * 23.0)) + 0.001);
      p += dir * uScatter * (0.35 + aPhase * 0.6) + dir * uScatter * 0.08 * sin(uTime * 1.5 + aPhase * 30.0);
      p.xy += 0.004 * vec2(sin(uTime * 2.1 + aPhase * 60.0), cos(uTime * 1.7 + aPhase * 40.0)) * (1.0 + uLevel * 5.0);
      // The bust reaches x=+-1.081, so the side fade has to begin well inside
      // that or the shoulder tips end on a hard edge. Dissolving them over
      // 0.90..1.15 matches how the reference feathers its outer shoulders away
      // into loose particles rather than cutting them off.
      alpha = smoothstep(-1.45, -1.2, position.y) * smoothstep(1.15, 0.9, abs(position.x));
    } else if (aKind < 1.5) {     // rings: ripple outward, faster with sound
      vec2 d = p.xy - HEAD;
      float r = length(d);
      float shift = fract(uTime * (0.05 + uSpin * 0.2 + uLevel * 0.35) + aPhase * 0.02) * 0.085;
      p.xy = HEAD + d / r * (r + shift);
      alpha = 0.55 * (1.0 - smoothstep(0.5, 1.4, r)) * (0.6 + uLevel * 1.4);
    } else if (aKind < 2.5) {     // mountains: slow flowing waves
      p.y += 0.05 * sin(p.x * 2.4 + uTime * 0.55 + aPhase * 0.6) * (1.0 + uLevel * 1.5);
      p.x += 0.02 * sin(uTime * 0.3 + p.y * 4.0);
      alpha = 0.85 * smoothstep(3.7, 2.4, abs(p.x)) * smoothstep(0.35, 1.1, abs(p.x)); // soft at both ends
    } else {                      // warm core: swells and swirls with sound
      vec2 d = p.xy - (HEAD + vec2(0.0, 0.02));
      float a = uTime * (0.4 + uSpin * 2.0) * (1.0 - length(d) * 2.0);
      d = mat2(cos(a), -sin(a), sin(a), cos(a)) * d;
      p.xy = HEAD + vec2(0.0, 0.02) + d * (0.9 + uLevel * 0.55);
      alpha = 0.2;
    }

    // Opening: particles stream up from the bright point, then fly into place.
    vec3 s = aStart;
    float swirl = uTime * 0.6;
    vec2 rel = s.xy - POINT;
    s.xy = POINT + mat2(cos(swirl * 0.2), -sin(swirl * 0.2), sin(swirl * 0.2), cos(swirl * 0.2)) * rel;
    float m = smoothstep(0.0, 1.0, clamp(uMorph * 1.6 - aPhase * 0.6, 0.0, 1.0));
    p = mix(s, p, m);
    alpha = mix(0.7, alpha, m);

    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_PointSize = aSize * uScale / -mv.z;
    gl_Position = projectionMatrix * mv;
    vColor = aColor;
    vAlpha = alpha;
  }
`;

const fragmentShader = /* glsl */`
  uniform vec3 uTint;
  varying vec3 vColor;
  varying float vAlpha;
  void main() {
    float d = length(gl_PointCoord - 0.5);
    float a = smoothstep(0.5, 0.0, d) * vAlpha;
    if (a < 0.01) discard;
    gl_FragColor = vec4(vColor * uTint * a, a);
  }
`;

// `soft` trades the shared gradient's bright plateau for a fast decay: the core
// still reads hot, but the halo spreads four times further. The chest point
// needs that or it renders as a small opaque disc; the wide body wash and the
// face glow are better served by the plateau.
function glowTexture(rgb, soft = false) {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d');
  const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  if (soft) {
    grad.addColorStop(0, `rgba(${rgb},1)`);
    grad.addColorStop(0.16, `rgba(${rgb},0.78)`);
    grad.addColorStop(0.4, `rgba(${rgb},0.42)`);
    grad.addColorStop(0.7, `rgba(${rgb},0.16)`);
    grad.addColorStop(1, `rgba(${rgb},0)`);
  } else {
    grad.addColorStop(0, `rgba(${rgb},1)`);
    grad.addColorStop(0.35, `rgba(${rgb},0.35)`);
    grad.addColorStop(1, `rgba(${rgb},0)`);
  }
  g.fillStyle = grad;
  g.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}

function glowSprite(rgb, scale, x, y, z, soft = false) {
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
    map: glowTexture(rgb, soft), blending: THREE.AdditiveBlending, depthWrite: false, transparent: true,
  }));
  sprite.scale.set(scale, scale, 1);
  sprite.position.set(x, y, z);
  return sprite;
}

const TINTS = {
  idle: new THREE.Color(1, 1, 1),
  listening: new THREE.Color(1.05, 1.1, 1.15),
  thinking: new THREE.Color(1, 1, 1),
  speaking: new THREE.Color(1.15, 1.15, 1.15),
  error: new THREE.Color(1.6, 0.55, 0.55),
};

const REDUCED = typeof window !== 'undefined'
  && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

// The intro runs on this clock: comet first, then the figure assembles.
const OPEN_SECONDS = 4.8;

// The resting field of view. Kept as a named constant because three different
// places have to agree on it: the camera and the height the resize() fit solves.
const HOME_FOV = 35;

// Cut scenes. One entry is one shot — where the camera sits, what it looks at,
// its field of view, and how long it holds. Switching between shots is
// instantaneous: an edit, not a swoop. That is the difference between a
// directed opening and a camera on rails, and it is the only way a cut reads
// as a cut. `home: true` means the final framing computed by resize(), so the
// sequence lands exactly where the resting view wants to be.
const SHOTS = [
  // The bright point at the chest, where the comet is born.
  { at: 0.0, dur: 1.6, pos: [0.0, -1.16, 2.5], look: [0.0, -1.08, 0.0], fov: 36, drift: [0.04, 0.02] },
  // Three-quarter from her right as the shoulders sweep out.
  { at: 1.6, dur: 1.2, pos: [2.5, -0.55, 4.3], look: [0.0, -0.45, 0.0], fov: 33, drift: [-0.08, 0.05] },
  // Close on the head from her left, the warm face core filling the frame.
  { at: 2.8, dur: 1.1, pos: [-1.7, 0.72, 3.8], look: [0.0, 0.45, 0.0], fov: 31, drift: [0.06, -0.04] },
  // Settle front. No drift: the resting view must be perfectly still.
  { at: 3.9, dur: 0.9, home: true, fov: 35, drift: [0, 0] },
];

// The two readouts from the reference footage: assembly progress while she
// forms, then a live status line once she is up.
function makeOverlay() {
  const el = document.createElement('div');
  el.style.cssText = [
    'position:absolute', 'right:14px', 'top:47%', 'pointer-events:none',
    'font:11px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace',
    'color:#3ae3ff', 'letter-spacing:0.12em',
    'text-shadow:0 0 10px rgba(58,227,255,0.75)',
    'white-space:pre', 'opacity:0', 'transition:opacity 0.4s ease',
    'z-index:2',
  ].join(';');
  return el;
}

// Only touch the DOM when the text actually changes — this runs every frame.
function setOverlay(el, text) {
  if (el.__text === text) return;
  el.__text = text;
  el.textContent = text;
  el.style.opacity = text ? '1' : '0';
}

// getSignal() -> { level: 0..1, state: 'idle' | 'listening' | 'thinking' | 'speaking' | 'error' }
export async function createHologram(container, getSignal) {
  const reference = await loadReference();
  const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x000000, 1);
  container.appendChild(renderer.domElement);
  const assembleEl = makeOverlay();
  const statusEl = makeOverlay();
  container.appendChild(assembleEl);
  container.appendChild(statusEl);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(HOME_FOV, 1, 0.1, 50);
  camera.position.set(0, -0.15, 6);

  const material = new THREE.ShaderMaterial({
    vertexShader,
    fragmentShader,
    uniforms: {
      uTime: { value: 0 },
      uMorph: { value: 0 },
      uLevel: { value: 0 },
      uScale: { value: 400 },
      uSpin: { value: 0 },
      uJaw: { value: 0 },
      uBlink: { value: 0 },
      uScatter: { value: 0 },
      uBreath: { value: 0 },
      uTint: { value: new THREE.Color(1, 1, 1) },
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const points = new THREE.Points(buildParticles(reference), material);
  scene.add(points);

  const coreGlow = glowSprite('255,120,30', 0.3, HEAD.x, 0.04, -0.2);
  // Soft glow on the lips: brightens with the voice so you can see her speak.
  const lipGlow = glowSprite('255,150,125', 0.1, HEAD.x, MOUTH_Y, 0.22);
  const bodyGlow = glowSprite('60,150,255', 2.4, 0, 0.2, -0.4);
  // The reference's chest point is a saturated blue bloom, not a white one,
  // and it spreads wide rather than sitting as a bead.
  const point = glowSprite('80,175,255', 0.35, CHEST_POINT.x, CHEST_POINT.y, 0.3, true);
  scene.add(bodyGlow, coreGlow, lipGlow, point);

  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.28, 0.4, 0.62);
  composer.addPass(bloom);

  // The resting framing: straight on, pulled back far enough that a tall phone
  // still shows the whole bust. Every cut departs from here and returns to it.
  const homePos = new THREE.Vector3(0, -0.15, 6);
  const homeTarget = new THREE.Vector3();

  // uScale turns a particle's size into screen pixels and depends on the field
  // of view, so a cut that changes fov has to recompute it — otherwise the
  // figure would appear to swell every time the camera moves in closer.
  function applyProjection(w, h) {
    camera.updateProjectionMatrix();
    material.uniforms.uScale.value =
      (h * renderer.getPixelRatio()) / (2 * Math.tan((camera.fov * Math.PI) / 360));
  }

  function resize() {
    const w = container.clientWidth || 1;
    const h = container.clientHeight || 1;
    renderer.setSize(w, h, false);
    composer.setSize(w, h);
    camera.aspect = w / h;
    // The baked bust measures 1.081 half-wide and 0.971 half-tall about
    // y = -0.15, which is exactly where the camera rests — so height nearly
    // sets the distance on its own. The second term only bites on a narrow
    // container, where it backs off far enough to keep the head whole and lets
    // the shoulders run past the edge, the way they do in the reference
    // framing. (It used to be a flat 6, tuned for a point cloud whose
    // shoulders reached x=+-3; with the corrected bake that left the figure
    // floating small in the middle of the frame.)
    const tan = Math.tan((HOME_FOV * Math.PI) / 360);
    homePos.z = Math.max((0.971 * 1.06) / tan, (0.47 * 1.12) / (tan * camera.aspect));
    // Looking straight down -Z gives the camera the same orientation it has
    // with no lookAt at all; only the distance is being solved here.
    homeTarget.set(homePos.x, homePos.y, homePos.z - 1);
    applyProjection(w, h);
  }
  resize();
  const observer = new ResizeObserver(resize);
  observer.observe(container);

  const clock = new THREE.Clock();
  const opened = performance.now();
  let level = 0;
  let spin = 0;
  let scatter = 0;
  let nextBlink = 2;
  let raf = 0;
  // Mood tints the whole figure (warm when upbeat, cool when low) and sets how lively it breathes;
  // gaze (from the webcam) turns the head a little toward you.
  const feel = { valence: 0.2, energy: 0.5, gx: 0, gy: 0, rx: 0, ry: 0, room: 0.5, glow: 1 };
  const moodTint = new THREE.Color(1, 1, 1);
  const goalTint = new THREE.Color();

  function frame() {
    raf = requestAnimationFrame(frame);
    const t = clock.getElapsedTime();
    const sig = getSignal() || {};
    level += ((sig.level || 0) - level) * 0.2;
    spin += ((sig.state === 'thinking' ? 1 : 0) - spin) * 0.05;
    const since = (performance.now() - opened) / 1000;
    const morph = smooth(1.6, OPEN_SECONDS, since); // comet first, then the humanoid forms
    const u = material.uniforms;
    u.uTime.value = t;
    u.uMorph.value = morph;
    u.uLevel.value = level;
    u.uSpin.value = spin;
    // Mouth follows the voice; a quick blink every few seconds; slow breathing.
    u.uJaw.value = sig.state === 'speaking' ? Math.min(1, level * 1.6) : 0;
    if (t > nextBlink) nextBlink = t + 2.5 + Math.random() * 3.5;
    u.uBlink.value = Math.max(0, 1 - Math.abs(nextBlink - t - 0.08) / 0.08);
    u.uBreath.value = Math.sin(t * (0.9 + feel.energy * 0.7));
    scatter += ((sig.state === 'thinking' ? 1 : 0) - scatter) * (sig.state === 'thinking' ? 0.03 : 0.08);
    u.uScatter.value = scatter * morph;
    const v = feel.valence;
    moodTint.setRGB(1 + 0.12 * Math.max(0, v) - 0.1 * Math.max(0, -v), 1 + 0.02 * v, 1 - 0.1 * Math.max(0, v) + 0.12 * Math.max(0, -v));
    // Dark room: ease the glow off so it is not glaring; bright room: lift it a little so it stays visible.
    feel.glow += ((0.7 + 0.5 * Math.min(1, feel.room * 1.6)) - feel.glow) * 0.03;
    goalTint.copy(TINTS[sig.state] || TINTS.idle).multiply(moodTint).multiplyScalar(feel.glow);
    u.uTint.value.lerp(goalTint, 0.08);
    feel.ry += (feel.gx * 0.22 - feel.ry) * 0.06;
    feel.rx += (feel.gy * 0.1 - feel.rx) * 0.06;
    points.rotation.y = feel.ry;
    points.rotation.x = feel.rx;
    const breathe = 0.5 + 0.5 * Math.sin(t * 1.3);
    coreGlow.material.opacity = morph * (0.52 + 0.12 * breathe + level * 0.1);
    coreGlow.scale.setScalar(0.72 + level * 0.12);
    const speaking = sig.state === 'speaking';
    lipGlow.material.opacity = morph * (0.1 + (speaking ? Math.min(1, level * 1.6) * 0.85 : 0));
    lipGlow.scale.setScalar(0.07 + (speaking ? level * 0.1 : 0));
    bodyGlow.material.opacity = 0.05 + morph * 0.06 + level * 0.12;
    point.material.opacity = 0.9;
    // Sized against the bust rather than a fixed screen fraction: at the fitted
    // distance it lands at roughly an eighth of the figure's width, which is
    // how large the bloom reads in the reference footage.
    point.scale.setScalar(0.32 + 0.07 * breathe + level * 0.22);

    // ---- cut scenes: one shot at a time, switching instantly ----
    // With reduced motion the shot list is never consulted and the camera just
    // sits at its resting framing, so the intro stays a single still view.
    let shot = null;
    if (!REDUCED) {
      for (let i = 0; i < SHOTS.length; i += 1) {
        if (since >= SHOTS[i].at && since < SHOTS[i].at + SHOTS[i].dur) { shot = SHOTS[i]; break; }
      }
    }
    if (shot) {
      const held = (since - shot.at) / shot.dur; // 0..1 across this shot
      if (shot.home) {
        camera.position.copy(homePos);
        camera.lookAt(homeTarget);
      } else {
        camera.position.set(
          shot.pos[0] + shot.drift[0] * held,
          shot.pos[1] + shot.drift[1] * held,
          shot.pos[2],
        );
        camera.lookAt(shot.look[0], shot.look[1], shot.look[2]);
      }
      if (camera.fov !== shot.fov) {
        camera.fov = shot.fov;
        applyProjection(container.clientWidth || 1, container.clientHeight || 1);
      }
    } else {
      camera.position.copy(homePos);
      camera.lookAt(homeTarget);
      if (camera.fov !== HOME_FOV) {
        camera.fov = HOME_FOV;
        applyProjection(container.clientWidth || 1, container.clientHeight || 1);
      }
    }

    // ---- readouts ----
    if (since < OPEN_SECONDS) {
      // Progress through the assembly sequence — which is exactly what the
      // number claims to be. It is deliberately not a count of particles
      // placed, because nothing measures that.
      const pct = Math.min(100, Math.round((since / OPEN_SECONDS) * 100));
      setOverlay(assembleEl, `ASSEMBLING... ${pct}%`);
      setOverlay(statusEl, '');
    } else {
      setOverlay(assembleEl, '');
      const busy = sig.state && sig.state !== 'idle';
      setOverlay(statusEl, busy
        ? `STATUS: ${sig.state.toUpperCase()} INTENSITY: ${level > 0.6 ? 'HIGH' : level > 0.25 ? 'MED' : 'LOW'}`
        : '');
    }

    bloom.strength = 0.35 + level * 0.25;
    composer.render();
  }
  frame();

  return {
    setMood(m) { if (m) { feel.valence = Number(m.valence) || 0; feel.energy = Number(m.energy) || 0.5; } },
    setAmbient(level) { feel.room = Math.max(0, Math.min(1, Number(level) || 0)); },
    setGaze(x, y) { feel.gx = Math.max(-1, Math.min(1, x || 0)); feel.gy = Math.max(-1, Math.min(1, y || 0)); },
    isOpening() { return (performance.now() - opened) / 1000 < OPEN_SECONDS; },
    dispose() {
      cancelAnimationFrame(raf);
      observer.disconnect();
      points.geometry.dispose();
      material.dispose();
      [coreGlow, bodyGlow, lipGlow, point].forEach((s) => { s.material.map.dispose(); s.material.dispose(); });
      composer.dispose?.();
      renderer.dispose();
      container.replaceChildren();
    },
  };
}
