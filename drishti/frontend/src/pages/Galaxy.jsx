import React, { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../../api.js';

// One galaxy disc, like a scatter of thousands of experiments: every dot is
// something Atulya knows. What matters most about you sits in the bright core;
// Atulya's skills form the outer arms. Size = importance, colour = constellation.
const GROUPS = {
  you: { color: [255, 153, 51], depth: 0.0 },
  about: { color: [255, 179, 102], depth: 0.18 },
  habit: { color: [244, 196, 48], depth: 0.3 },
  trust: { color: [126, 226, 160], depth: 0.38 },
  topic: { color: [251, 246, 238], depth: 0.5 },
  memory: { color: [180, 200, 255], depth: 0.64 },
  skill: { color: [46, 184, 92], depth: 0.82 },
};
const TILT = 0.42; // vertical squash of the disc
const GOLDEN = 2.399963;

const rgba = ([r, g, b], a) => `rgba(${r},${g},${b},${a})`;
// Dust colour by radius: saffron core → ivory → India green rim.
function dustColor(t) {
  const stops = [[255, 153, 51], [255, 214, 170], [251, 246, 238], [140, 210, 170], [46, 184, 92]];
  const x = Math.min(0.999, t) * (stops.length - 1);
  const i = Math.floor(x); const f = x - i;
  return stops[i].map((v, k) => Math.round(v + (stops[i + 1][k] - v) * f));
}

function build(data) {
  const groups = {};
  data.nodes.forEach((n) => (groups[n.group] ||= []).push(n));
  const stars = [];
  Object.entries(groups).forEach(([g, nodes]) => {
    const base = GROUPS[g] || GROUPS.memory;
    nodes
      .slice()
      .sort((a, b) => b.weight - a.weight)
      .forEach((n, i) => {
        // Scattered across a wide band (not a ring) so groups blend like a real galaxy.
        const band = base.depth + (Math.random() - 0.35) * 0.3;
        const r = g === 'you' ? (i === 0 ? 0 : 0.16) : Math.min(0.98, Math.max(0.1, band));
        stars.push({
          ...n, r, a: g === 'you' ? -Math.PI / 2 : i * GOLDEN + Math.random() * 0.8, color: base.color,
          size: g === 'you' ? 9 - i * 2 : Math.min(7, 2.4 + n.weight * 1.4),
        });
      });
  });
  // Dust: denser toward the core, in two faint spiral arms.
  const dust = Array.from({ length: 4200 }, (_, i) => {
    const r = Math.pow(Math.random(), 0.9);
    const arm = i % 2 ? 0 : Math.PI;
    const spread = i % 3 ? 1.1 : 3.2; // two soft arms plus an even halo
    return { r, a: arm + r * 5.5 + (Math.random() - 0.5) * spread, s: 0.6 + Math.random() * 2.2 * (1 - r * 0.5), c: dustColor(r), o: 0.18 + Math.random() * 0.4 };
  });
  return { stars, dust };
}

export function Galaxy() {
  const canvasRef = useRef(null);
  const wrapRef = useRef(null);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [hover, setHover] = useState(null);
  const [pinned, setPinned] = useState(null);
  const [hidden, setHidden] = useState({});
  const [query, setQuery] = useState('');
  const [tip, setTip] = useState({ x: 0, y: 0 });
  const view = useRef({ zoom: 1, px: 0, py: 0, drag: null, spin: 0 });
  const screen = useRef([]); // last drawn star positions, for hit testing

  useEffect(() => { api.get('/api/knowledge/galaxy').then(setData).catch((e) => setError(e.message)); }, []);
  const world = useMemo(() => (data ? build(data) : null), [data]);
  const byId = useMemo(() => Object.fromEntries((world?.stars || []).map((s) => [s.id, s])), [world]);
  const neighbours = useMemo(() => {
    const m = {};
    (data?.links || []).forEach(({ source, target }) => { (m[source] ||= new Set()).add(target); (m[target] ||= new Set()).add(source); });
    return m;
  }, [data]);

  const focus = pinned || hover;
  const q = query.trim().toLowerCase();

  useEffect(() => {
    if (!world) return undefined;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    let raf; let last = performance.now();
    const resize = () => {
      const { width, height } = wrapRef.current.getBoundingClientRect();
      canvas.width = width * dpr; canvas.height = height * dpr;
      canvas.style.width = `${width}px`; canvas.style.height = `${height}px`;
    };
    resize();
    window.addEventListener('resize', resize);

    const draw = (now) => {
      const v = view.current;
      if (!focus) v.spin += (now - last) * 0.00003; // slow drift, paused while inspecting
      last = now;
      const W = canvas.width / dpr; const H = canvas.height / dpr;
      const R = Math.min(W * 0.46, H / TILT * 0.44) * v.zoom;
      const cx = W / 2 + v.px; const cy = H / 2 + v.py;
      const project = (r, a) => {
        const ang = a + v.spin / Math.max(0.25, r); // inner parts turn faster, like a real disc
        return [cx + Math.cos(ang) * r * R, cy + Math.sin(ang) * r * R * TILT];
      };

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.fillStyle = '#070a18';
      ctx.fillRect(0, 0, W, H);
      const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * 0.5);
      glow.addColorStop(0, 'rgba(255,153,51,0.28)'); glow.addColorStop(1, 'rgba(255,153,51,0)');
      ctx.fillStyle = glow; ctx.fillRect(0, 0, W, H);

      world.dust.forEach((d) => {
        const [x, y] = project(d.r, d.a);
        ctx.fillStyle = rgba(d.c, focus || q ? d.o * 0.35 : d.o);
        ctx.beginPath(); ctx.arc(x, y, d.s / 2, 0, Math.PI * 2); ctx.fill();
      });

      const near = focus ? neighbours[focus] || new Set() : null;
      const drawn = [];
      world.stars.forEach((s) => { if (!hidden[s.group]) { const [x, y] = project(s.r, s.a); drawn.push({ s, x, y }); } });

      if (focus) {
        const f = drawn.find((d) => d.s.id === focus);
        if (f) {
          ctx.strokeStyle = 'rgba(255,153,51,0.55)'; ctx.lineWidth = 1;
          drawn.forEach((d) => { if (near.has(d.s.id)) { ctx.beginPath(); ctx.moveTo(f.x, f.y); ctx.lineTo(d.x, d.y); ctx.stroke(); } });
        }
      }

      drawn.forEach(({ s, x, y }) => {
        const match = !q || s.label.toLowerCase().includes(q) || (s.detail || '').toLowerCase().includes(q);
        const dim = (focus && s.id !== focus && !near.has(s.id)) || !match;
        const size = s.size * (s.id === focus ? 1.6 : 1) * Math.sqrt(v.zoom);
        ctx.fillStyle = rgba(s.color, dim ? 0.12 : 0.9);
        ctx.beginPath(); ctx.arc(x, y, size, 0, Math.PI * 2); ctx.fill();
        if (!dim) {
          ctx.strokeStyle = rgba(s.color, 0.35); ctx.lineWidth = 3;
          ctx.beginPath(); ctx.arc(x, y, size + 2.5, 0, Math.PI * 2); ctx.stroke();
        }
        if (!dim && (s.group === 'you' || s.id === focus || (q && match) || (v.zoom > 1.8 && size > 4))) {
          ctx.fillStyle = '#fbf6ee'; ctx.font = '12px Inter, system-ui, sans-serif'; ctx.textAlign = 'center';
          ctx.fillText(s.label, x, y - size - 7);
        }
      });
      screen.current = drawn;
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', resize); };
  }, [world, focus, hidden, neighbours, q]);

  function pick(e) {
    const rect = canvasRef.current.getBoundingClientRect();
    const mx = e.clientX - rect.left; const my = e.clientY - rect.top;
    let best = null; let bd = 14;
    screen.current.forEach(({ s, x, y }) => { const d = Math.hypot(x - mx, y - my); if (d < Math.max(bd, s.size + 3) && d < bd + s.size) { best = s; bd = d; } });
    return { star: best, mx, my };
  }
  function onMove(e) {
    const v = view.current;
    if (v.drag) { v.px = v.drag.px + e.clientX - v.drag.x; v.py = v.drag.py + e.clientY - v.drag.y; return; }
    const { star, mx, my } = pick(e);
    setHover(star?.id || null); setTip({ x: mx, y: my });
    canvasRef.current.style.cursor = star ? 'pointer' : 'grab';
  }
  function onUp(e) {
    const d = view.current.drag; view.current.drag = null;
    if (d && Math.hypot(e.clientX - d.x, e.clientY - d.y) < 4) setPinned(pick(e).star?.id || null);
  }

  const shown = focus ? byId[focus] : null;
  const label = (g) => data?.clusters.find((c) => c.id === g)?.label || g;
  const W = wrapRef.current?.clientWidth || 0;

  return (
    <div className="galaxy">
      <div className="galaxy-bar">
        <div>
          <h2>Knowledge map</h2>
          <p className="muted">Everything Atulya knows. Brighter and closer to the centre means more about you; size shows importance.</p>
        </div>
        <input className="galaxy-search" placeholder="Search…" value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>
      <div className="galaxy-legend">
        {(data?.clusters || []).map((c) => (
          <button type="button" key={c.id} className={hidden[c.id] ? 'off' : ''} onClick={() => setHidden((h) => ({ ...h, [c.id]: !h[c.id] }))}>
            <span className="dot" style={{ background: rgba((GROUPS[c.id] || GROUPS.memory).color, 1) }} />
            {c.label} <small>{c.count}</small>
          </button>
        ))}
      </div>
      <div className="galaxy-canvas" ref={wrapRef}>
        {error && <div className="alert">{error}</div>}
        {!data && !error && <div className="lazy-loading">Mapping what I know…</div>}
        <canvas ref={canvasRef} onMouseMove={onMove}
          onMouseDown={(e) => { view.current.drag = { x: e.clientX, y: e.clientY, px: view.current.px, py: view.current.py }; }}
          onMouseUp={onUp} onMouseLeave={() => { view.current.drag = null; setHover(null); }}
          onWheel={(e) => { const v = view.current; v.zoom = Math.min(5, Math.max(0.5, v.zoom * (e.deltaY < 0 ? 1.12 : 0.89))); }} />
        {shown && (
          <div className="galaxy-tip" style={pinned ? { right: 16, top: 16 } : { left: Math.min(tip.x + 16, W - 316), top: tip.y + 16 }}>
            <div className="galaxy-tip-kind" style={{ color: rgba(shown.color, 1) }}>{shown.id === 'atulya' ? 'Assistant' : label(shown.group)}</div>
            <div className="galaxy-tip-title">{shown.label}</div>
            {shown.detail && shown.detail !== shown.label && <p>{shown.detail}</p>}
            {Object.entries(shown.meta || {}).filter(([, v]) => v !== '' && v !== null && v !== undefined).map(([k, v]) => (
              <div key={k} className="galaxy-tip-meta"><span>{k}</span><b>{String(v)}</b></div>
            ))}
            <div className="galaxy-tip-meta"><span>connections</span><b>{neighbours[shown.id]?.size || 0}</b></div>
            {pinned && <small className="muted">Click empty space to let go</small>}
          </div>
        )}
        <div className="galaxy-hint">Hover a dot for details · click to pin · drag to move · scroll to zoom</div>
      </div>
    </div>
  );
}
