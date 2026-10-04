import React, { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';

// A living tree of what Atulya remembers about you. The trunk is you, each branch a kind of memory,
// each glowing leaf a real stored fact. New facts grow in while the panel is open.

const COLORS = {
  person: '#ffb347', place: '#7ee0ff', work: '#b69cff', preference: '#ff8fb1',
  health: '#8bf0a0', date: '#ffd86b', habit: '#6fe3d0', note: '#c9d3e0', root: '#ffd36b',
};
const SAMPLES = 28;
const REDUCED = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

const clamp = (v) => Math.max(0, Math.min(1, v));
const ease = (v) => 1 - Math.pow(1 - clamp(v), 3);

function hash(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i += 1) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
  return (h >>> 0) / 4294967295;
}

function bezier(p0, c, p1, t) {
  const u = 1 - t;
  return { x: u * u * p0.x + 2 * u * t * c.x + t * t * p1.x, y: u * u * p0.y + 2 * u * t * c.y + t * t * p1.y };
}

// Fixed geometry for the current graph and size; the animation only moves it a little.
function layout(graph, w, h) {
  const base = { x: w / 2, y: h * 0.94 };
  const fork = { x: w / 2, y: h * 0.72 };
  const branches = graph.nodes.filter((n) => n.kind === 'branch');
  const reach = Math.min(w * 0.5, h * 0.66);
  const out = { base, fork, branches: [], leaves: [] };
  branches.forEach((b, i) => {
    const spread = Math.min(1.4, 0.5 + branches.length * 0.17);
    const angle = branches.length === 1 ? 0 : -spread + (2 * spread * i) / (branches.length - 1);
    const len = reach * (i % 2 === 0 ? 0.98 : 0.66) * (0.94 + 0.06 * hash(b.id));
    const dir = { x: Math.sin(angle), y: -Math.cos(angle) };
    const tip = { x: Math.max(80, Math.min(w - 80, fork.x + dir.x * len)), y: Math.max(40, fork.y + dir.y * len * 0.92) };
    const bend = (hash(b.id + 'b') - 0.5) * len * 0.5;
    const ctrl = { x: fork.x + dir.x * len * 0.5 - dir.y * bend, y: fork.y + dir.y * len * 0.5 + dir.x * bend };
    const pts = Array.from({ length: SAMPLES + 1 }, (_, k) => bezier(fork, ctrl, tip, k / SAMPLES));
    out.branches.push({ node: b, from: fork, ctrl, tip, pts, born: i });
    const kids = graph.nodes.filter((n) => n.kind === 'leaf' && n.group === b.group);
    kids.forEach((leaf, k) => {
      const t = 0.42 + (0.58 * (k + 1)) / (kids.length + 1);
      const anchor = bezier(fork, ctrl, tip, t);
      const side = k % 2 === 0 ? 1 : -1;
      const reachOut = 22 + 20 * hash(leaf.id) + Math.min(34, kids.length * 2);
      const pos = { x: anchor.x - dir.y * side * reachOut + dir.x * 8, y: anchor.y + dir.x * side * reachOut + dir.y * 8 };
      out.leaves.push({ node: leaf, branch: b.id, anchor, pos, order: k });
    });
  });
  return out;
}

export function MemoryTree() {
  const wrap = useRef(null);
  const canvas = useRef(null);
  const geo = useRef(null);
  const born = useRef({});
  const mounted = useRef(performance.now());
  const hoverRef = useRef(null);
  const [graph, setGraph] = useState(null);
  const [error, setError] = useState('');
  const [picked, setPicked] = useState(null);

  // Load now, then again every 20 s so newly learned facts grow in.
  useEffect(() => {
    let alive = true;
    const load = () => api.get('/api/memory/graph')
      .then((g) => { if (alive) { setGraph(g); setError(''); } })
      .catch((e) => alive && setError(e.message || 'Could not load memory'));
    load();
    const timer = setInterval(load, 20000);
    return () => { alive = false; clearInterval(timer); };
  }, []);

  useEffect(() => {
    if (!graph) return;
    const now = performance.now();
    const first = Object.keys(born.current).length === 0;
    let i = 0;
    graph.nodes.forEach((n) => {
      if (born.current[n.id] !== undefined) return;
      const stagger = n.kind === 'branch' ? 400 + i * 260 : 1500 + i * 70;
      born.current[n.id] = REDUCED ? -1e9 : first ? mounted.current + stagger : now;
      i += 1;
    });
  }, [graph]);

  useEffect(() => {
    const el = canvas.current;
    const box = wrap.current;
    if (!el || !box || !graph) return undefined;
    const ctx = el.getContext('2d');
    let raf = 0;
    let w = 0;
    let h = 0;

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = box.clientWidth;
      h = box.clientHeight;
      el.width = w * dpr;
      el.height = h * dpr;
      el.style.width = `${w}px`;
      el.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      geo.current = layout(graph, w, h);
    }
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(box);

    const sway = (p, time) => {
      const depth = clamp((geo.current.base.y - p.y) / h);
      return REDUCED ? p : { x: p.x + Math.sin(time / 1500 + p.y / 110) * 5 * depth, y: p.y + Math.cos(time / 1900 + p.x / 140) * 2.5 * depth };
    };

    function strand(points, progress, width, alpha, color, offset) {
      const n = Math.max(2, Math.floor(points.length * progress));
      ctx.beginPath();
      for (let k = 0; k < n; k += 1) {
        const p = points[k];
        const q = points[Math.min(k + 1, points.length - 1)];
        const dx = q.x - p.x;
        const dy = q.y - p.y;
        const len = Math.hypot(dx, dy) || 1;
        const x = p.x - (dy / len) * offset;
        const y = p.y + (dx / len) * offset;
        if (k === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.lineWidth = width;
      ctx.strokeStyle = color;
      ctx.globalAlpha = alpha;
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    function frame(time) {
      const g = geo.current;
      ctx.clearRect(0, 0, w, h);
      // Trunk
      const trunkP = ease((time - mounted.current) / 1200);
      const trunk = Array.from({ length: 16 }, (_, k) => {
        const t = k / 15;
        const bendX = Math.sin(t * Math.PI) * 10 * (hash('trunk') - 0.5);
        return sway({ x: g.base.x + bendX, y: g.base.y + (g.fork.y - g.base.y) * t }, time);
      });
      ctx.lineCap = 'round';
      ctx.shadowColor = '#3dd6c8';
      ctx.shadowBlur = 16;
      strand(trunk, trunkP, 9, 0.22, '#3dd6c8', 0);
      ctx.shadowBlur = 0;
      [-3, -1, 1, 3].forEach((o) => strand(trunk, trunkP, 1.4, 0.75, '#5ff0dd', o));

      // Branches
      const tips = {};
      g.branches.forEach((br) => {
        const p = ease((time - (born.current[br.node.id] ?? mounted.current)) / 1400);
        if (p <= 0) return;
        const pts = br.pts.map((q) => sway(q, time));
        const color = COLORS[br.node.group] || '#3dd6c8';
        ctx.shadowColor = color;
        ctx.shadowBlur = 12;
        strand(pts, p, 6, 0.13, color, 0);
        ctx.shadowBlur = 0;
        [-2.4, 0, 2.4].forEach((o) => strand(pts, p, 1.2, o === 0 ? 0.9 : 0.55, '#4fe6d4', o));
        const end = pts[Math.max(1, Math.floor(pts.length * p)) - 1];
        tips[br.node.id] = { p: end, color, grown: p };
        // data flowing outward
        if (p > 0.95 && !REDUCED) {
          for (let k = 0; k < 3; k += 1) {
            const f = ((time / 2600 + k / 3 + hash(br.node.id)) % 1);
            const q = pts[Math.floor(f * (pts.length - 1))];
            ctx.beginPath();
            ctx.arc(q.x, q.y, 2.1, 0, 7);
            ctx.fillStyle = '#d6fff8';
            ctx.shadowColor = '#7ff';
            ctx.shadowBlur = 10;
            ctx.fill();
            ctx.shadowBlur = 0;
          }
        }
      });

      // Leaves (twig + glowing node)
      const hover = hoverRef.current;
      g.leaves.forEach((lf) => {
        const p = ease((time - (born.current[lf.node.id] ?? mounted.current)) / 800);
        const tip = tips[lf.branch];
        if (p <= 0 || !tip || tip.grown < 0.9) return;
        const a = sway(lf.anchor, time);
        const e = sway(lf.pos, time);
        const x = a.x + (e.x - a.x) * p;
        const y = a.y + (e.y - a.y) * p;
        const color = COLORS[lf.node.group] || '#ffb347';
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.quadraticCurveTo((a.x + x) / 2 + 5, (a.y + y) / 2 - 5, x, y);
        ctx.strokeStyle = 'rgba(95,240,221,.55)';
        ctx.lineWidth = 1;
        ctx.stroke();
        const pulse = REDUCED ? 0 : Math.sin(time / 700 + hash(lf.node.id) * 6) * 0.8;
        const isHot = hover === lf.node.id || picked?.id === lf.node.id;
        ctx.beginPath();
        ctx.arc(x, y, (isHot ? 7 : 4.2 + pulse) * (0.4 + 0.6 * p), 0, 7);
        ctx.fillStyle = color;
        ctx.shadowColor = color;
        ctx.shadowBlur = isHot ? 24 : 13;
        ctx.fill();
        ctx.shadowBlur = 0;
        lf.screen = { x, y };
        if (isHot) {
          ctx.font = '13px system-ui, sans-serif';
          ctx.textAlign = 'center';
          ctx.fillStyle = '#fff';
          ctx.fillText(lf.node.label.slice(0, 28), x, y - 14);
        } else if (graph.total <= 16 && p > 0.9) {
          ctx.font = '11px system-ui, sans-serif';
          ctx.textAlign = x < g.base.x ? 'right' : 'left';
          ctx.fillStyle = 'rgba(224,255,250,.72)';
          ctx.fillText(lf.node.label.slice(0, 22), x + (x < g.base.x ? -9 : 9), y + 4);
        }
      });

      // Branch labels and the root
      g.branches.forEach((br) => {
        const tip = tips[br.node.id];
        if (!tip || tip.grown < 0.85) return;
        ctx.font = '600 13px system-ui, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillStyle = tip.color;
        ctx.shadowColor = '#000';
        ctx.shadowBlur = 6;
        ctx.fillText(`${br.node.label} · ${br.node.count}`, tip.p.x, tip.p.y - 12);
        ctx.shadowBlur = 0;
        ctx.beginPath();
        ctx.arc(tip.p.x, tip.p.y, 5, 0, 7);
        ctx.fillStyle = tip.color;
        ctx.fill();
      });
      ctx.beginPath();
      ctx.arc(g.base.x, g.base.y, 8 + (REDUCED ? 0 : Math.sin(time / 600) * 1.5), 0, 7);
      ctx.fillStyle = COLORS.root;
      ctx.shadowColor = COLORS.root;
      ctx.shadowBlur = 22;
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.font = '600 14px system-ui, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillStyle = '#ffe9a8';
      ctx.fillText(graph.nodes[0]?.label || 'You', g.base.x, g.base.y + 24);

      raf = requestAnimationFrame(frame);
    }
    raf = requestAnimationFrame(frame);
    return () => { cancelAnimationFrame(raf); ro.disconnect(); };
  }, [graph, picked]);

  function nearestLeaf(evt) {
    const rect = canvas.current.getBoundingClientRect();
    const x = evt.clientX - rect.left;
    const y = evt.clientY - rect.top;
    let best = null;
    let bestD = 18;
    (geo.current?.leaves || []).forEach((lf) => {
      if (!lf.screen) return;
      const d = Math.hypot(lf.screen.x - x, lf.screen.y - y);
      if (d < bestD) { best = lf.node; bestD = d; }
    });
    return best;
  }

  const total = graph?.total || 0;
  const empty = graph && total === 0;
  return (
    <div ref={wrap} style={{
      position: 'relative', width: '100%', height: 'min(72vh, 640px)', minHeight: 380, overflow: 'hidden', borderRadius: 14,
      background: 'radial-gradient(ellipse at 50% 85%, #0b2a2d 0%, #060d14 60%, #03060a 100%)',
    }}>
      <canvas
        ref={canvas}
        aria-label="Memory tree"
        style={{ display: 'block', cursor: 'pointer' }}
        onMouseMove={(e) => { const n = nearestLeaf(e); hoverRef.current = n ? n.id : null; }}
        onMouseLeave={() => { hoverRef.current = null; }}
        onClick={(e) => setPicked(nearestLeaf(e))}
      />
      <div style={{ position: 'absolute', top: 12, left: 16, color: '#9fd8d0', fontSize: 13 }}>
        {graph ? `${total} thing${total === 1 ? '' : 's'} remembered` : 'Growing…'}
      </div>
      {error && <div role="alert" style={{ position: 'absolute', top: 12, right: 16, color: '#ff9a9a', fontSize: 13 }}>{error}</div>}
      {empty && (
        <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', textAlign: 'center', color: '#bfe9e3', padding: 24 }}>
          <div>
            <p style={{ fontSize: 16, margin: 0 }}>Nothing here yet.</p>
            <p style={{ opacity: 0.75, margin: '6px 0 0' }}>Tell Atulya about yourself, e.g. “my wife is Priya” or “I live in Delhi”, and watch it grow.</p>
          </div>
        </div>
      )}
      {picked && (
        <div style={{
          position: 'absolute', left: 16, right: 16, bottom: 14, padding: '10px 14px', borderRadius: 10,
          background: 'rgba(8,22,28,.88)', border: `1px solid ${COLORS[picked.group] || '#3dd6c8'}`, color: '#eafffb',
        }}>
          <strong style={{ color: COLORS[picked.group] }}>{picked.label}</strong>
          {picked.detail && picked.detail !== picked.label && <div style={{ opacity: 0.85, marginTop: 2 }}>{picked.detail}</div>}
          <button type="button" onClick={() => setPicked(null)} style={{ position: 'absolute', top: 6, right: 10, background: 'none', border: 0, color: '#9fd8d0', cursor: 'pointer' }} aria-label="Close">×</button>
        </div>
      )}
    </div>
  );
}

export default MemoryTree;
