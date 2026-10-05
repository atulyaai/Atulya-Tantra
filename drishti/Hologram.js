// Atulya's face: a faceless holographic bust drawn only in fine particle lines, in front of flowing
// mountains and a lake of light (three.js).
//
// It opens as a comet of particles streaming up from a bright point, then the
// stream folds into a bust: dense horizontal contour lines on the head, a warm
// wavy glow where a face would be, golden veins down the neck, and nested arches
// across the shoulders and chest. The warm lines ripple with the live sound level
// (your voice while it listens, its own voice while it speaks).
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';

// Scene units: the chin sits at y = 0, the crown at y = 1.1, the bust ends at y = -0.85.
const HEAD = { x: 0, y: 0.55, rx: 0.42, ry: 0.55 };
const FACE = { y: 0.46, rx: 0.31, ry: 0.34 }; // where the warm glow lives
const NECK = { half: 0.27, flare: 0.05, base: -0.2 };
const SHOULDER = { x: 1.24, y: -0.8 };
const ORB = { x: 0, y: -0.8 };
const KIND = { body: 0, glow: 1, vein: 2, dust: 3 };
const BLUE = [0.12, 0.42, 0.95];
const DIM = [0.14, 0.4, 0.9];
const ICE = [0.55, 0.88, 1.0];
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

// Half-width of the neck at height y: it flares out towards the shoulders.
function neckHalf(y) { return NECK.half + NECK.flare * smooth(0.0, NECK.base, y); }

// Height of the shoulder line at sideways distance ax: drops quickly off the neck, then levels out.
function shoulderY(ax) {
  const x0 = neckHalf(NECK.base);
  const raw = (v) => {
    const t = Math.min(1, Math.max(0, (v - x0) / (SHOULDER.x - x0)));
    return NECK.base + (SHOULDER.y - NECK.base) * (0.62 * (1 - (1 - t) ** 1.6) + 0.38 * t ** 3);
  };
  return (raw(ax - 0.09) + 2 * raw(ax) + raw(ax + 0.09)) / 4; // averaged, so the corners are soft
}

// The outline, as a list of [x, y] points walking from the left shoulder up and over the head.
function outlinePoints(step) {
  const pts = [];
  for (let x = -SHOULDER.x; x <= -neckHalf(NECK.base); x += step) pts.push([x, shoulderY(-x)]);
  for (let y = NECK.base; y <= 0.06; y += step) pts.push([-neckHalf(y), y]);
  for (let a = 0; a <= Math.PI; a += step / 0.5) {
    // Walk the head from the chin round the left side to the crown.
    const y = HEAD.y - HEAD.ry * Math.cos(a);
    pts.push([-headHalf(y), y]);
  }
  const left = pts.slice();
  const right = left.map(([x, y]) => [-x, y]).reverse();
  return left.concat(right);
}

// Where a particle starts: a curling comet trail rising from the bright point.
function cometStart(s) {
  const spread = 0.03 + s * 0.2;
  return [
    ORB.x + Math.sin(s * 3.3 + 0.4) * 0.95 * s + gauss() * spread,
    ORB.y + s * 1.9 + gauss() * spread * 0.6,
    gauss() * spread,
  ];
}

// The world behind the bust: layered ridge lines (mountains) whose particles flow along them like rivers of
// knowledge, a rippling lake below, and slow motes of light drifting up into the sky.
const LAND = { layers: 5, span: 9.4, rows: 22 };

function buildLand() {
  const pos = [];
  const color = [];
  const size = [];
  const layer = [];
  const u = [];
  const drop = [];
  const kind = [];
  const phase = [];
  function add(z, c, sz, k, l, uu, d) {
    pos.push(0, 0, z);
    color.push(c[0], c[1], c[2]);
    size.push(sz);
    kind.push(k);
    layer.push(l);
    u.push(uu);
    drop.push(d);
    phase.push(Math.random());
  }
  for (let l = 0; l < LAND.layers; l += 1) {
    const z = -2.6 + l * 0.5;
    const near = l / (LAND.layers - 1);
    const base = [0.1 + 0.25 * near, 0.38 + 0.3 * near, 0.85 + 0.1 * near];
    // The crest of each ridge: a dense bright line.
    for (let i = 0; i < 9000; i += 1) {
      const gold = (l === 1 || l === 3) && Math.random() < 0.35;
      add(z, gold ? GOLD : lerp(base, ICE, 0.45), rand(0.007, 0.012) * (0.8 + near * 0.6), 0, l, Math.random(), 0);
    }
    // Soft hatching below the crest, so each ridge reads as a mountain and not just a line.
    for (let i = 0; i < 7000; i += 1) {
      add(z, lerp(base, [0, 0, 0], 0.35), rand(0.006, 0.011), 0, l, Math.random(), Math.pow(Math.random(), 1.6) * 0.6);
    }
  }
  // The lake: rows of ripples that grow further apart towards the viewer.
  for (let r = 0; r < LAND.rows; r += 1) {
    const t = r / (LAND.rows - 1);
    const y = 1.0 + t * t * 1.5;
    for (let i = 0; i < 3600; i += 1) {
      const gold = Math.random() < 0.06;
      add(-0.4 + t * 1.6, gold ? GOLD : lerp(DIM, ICE, 0.05 + 0.3 * t), rand(0.007, 0.013) * (0.8 + t), 1, r, Math.random(), y);
    }
  }
  // Motes of light rising from the lake into the sky.
  for (let i = 0; i < 900; i += 1) {
    add(rand(-1.5, 0.5), Math.random() < 0.55 ? GOLD : ICE, rand(0.006, 0.014), 2, 0, Math.random(), Math.random());
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
  return g;
}

const landVertex = /* glsl */`
  uniform float uTime;
  uniform float uFlow;
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
  varying vec3 vColor;
  varying float vAlpha;
  const float SPAN = ${LAND.span.toFixed(1)};

  float ridge(float x, float L) {
    float h = sin(1.1 * x + L * 1.9) * 0.5 + sin(2.6 * x + L * 3.3) * 0.28 + sin(5.7 * x + L * 0.7) * 0.1;
    float rise = 0.1 + 0.9 * smoothstep(0.3, 2.2, abs(x));       // lower in the middle, so the bust is framed
    return -0.1 - L * 0.1 + (0.95 - L * 0.1) * rise * (0.62 + h) * (1.0 + uLevel * 0.35);
  }

  void main() {
    vec3 p = position;
    vec3 col = aColor;
    float alpha = 1.0;
    float x;
    if (aKind < 0.5) {                      // mountains: particles flow along the ridge
      x = -SPAN * 0.5 + mod(aU * SPAN - uFlow * (0.1 + 0.05 * aLayer), SPAN);
      p.y = ridge(x, aLayer) - aDrop + 0.012 * sin(x * 3.0 + uTime * 0.6 + aPhase * 6.0);
      alpha = (aDrop > 0.0 ? 0.55 * (1.0 - aDrop / 0.7) : 0.7) * (0.35 + 0.65 * smoothstep(0.2, 1.1, abs(x)));
    } else if (aKind < 1.5) {               // lake: rippling rows that drift sideways
      x = -SPAN * 0.5 + mod(aU * SPAN + uFlow * (0.22 + aLayer * 0.012), SPAN);
      float w = sin(x * 2.2 + uTime * 0.9 + aLayer * 1.3) + 0.5 * sin(x * 5.5 - uTime * 1.5 + aLayer * 2.1);
      p.y = -aDrop + (0.018 + uLevel * 0.05) * w;
      float crest = pow(0.5 + 0.25 * w, 5.0);
      col += vec3(0.12, 0.25, 0.4) * crest;
      alpha = 0.5 - aLayer * 0.012 + crest;
      alpha *= (0.55 + 0.45 * smoothstep(0.0, 1.2, abs(x))) * (1.0 + 1.4 * exp(-x * x * 1.2)); // light pools under the bust
    } else {                                // motes
      x = -SPAN * 0.5 + aU * SPAN + 0.12 * sin(uTime * 0.3 + aPhase * 30.0);
      float rise = mod(aDrop + uTime * 0.025 + aPhase, 1.0);
      p.y = -0.9 + rise * 3.6;
      alpha = (0.25 + 0.6 * (0.5 + 0.5 * sin(uTime * 2.0 + aPhase * 80.0))) * smoothstep(0.0, 0.2, rise) * smoothstep(1.0, 0.7, rise);
    }
    p.x = x;
    alpha *= smoothstep(4.6, 3.4, abs(x)) * smoothstep(0.3, 1.0, uMorph);
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_PointSize = aSize * uScale / -mv.z;
    gl_Position = projectionMatrix * mv;
    vColor = col;
    vAlpha = alpha;
  }
`;

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
  const lerp3 = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
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
        const warm = hot < 0.4 ? lerp3(DIM, ORANGE, hot / 0.4) : lerp3(ORANGE, GOLD, ((hot - 0.4) / 0.6) ** 1.5);
        add([x, y, z], warm, rand(0.008, 0.013), KIND.glow, 0.25 + 0.3 * Math.random());
      } else {
        const edge = smooth(0.7, 1, Math.abs(x) / w); // the rim of each line brightens
        add([x, y, z], lerp3(DIM, ICE, edge * 0.6), rand(0.008, 0.012) * (1 + edge * 0.5), KIND.body, 0.2 + 0.2 * Math.random());
      }
    }
  }

  // Bright rim: the whole silhouette, three parallel lines fading inward, plus a lit crown.
  const rim = outlinePoints(0.0035);
  for (let layer = 0; layer < 3; layer += 1) {
    for (const [x, y] of rim) {
      const inset = layer * 0.0075;
      const dir = x === 0 ? 0 : Math.sign(x);
      const px = x - dir * inset * (y > NECK.base ? 1 : 0.4);
      const py = y - (y > NECK.base ? 0 : inset * 0.7);
      if (Math.random() < 0.82 - layer * 0.18) {
        add([px + gauss() * 0.0015, py + gauss() * 0.0015, py > 0 ? 0.04 + faceDepth(px, py) : 0.3 * (1 - Math.min(1, (px / SHOULDER.x) ** 2)) - 0.1],
          layer === 0 ? ICE : BLUE, rand(0.011, 0.019) * (1 - layer * 0.18), KIND.body, 0.1 + 0.5 * Math.random());
      }
    }
  }

  // Neck and chest: nested arches around the orb; their sides run up the neck as fine vertical lines.
  for (let r = 0.1; r < 1.36; r += 0.05) {
    const steps = Math.floor((Math.PI * r * 1.8) / 0.0048);
    for (let i = 0; i <= steps; i += 1) {
      const a = -0.3 + (i / steps) * (Math.PI + 0.6);
      const x = ORB.x + Math.cos(a) * r * 0.98;
      const y = ORB.y + Math.sin(a) * r * 1.12;
      if (y > 0.04 || y < -0.95 || Math.abs(x) > shoulderX(y) - 0.012) continue;
      add([x, y, 0.3 * (1 - Math.min(1, (x / SHOULDER.x) ** 2)) - 0.1], Math.random() < 0.1 ? ICE : DIM, rand(0.007, 0.012), KIND.body, 0.35 + 0.5 * Math.random());
    }
  }

  // Golden veins: a central stem with zigzag branches, flickering as light runs down them.
  function vein(x0, y0, x1, y1, jag, thick) {
    const len = Math.hypot(x1 - x0, y1 - y0);
    const n = Math.floor(len / 0.0035);
    const bend = rand(-1, 1) * jag;
    for (let i = 0; i < n; i += 1) {
      const t = i / n;
      const x = x0 + (x1 - x0) * t + Math.sin(t * 9 + bend * 20) * jag * 0.35;
      const y = y0 + (y1 - y0) * t;
      add([x + gauss() * 0.0012, y, 0.05], Math.random() < 0.3 ? ORANGE : GOLD, rand(0.01, 0.016) * thick, KIND.vein, 0.6 + 0.3 * t);
    }
  }
  vein(0.0, -0.04, 0.0, -0.84, 0.012, 1.1);
  for (const side of [-1, 1]) {
    for (let b = 0; b < 4; b += 1) {
      const y0 = -0.12 - b * 0.15;
      const reach = 0.1 + b * 0.02 + rand(0, 0.04);
      vein(side * 0.01, y0, side * reach, y0 + 0.13 + rand(0, 0.05), 0.03, 0.8);
      if (b < 3) vein(side * reach, y0 + 0.13, side * (reach + 0.06), y0 + 0.22, 0.02, 0.6);
    }
  }

  // Sparkle: a few stray particles drifting off the outline and above the crown.
  for (let i = 0; i < 1500; i += 1) {
    const [x, y] = rim[Math.floor(Math.random() * rim.length)];
    const away = rand(0.015, 0.14);
    add([x + gauss() * away, y + Math.abs(gauss()) * away * (y > 0 ? 1.4 : 0.5), 0.05 + gauss() * 0.05],
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

// Sideways reach of the bust at height y (used to keep the chest arches inside the shoulders).
function shoulderX(y) {
  if (y > NECK.base) return neckHalf(y);
  let lo = neckHalf(NECK.base);
  let hi = SHOULDER.x;
  for (let i = 0; i < 18; i += 1) {
    const mid = (lo + hi) / 2;
    if (shoulderY(mid) > y) lo = mid; else hi = mid;
  }
  return y < SHOULDER.y ? SHOULDER.x : (lo + hi) / 2;
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

    if (aKind < 0.5) {            // lines: breathe, shimmer, dissolve when thinking
      p.y += uBreath * (p.y + 0.9) * 0.006;
      p.x += uBreath * p.x * (p.y < -0.1 ? 0.008 : 0.0);
      alpha = smoothstep(-0.95, -0.6, p.y);
    } else if (aKind < 1.5) {     // warm face lines: ripple with the voice
      float amp = 0.006 + uLevel * 0.05;
      p.y += amp * sin(p.x * 17.0 + uTime * (2.0 + uSpin * 3.0) + p.y * 9.0);
      p.z += 0.02 * uLevel;
      col *= 0.9 + uLevel * 0.9 + 0.12 * sin(uTime * 1.4 + p.y * 6.0);
      alpha = 0.95;
    } else if (aKind < 2.5) {     // veins: light runs down them
      float run = 0.55 + 0.45 * sin(uTime * 2.2 - p.y * 7.0 + aPhase * 6.0);
      alpha = (0.35 + 0.65 * run) * smoothstep(-0.9, -0.55, p.y);
      col *= 1.0 + uLevel * 1.2;
    } else {                      // dust: twinkles and drifts up
      p.y += mod(uTime * 0.03 + aPhase, 1.0) * 0.06;
      p.x += 0.01 * sin(uTime * 0.7 + aPhase * 40.0);
      alpha = 0.25 + 0.55 * (0.5 + 0.5 * sin(uTime * 2.0 + aPhase * 80.0));
    }

    // Thinking: the lines dissolve into a drifting cloud, then pull back together.
    vec3 dir = normalize(vec3(sin(aPhase * 91.0), cos(aPhase * 57.0), sin(aPhase * 23.0)) + 0.001);
    p += dir * uScatter * (0.3 + aPhase * 0.5) + dir * uScatter * 0.06 * sin(uTime * 1.5 + aPhase * 30.0);

    // Opening: particles stream up from the bright point, then fly into place (crown and rim first).
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
  const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 50);
  camera.position.set(0, 0.15, 6);

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
  const landMaterial = new THREE.ShaderMaterial({
    vertexShader: landVertex,
    fragmentShader,
    uniforms: {
      uTime: material.uniforms.uTime, uMorph: material.uniforms.uMorph, uLevel: material.uniforms.uLevel,
      uScale: material.uniforms.uScale, uTint: material.uniforms.uTint, uFlow: { value: 0 },
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const land = new THREE.Points(buildLand(), landMaterial);
  scene.add(land);
  const points = new THREE.Points(buildParticles(), material);
  scene.add(points);

  // A soft warm glow inside the head, a cool wash behind the bust, and the bright point at the chest.
  const coreGlow = glowSprite('255,130,30', 1.1, 0, FACE.y, -0.05);
  const bodyGlow = glowSprite('40,120,255', 3.4, 0, 0.1, -0.4);
  const point = glowSprite('110,190,255', 0.5, ORB.x, ORB.y, 0.3);
  scene.add(bodyGlow, coreGlow, point);

  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.35, 0.2, 0.62);
  composer.addPass(bloom);

  function resize() {
    const w = container.clientWidth || 1;
    const h = container.clientHeight || 1;
    renderer.setSize(w, h, false);
    composer.setSize(w, h);
    camera.aspect = w / h;
    // Step back far enough that the shoulders always fit across the screen.
    camera.position.z = Math.max(6, 2.7 / (2 * Math.tan((camera.fov * Math.PI) / 360) * camera.aspect));
    camera.position.y = camera.aspect < 1 ? -0.3 : 0.0;
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
  let raf = 0;
  let flow = 0;
  let lastT = 0;
  // Mood tints the whole figure (warm when upbeat, cool when low) and sets how lively it breathes;
  // gaze (from the webcam) turns the bust a little toward you.
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
    const morph = smooth(1.2, 5.2, since); // comet first, then the bust forms
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
    points.rotation.y = feel.ry + 0.16 * Math.sin(t * 0.45);
    points.rotation.x = feel.rx;
    const breathe = 0.5 + 0.5 * Math.sin(t * 1.3);
    coreGlow.material.opacity = morph * (0.1 + 0.04 * breathe + level * 0.3);
    coreGlow.scale.setScalar(0.9 + level * 0.25);
    bodyGlow.material.opacity = 0.01 + morph * 0.025 + level * 0.06;
    // The bright point at the chest: big while the stream flows, a quiet pulse once the bust has formed.
    point.material.opacity = 1 - 0.65 * morph;
    point.scale.setScalar(0.45 - 0.2 * morph + 0.04 * breathe);
    bloom.strength = 0.5 + level * 0.3;
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
      [coreGlow, bodyGlow, point].forEach((s) => { s.material.map.dispose(); s.material.dispose(); });
      composer.dispose?.();
      renderer.dispose();
      container.replaceChildren();
    },
  };
}
