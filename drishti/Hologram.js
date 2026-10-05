// Atulya's body: a faceless holographic human drawn only in fine particle lines (three.js), standing in
// front of snow-lit mountains under a deep blue sky.
//
// It opens as a comet of particles streaming up from a bright point on the chest, then the stream folds into
// a figure: contour lines across the head with a warm wavy glow where a face would be, shoulders, arms and
// hands, a chest and a six-pack picked out in bright lines, and golden veins down the neck. Gold rivers of
// light run down the mountains behind. Everything reacts to the live sound level (your voice while it
// listens, its own voice while it speaks).
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';

// Scene units: the chin is at y = 0, the crown at 1.1, the hips fade out at -3.1.
const HEAD = { x: 0, y: 0.55, rx: 0.42, ry: 0.55 };
const FACE = { y: 0.46, rx: 0.31, ry: 0.34 }; // where the warm glow lives
const ORB = { x: 0, y: -1.05 };               // the bright point on the chest
const KIND = { body: 0, glow: 1, vein: 2, dust: 3 };
const BLUE = [0.15, 0.5, 1.0];
const DIM = [0.2, 0.6, 1.0];
const ICE = [0.7, 0.92, 1.0];
const GOLD = [1.0, 0.72, 0.15];
const ORANGE = [1.0, 0.42, 0.06];

function rand(a = 0, b = 1) { return a + Math.random() * (b - a); }
function gauss() { return (Math.random() + Math.random() + Math.random() - 1.5) / 1.5; }
function lerp(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }
function smooth(e0, e1, x) { const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0))); return t * t * (3 - 2 * t); }

// Half-width of the head at height y: a round crown, a broad rounded jaw, small ears.
function headHalf(y) {
  const k = (y - HEAD.y) / HEAD.ry;
  if (Math.abs(k) >= 1) return 0;
  const ear = 0.035 * Math.exp(-(((y - 0.5) / 0.07) ** 2));
  const round = k > 0 ? (1 - k ** 2.3) ** (1 / 2.1) : (1 - (-k) ** 2.4) ** (1 / 2.2);
  return HEAD.rx * round + ear;
}

// ── The body, as a signed distance (negative inside) ───────────────────────────────────────────────────────
// Torso: half-width by height, smoothly interpolated: neck, sloping shoulders, chest, waist, hips.
const TORSO = [
  [0.06, 0.2], [-0.12, 0.24], [-0.25, 0.34], [-0.38, 0.55], [-0.5, 0.82], [-0.7, 0.7], [-1.0, 0.68],
  [-1.5, 0.6], [-1.95, 0.5], [-2.4, 0.57], [-3.2, 0.6],
];
function torsoHalf(y) {
  if (y > TORSO[0][0] || y < TORSO[TORSO.length - 1][0]) return -1;
  for (let i = 0; i < TORSO.length - 1; i += 1) {
    const [y0, w0] = TORSO[i];
    const [y1, w1] = TORSO[i + 1];
    if (y <= y0 && y >= y1) return w0 + (w1 - w0) * smooth(y0, y1, y);
  }
  return -1;
}
function capsule(px, py, ax, ay, bx, by, ra, rb) {
  const dx = bx - ax;
  const dy = by - ay;
  const t = Math.min(1, Math.max(0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)));
  return Math.hypot(px - (ax + dx * t), py - (ay + dy * t)) - (ra + (rb - ra) * t);
}
// Right arm and hand (the left is the mirror image): deltoid, upper arm, forearm, palm, thumb and four fingers.
const FINGERS = [
  [0.98, -2.7, 1.01, -3.1, 0.034], [0.92, -2.72, 0.93, -3.18, 0.036], [0.86, -2.7, 0.85, -3.13, 0.034],
  [0.81, -2.66, 0.78, -3.0, 0.03], [1.06, -2.6, 1.17, -2.9, 0.034],
];
function bodySdf(x, y) {
  const ax = Math.abs(x);
  let d = 9;
  const w = torsoHalf(y);
  if (w > 0) {
    const e = 0.01;
    const slope = (torsoHalf(y + e) - torsoHalf(y - e)) / (2 * e);
    d = (ax - w) / Math.sqrt(1 + slope * slope);
  }
  d = Math.min(d, Math.hypot(ax - 0.93, y + 0.62) - 0.27);                               // deltoid
  d = Math.min(d, capsule(ax, y, 0.95, -0.7, 1.0, -1.85, 0.2, 0.16));                    // upper arm
  d = Math.min(d, capsule(ax, y, 1.0, -1.85, 0.93, -2.55, 0.16, 0.1));                   // forearm
  d = Math.min(d, capsule(ax, y, 0.92, -2.62, 0.91, -2.78, 0.13, 0.115));                 // palm
  for (const [x0, y0, x1, y1, r] of FINGERS) d = Math.min(d, capsule(ax, y, x0, y0, x1, y1, r, r * 0.8));
  return d;
}
const BODY_TOP = 0.04;
const BODY_BOTTOM = -3.1;

// Where a particle starts: a curling comet trail rising from the bright point.
function cometStart(s) {
  const spread = 0.04 + s * 0.3;
  return [
    ORB.x + Math.sin(s * 3.3 + 0.4) * 1.4 * s + gauss() * spread,
    ORB.y + s * 2.8 + gauss() * spread * 0.6,
    gauss() * spread,
  ];
}

// ── The mountains ──────────────────────────────────────────────────────────────────────────────────────────
const LAND = { layers: 4, span: 16 };

function buildLand() {
  const pos = [];
  const color = [];
  const size = [];
  const layer = [];
  const u = [];
  const drop = [];
  const kind = [];
  const phase = [];
  const seg = [];
  function add(z, c, sz, k, l, uu, d, s = [0, 0, 0, 0]) {
    pos.push(0, 0, z);
    color.push(c[0], c[1], c[2]);
    size.push(sz);
    kind.push(k);
    layer.push(l);
    u.push(uu);
    drop.push(d);
    phase.push(Math.random());
    seg.push(...s);
  }
  for (let l = 0; l < LAND.layers; l += 1) {
    const z = -3.4 + l * 0.9;
    const near = l / (LAND.layers - 1);
    const base = [0.15 + 0.2 * near, 0.5 + 0.25 * near, 1.0];
    // The crest of each ridge: a dense bright line of snow light.
    for (let i = 0; i < 9000; i += 1) {
      add(z, lerp(base, ICE, 0.55), rand(0.009, 0.016) * (0.8 + near * 0.5), 0, l, Math.random(), 0);
    }
    // The body of the mountain: glittering blue texture that fades down the slope.
    for (let i = 0; i < 6000; i += 1) {
      add(z, lerp(base, [0.05, 0.25, 0.9], Math.random() * 0.7), rand(0.008, 0.016), 0, l, Math.random(), Math.pow(Math.random(), 1.5) * 3.2);
    }
  }
  // Golden rivers of light running down the slopes.
  for (let i = 0; i < 16; i += 1) {
    const side = i % 2 ? 1 : -1;
    const x0 = side * rand(1.2, 3.6);
    const y0 = rand(-0.5, 0.8);
    const x1 = x0 - side * rand(0.5, 1.8);
    const y1 = y0 - rand(0.9, 1.9);
    for (let k = 0; k < 1500; k += 1) add(rand(-0.6, -0.3), Math.random() < 0.15 ? ORANGE : GOLD, rand(0.007, 0.013), 1, 0, Math.random(), 0, [x0, y0, x1, y1]);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('aColor', new THREE.Float32BufferAttribute(color, 3));
  g.setAttribute('aSize', new THREE.Float32BufferAttribute(size, 1));
  g.setAttribute('aKind', new THREE.Float32BufferAttribute(kind, 1));
  g.setAttribute('aLayer', new THREE.Float32BufferAttribute(layer, 1));
  g.setAttribute('aU', new THREE.Float32BufferAttribute(u, 1));
  g.setAttribute('aDrop', new THREE.Float32BufferAttribute(drop, 1));
  g.setAttribute('aPhase', new THREE.Float32BufferAttribute(phase, 1));
  g.setAttribute('aSeg', new THREE.Float32BufferAttribute(seg, 4));
  return g;
}

// Jagged peaks: sums of triangle waves are sharp at the top and straight on the slopes. Low in the middle so
// the figure stands clear, high at the sides. Shared by the solid slopes and the particles on their crests.
const RIDGE = /* glsl */`
  float tri(float x) { return abs(fract(x) - 0.5) * 2.0; }
  float ridge(float x0, float L, float level, float k) {
    float x = x0 * k;
    float h = (1.0 - tri(x * 0.19 + L * 0.37)) + 0.38 * (1.0 - tri(x * 0.57 + L * 0.71)) + 0.12 * (1.0 - tri(x * 1.9 + L * 0.13));
    float rise = 0.12 + 0.88 * smoothstep(1.0, 4.2, abs(x));
    return -0.75 - L * 0.4 + h * rise * (1.8 + 0.2 * L) * (1.0 + level * 0.12);
  }
`;

const landVertex = /* glsl */`
  uniform float uTime;
  uniform float uFlow;
  uniform float uK;
  uniform float uMorph;
  uniform float uLevel;
  uniform float uScale;
  attribute vec3 aColor;
  attribute float aSize;
  attribute float aKind;
  attribute float aLayer;
  attribute float aU;
  attribute float aDrop;
  attribute float aPhase;
  attribute vec4 aSeg;
  varying vec3 vColor;
  varying float vAlpha;
  const float SPAN = ${LAND.span.toFixed(1)};

  ${RIDGE}

  void main() {
    vec3 p = position;
    vec3 col = aColor;
    float alpha = 1.0;
    float x;
    if (aKind < 0.5) {                      // mountains: particles flow along the ridge
      x = -SPAN * 0.5 + mod(aU * SPAN - uFlow * (0.05 + 0.03 * aLayer), SPAN);
      p.y = ridge(x, aLayer, uLevel, uK) - aDrop;
      float sparkle = 0.6 + 0.4 * sin(uTime * 1.3 + aPhase * 60.0);
      alpha = (aDrop > 0.0 ? 0.85 * pow(1.0 - aDrop / 3.4, 1.1) * sparkle : 1.0) * (0.4 + 0.6 * smoothstep(0.4, 2.0, abs(x)));
    } else {                                // golden rivers: light runs down each strand
      float t = fract(aU - uFlow * 0.12);
      vec2 a = aSeg.xy;
      vec2 b = aSeg.zw;
      vec2 d = b - a;
      vec2 n = normalize(vec2(-d.y, d.x));
      x = mix(a.x, b.x, t) + n.x * 0.05 * sin(t * 9.0 + aPhase * 0.6);
      p.y = mix(a.y, b.y, t) + n.y * 0.05 * sin(t * 9.0 + aPhase * 0.6);
      alpha = 0.55 * smoothstep(0.0, 0.15, t) * smoothstep(1.0, 0.6, t) * (0.7 + uLevel);
    }
    p.x = x;
    alpha *= smoothstep(8.0, 6.0, abs(x)) * smoothstep(0.3, 1.0, uMorph);
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_PointSize = aSize * uScale / -mv.z;
    gl_Position = projectionMatrix * mv;
    vColor = col;
    vAlpha = alpha;
  }
`;

// Solid slopes: one dark, faceted strip per ridge, so the mountains hide what is behind them and read as mountains.
const slopeVertex = /* glsl */`
  uniform float uL;
  uniform float uK;
  uniform float uLevel;
  uniform float uMorph;
  attribute float aX;
  attribute float aSide;
  varying vec3 vHi;
  varying vec3 vLo;
  varying float vDepth;
  varying float vA;
  const float SPAN = ${LAND.span.toFixed(1)};
  ${RIDGE}
  void main() {
    float x = (aX - 0.5) * SPAN;
    float top = ridge(x, uL, uLevel, uK);
    float slope = ridge(x + 0.06, uL, uLevel, uK) - ridge(x - 0.06, uL, uLevel, uK);
    float near = uL / ${(LAND.layers - 1).toFixed(1)};
    float lit = 0.6 + 0.8 * clamp(-slope * 1.4, -0.7, 0.7);
    vHi = mix(vec3(0.05, 0.2, 0.62), vec3(0.08, 0.28, 0.82), near) * lit;
    vLo = mix(vec3(0.02, 0.06, 0.3), vec3(0.015, 0.04, 0.22), near);
    vDepth = (top + 8.0) * aSide;
    vA = smoothstep(0.3, 1.0, uMorph);
    vec4 mv = modelViewMatrix * vec4(x, mix(top, -8.0, aSide), position.z, 1.0);
    gl_Position = projectionMatrix * mv;
  }
`;
const slopeFragment = /* glsl */`
  varying vec3 vHi;
  varying vec3 vLo;
  varying float vDepth;
  varying float vA;
  void main() { gl_FragColor = vec4(mix(vHi, vLo, smoothstep(0.0, 1.8, vDepth)), vA); }
`;
function buildSlope(layer) {
  const n = 480;
  const x = [];
  const side = [];
  const pos = [];
  const index = [];
  for (let i = 0; i <= n; i += 1) {
    x.push(i / n, i / n);
    side.push(0, 1);
    pos.push(0, 0, -3.4 + layer * 0.9 - 0.02, 0, 0, -3.4 + layer * 0.9 - 0.02);
    if (i < n) index.push(2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 1, 2 * i + 3, 2 * i + 2);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('aX', new THREE.Float32BufferAttribute(x, 1));
  g.setAttribute('aSide', new THREE.Float32BufferAttribute(side, 1));
  g.setIndex(index);
  return g;
}

// ── The figure ─────────────────────────────────────────────────────────────────────────────────────────────
function buildParticles() {
  const target = [];
  const start = [];
  const color = [];
  const size = [];
  const kind = [];
  const phase = [];
  const order = []; // 0..1 how early this particle lands (lower = earlier)
  function add(p, c, sz, k, ord = Math.random()) {
    target.push(p[0], p[1], p[2]);
    start.push(...cometStart(Math.random()));
    color.push(c[0], c[1], c[2]);
    size.push(sz);
    kind.push(k);
    phase.push(Math.random());
    order.push(ord);
  }
  const bodyZ = (x, y) => 0.28 * (1 - Math.min(1, (x / 1.3) ** 2)) - 0.1 + (y > -0.1 ? 0.1 : 0);
  const faceDepth = (x, y) => 0.2 * Math.sqrt(Math.max(0, 1 - (x / (headHalf(y) + 1e-6)) ** 2));

  // Head: dense horizontal contour lines; the part inside the face ellipse glows warm and ripples.
  for (let y = 0.012; y < HEAD.y + HEAD.ry - 0.01; y += 0.0175) {
    const w = headHalf(y);
    const fk = (y - FACE.y) / FACE.ry;
    const fw = Math.abs(fk) < 1 ? FACE.rx * Math.sqrt(1 - fk * fk) : 0;
    const n = Math.floor(w * 2 / 0.0042);
    for (let i = 0; i < n; i += 1) {
      const x = -w + (i + Math.random() * 0.6) * (2 * w / n);
      const z = faceDepth(x, y);
      if (Math.abs(x) < fw) {
        const heat = 1 - (Math.hypot(x / FACE.rx, fk) ** 1.5);
        const hot = Math.max(0, heat);
        const warm = hot < 0.4 ? lerp(DIM, ORANGE, hot / 0.4) : lerp(ORANGE, GOLD, ((hot - 0.4) / 0.6) ** 1.5);
        add([x, y, z], warm, rand(0.008, 0.013), KIND.glow, 0.25 + 0.3 * Math.random());
      } else {
        const edge = smooth(0.7, 1, Math.abs(x) / w); // the rim of each line brightens
        add([x, y, z], lerp(DIM, ICE, edge * 0.6), rand(0.008, 0.012) * (1 + edge * 0.5), KIND.body, 0.2 + 0.2 * Math.random());
      }
    }
  }
  // Head rim: a bright outline, three lines fading inward, plus sparkle drifting off it.
  const rim = [];
  for (let a = 0; a <= Math.PI; a += 0.0045) {
    const y = HEAD.y - HEAD.ry * Math.cos(a);
    const w = headHalf(y);
    rim.push([-w, y], [w, y]);
  }
  for (let layer = 0; layer < 3; layer += 1) {
    for (const [x, y] of rim) {
      if (Math.random() > 0.85 - layer * 0.2) continue;
      const px = x - Math.sign(x) * layer * 0.0075;
      add([px + gauss() * 0.0015, y + gauss() * 0.0015, 0.04 + faceDepth(px, y)],
        layer === 0 ? ICE : BLUE, rand(0.011, 0.019) * (1 - layer * 0.18), KIND.body, 0.1 + 0.5 * Math.random());
    }
  }

  // Body: contour lines across torso, arms and hands; a bright rim from the signed distance.
  for (let y = BODY_TOP; y > BODY_BOTTOM; y -= 0.0175) {
    for (let x = -1.5; x <= 1.5; x += 0.0062) {
      const d = bodySdf(x, y);
      if (d >= 0) continue;
      add([x + gauss() * 0.001, y, bodyZ(x, y)], d > -0.02 ? BLUE : lerp(DIM, BLUE, 0.4),
        rand(0.007, 0.011) * (d > -0.04 ? 1.2 : 1), KIND.body, 0.3 + 0.5 * Math.random());
    }
  }
  for (let y = 0.0; y > BODY_BOTTOM; y -= 0.0042) {
    for (let x = 0; x <= 1.5; x += 0.0042) {
      const d = bodySdf(x, y);
      if (d > 0.004 || d < -0.032) continue;
      const layer = d > -0.004 ? 0 : d > -0.016 ? 1 : 2;
      for (const sx of x === 0 ? [1] : [-1, 1]) {
        if (Math.random() > 0.95 - layer * 0.18) continue;
        add([sx * x + gauss() * 0.0012, y + gauss() * 0.0012, bodyZ(x, y) + 0.04],
          layer === 0 ? ICE : layer === 1 ? lerp(BLUE, ICE, 0.35) : BLUE,
          rand(0.01, 0.017) * (1 - layer * 0.15), KIND.body, 0.1 + 0.6 * Math.random());
      }
    }
  }

  // Muscle: bright lines for the collarbones, chest, ribs, a six-pack and the hip lines.
  function stroke(fn, n, c, sz, mirror = true) {
    for (let i = 0; i <= n; i += 1) {
      const t = i / n;
      const [x, y] = fn(t);
      for (const sx of mirror && Math.abs(x) > 1e-6 ? [-1, 1] : [1]) {
        for (let k = 0; k < 2; k += 1) {
          const px = sx * x + gauss() * 0.0015;
          add([px, y + gauss() * 0.0015, bodyZ(px, y) + 0.06], c, rand(0.009, 0.015) * sz, KIND.body, 0.45 + 0.4 * Math.random());
        }
      }
    }
  }
  stroke((t) => [0.09 + t * 0.62, -0.3 - 0.12 * Math.sin(t * Math.PI * 0.9) - t * 0.1], 160, ICE, 0.9);   // collarbones
  stroke((t) => [0, -0.45 - t * 0.8], 200, ICE, 0.9, false);                                              // breastbone
  stroke((t) => [0.04 + t * 0.62, -0.78 - 0.34 * Math.sin(t * Math.PI * 0.85) * (1 - t * 0.35)], 200, ICE, 1); // lower chest
  stroke((t) => [0.04 + t * 0.52, -0.5 - t * 0.28], 120, DIM, 0.8);                                      // upper chest
  for (let r = 0; r < 3; r += 1) stroke((t) => [0.38 + t * 0.2, -1.12 - r * 0.14 - 0.05 * Math.sin(t * 3)], 40, DIM, 0.8); // ribs
  stroke((t) => [0, -1.25 - t * 1.3], 240, ICE, 1, false);                                                // centre line
  for (let r = 0; r < 4; r += 1) {                                                                        // abs: 4 grooves = 3 rows of 2
    const y0 = -1.45 - r * 0.265;
    stroke((t) => [t * 0.3, y0 + 0.035 * (t ** 2)], 90, ICE, 1);
  }
  stroke((t) => [0.3 + 0.03 * Math.sin(t * Math.PI), -1.45 - t * 0.8], 140, DIM, 0.9);                     // outer abs edge
  stroke((t) => [0.3 - t * 0.17, -2.2 - t * 0.55], 90, ICE, 0.9);                                         // hip lines
  stroke((t) => [0.7 + 0.25 * t, -0.62 - 0.22 * Math.sin(t * Math.PI)], 100, DIM, 0.8);                    // deltoid
  stroke((t) => [0.95 + 0.04 * t, -0.95 - t * 0.7], 100, DIM, 0.7);                                       // upper arm
  stroke((t) => [0.97 - 0.04 * t, -1.95 - t * 0.5], 70, DIM, 0.7);                                        // forearm

  // Golden veins: down the neck and the breastbone, flickering as light runs down them.
  function vein(x0, y0, x1, y1, jag, thick) {
    const len = Math.hypot(x1 - x0, y1 - y0);
    const n = Math.floor(len / 0.0035);
    const bend = rand(-1, 1) * jag;
    for (let i = 0; i < n; i += 1) {
      const t = i / n;
      const x = x0 + (x1 - x0) * t + Math.sin(t * 9 + bend * 20) * jag * 0.35;
      const y = y0 + (y1 - y0) * t;
      add([x + gauss() * 0.0012, y, bodyZ(x, y) + 0.08], Math.random() < 0.3 ? ORANGE : GOLD, rand(0.01, 0.016) * thick, KIND.vein, 0.6 + 0.3 * t);
    }
  }
  vein(0.0, -0.02, 0.0, -1.05, 0.012, 1.1);
  for (const side of [-1, 1]) {
    for (let b = 0; b < 4; b += 1) {
      const y0 = -0.1 - b * 0.12;
      const reach = 0.1 + b * 0.04 + rand(0, 0.04);
      vein(side * 0.01, y0, side * reach, y0 + 0.12 + rand(0, 0.05), 0.03, 0.8);
      if (b < 3) vein(side * reach, y0 + 0.12, side * (reach + 0.06), y0 + 0.2, 0.02, 0.6);
    }
  }

  // Sparkle: a few stray particles drifting off the head and shoulders.
  for (let i = 0; i < 1500; i += 1) {
    const [x, y] = rim[Math.floor(Math.random() * rim.length)];
    const away = rand(0.015, 0.14);
    add([x + gauss() * away, y + Math.abs(gauss()) * away * 1.4, 0.05 + gauss() * 0.05],
      Math.random() < 0.7 ? ICE : BLUE, rand(0.006, 0.014), KIND.dust, 0.5 + 0.5 * Math.random());
  }

  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(target, 3));
  g.setAttribute('aStart', new THREE.Float32BufferAttribute(start, 3));
  g.setAttribute('aColor', new THREE.Float32BufferAttribute(color, 3));
  g.setAttribute('aSize', new THREE.Float32BufferAttribute(size, 1));
  g.setAttribute('aKind', new THREE.Float32BufferAttribute(kind, 1));
  g.setAttribute('aPhase', new THREE.Float32BufferAttribute(phase, 1));
  g.setAttribute('aOrder', new THREE.Float32BufferAttribute(order, 1));
  return g;
}

const vertexShader = /* glsl */`
  uniform float uTime;
  uniform float uMorph;
  uniform float uLevel;
  uniform float uScale;
  uniform float uSpin;
  uniform float uScatter;
  uniform float uBreath;
  attribute vec3 aStart;
  attribute vec3 aColor;
  attribute float aSize;
  attribute float aKind;
  attribute float aPhase;
  attribute float aOrder;
  varying vec3 vColor;
  varying float vAlpha;
  const vec2 ORB = vec2(${ORB.x.toFixed(2)}, ${ORB.y.toFixed(2)});

  void main() {
    vec3 p = position;
    float alpha = 1.0;
    vec3 col = aColor;

    if (aKind < 0.5) {            // lines: the chest rises and falls with the breath; fades out at the hips
      float chest = smoothstep(-0.2, -0.9, p.y) * smoothstep(-2.0, -1.1, p.y);
      p.x += uBreath * p.x * 0.012 * chest;
      p.y += uBreath * 0.01 * smoothstep(0.0, -0.6, p.y);
      alpha = smoothstep(-3.1, -2.7, p.y);
    } else if (aKind < 1.5) {     // warm face lines: ripple with the voice
      float amp = 0.006 + uLevel * 0.05;
      p.y += amp * sin(p.x * 17.0 + uTime * (2.0 + uSpin * 3.0) + p.y * 9.0);
      p.z += 0.02 * uLevel;
      col *= 1.25 + uLevel * 0.9 + 0.12 * sin(uTime * 1.4 + p.y * 6.0);
      alpha = 0.95;
    } else if (aKind < 2.5) {     // veins: light runs down them
      float run = 0.55 + 0.45 * sin(uTime * 2.2 - p.y * 7.0 + aPhase * 6.0);
      alpha = 0.35 + 0.65 * run;
      col *= 1.0 + uLevel * 1.2;
    } else {                      // dust: twinkles and drifts up
      p.y += mod(uTime * 0.03 + aPhase, 1.0) * 0.06;
      p.x += 0.01 * sin(uTime * 0.7 + aPhase * 40.0);
      alpha = 0.25 + 0.55 * (0.5 + 0.5 * sin(uTime * 2.0 + aPhase * 80.0));
    }

    // Thinking: the lines dissolve into a drifting cloud, then pull back together.
    vec3 dir = normalize(vec3(sin(aPhase * 91.0), cos(aPhase * 57.0), sin(aPhase * 23.0)) + 0.001);
    p += dir * uScatter * (0.3 + aPhase * 0.5) + dir * uScatter * 0.06 * sin(uTime * 1.5 + aPhase * 30.0);

    // Opening: particles stream up from the bright point, then fly into place (head and rim first).
    vec3 s = aStart;
    float swirl = uTime * 0.12;
    vec2 rel = s.xy - ORB;
    s.xy = ORB + mat2(cos(swirl), -sin(swirl), sin(swirl), cos(swirl)) * rel;
    float m = smoothstep(0.0, 1.0, clamp(uMorph * 1.7 - aOrder * 0.7, 0.0, 1.0));
    p = mix(s, p, m);
    alpha = mix(0.75, alpha, m);

    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_PointSize = aSize * uScale / -mv.z;
    gl_Position = projectionMatrix * mv;
    vColor = col;
    vAlpha = alpha;
  }
`;

const fragmentShader = /* glsl */`
  uniform vec3 uTint;
  varying vec3 vColor;
  varying float vAlpha;
  void main() {
    float d = length(gl_PointCoord - 0.5);
    float a = smoothstep(0.5, 0.05, d) * vAlpha;
    if (a < 0.01) discard;
    gl_FragColor = vec4(vColor * uTint * a, a);
  }
`;

// The sky: deep navy at the top, royal blue towards the horizon.
const skyVertex = /* glsl */`
  varying vec2 vUv;
  void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }
`;
const skyFragment = /* glsl */`
  uniform float uH;
  void main() {
    float v = gl_FragCoord.y / uH;
    vec3 top = vec3(0.01, 0.02, 0.1);
    vec3 mid = vec3(0.02, 0.08, 0.38);
    vec3 low = vec3(0.03, 0.12, 0.45);
    vec3 c = mix(low, mid, smoothstep(0.0, 0.6, v));
    c = mix(c, top, smoothstep(0.55, 1.0, v));
    gl_FragColor = vec4(c, 1.0);
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
  const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x000000, 1);
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 80);
  camera.position.set(0, -0.9, 8);

  const sky = new THREE.Mesh(
    new THREE.PlaneGeometry(120, 90),
    new THREE.ShaderMaterial({ vertexShader: skyVertex, fragmentShader: skyFragment, uniforms: { uH: { value: 800 } }, depthTest: false, depthWrite: false }),
  );
  sky.position.set(0, -4, -25);
  sky.renderOrder = -10;
  scene.add(sky);

  const material = new THREE.ShaderMaterial({
    vertexShader,
    fragmentShader,
    uniforms: {
      uTime: { value: 0 },
      uMorph: { value: 0 },
      uLevel: { value: 0 },
      uScale: { value: 400 },
      uSpin: { value: 0 },
      uScatter: { value: 0 },
      uBreath: { value: 0 },
      uTint: { value: new THREE.Color(1, 1, 1) },
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const kUniform = { value: 1 }; // how much the mountains are squeezed so their peaks always fall inside the screen
  const landMaterial = new THREE.ShaderMaterial({
    vertexShader: landVertex,
    fragmentShader,
    uniforms: {
      uTime: material.uniforms.uTime, uMorph: material.uniforms.uMorph, uLevel: material.uniforms.uLevel,
      uScale: material.uniforms.uScale, uTint: material.uniforms.uTint, uFlow: { value: 0 }, uK: kUniform,
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const slopes = [];
  for (let l = 0; l < LAND.layers; l += 1) {
    const mesh = new THREE.Mesh(buildSlope(l), new THREE.ShaderMaterial({
      vertexShader: slopeVertex,
      fragmentShader: slopeFragment,
      uniforms: { uL: { value: l }, uK: kUniform, uLevel: material.uniforms.uLevel, uMorph: material.uniforms.uMorph },
      transparent: true, depthTest: false, depthWrite: false,
    }));
    mesh.renderOrder = -5 + l;
    mesh.frustumCulled = false;
    scene.add(mesh);
    slopes.push(mesh);
  }
  const land = new THREE.Points(buildLand(), landMaterial);
  scene.add(land);
  const points = new THREE.Points(buildParticles(), material);
  scene.add(points);

  // A soft warm glow inside the head and the bright point on the chest.
  const coreGlow = glowSprite('255,130,30', 1.1, 0, FACE.y, -0.05);
  const point = glowSprite('150,215,255', 0.6, ORB.x, ORB.y, 0.4);
  scene.add(coreGlow, point);

  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.35, 0.25, 0.7);
  composer.addPass(bloom);

  function resize() {
    const w = container.clientWidth || 1;
    const h = container.clientHeight || 1;
    renderer.setSize(w, h, false);
    composer.setSize(w, h);
    camera.aspect = w / h;
    // Step back far enough that the whole figure fits and the mountains show on both sides.
    const tan = Math.tan((camera.fov * Math.PI) / 360);
    camera.position.z = Math.max(8.2, 4.8 / (2 * tan * camera.aspect));
    camera.position.y = -0.95;
    camera.updateProjectionMatrix();
    material.uniforms.uScale.value = (h * renderer.getPixelRatio()) / (2 * tan);
    sky.material.uniforms.uH.value = h * renderer.getPixelRatio();
    kUniform.value = 3.6 / (tan * (camera.position.z + 2) * camera.aspect);
  }
  resize();
  const observer = new ResizeObserver(resize);
  observer.observe(container);

  const clock = new THREE.Clock();
  const opened = performance.now();
  let level = 0;
  let spin = 0;
  let scatter = 0;
  let raf = 0;
  let flow = 0;
  let lastT = 0;
  // Mood tints the whole figure (warm when upbeat, cool when low) and sets how lively it breathes;
  // gaze (from the webcam) turns the figure a little toward you.
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
    const morph = smooth(1.2, 5.2, since); // comet first, then the figure forms
    const u = material.uniforms;
    flow += (t - lastT) * (1 + level * 3 + spin * 2);
    lastT = t;
    landMaterial.uniforms.uFlow.value = flow;
    u.uTime.value = t;
    u.uMorph.value = morph;
    u.uLevel.value = level;
    u.uSpin.value = spin;
    u.uBreath.value = Math.sin(t * (0.9 + feel.energy * 0.7));
    scatter += ((sig.state === 'thinking' ? 1 : 0) - scatter) * (sig.state === 'thinking' ? 0.03 : 0.08);
    u.uScatter.value = scatter * morph;
    const v = feel.valence;
    moodTint.setRGB(1 + 0.12 * Math.max(0, v) - 0.1 * Math.max(0, -v), 1 + 0.02 * v, 1 - 0.1 * Math.max(0, v) + 0.12 * Math.max(0, -v));
    // Dark room: ease the glow off so it is not glaring; bright room: lift it a little so it stays visible.
    feel.glow += ((0.8 + 0.4 * Math.min(1, feel.room * 1.6)) - feel.glow) * 0.03;
    goalTint.copy(TINTS[sig.state] || TINTS.idle).multiply(moodTint).multiplyScalar(feel.glow);
    u.uTint.value.lerp(goalTint, 0.08);
    feel.ry += (feel.gx * 0.22 - feel.ry) * 0.06;
    feel.rx += (feel.gy * 0.1 - feel.rx) * 0.06;
    points.rotation.y = feel.ry + 0.1 * Math.sin(t * 0.45);
    points.rotation.x = feel.rx;
    const breathe = 0.5 + 0.5 * Math.sin(t * 1.3);
    coreGlow.material.opacity = morph * (0.1 + 0.04 * breathe + level * 0.3);
    coreGlow.scale.setScalar(0.9 + level * 0.25);
    // The bright point on the chest: big while the stream flows, a quiet pulse once the figure has formed.
    point.material.opacity = 1 - 0.6 * morph;
    point.scale.setScalar(0.6 - 0.3 * morph + 0.04 * breathe);
    bloom.strength = 0.35 + level * 0.3;
    composer.render();
  }
  frame();

  return {
    setMood(m) { if (m) { feel.valence = Number(m.valence) || 0; feel.energy = Number(m.energy) || 0.5; } },
    setAmbient(level) { feel.room = Math.max(0, Math.min(1, Number(level) || 0)); },
    setGaze(x, y) { feel.gx = Math.max(-1, Math.min(1, x || 0)); feel.gy = Math.max(-1, Math.min(1, y || 0)); },
    isOpening() { return (performance.now() - opened) / 1000 < 5.2; },
    dispose() {
      cancelAnimationFrame(raf);
      observer.disconnect();
      points.geometry.dispose();
      land.geometry.dispose();
      material.dispose();
      landMaterial.dispose();
      slopes.forEach((m) => { m.geometry.dispose(); m.material.dispose(); });
      sky.geometry.dispose();
      sky.material.dispose();
      [coreGlow, point].forEach((s) => { s.material.map.dispose(); s.material.dispose(); });
      composer.dispose?.();
      renderer.dispose();
      container.replaceChildren();
    },
  };
}
