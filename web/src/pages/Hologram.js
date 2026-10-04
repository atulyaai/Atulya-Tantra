// Atulya's face: a holographic particle humanoid (three.js).
//
// It opens as a comet-like stream of particles rising from a bright point,
// then the particles fly into a glowing bust with contour lines, a warm core
// in the head, ripple rings behind it and flowing particle "mountains" on both
// sides. Everything pulses with the live sound level (your voice while it
// listens, its own voice while it speaks).
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';

const HEAD = { x: 0, y: 0.45, rx: 0.3, ry: 0.4 };
const CHEST_POINT = { x: 0, y: -1.08 };
const KIND = { body: 0, ring: 1, wave: 2, core: 3 };
const BLUE = [0.25, 0.62, 1.0];
const DIM = [0.13, 0.36, 0.7]; // contour lines: dimmer, so the many particles don't wash out
const ICE = [0.6, 0.85, 1.0];
const GOLD = [1.0, 0.62, 0.18];
const ORANGE = [1.0, 0.45, 0.08];

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

const SKIN = [0.12, 0.3, 0.6];
const HEAD_FILE_SCALE = 8000; // see web/bake_hologram_head.py
const MESH_SCALE = 3.2;
const MESH_Y = 0.5; // eye level in the scene

async function loadHead() {
  const res = await fetch('/hologram-head.bin');
  if (!res.ok) throw new Error(`head model missing (${res.status})`);
  const buf = await res.arrayBuffer();
  const n = new DataView(buf).getUint32(0, true);
  return { n, data: new Int16Array(buf, 4, n * 13) };
}

function buildParticles(head) {
  const deform = []; // per particle: jaw xyz, "aa" xyz, blink xyz (zero for non-face particles)
  const target = [];
  const start = [];
  const color = [];
  const size = [];
  const kind = [];
  const phase = [];
  let fromMesh = false;
  function add(p, c, sz, k, s = Math.random()) {
    target.push(p[0], p[1], p[2]);
    start.push(...cometStart(s));
    color.push(c[0], c[1], c[2]);
    size.push(sz);
    kind.push(k);
    phase.push(Math.random());
    if (!fromMesh) deform.push(0, 0, 0, 0, 0, 0, 0, 0, 0);
  }

  if (head) {
    // A real human head and shoulders, baked from a CC0 3D scan, as contour lines.
    const { n, data } = head;
    for (let i = 0; i < n; i += 1) {
      const o = i * 13;
      const v = (k) => data[o + k] / HEAD_FILE_SCALE * MESH_SCALE;
      const region = data[o + 12];
      const fx = Math.abs(data[o] / HEAD_FILE_SCALE);
      const fy = data[o + 1] / HEAD_FILE_SCALE;
      // Head, neck and shoulders only: drop the arms, thin the skin so the face isn't washed out.
      if (fx > 0.24 || (fx > 0.17 && fy < -0.4)) continue;
      if (Math.random() < (region === 1 ? 0.85 : region === 2 ? 0.5 : 0.55)) continue;
      const c = region === 1 ? ICE : region === 2 ? BLUE : SKIN;
      fromMesh = true;
      add([v(0), v(1) + MESH_Y, v(2)], c, region === 1 ? rand(0.008, 0.012) : rand(0.007, 0.011), KIND.body);
      fromMesh = false;
      deform.push(v(3), v(4), v(5), v(6), v(7), v(8), v(9), v(10), v(11));
    }
  } else {
    // Head: horizontal contour lines.
    for (let y = HEAD.y - HEAD.ry; y <= HEAD.y + HEAD.ry; y += 0.018) {
      const w = halfWidth(y);
      const n = Math.floor(w * 120);
      for (let i = 0; i < n; i += 1) {
        const x = rand(-w, w);
        const z = Math.sqrt(Math.max(0, 1 - (x / (w + 1e-6)) ** 2)) * 0.18;
        add([x, y + gauss() * 0.002, z], DIM, rand(0.01, 0.017), KIND.body);
      }
    }
    // Body: U-shaped contours around the bright point on the chest.
    for (let r = 0.06; r < 1.25; r += 0.035) {
      const n = Math.floor(r * 420);
      for (let i = 0; i < n; i += 1) {
        const a = rand(0, Math.PI);
        const x = CHEST_POINT.x + Math.cos(a) * r * 1.05;
        const y = CHEST_POINT.y + Math.sin(a) * r * 0.85;
        if (y > -0.14 || Math.abs(x) > halfWidth(y)) continue;
        add([x + gauss() * 0.003, y, 0.05], DIM, rand(0.01, 0.016), KIND.body);
      }
    }
    // Bright outline of the whole silhouette.
    for (let i = 0; i < 3000; i += 1) {
      const y = rand(-1.15, HEAD.y + HEAD.ry);
      const w = halfWidth(y);
      const side = Math.random() < 0.5 ? -1 : 1;
      add([side * w + gauss() * 0.006, y, 0.12], BLUE, rand(0.012, 0.022), KIND.body);
    }
    // Top of the head outline.
    for (let i = 0; i < 350; i += 1) {
      const a = rand(0.15, Math.PI - 0.15);
      add([HEAD.x + Math.cos(a) * HEAD.rx, HEAD.y + Math.sin(a) * HEAD.ry, 0.12], BLUE, rand(0.012, 0.022), KIND.body);
    }
  }
  // Gold strands down the neck and chest.
  for (let strand = 0; strand < 7; strand += 1) {
    const x0 = (strand - 3) * 0.025;
    for (let i = 0; i < 140; i += 1) {
      const y = rand(-0.85, 0.06);
      const x = x0 + Math.sin(y * 9 + strand) * 0.025 * (1 + (-y) * 0.8);
      add([x, y, 0.14], GOLD, rand(0.012, 0.02), KIND.body);
    }
  }
  // Warm core inside the head.
  for (let i = 0; i < 1600; i += 1) {
    add([HEAD.x + gauss() * 0.12, HEAD.y - 0.05 + gauss() * 0.12, 0.2 + gauss() * 0.05],
      Math.random() < 0.8 ? ORANGE : GOLD, rand(0.014, 0.026), KIND.core);
  }
  // Ripple rings behind the head.
  for (let ring = 0; ring < 10; ring += 1) {
    const r = 0.52 + ring * 0.085;
    const n = Math.floor(r * 520);
    for (let i = 0; i < n; i += 1) {
      const a = rand(-0.25, Math.PI + 0.25);
      add([HEAD.x + Math.cos(a) * r * 0.95, HEAD.y - 0.05 + Math.sin(a) * r, -0.1], BLUE, rand(0.01, 0.016), KIND.ring);
    }
  }
  // Flowing particle mountains on both sides.
  for (const side of [-1, 1]) {
    for (let layer = 0; layer < 6; layer += 1) {
      for (let i = 0; i < 4200; i += 1) {
        const x = side * rand(0.35, 3.8);
        const peak = smooth(3.8, 1.2, Math.abs(x)) * 0.35; // taller near the figure
        const ridge = -0.15 - layer * 0.12 + peak
          + (0.3 * Math.sin(1.3 * x + layer * 1.7) + 0.15 * Math.sin(3.1 * x + layer) + 0.07 * Math.sin(7 * x + layer * 2))
          * (0.7 + layer * 0.12);
        const fill = Math.random() < 0.45;
        const drop = fill ? rand(0, 0.55) * rand(0.3, 1) : Math.abs(gauss()) * 0.03;
        const nearRidge = drop < 0.025;
        const gold = nearRidge && (layer === 1 || layer === 3) && Math.random() < 0.6;
        const c = gold ? GOLD : nearRidge ? BLUE : DIM;
        add([x, ridge - drop, -0.25 - layer * 0.12], c, rand(0.008, gold ? 0.02 : 0.015), KIND.wave);
      }
    }
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
      alpha = smoothstep(-1.2, -0.85, position.y) * smoothstep(1.55, 1.2, abs(position.x));
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
      alpha = 0.9;
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

function glowTexture(rgb) {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d');
  const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grad.addColorStop(0, `rgba(${rgb},1)`);
  grad.addColorStop(0.35, `rgba(${rgb},0.35)`);
  grad.addColorStop(1, `rgba(${rgb},0)`);
  g.fillStyle = grad;
  g.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}

function glowSprite(rgb, scale, x, y, z) {
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
    map: glowTexture(rgb), blending: THREE.AdditiveBlending, depthWrite: false, transparent: true,
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

// getSignal() -> { level: 0..1, state: 'idle' | 'listening' | 'thinking' | 'speaking' | 'error' }
export async function createHologram(container, getSignal) {
  const head = await loadHead().catch((err) => { console.warn('Hologram head:', err); return null; });
  const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x000000, 1);
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 50);
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
  const points = new THREE.Points(buildParticles(head), material);
  scene.add(points);

  const coreGlow = glowSprite('255,120,30', 0.3, HEAD.x, HEAD.y - 0.03, -0.1);
  const bodyGlow = glowSprite('60,150,255', 2.4, 0, 0.2, -0.4);
  const point = glowSprite('200,235,255', 0.35, CHEST_POINT.x, CHEST_POINT.y, 0.3);
  scene.add(bodyGlow, coreGlow, point);

  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.7, 0.5, 0.12);
  composer.addPass(bloom);

  function resize() {
    const w = container.clientWidth || 1;
    const h = container.clientHeight || 1;
    renderer.setSize(w, h, false);
    composer.setSize(w, h);
    camera.aspect = w / h;
    // On a tall phone screen, step back so the whole bust fits.
    camera.position.z = 6 * Math.max(1, 1.15 / camera.aspect);
    camera.updateProjectionMatrix();
    material.uniforms.uScale.value = (h * renderer.getPixelRatio()) / (2 * Math.tan((camera.fov * Math.PI) / 360));
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
  function frame() {
    raf = requestAnimationFrame(frame);
    const t = clock.getElapsedTime();
    const sig = getSignal() || {};
    level += ((sig.level || 0) - level) * 0.2;
    spin += ((sig.state === 'thinking' ? 1 : 0) - spin) * 0.05;
    const since = (performance.now() - opened) / 1000;
    const morph = smooth(1.6, 4.8, since); // comet first, then the humanoid forms
    const u = material.uniforms;
    u.uTime.value = t;
    u.uMorph.value = morph;
    u.uLevel.value = level;
    u.uSpin.value = spin;
    // Mouth follows the voice; a quick blink every few seconds; slow breathing.
    u.uJaw.value = sig.state === 'speaking' ? Math.min(1, level * 1.6) : 0;
    if (t > nextBlink) nextBlink = t + 2.5 + Math.random() * 3.5;
    u.uBlink.value = Math.max(0, 1 - Math.abs(nextBlink - t - 0.08) / 0.08);
    u.uBreath.value = Math.sin(t * 1.25);
    scatter += ((sig.state === 'thinking' ? 1 : 0) - scatter) * (sig.state === 'thinking' ? 0.03 : 0.08);
    u.uScatter.value = scatter * morph;
    u.uTint.value.lerp(TINTS[sig.state] || TINTS.idle, 0.08);
    const breathe = 0.5 + 0.5 * Math.sin(t * 1.3);
    coreGlow.material.opacity = morph * (0.38 + 0.12 * breathe + level * 0.5);
    coreGlow.scale.setScalar(0.85 + level * 0.5);
    bodyGlow.material.opacity = 0.05 + morph * 0.06 + level * 0.12;
    point.material.opacity = 0.9;
    point.scale.setScalar(0.17 + 0.05 * breathe + level * 0.2);
    bloom.strength = 0.65 + level * 0.5;
    composer.render();
  }
  frame();

  return {
    isOpening() { return (performance.now() - opened) / 1000 < 4.8; },
    dispose() {
      cancelAnimationFrame(raf);
      observer.disconnect();
      points.geometry.dispose();
      material.dispose();
      [coreGlow, bodyGlow, point].forEach((s) => { s.material.map.dispose(); s.material.dispose(); });
      composer.dispose?.();
      renderer.dispose();
      container.replaceChildren();
    },
  };
}
