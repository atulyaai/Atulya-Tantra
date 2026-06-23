import React, { useEffect, useRef, useState, useCallback } from 'react';
import { api } from '../../api.js';

const PHASES = [
  { name: 'SPIRIT', palette: ['#cc88ff', '#88aaff', '#ff88cc', '#aaffee', '#ffcc88'] },
  { name: 'WINGS',  palette: ['#ffaa44', '#ff6688', '#aa44ff', '#ff88aa', '#ffdd66'] },
  { name: 'LOTUS',  palette: ['#ff55aa', '#aa44ff', '#ff8844', '#ff44cc', '#ffaa55'] },
  { name: 'STORM',  palette: ['#44ccff', '#88ffee', '#4488ff', '#22eecc', '#88aaff'] },
  { name: 'GALAXY', palette: ['#ff88cc', '#88aaff', '#aaffcc', '#ccaaff', '#ffaadd'] },
  { name: 'VORTEX', palette: ['#ff4466', '#ffaa22', '#44ffaa', '#4488ff', '#ff44aa'] }
];

const NODES = [
  { id: 'PF', label: 'PREFRONTAL',    x: 0.78, y: 0.18, color: '#ff6644', fire: 0.55, neurons: 150, info: 'Executive function · planning' },
  { id: 'MC', label: 'MOTOR CORTEX',  x: 0.62, y: 0.28, color: '#ffaa00', fire: 0.42, neurons: 100, info: 'Movement control' },
  { id: 'SC', label: 'SENSORY CORTEX',x: 0.66, y: 0.46, color: '#ff4477', fire: 0.48, neurons: 120, info: 'Input processing' },
  { id: 'CO', label: 'CONCEPT LAYER', x: 0.86, y: 0.36, color: '#ffdd00', fire: 0.44, neurons: 160, info: 'Abstract thought' },
  { id: 'FO', label: 'FOUNDATION',    x: 0.76, y: 0.42, color: '#00ccff', fire: 0.46, neurons: 250, info: 'Core knowledge base' },
  { id: 'FL', label: 'FEATURE LAYER', x: 0.68, y: 0.66, color: '#ff8833', fire: 0.85, neurons: 100, info: 'Pattern detection' },
  { id: 'LG', label: 'LANGUAGE',      x: 0.54, y: 0.58, color: '#cc44ff', fire: 0.75, neurons: 170, info: 'NLP & generation' },
  { id: 'HC', label: 'HIPPOCAMPUS',   x: 0.80, y: 0.76, color: '#00ff88', fire: 0.35, neurons: 80,  info: 'Memory formation' },
  { id: 'BS', label: 'BRAINSTEM',     x: 0.66, y: 0.84, color: '#44ff44', fire: 0.60, neurons: 60,  info: 'Vital functions' }
];

const EDGES = [
  ['PF','MC'], ['PF','CO'], ['PF','FO'],
  ['MC','SC'], ['MC','FO'],
  ['SC','FO'], ['SC','LG'],
  ['CO','FO'], ['CO','FL'],
  ['FO','FL'], ['FO','LG'], ['FO','HC'],
  ['FL','LG'], ['FL','BS'],
  ['LG','HC'], ['HC','BS'],
  ['BS','SC']
];

function dist(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y, (a.z || 0) - (b.z || 0));
}

function recognizeGesture(lm) {
  if (!lm || lm.length < 21) return { gesture: 'NONE', fingers: 0, pinch: 0, fist: 0 };
  const tips = [8, 12, 16, 20];
  const pips = [6, 10, 14, 18];
  let fingers = 0;
  for (let i = 0; i < 4; i++) {
    const dTip = dist(lm[tips[i]], lm[0]);
    const dPip = dist(lm[pips[i]], lm[0]);
    if (dTip > dPip * 1.08) fingers++;
  }
  const thumbExt = dist(lm[4], lm[5]) > dist(lm[3], lm[5]) * 1.1;
  const total = fingers + (thumbExt ? 1 : 0);
  const pinch = Math.max(0, 1 - dist(lm[4], lm[8]) / 0.08);
  const fist = Math.max(0, 1 - total / 5);
  let g = 'POINT';
  if (pinch > 0.6) g = 'PINCH';
  else if (total >= 4) g = 'PALM';
  else if (fist > 0.7) g = 'FIST';
  else if (fingers >= 2) g = 'WAVE';
  return { gesture: g, fingers: total, pinch, fist };
}

export function HolographicSpirit() {
  const rootRef = useRef(null);
  const mainRef = useRef(null);
  const fxRef = useRef(null);
  const handRef = useRef(null);
  const camRef = useRef(null);
  const stateRef = useRef(null);
  const [cameraOn, setCameraOn] = useState(false);
  const [cameraError, setCameraError] = useState('');
  const [hudInfo, setHudInfo] = useState({ phase: 0, gesture: 'NONE', fingers: 0, status: 'INITIALIZING' });
  const [spiritPrompt, setSpiritPrompt] = useState('');
  const [spiritMessages, setSpiritMessages] = useState([
    { role: 'assistant', text: 'Holographic Spirit online. Type or use gestures to interact.' }
  ]);
  const [spiritBusy, setSpiritBusy] = useState(false);

  useEffect(() => {
    const root = rootRef.current;
    const mainC = mainRef.current;
    const fxC = fxRef.current;
    if (!root || !mainC || !fxC) return;

    let W = 0, H = 0, CX = 0, CY = 0;
    let X = null, FX = null;

    function resize() {
      W = root.clientWidth;
      H = root.clientHeight;
      mainC.width = W; mainC.height = H;
      fxC.width = W; fxC.height = H;
      CX = W / 2; CY = H / 2 - 30;
      X = mainC.getContext('2d');
      FX = fxC.getContext('2d');
    }
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(root);

    const state = {
      t: 0,
      phase: 0,
      phaseMorph: 0,
      cursor: { x: 0, y: 0 },
      mouse: { x: 0, y: 0, active: false },
      usingHand: false,
      gesture: 'NONE',
      fingers: 0,
      pinch: 0,
      fist: 0,
      handSpeed: 0,
      graphReveal: 0,
      graphTarget: 0,
      hoveredNode: null,
      selectedNode: null,
      hoveredStoryboard: -1,
      palmDebounce: false,
      fistDebounce: false
    };
    stateRef.current = state;
    state.cursor.x = CX; state.cursor.y = CY;
    state.mouse.x = CX; state.mouse.y = CY;

    // stars
    const stars = Array.from({ length: 200 }, () => ({
      x: Math.random(), y: Math.random(),
      r: Math.random() * 1.3 + 0.2,
      tw: Math.random() * Math.PI * 2,
      layer: Math.random()
    }));

    // crystals
    const crystals = Array.from({ length: 22 }, () => ({
      angle: Math.random() * Math.PI * 2,
      r: 130 + Math.random() * 180,
      drift: (Math.random() - 0.5) * 0.008,
      size: 8 + Math.random() * 18,
      phase: Math.random() * Math.PI * 2,
      color: Math.floor(Math.random() * 5)
    }));

    // ribbons
    const ribbons = Array.from({ length: 7 }, (_, i) => ({
      pts: Array.from({ length: 90 }, () => ({ x: 0, y: 0 })),
      phase: i * Math.PI * 2 / 7,
      width: 1.5 + i * 0.4,
      colorIdx: i % 5,
      speedMul: 0.8 + Math.random() * 0.4
    }));
    ribbons.forEach(rb => rb.pts.forEach(p => { p.x = CX; p.y = CY; }));

    // sphere points
    const NSPHERE = 700;
    const spherePts = [];
    for (let i = 0; i < NSPHERE; i++) {
      const phi = Math.acos(1 - 2 * (i + 0.5) / NSPHERE);
      const theta = Math.PI * (1 + Math.sqrt(5)) * (i + 0.5);
      spherePts.push({ phi, theta, size: 0.5 + Math.random() * 1.4 });
    }
    let sphRotY = 0, sphRotX = 0;

    // wisps
    const wisps = Array.from({ length: 36 }, (_, i) => ({
      angle: i * Math.PI * 2 / 36,
      r: 60 + Math.random() * 40,
      phase: Math.random() * Math.PI * 2,
      color: Math.floor(Math.random() * 5),
      size: 2 + Math.random() * 3
    }));

    // lotus petals
    const lotusPetals = Array.from({ length: 14 }, (_, i) => ({
      angle: i * Math.PI * 2 / 14,
      phase: Math.random() * Math.PI * 2
    }));

    // pulses
    const pulses = [];
    EDGES.forEach(([a, b]) => pulses.push({ a, b, t: Math.random() }));

    // bursts
    const bursts = [];
    function triggerBurst(x, y) {
      for (let i = 0; i < 20; i++) {
        const ang = Math.random() * Math.PI * 2;
        const spd = 1 + Math.random() * 4;
        bursts.push({
          x, y,
          vx: Math.cos(ang) * spd, vy: Math.sin(ang) * spd,
          life: 0, max: 0.6 + Math.random() * 0.6,
          color: Math.floor(Math.random() * 5),
          size: 1 + Math.random() * 3
        });
      }
    }

    function nextPhase() {
      state.phase = (state.phase + 1) % PHASES.length;
      state.phaseMorph = 0;
      triggerBurst(CX, CY);
    }

    function selectNode(n) {
      state.selectedNode = n;
      triggerBurst(n.x * W, n.y * H);
    }

    // input handlers
    function onMouseMove(e) {
      const rect = root.getBoundingClientRect();
      state.mouse.x = e.clientX - rect.left;
      state.mouse.y = e.clientY - rect.top;
      state.mouse.active = true;
    }
    function onMouseLeave() { state.mouse.active = false; }
    function onMouseDown(e) {
      const rect = root.getBoundingClientRect();
      const x = e.clientX - rect.left, y = e.clientY - rect.top;
      triggerBurst(x, y);
      if (state.hoveredNode) selectNode(state.hoveredNode);
    }
    function onTouchMove(e) {
      if (e.touches.length) {
        const rect = root.getBoundingClientRect();
        state.mouse.x = e.touches[0].clientX - rect.left;
        state.mouse.y = e.touches[0].clientY - rect.top;
        state.mouse.active = true;
      }
      e.preventDefault();
    }
    function onTouchStart(e) {
      if (e.touches.length) {
        const rect = root.getBoundingClientRect();
        state.mouse.x = e.touches[0].clientX - rect.left;
        state.mouse.y = e.touches[0].clientY - rect.top;
        state.mouse.active = true;
      }
    }
    function onClickStoryboard(idx) {
      if (state.phase === idx) {
        nextPhase();
      } else {
        state.phase = idx;
        state.phaseMorph = 0;
        triggerBurst(CX, CY);
      }
    }

    root.addEventListener('mousemove', onMouseMove);
    root.addEventListener('mouseleave', onMouseLeave);
    root.addEventListener('mousedown', onMouseDown);
    root.addEventListener('touchmove', onTouchMove, { passive: false });
    root.addEventListener('touchstart', onTouchStart, { passive: true });

    // public API for hand tracking
    root._holographicState = state;
    root._holographicTriggerBurst = triggerBurst;
    root._holographicNextPhase = nextPhase;
    root._holographicResize = resize;
    root._holographicSelectNode = selectNode;

    // ─── DRAW FUNCTIONS ───
    function drawBg() {
      X.fillStyle = '#000008';
      X.fillRect(0, 0, W, H);
      stars.forEach(s => {
        s.tw += 0.02;
        const a = 0.2 + 0.4 * Math.sin(s.tw);
        const r = s.r * (1 + s.layer * 0.5);
        X.beginPath();
        X.arc(s.x * W, s.y * H, r, 0, Math.PI * 2);
        X.fillStyle = `rgba(180,160,255,${a})`;
        X.fill();
      });
      const g = X.createRadialGradient(CX, CY, 0, CX, CY, 260);
      const pal = PHASES[state.phase].palette;
      g.addColorStop(0, pal[0] + '22');
      g.addColorStop(0.5, '#10001a55');
      g.addColorStop(1, 'transparent');
      X.fillStyle = g;
      X.beginPath(); X.arc(CX, CY, 260, 0, Math.PI * 2); X.fill();
    }

    function drawCrystals(time) {
      const pal = PHASES[state.phase].palette;
      crystals.forEach(c => {
        c.angle += c.drift + (state.cursor.x - CX) * 0.00004;
        const cx2 = CX + Math.cos(c.angle) * c.r;
        const cy2 = CY + Math.sin(c.angle) * c.r * 0.6;
        const pls = 0.7 + 0.3 * Math.sin(time * 1.5 + c.phase);
        const col = pal[c.color];
        X.save();
        X.translate(cx2, cy2);
        X.rotate(c.angle + time * 0.4);
        X.beginPath();
        X.moveTo(0, -c.size * pls);
        X.lineTo(c.size * 0.4, 0);
        X.lineTo(0, c.size * pls);
        X.lineTo(-c.size * 0.4, 0);
        X.closePath();
        X.strokeStyle = col + 'cc';
        X.lineWidth = 1.2;
        X.stroke();
        X.fillStyle = col + '33';
        X.fill();
        X.restore();
        const gl = X.createRadialGradient(cx2, cy2, 0, cx2, cy2, c.size * 2.4);
        gl.addColorStop(0, col + '44');
        gl.addColorStop(1, 'transparent');
        X.fillStyle = gl;
        X.beginPath(); X.arc(cx2, cy2, c.size * 2.4, 0, Math.PI * 2); X.fill();
      });
    }

    function drawSphere(time) {
      const pal = PHASES[state.phase].palette;
      const handInfluence = state.usingHand ? (state.cursor.x - CX) / W : 0;
      sphRotY += 0.008 + handInfluence * 0.02;
      const dx = (state.cursor.x - CX) / W * 0.5;
      sphRotX += (dx * 0.03 - sphRotX) * 0.05;
      const compress = 1 - state.fist * 0.35;
      const baseR = 110 * compress * (1 - state.phaseMorph * 0.3);

      const projected = spherePts.map((p, i) => {
        const wobble = 0.85 + 0.15 * Math.sin(time * 1.2 + i * 0.1);
        let x = baseR * Math.sin(p.phi) * Math.cos(p.theta + sphRotY) * wobble;
        let y = baseR * Math.cos(p.phi) * wobble;
        let z = baseR * Math.sin(p.phi) * Math.sin(p.theta + sphRotY) * wobble;
        const cosX = Math.cos(sphRotX), sinX = Math.sin(sphRotX);
        const y2 = y * cosX - z * sinX;
        const z2 = y * sinX + z * cosX;
        const depth = (z2 + baseR) / (2 * baseR);
        return { sx: CX + x, sy: CY + y2, depth, i };
      }).sort((a, b) => a.depth - b.depth);

      projected.forEach(p => {
        const a = 0.15 + p.depth * 0.85;
        const r = p.i % 7 === 0 ? (0.8 + p.depth * 1.8) : (0.5 + p.depth * 1.2);
        const colIdx = p.depth > 0.7 ? 0 : (p.depth > 0.4 ? 1 : 2);
        const col = pal[colIdx];
        const alphaHex = Math.floor(a * 255).toString(16).padStart(2, '0');
        X.beginPath();
        X.arc(p.sx, p.sy, r, 0, Math.PI * 2);
        X.fillStyle = col + alphaHex;
        X.fill();
        if (p.i % 23 === 0) {
          X.beginPath();
          X.arc(p.sx, p.sy, r * 2.5, 0, Math.PI * 2);
          X.fillStyle = col + '33';
          X.fill();
        }
      });

      const rx = baseR * 1.4, ry = baseR * 0.3;
      X.beginPath();
      X.ellipse(CX, CY, rx, ry, -0.15, 0, Math.PI * 2);
      X.strokeStyle = pal[0] + '44';
      X.lineWidth = 1.5;
      X.stroke();
    }

    function drawRibbons(time) {
      const pal = PHASES[state.phase].palette;
      ribbons.forEach(rib => {
        const spd = 0.025 * rib.speedMul * (state.gesture === 'FIST' ? 2 : 1);
        const a = time * spd * 2 + rib.phase;
        const r2 = 70 + Math.sin(time * 0.7 + rib.phase) * 40;
        let hx = CX + Math.cos(a) * r2 + Math.cos(a * 2.3 + rib.phase) * 30;
        let hy = CY + Math.sin(a) * r2 * 0.7 + Math.sin(a * 1.7) * 20;
        hx += (state.cursor.x - CX) * 0.12 * Math.sin(rib.phase);
        hy += (state.cursor.y - CY) * 0.10 * Math.cos(rib.phase);
        rib.pts.unshift({ x: hx, y: hy });
        rib.pts.pop();
        X.beginPath();
        X.moveTo(rib.pts[0].x, rib.pts[0].y);
        for (let i = 1; i < rib.pts.length - 1; i++) {
          const mx2 = (rib.pts[i].x + rib.pts[i + 1].x) / 2;
          const my2 = (rib.pts[i].y + rib.pts[i + 1].y) / 2;
          X.quadraticCurveTo(rib.pts[i].x, rib.pts[i].y, mx2, my2);
        }
        const col = pal[rib.colorIdx];
        const grd = X.createLinearGradient(rib.pts[0].x, rib.pts[0].y, rib.pts[40].x, rib.pts[40].y);
        grd.addColorStop(0, col + 'ff');
        grd.addColorStop(0.3, col + '88');
        grd.addColorStop(1, col + '00');
        X.strokeStyle = grd;
        X.lineWidth = rib.width * (state.gesture === 'FIST' ? 1.8 : 1);
        X.stroke();
      });
    }

    function drawEntity(time) {
      const pal = PHASES[state.phase].palette;
      const br = 0.9 + 0.1 * Math.sin(time * 0.04);
      const ph = state.phase;

      if (ph === 0 || ph === 3) {
        for (let i = 0; i < 3; i++) {
          const r = (28 + i * 14) * br;
          const off = time * 0.8 + i * Math.PI / 3;
          X.beginPath();
          X.ellipse(CX + Math.cos(off) * 6, CY + Math.sin(off) * 4, r, r * 0.4 + i * 3, off, 0, Math.PI * 2);
          X.strokeStyle = pal[i] + (i === 0 ? 'cc' : '66');
          X.lineWidth = 1.5 - i * 0.3;
          X.stroke();
        }
        const haloR = 55 * br;
        X.beginPath(); X.arc(CX, CY - 10, haloR, 0, Math.PI * 2);
        X.strokeStyle = pal[0] + 'aa'; X.lineWidth = 2; X.stroke();
        const bodyG = X.createRadialGradient(CX, CY, 0, CX, CY, 60);
        bodyG.addColorStop(0, pal[0] + '55');
        bodyG.addColorStop(0.5, pal[1] + '22');
        bodyG.addColorStop(1, 'transparent');
        X.fillStyle = bodyG;
        X.beginPath(); X.ellipse(CX, CY, 40, 70, 0, 0, Math.PI * 2); X.fill();
        for (let i = 0; i < 8; i++) {
          const a = i * Math.PI / 4 + time * 0.3;
          const r = 50 + 20 * Math.sin(time + i);
          const ex = CX + Math.cos(a) * r, ey = CY + Math.sin(a) * r * 0.6;
          X.beginPath(); X.moveTo(CX, CY);
          X.quadraticCurveTo(CX + Math.cos(a + 0.5) * r * 0.6, CY + Math.sin(a + 0.5) * r * 0.4, ex, ey);
          X.strokeStyle = pal[i % 5] + '55'; X.lineWidth = 0.8; X.stroke();
        }
      }

      if (ph === 2) {
        lotusPetals.forEach((p, i) => {
          p.phase += 0.012;
          const r = 60 + 20 * Math.sin(p.phase) * br;
          const px2 = CX + Math.cos(p.angle) * r;
          const py2 = CY + Math.sin(p.angle) * r * 0.5;
          const cpx = CX + Math.cos(p.angle + 0.4) * r * 0.7;
          const cpy = CY + Math.sin(p.angle + 0.4) * r * 0.35;
          X.beginPath(); X.moveTo(CX, CY);
          X.quadraticCurveTo(cpx, cpy, px2, py2);
          X.quadraticCurveTo(cpx - 5, cpy + 5, CX, CY);
          X.strokeStyle = pal[i % 5] + 'bb'; X.lineWidth = 1.5; X.stroke();
          X.fillStyle = pal[i % 5] + '22'; X.fill();
        });
        const cg = X.createRadialGradient(CX, CY, 0, CX, CY, 35);
        cg.addColorStop(0, pal[0] + '99');
        cg.addColorStop(0.6, pal[1] + '44');
        cg.addColorStop(1, 'transparent');
        X.fillStyle = cg;
        X.beginPath(); X.arc(CX, CY, 35, 0, Math.PI * 2); X.fill();
      }

      if (ph === 1) {
        for (let s = -1; s <= 1; s += 2) {
          for (let i = 0; i < 5; i++) {
            const flap = Math.sin(time * 1.2 + i * 0.3) * 0.3 * s;
            const wa = s * (0.2 + i * 0.18) + flap;
            const wr = 80 + i * 25;
            const wx = CX + Math.cos(wa) * wr * s;
            const wy = CY + Math.sin(Math.abs(wa)) * (30 + i * 8) - i * 10;
            const cpx = CX + Math.cos(wa + 0.6 * s) * wr * 0.6 * s;
            const cpy = CY + Math.sin(Math.abs(wa + 0.3)) * (20 + i * 5);
            X.beginPath(); X.moveTo(CX, CY);
            X.quadraticCurveTo(cpx, cpy, wx, wy);
            X.quadraticCurveTo(cpx * 0.5, cpy + 20, CX, CY + 30);
            X.strokeStyle = pal[i % 5] + 'cc'; X.lineWidth = 1.8 - i * 0.2; X.stroke();
            X.fillStyle = pal[i % 5] + (i < 2 ? '33' : '18'); X.fill();
          }
        }
      }

      if (ph === 4) {
        for (let arm = 0; arm < 4; arm++) {
          X.beginPath();
          for (let t = 0; t < 60; t++) {
            const a = arm * Math.PI / 2 + t * 0.04 + time * 0.1;
            const r = t * 1.2;
            const px = CX + Math.cos(a) * r;
            const py = CY + Math.sin(a) * r * 0.5;
            if (t === 0) X.moveTo(px, py); else X.lineTo(px, py);
          }
          X.strokeStyle = pal[arm % 5] + '66';
          X.lineWidth = 1.5;
          X.stroke();
        }
      }

      if (ph === 5) {
        X.beginPath();
        for (let t = 0; t < 200; t++) {
          const a = t * 0.15 + time * 0.3;
          const r = t * 0.5;
          const px = CX + Math.cos(a) * r;
          const py = CY + Math.sin(a) * r;
          if (t === 0) X.moveTo(px, py); else X.lineTo(px, py);
        }
        X.strokeStyle = pal[1] + '88';
        X.lineWidth = 2;
        X.stroke();
      }

      const core = X.createRadialGradient(CX, CY, 0, CX, CY, 22);
      core.addColorStop(0, '#ffffff');
      core.addColorStop(0.3, pal[0] + 'ff');
      core.addColorStop(0.7, pal[1] + '88');
      core.addColorStop(1, 'transparent');
      X.fillStyle = core;
      X.beginPath(); X.arc(CX, CY, 22, 0, Math.PI * 2); X.fill();
    }

    function drawWisps(time) {
      const pal = PHASES[state.phase].palette;
      wisps.forEach(w => {
        w.phase += 0.015;
        const r = w.r + Math.sin(w.phase) * 20;
        const wx = CX + Math.cos(w.angle + time * 0.1) * r;
        const wy = CY + Math.sin(w.angle + time * 0.1) * r * 0.5;
        const a = 0.5 + 0.5 * Math.sin(w.phase);
        const alphaHex = Math.floor(a * 180).toString(16).padStart(2, '0');
        X.beginPath();
        X.arc(wx, wy, w.size * a, 0, Math.PI * 2);
        X.fillStyle = pal[w.color] + alphaHex;
        X.fill();
      });
    }

    function drawBursts(dt) {
      const pal = PHASES[state.phase].palette;
      for (let i = bursts.length - 1; i >= 0; i--) {
        const p = bursts[i];
        p.life += dt;
        p.x += p.vx; p.y += p.vy; p.vy += 0.05;
        const frac = 1 - p.life / p.max;
        if (frac <= 0) { bursts.splice(i, 1); continue; }
        const alphaHex = Math.floor(frac * 255).toString(16).padStart(2, '0');
        X.beginPath();
        X.arc(p.x, p.y, p.size * frac, 0, Math.PI * 2);
        X.fillStyle = pal[p.color] + alphaHex;
        X.fill();
      }
    }

    function drawGraph(time) {
      state.graphReveal += (state.graphTarget - state.graphReveal) * 0.04;
      if (state.graphReveal < 0.01) {
        state.hoveredNode = null;
        return;
      }
      const pal = PHASES[state.phase].palette;
      const baseX = W * 0.78;
      const baseY = H * 0.5;
      const scale = Math.min(W, H) * 0.18;
      const yScale = state.usingHand ? 1 + (state.cursor.y / H - 0.5) * 0.4 : 1;

      X.save();
      X.translate(baseX, baseY);
      X.scale(state.graphReveal * yScale, state.graphReveal * yScale);

      EDGES.forEach(([aid, bid]) => {
        const a = NODES.find(n => n.id === aid);
        const b = NODES.find(n => n.id === bid);
        const ax = a.x * scale - scale * 0.5, ay = a.y * scale - scale * 0.5;
        const bx = b.x * scale - scale * 0.5, by = b.y * scale - scale * 0.5;
        X.beginPath();
        X.moveTo(ax, ay); X.lineTo(bx, by);
        X.strokeStyle = pal[1] + '44';
        X.lineWidth = 0.7;
        X.stroke();
      });

      pulses.forEach(p => {
        p.t = (p.t + 0.012) % 1;
        if (Math.random() < 0.005) {
          const e = EDGES[Math.floor(Math.random() * EDGES.length)];
          pulses.push({ a: e[0], b: e[1], t: 0 });
        }
        const a = NODES.find(n => n.id === p.a);
        const b = NODES.find(n => n.id === p.b);
        const ax = a.x * scale - scale * 0.5, ay = a.y * scale - scale * 0.5;
        const bx = b.x * scale - scale * 0.5, by = b.y * scale - scale * 0.5;
        const px = ax + (bx - ax) * p.t, py = ay + (by - ay) * p.t;
        const fade = 1 - Math.abs(p.t - 0.5) * 2;
        X.beginPath(); X.arc(px, py, 2.5, 0, Math.PI * 2);
        X.fillStyle = `rgba(255,255,255,${fade * 0.9})`;
        X.fill();
      });

      state.hoveredNode = null;
      NODES.forEach(n => {
        const nx = n.x * scale - scale * 0.5, ny = n.y * scale - scale * 0.5;
        const worldX = baseX + nx * state.graphReveal * yScale;
        const worldY = baseY + ny * state.graphReveal * yScale;
        const d = Math.hypot(state.cursor.x - worldX, state.cursor.y - worldY);
        const isHov = d < 30;
        if (isHov) state.hoveredNode = n;
        const pulse = 0.7 + 0.3 * Math.sin(time * 2 + n.x * 10);
        const r = (state.selectedNode === n ? 12 : (isHov ? 11 : 7 * pulse));
        const grd = X.createRadialGradient(nx, ny, 0, nx, ny, r * 3);
        grd.addColorStop(0, n.color + '88');
        grd.addColorStop(1, 'transparent');
        X.beginPath(); X.arc(nx, ny, r * 3, 0, Math.PI * 2);
        X.fillStyle = grd; X.fill();
        X.beginPath(); X.arc(nx, ny, r, 0, Math.PI * 2);
        X.fillStyle = isHov || state.selectedNode === n ? '#ffffff' : n.color;
        X.fill();
        X.fillStyle = isHov || state.selectedNode === n ? '#ffffff' : n.color + 'dd';
        X.font = (isHov ? 'bold ' : '') + '8px Courier New';
        X.fillText(n.label, nx + r + 3, ny - 2);
      });
      X.restore();

      if (state.graphReveal > 0.3) {
        X.fillStyle = pal[0] + 'cc';
        X.font = '9px Courier New';
        X.fillText('◆ NEURAL KNOWLEDGE GRAPH', baseX - scale * 0.5, baseY - scale * 0.55);
      }
    }

    function drawCursorFx() {
      const pal = PHASES[state.phase].palette;
      const ringR = 8 + (state.gesture === 'PALM' ? 8 + Math.sin(state.t * 4) * 3 : 0) + state.pinch * 10;
      const g = FX.createRadialGradient(state.cursor.x, state.cursor.y, 0, state.cursor.x, state.cursor.y, ringR);
      g.addColorStop(0, pal[0] + 'cc');
      g.addColorStop(0.5, pal[1] + '44');
      g.addColorStop(1, 'transparent');
      FX.fillStyle = g;
      FX.beginPath();
      FX.arc(state.cursor.x, state.cursor.y, ringR, 0, Math.PI * 2);
      FX.fill();
      FX.strokeStyle = pal[0] + '88';
      FX.lineWidth = 0.8;
      FX.beginPath();
      FX.moveTo(state.cursor.x - 18, state.cursor.y); FX.lineTo(state.cursor.x - 6, state.cursor.y);
      FX.moveTo(state.cursor.x + 6, state.cursor.y); FX.lineTo(state.cursor.x + 18, state.cursor.y);
      FX.moveTo(state.cursor.x, state.cursor.y - 18); FX.lineTo(state.cursor.x, state.cursor.y - 6);
      FX.moveTo(state.cursor.x, state.cursor.y + 6); FX.lineTo(state.cursor.x, state.cursor.y + 18);
      FX.stroke();
      if (state.pinch > 0.3) {
        FX.beginPath();
        FX.arc(state.cursor.x, state.cursor.y, 22 + state.pinch * 8, 0, Math.PI * 2);
        FX.strokeStyle = `rgba(255,255,255,${state.pinch})`;
        FX.lineWidth = 2;
        FX.stroke();
      }
      if (state.fist > 0.5) {
        FX.beginPath();
        FX.arc(state.cursor.x, state.cursor.y, 30, 0, Math.PI * 2);
        FX.strokeStyle = `rgba(255,80,80,${state.fist * 0.5})`;
        FX.lineWidth = 3;
        FX.stroke();
      }
    }

    // ─── RENDER LOOP ───
    let raf = 0;
    let lastT = performance.now();
    function loop(now) {
      const dt = Math.min(0.05, (now - lastT) / 1000);
      lastT = now;
      state.t += dt;
      state.phaseMorph = Math.min(1, state.phaseMorph + dt * 0.8);

      // smooth cursor
      if (!state.usingHand && state.mouse.active) {
        state.cursor.x += (state.mouse.x - state.cursor.x) * 0.18;
        state.cursor.y += (state.mouse.y - state.cursor.y) * 0.18;
      }

      // auto cycle phases slowly if no hand
      if (!state.usingHand && state.t > 8 && state.t % 12 < dt) {
        // subtle drift
      }

      drawBg();
      drawWisps(state.t);
      drawCrystals(state.t);
      drawRibbons(state.t);
      drawSphere(state.t);
      drawEntity(state.t);
      drawGraph(state.t);
      drawBursts(dt);

      FX.clearRect(0, 0, W, H);
      drawCursorFx();
      const vg = FX.createRadialGradient(CX, CY, 0, CX, CY, Math.max(W, H) * 0.7);
      vg.addColorStop(0, 'transparent');
      vg.addColorStop(1, '#00000099');
      FX.fillStyle = vg;
      FX.fillRect(0, 0, W, H);

      // update HUD (throttled)
      if (Math.floor(state.t * 6) !== Math.floor((state.t - dt) * 6)) {
        setHudInfo({
          phase: state.phase,
          gesture: state.gesture,
          fingers: state.fingers,
          status: state.usingHand ? 'HAND ACTIVE' : (state.mouse.active ? 'MOUSE' : 'IDLE')
        });
      }

      raf = requestAnimationFrame(loop);
    }
    raf = requestAnimationFrame(loop);
    setHudInfo({ phase: 0, gesture: 'NONE', fingers: 0, status: 'ACTIVE' });

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      root.removeEventListener('mousemove', onMouseMove);
      root.removeEventListener('mouseleave', onMouseLeave);
      root.removeEventListener('mousedown', onMouseDown);
      root.removeEventListener('touchmove', onTouchMove);
      root.removeEventListener('touchstart', onTouchStart);
      delete root._holographicState;
      delete root._holographicTriggerBurst;
      delete root._holographicNextPhase;
      delete root._holographicResize;
      delete root._holographicSelectNode;
    };
  }, []);

  // camera effect
  useEffect(() => {
    if (!cameraOn) {
      setCameraError('');
      return;
    }
    const cam = camRef.current;
    if (!cam) return;
    let stream = null;
    let stopped = false;

    async function start() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 320, height: 240, facingMode: 'user' },
          audio: false
        });
        if (stopped) { stream.getTracks().forEach(t => t.stop()); return; }
        cam.srcObject = stream;
        await cam.play();
        await loadMediaPipe(rootRef.current, cam, handRef.current, stateRef);
      } catch (err) {
        setCameraError('Camera unavailable: ' + err.message);
      }
    }
    start();

    return () => {
      stopped = true;
      if (stream) stream.getTracks().forEach(t => t.stop());
    };
  }, [cameraOn]);

  const onStoryboardClick = useCallback((i) => {
    const root = rootRef.current;
    if (!root) return;
    const state = root._holographicState;
    if (!state) return;
    if (state.phase === i) {
      state.phase = (state.phase + 1) % PHASES.length;
    } else {
      state.phase = i;
    }
    state.phaseMorph = 0;
    if (root._holographicTriggerBurst) root._holographicTriggerBurst(root.clientWidth / 2, root.clientHeight / 2);
  }, []);

  function sendSpirit(text) {
    const msg = (text || spiritPrompt).trim();
    if (!msg || spiritBusy) return;
    const id = Date.now();
    setSpiritPrompt('');
    setSpiritBusy(true);
    setSpiritMessages((prev) => [...prev, { role: 'user', text: msg }, { role: 'assistant', text: '', id }]);

    const history = spiritMessages
      .filter((m) => m.text)
      .slice(-10)
      .map((m) => ({ role: m.role, content: m.text }));

    api.post('/api/voice/chat', {
      prompt: msg,
      voice: 'en_male',
      history,
    })
      .then((res) => {
        setSpiritBusy(false);
        if (res.error && !res.response_text) throw new Error(res.error);
        setSpiritMessages((prev) => prev.map((m) => m.id === id ? { ...m, text: res.response_text } : m));
      })
      .catch((err) => {
        setSpiritBusy(false);
        setSpiritMessages((prev) => prev.map((m) => m.id === id ? { ...m, text: `Error: ${err.message}` } : m));
      });
  }

  return (
    <div ref={rootRef} className="holo-root">
      <canvas ref={mainRef} className="holo-canvas" />
      <canvas ref={fxRef} className="holo-canvas holo-fx" />
      <video ref={camRef} autoPlay playsInline muted className="holo-cam" />
      <canvas ref={handRef} className="holo-hand" />

      <div className="holo-hud">
        <div className="holo-name">⬡ ATULYA ⬡</div>
        <div className="holo-sub">HOLOGRAPHIC SPIRIT ENTITY · v2.0</div>
        <div className="holo-state">PHASE: {PHASES[hudInfo.phase].name}</div>
        <div className="holo-gesture">GESTURE: {hudInfo.gesture}</div>
        <div className="holo-fingers">FINGERS: {hudInfo.fingers} · INPUT: {hudInfo.status}</div>
        <div className="holo-pill">{hudInfo.status}</div>
      </div>

      <button
        className={`holo-cam-btn ${cameraOn ? 'on' : ''}`}
        onClick={() => setCameraOn(v => !v)}
        title="Toggle hand tracking"
      >
        {cameraOn ? '◉ CAMERA ON' : '◯ ENABLE HAND TRACKING'}
      </button>
      {cameraError && <div className="holo-cam-err">{cameraError}</div>}

      <div className="holo-corner tl" /><div className="holo-corner tr" />
      <div className="holo-corner bl" /><div className="holo-corner br" />

      <div className="holo-storyboard">
        {PHASES.map((p, i) => (
          <div
            key={p.name}
            className={`holo-frame ${hudInfo.phase === i ? 'active' : ''}`}
            onClick={() => onStoryboardClick(i)}
          >
            <div className="holo-frame-num">{i + 1}</div>
            <div className="holo-frame-lbl">{p.name}</div>
          </div>
        ))}
      </div>

      <div className="holo-legend">
        <span>👆 POINT · MOVE</span>
        <span>🤏 PINCH · SELECT</span>
        <span>✋ PALM · NEXT PHASE</span>
        <span>✊ FIST · COMPRESS</span>
      </div>

      <div className="holo-chat-panel">
        <div className="holo-chat-header">
          <span>SPIRIT CHAT</span>
          <span className="holo-chat-status">{spiritBusy ? 'THINKING' : 'READY'}</span>
        </div>
        <div className="holo-chat-messages">
          {spiritMessages.map((msg, idx) => (
            <div className={`holo-chat-msg ${msg.role}`} key={msg.id || idx}>
              <div>{msg.text || (msg.role === 'assistant' && spiritBusy ? 'Spirit thinking...' : '')}</div>
              <small>{msg.role === 'user' ? 'YOU' : 'SPIRIT'}</small>
            </div>
          ))}
          {spiritBusy && <div className="holo-chat-msg assistant"><div>Spirit thinking...</div></div>}
        </div>
        <form className="holo-chat-input" onSubmit={(e) => { e.preventDefault(); sendSpirit(); }}>
          <input
            value={spiritPrompt}
            onChange={(e) => setSpiritPrompt(e.target.value)}
            placeholder="Speak to the Spirit..."
            disabled={spiritBusy}
          />
          <button type="submit" disabled={spiritBusy || !spiritPrompt.trim()}>
            {spiritBusy ? '...' : '_SEND'}
          </button>
        </form>
      </div>
    </div>
  );
}

async function loadMediaPipe(root, cam, handCanvas, stateRef) {
  if (typeof window.Hands === 'undefined') {
    await loadScript('https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4.1675469240/hands.js');
  }
  if (typeof window.Hands === 'undefined') {
    throw new Error('MediaPipe Hands failed to load');
  }
  const Hands = window.Hands;
  const hands = new Hands({
    locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4.1675469240/${file}`
  });
  hands.setOptions({
    maxNumHands: 1,
    modelComplexity: 1,
    minDetectionConfidence: 0.6,
    minTrackingConfidence: 0.5
  });
  const handX = handCanvas.getContext('2d');
  const state = stateRef.current;

  hands.onResults((results) => {
    drawHandViz(handX, handCanvas, results);
    if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
      const lm = results.multiHandLandmarks[0];
      state.usingHand = true;
      state.cursor.x = (1 - lm[8].x) * root.clientWidth;
      state.cursor.y = lm[8].y * root.clientHeight;
      const r = recognizeGesture(lm);
      state.gesture = r.gesture;
      state.fingers = r.fingers;
      state.pinch = r.pinch;
      state.fist = r.fist;
      // process gesture
      if (r.pinch > 0.7) {
        state.graphTarget = 1;
        if (state.hoveredNode && state.hoveredNode !== state.selectedNode && root._holographicSelectNode) {
          root._holographicSelectNode(state.hoveredNode);
        }
      }
      if (r.gesture === 'PALM' && !state.palmDebounce) {
        state.palmDebounce = true;
        if (root._holographicNextPhase) root._holographicNextPhase();
        setTimeout(() => { state.palmDebounce = false; }, 800);
      }
      if (r.gesture === 'FIST' && !state.fistDebounce) {
        state.fistDebounce = true;
        state.graphTarget = 0;
        setTimeout(() => { state.fistDebounce = false; }, 600);
      }
      if (r.gesture === 'WAVE') {
        state.graphTarget = Math.min(1, state.graphTarget + 0.02);
      }
    } else {
      state.usingHand = false;
      state.gesture = 'NONE';
    }
  });

  async function tick() {
    if (cam.readyState >= 2) {
      try { await hands.send({ image: cam }); } catch (e) {}
    }
    if (handCanvas.dataset.running === '1') requestAnimationFrame(tick);
  }
  handCanvas.dataset.running = '1';
  tick();

  // cleanup when component unmounts / camera off
  handCanvas._handsStop = () => {
    handCanvas.dataset.running = '0';
    try { hands.close(); } catch (e) {}
  };
}

function drawHandViz(ctx, canvas, results) {
  ctx.save();
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.translate(canvas.width, 0);
  ctx.scale(-1, 1);
  if (results.image) {
    try { ctx.drawImage(results.image, 0, 0, canvas.width, canvas.height); } catch (e) {}
  }
  ctx.restore();
  if (results.multiHandLandmarks) {
    results.multiHandLandmarks.forEach(lm => {
      const conns = [[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],
                     [5,9],[9,10],[10,11],[11,12],[9,13],[13,14],[14,15],[15,16],
                     [13,17],[17,18],[18,19],[19,20],[0,17]];
      ctx.strokeStyle = '#cc88ff';
      ctx.lineWidth = 1.5;
      conns.forEach(([a, b]) => {
        ctx.beginPath();
        ctx.moveTo((1 - lm[a].x) * canvas.width, lm[a].y * canvas.height);
        ctx.lineTo((1 - lm[b].x) * canvas.width, lm[b].y * canvas.height);
        ctx.stroke();
      });
      ctx.fillStyle = '#ffaaff';
      lm.forEach(p => {
        ctx.beginPath();
        ctx.arc((1 - p.x) * canvas.width, p.y * canvas.height, 2.5, 0, Math.PI * 2);
        ctx.fill();
      });
    });
  }
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) return resolve();
    const s = document.createElement('script');
    s.src = src; s.async = true; s.crossOrigin = 'anonymous';
    s.onload = resolve;
    s.onerror = () => reject(new Error('Failed to load ' + src));
    document.head.appendChild(s);
  });
}
