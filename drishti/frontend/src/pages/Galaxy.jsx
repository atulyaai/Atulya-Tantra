import React, { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../../api.js';

// Tantra palette: saffron sun, white Atulya, India green skills, chakra blue topics.
const GROUP_STYLE = {
  you: { color: '#ff9933', ring: 0 },
  about: { color: '#ffb366', ring: 1 },
  habit: { color: '#f4c430', ring: 1 },
  trust: { color: '#7ee2a0', ring: 1 },
  topic: { color: '#6fa8ff', ring: 2 },
  memory: { color: '#fbf6ee', ring: 2 },
  skill: { color: '#2eb85c', ring: 2 },
};
// Where each constellation sits around the sun (radians).
const CLUSTER_ANGLE = { about: -1.9, habit: -0.9, trust: 0.1, topic: 1.2, memory: 2.3, skill: 3.4 };

function layout(data) {
  const byGroup = {};
  data.nodes.forEach((n) => { (byGroup[n.group] ||= []).push(n); });
  const placed = {};
  (byGroup.you || []).forEach((n, i) => {
    placed[n.id] = { ...n, x: i === 0 ? 0 : 150, y: i === 0 ? 0 : -60, r: 6 + n.weight * 3, orbit: 0 };
  });
  Object.entries(byGroup).forEach(([group, nodes]) => {
    if (group === 'you') return;
    const base = CLUSTER_ANGLE[group] ?? 0;
    const dist = 260 + (GROUP_STYLE[group]?.ring || 1) * 90;
    const cx = Math.cos(base) * dist;
    const cy = Math.sin(base) * dist;
    nodes.forEach((n, i) => {
      // Golden-angle spiral keeps each constellation compact and readable.
      const a = i * 2.399963;
      const rad = 18 + Math.sqrt(i) * 34;
      placed[n.id] = {
        ...n, cx, cy, a, rad,
        x: cx + Math.cos(a) * rad, y: cy + Math.sin(a) * rad,
        r: Math.min(9, 2.5 + n.weight * 1.8),
        speed: 0.00008 + (i % 5) * 0.00002,
        twinkle: Math.random() * Math.PI * 2,
      };
    });
  });
  return placed;
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
  const view = useRef({ x: 0, y: 0, k: 0.85, drag: null });
  const nodesRef = useRef({});

  useEffect(() => {
    api.get('/api/knowledge/galaxy').then(setData).catch((e) => setError(e.message));
  }, []);

  const placed = useMemo(() => (data ? layout(data) : {}), [data]);
  useEffect(() => {
    nodesRef.current = placed;
    // Zoom to fit every constellation on first view.
    const pts = Object.values(placed);
    const box = wrapRef.current?.getBoundingClientRect();
    if (!pts.length || !box) return;
    const span = Math.max(...pts.map((n) => Math.max(Math.abs(n.x), Math.abs(n.y)) + 40));
    view.current.k = Math.min(1.2, Math.max(0.3, Math.min(box.width, box.height) / 2 / span));
  }, [placed]);

  const neighbours = useMemo(() => {
    const map = {};
    (data?.links || []).forEach(({ source, target }) => {
      (map[source] ||= new Set()).add(target);
      (map[target] ||= new Set()).add(source);
    });
    return map;
  }, [data]);

  const focus = pinned || hover;
  const q = query.trim().toLowerCase();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !data) return undefined;
    const ctx = canvas.getContext('2d');
    const stars = Array.from({ length: 260 }, () => ({
      x: Math.random(), y: Math.random(), s: Math.random() * 1.3, p: Math.random() * 6,
    }));
    let raf;
    const dpr = window.devicePixelRatio || 1;

    function resize() {
      const { width, height } = wrapRef.current.getBoundingClientRect();
      canvas.width = width * dpr; canvas.height = height * dpr;
      canvas.style.width = `${width}px`; canvas.style.height = `${height}px`;
    }
    resize();
    window.addEventListener('resize', resize);

    function draw(t) {
      const W = canvas.width / dpr; const H = canvas.height / dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const bg = ctx.createRadialGradient(W / 2, H / 2, 0, W / 2, H / 2, Math.max(W, H) * 0.7);
      bg.addColorStop(0, '#141a3a'); bg.addColorStop(1, '#05070f');
      ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
      stars.forEach((s) => {
        ctx.globalAlpha = 0.25 + 0.35 * Math.sin(t / 900 + s.p) ** 2;
        ctx.fillStyle = '#fbf6ee';
        ctx.fillRect(s.x * W, s.y * H, s.s, s.s);
      });
      ctx.globalAlpha = 1;

      const v = view.current;
      ctx.translate(W / 2 + v.x, H / 2 + v.y);
      ctx.scale(v.k, v.k);

      const nodes = nodesRef.current;
      Object.values(nodes).forEach((n) => {
        if (n.cx === undefined) return;
        const a = n.a + t * n.speed;
        n.x = n.cx + Math.cos(a) * n.rad; n.y = n.cy + Math.sin(a) * n.rad;
      });

      const near = focus ? neighbours[focus] || new Set() : null;
      ctx.lineWidth = 1 / v.k;
      data.links.forEach(({ source, target }) => {
        const a = nodes[source]; const b = nodes[target];
        if (!a || !b || hidden[a.group] || hidden[b.group]) return;
        const lit = focus && (source === focus || target === focus);
        ctx.strokeStyle = lit ? 'rgba(255,153,51,0.8)' : 'rgba(255,153,51,0.07)';
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      });

      Object.values(nodes).forEach((n) => {
        if (hidden[n.group]) return;
        const style = GROUP_STYLE[n.group] || GROUP_STYLE.memory;
        const match = !q || n.label.toLowerCase().includes(q) || n.detail.toLowerCase().includes(q);
        const dim = (focus && n.id !== focus && !near.has(n.id)) || !match;
        const tw = n.twinkle !== undefined ? 0.75 + 0.25 * Math.sin(t / 600 + n.twinkle) : 1;
        ctx.globalAlpha = dim ? 0.15 : tw;
        const glow = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, n.r * 4);
        glow.addColorStop(0, style.color); glow.addColorStop(1, 'transparent');
        ctx.fillStyle = glow;
        ctx.beginPath(); ctx.arc(n.x, n.y, n.r * 4, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = n.group === 'you' && n.id === 'atulya' ? '#ffffff' : style.color;
        ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2); ctx.fill();
        if (!dim && (n.group === 'you' || n.id === focus || v.k > 1.4 || (q && match))) {
          ctx.globalAlpha = 1;
          ctx.fillStyle = '#fbf6ee';
          ctx.font = `${n.group === 'you' ? 14 : 11}px Inter, system-ui, sans-serif`;
          ctx.textAlign = 'center';
          ctx.fillText(n.label, n.x, n.y + n.r + 14);
        }
      });
      ctx.globalAlpha = 1;
      raf = requestAnimationFrame(draw);
    }
    raf = requestAnimationFrame(draw);
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', resize); };
  }, [data, focus, hidden, neighbours, q]);

  function toWorld(e) {
    const rect = canvasRef.current.getBoundingClientRect();
    const v = view.current;
    return {
      x: (e.clientX - rect.left - rect.width / 2 - v.x) / v.k,
      y: (e.clientY - rect.top - rect.height / 2 - v.y) / v.k,
      sx: e.clientX - rect.left, sy: e.clientY - rect.top,
    };
  }

  function hit(e) {
    const p = toWorld(e);
    let best = null; let bestD = Infinity;
    Object.values(nodesRef.current).forEach((n) => {
      if (hidden[n.group]) return;
      const d = Math.hypot(n.x - p.x, n.y - p.y);
      if (d < Math.max(n.r * 2.2, 10 / view.current.k) && d < bestD) { best = n; bestD = d; }
    });
    return { node: best, p };
  }

  const [tipPos, setTipPos] = useState({ x: 0, y: 0 });
  function onMove(e) {
    const v = view.current;
    if (v.drag) {
      v.x = v.drag.vx + e.clientX - v.drag.x; v.y = v.drag.vy + e.clientY - v.drag.y;
      return;
    }
    const { node, p } = hit(e);
    setHover(node ? node.id : null);
    setTipPos({ x: p.sx, y: p.sy });
    canvasRef.current.style.cursor = node ? 'pointer' : 'grab';
  }
  function onDown(e) { view.current.drag = { x: e.clientX, y: e.clientY, vx: view.current.x, vy: view.current.y, moved: false }; }
  function onUp(e) {
    const d = view.current.drag; view.current.drag = null;
    if (d && Math.hypot(e.clientX - d.x, e.clientY - d.y) < 4) {
      const { node } = hit(e);
      setPinned(node ? node.id : null);
    }
  }
  function onWheel(e) {
    const v = view.current;
    v.k = Math.min(4, Math.max(0.3, v.k * (e.deltaY < 0 ? 1.1 : 0.9)));
  }

  const shown = focus ? placed[focus] : null;
  const cluster = (g) => data?.clusters.find((c) => c.id === g)?.label || g;

  return (
    <div className="galaxy">
      <div className="galaxy-bar">
        <h2>Knowledge galaxy</h2>
        <input className="galaxy-search" placeholder="Find a star…" value={query} onChange={(e) => setQuery(e.target.value)} />
        <div className="galaxy-legend">
          {(data?.clusters || []).map((c) => (
            <button key={c.id} className={hidden[c.id] ? 'off' : ''}
              onClick={() => setHidden((h) => ({ ...h, [c.id]: !h[c.id] }))}>
              <span className="dot" style={{ background: GROUP_STYLE[c.id]?.color }} />
              {c.label} <small>{c.count}</small>
            </button>
          ))}
        </div>
      </div>
      <div className="galaxy-canvas" ref={wrapRef}>
        {error && <div className="alert">{error}</div>}
        {!data && !error && <div className="lazy-loading">Mapping the stars…</div>}
        <canvas ref={canvasRef} onMouseMove={onMove} onMouseDown={onDown} onMouseUp={onUp}
          onMouseLeave={() => { view.current.drag = null; setHover(null); }} onWheel={onWheel} />
        {shown && (
          <div className="galaxy-tip" style={pinned ? { right: 16, top: 16 } : { left: tipPos.x + 16, top: tipPos.y + 16 }}>
            <div className="galaxy-tip-kind" style={{ color: GROUP_STYLE[shown.group]?.color }}>{shown.id === 'atulya' ? 'Assistant' : cluster(shown.group)}</div>
            <div className="galaxy-tip-title">{shown.label}</div>
            {shown.detail && shown.detail !== shown.label && <p>{shown.detail}</p>}
            {Object.entries(shown.meta || {}).filter(([, v]) => v !== '' && v !== null).map(([k, v]) => (
              <div key={k} className="galaxy-tip-meta"><span>{k}</span><b>{String(v)}</b></div>
            ))}
            <div className="galaxy-tip-meta"><span>connections</span><b>{neighbours[shown.id]?.size || 0}</b></div>
            {pinned && <small className="muted">Click empty space to unpin</small>}
          </div>
        )}
        <div className="galaxy-hint">Drag to pan · scroll to zoom · click a star to pin it</div>
      </div>
    </div>
  );
}
