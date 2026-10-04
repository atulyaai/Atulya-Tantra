import React, { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api.js';
import { registerSections } from '../sections.js';

// The memory tree: a large living tree of what Atulya remembers. The trunk is you; every big branch is a kind
// of memory; every golden node is a real item (a fact, a remembered exchange, a skill, a module). Tap a branch
// to open its full contents; tap a node for its detail. "Open episodic memories" works by voice too.

const GOLD = '#ffc94d';
const TEAL = '95, 235, 220';
const ORDER = ['concepts', 'personal', 'episodic', 'world', 'self', 'preference', 'skills', 'arch'];
const REDUCED = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
const SAMPLES = 30;

const clamp = (v) => Math.max(0, Math.min(1, v));
const ease = (v) => 1 - Math.pow(1 - clamp(v), 3);

function hash(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i += 1) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
  return (h >>> 0) / 4294967295;
}
const bez = (a, c, b, t) => { const u = 1 - t; return { x: u * u * a.x + 2 * u * t * c.x + t * t * b.x, y: u * u * a.y + 2 * u * t * c.y + t * t * b.y }; };

// Small word-fragments of an item's own text: they make a busy item look busy, in proportion to what it holds.
function fragments(text) {
  return [...new Set(String(text || '').toLowerCase().match(/[a-zऀ-ॿ]{5,}/g) || [])].slice(0, 5);
}

function layout(graph, w, h) {
  const base = { x: w / 2, y: h * 0.985 };
  const fork = { x: w / 2, y: h * 0.66 };
  const branches = ORDER.map((id) => graph.nodes.find((n) => n.id === `branch:${id}`)).filter(Boolean);
  const out = { base, fork, branches: [], leaves: [] };
  const reach = Math.min(w * 0.42, h * 0.5);
  branches.forEach((b, i) => {
    const slots = branches.length;
    const frac = slots === 1 ? 0.5 : i / (slots - 1);
    const angle = (frac - 0.5) * 2 * Math.min(1.1, 0.4 + slots * 0.12);
    const len = reach * (i % 2 === 0 ? 1 : 0.68); // alternate long and short so neighbouring labels never collide
    const dir = { x: Math.sin(angle), y: -Math.cos(angle) };
    const tip = {
      x: Math.max(130, Math.min(w - 130, fork.x + dir.x * len)),
      y: Math.max(150, fork.y + dir.y * len * 0.95),
    };
    const bend = (hash(b.id + 'b') - 0.5) * len * 0.45;
    const ctrl = { x: fork.x + dir.x * len * 0.5 - dir.y * bend, y: fork.y + dir.y * len * 0.5 + dir.x * bend };
    out.branches.push({ node: b, ctrl, tip, pts: Array.from({ length: SAMPLES + 1 }, (_, k) => bez(fork, ctrl, tip, k / SAMPLES)), order: i });
    const kids = graph.nodes.filter((n) => n.kind === 'leaf' && n.group === b.group);
    const spread = 26 + Math.min(70, Math.sqrt(kids.length) * 17);
    kids.forEach((leaf, k) => {
      const ga = k * 2.399963 + hash(leaf.id) * 0.8; // golden angle: an even, natural-looking cloud
      const r = 16 + Math.sqrt(k + 1) * (spread / Math.sqrt(Math.max(4, kids.length))) * 1.25;
      const pos = {
        x: Math.max(24, Math.min(w - 24, tip.x + Math.cos(ga) * r * 1.3)),
        y: Math.max(40, Math.min(h - 40, tip.y + Math.sin(ga) * r * 0.85 - 10)),
      };
      const t = 0.38 + 0.6 * ((k + 1) / (kids.length + 1));
      out.leaves.push({ node: leaf, branch: b.id, anchor: bez(fork, ctrl, tip, t), pos, frags: fragments(leaf.detail || leaf.label), order: k });
    });
  });
  return out;
}

function Callout({ title, style, children }) {
  return (
    <div className="mt-callout" style={style}>
      <b>{title}</b>
      {children}
    </div>
  );
}

function VectorDots({ count }) {
  const dots = Math.min(160, Math.max(0, count));
  return (
    <svg width="120" height="64" viewBox="0 0 120 64" aria-hidden="true">
      {Array.from({ length: dots }, (_, i) => (
        <circle key={i} cx={8 + hash(`x${i}`) * 104} cy={6 + hash(`y${i}`) * 52} r={1.4 + hash(`r${i}`) * 1.2} fill={GOLD} opacity={0.5 + hash(`o${i}`) * 0.5} />
      ))}
    </svg>
  );
}

export function MemoryTree() {
  const wrap = useRef(null);
  const canvas = useRef(null);
  const geo = useRef(null);
  const born = useRef({});
  const mounted = useRef(performance.now());
  const hoverRef = useRef(null);
  const focusRef = useRef(null);
  const [graph, setGraph] = useState(null);
  const [error, setError] = useState('');
  const [picked, setPicked] = useState(null);
  const [focus, setFocus] = useState(null); // an opened branch id
  const [query, setQuery] = useState('');
  const [tips, setTips] = useState({});

  useEffect(() => {
    let alive = true;
    const load = () => api.get('/api/memory/graph')
      .then((g) => { if (alive) { setGraph(g); setError(''); } })
      .catch((e) => alive && setError(e.message || 'Could not load memory'));
    load();
    const timer = setInterval(load, 20000);
    return () => { alive = false; clearInterval(timer); };
  }, []);

  // Voice / UI: "open episodic memories" selects that branch.
  useEffect(() => {
    if (!graph) return undefined;
    return registerSections('memory', graph.sections, (id) => { setFocus(id); setPicked(null); setQuery(''); });
  }, [graph]);
  useEffect(() => { focusRef.current = focus; }, [focus]);

  useEffect(() => {
    if (!graph) return;
    const now = performance.now();
    const first = Object.keys(born.current).length === 0;
    let b = 0;
    let l = 0;
    graph.nodes.forEach((n) => {
      if (born.current[n.id] !== undefined) return;
      const stagger = n.kind === 'branch' ? 300 + b * 260 : 1500 + Math.min(l, 80) * 14;
      if (n.kind === 'branch') b += 1; else l += 1;
      born.current[n.id] = REDUCED ? -1e9 : first ? mounted.current + stagger : now;
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
    let lastTips = '';

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
      return REDUCED ? p : { x: p.x + Math.sin(time / 1700 + p.y / 120) * 4.5 * depth, y: p.y + Math.cos(time / 2100 + p.x / 150) * 2.2 * depth };
    };

    function strand(points, progress, width, alpha, color, offset) {
      const n = Math.max(2, Math.floor(points.length * progress));
      ctx.beginPath();
      for (let k = 0; k < n; k += 1) {
        const p = points[k];
        const q = points[Math.min(k + 1, points.length - 1)];
        const len = Math.hypot(q.x - p.x, q.y - p.y) || 1;
        const x = p.x - ((q.y - p.y) / len) * offset;
        const y = p.y + ((q.x - p.x) / len) * offset;
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
      const focusId = focusRef.current;
      ctx.clearRect(0, 0, w, h);
      ctx.lineCap = 'round';

      // Trunk: a twisting bundle of strands, as in the picture.
      const trunkP = ease((time - mounted.current) / 1200);
      for (let s = 0; s < 9; s += 1) {
        const off = (s - 4) * 3.2;
        const pts = Array.from({ length: 18 }, (_, k) => {
          const t = k / 17;
          const wob = Math.sin(t * 5 + s) * 3.5 * (1 - t);
          return sway({ x: g.base.x + off * (1 - t * 0.55) + wob, y: g.base.y + (g.fork.y - g.base.y) * t }, time);
        });
        strand(pts, trunkP, s === 4 ? 1.8 : 1.1, s === 4 ? 0.9 : 0.55, `rgb(${TEAL})`, 0);
      }
      ctx.shadowColor = 'rgb(60,200,190)';
      ctx.shadowBlur = 24;
      strand([sway(g.base, time), sway(g.fork, time)], trunkP, 16, 0.07, 'rgb(60,200,190)', 0);
      ctx.shadowBlur = 0;

      const tips = {};
      g.branches.forEach((br) => {
        const p = ease((time - (born.current[br.node.id] ?? mounted.current)) / 1500);
        if (p <= 0) return;
        const dim = focusId && focusId !== br.node.group ? 0.25 : 1;
        const pts = br.pts.map((q) => sway(q, time));
        ctx.globalAlpha = dim;
        ctx.shadowColor = 'rgb(60,200,190)';
        ctx.shadowBlur = 14;
        strand(pts, p, 9, 0.1, 'rgb(60,200,190)', 0);
        ctx.shadowBlur = 0;
        [-3.4, -1.7, 0, 1.7, 3.4].forEach((o) => strand(pts, p, 1, o === 0 ? 0.95 : 0.5, `rgb(${TEAL})`, o));
        ctx.globalAlpha = 1;
        const end = pts[Math.max(1, Math.floor(pts.length * p)) - 1];
        tips[br.node.group] = { p: end, grown: p, dim };
        if (p > 0.95 && !REDUCED) { // light flowing out along the branch
          for (let k = 0; k < 4; k += 1) {
            const f = (time / 2800 + k / 4 + hash(br.node.id)) % 1;
            const q = pts[Math.floor(f * (pts.length - 1))];
            ctx.beginPath();
            ctx.arc(q.x, q.y, 1.9, 0, 7);
            ctx.fillStyle = `rgba(230,255,250,${0.85 * dim})`;
            ctx.shadowColor = '#7ff';
            ctx.shadowBlur = 8;
            ctx.fill();
            ctx.shadowBlur = 0;
          }
        }
      });

      // Twigs, nodes and word-fragments
      const hover = hoverRef.current;
      g.leaves.forEach((lf) => {
        const tip = tips[lf.node.group];
        const p = ease((time - (born.current[lf.node.id] ?? mounted.current)) / 800);
        if (p <= 0 || !tip || tip.grown < 0.9) return;
        const dim = focusId && focusId !== lf.node.group ? 0.2 : 1;
        const a = sway(lf.anchor, time);
        const e = sway(lf.pos, time);
        const x = a.x + (e.x - a.x) * p;
        const y = a.y + (e.y - a.y) * p;
        ctx.globalAlpha = dim;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.quadraticCurveTo((a.x + x) / 2 + 6, (a.y + y) / 2 - 6, x, y);
        ctx.strokeStyle = `rgba(${TEAL},.5)`;
        ctx.lineWidth = 0.9;
        ctx.stroke();
        lf.frags.forEach((word, k) => {
          const ang = hash(lf.node.id + word) * 6.28;
          const fx = x + Math.cos(ang) * (14 + k * 5) * p;
          const fy = y + Math.sin(ang) * (14 + k * 5) * p;
          ctx.beginPath();
          ctx.moveTo(x, y);
          ctx.lineTo(fx, fy);
          ctx.strokeStyle = `rgba(${TEAL},.28)`;
          ctx.lineWidth = 0.6;
          ctx.stroke();
          ctx.beginPath();
          ctx.arc(fx, fy, 1.7, 0, 7);
          ctx.fillStyle = 'rgba(255,220,130,.75)';
          ctx.fill();
        });
        const isHot = hover === lf.node.id;
        const twinkle = REDUCED ? 0 : Math.sin(time / 650 + hash(lf.node.id) * 6) * 0.7;
        ctx.beginPath();
        ctx.arc(x, y, (isHot ? 7.5 : 4.6 + twinkle) * (0.4 + 0.6 * p), 0, 7);
        ctx.fillStyle = GOLD;
        ctx.shadowColor = GOLD;
        ctx.shadowBlur = isHot ? 26 : 12;
        ctx.fill();
        ctx.shadowBlur = 0;
        lf.screen = { x, y };
        if (isHot || (graph.total <= 14 && p > 0.9)) {
          ctx.font = '11.5px system-ui, sans-serif';
          ctx.textAlign = 'center';
          ctx.fillStyle = isHot ? '#fff' : 'rgba(224,255,250,.72)';
          ctx.fillText(lf.node.label.slice(0, 26), x, y - 12);
        }
        ctx.globalAlpha = 1;
      });

      // Branch labels (spaced capitals, like the picture) and tip nodes
      g.branches.forEach((br) => {
        const tip = tips[br.node.group];
        if (!tip || tip.grown < 0.85) return;
        ctx.globalAlpha = tip.dim;
        ctx.beginPath();
        ctx.arc(tip.p.x, tip.p.y, 6.5, 0, 7);
        ctx.fillStyle = GOLD;
        ctx.shadowColor = GOLD;
        ctx.shadowBlur = 20;
        ctx.fill();
        ctx.shadowBlur = 0;
        ctx.font = '600 13px system-ui, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillStyle = '#f2fffd';
        ctx.shadowColor = '#000';
        ctx.shadowBlur = 8;
        ctx.fillText(`${br.node.label.toUpperCase()}`, tip.p.x, tip.p.y + 26);
        ctx.fillStyle = 'rgba(190,240,235,.75)';
        ctx.font = '11px system-ui, sans-serif';
        ctx.fillText(`${br.node.count} item${br.node.count === 1 ? '' : 's'}`, tip.p.x, tip.p.y + 41);
        ctx.shadowBlur = 0;
        ctx.globalAlpha = 1;
        br.screen = tip.p;
      });

      ctx.beginPath();
      ctx.arc(g.base.x, g.base.y - 14, 7 + (REDUCED ? 0 : Math.sin(time / 600) * 1.4), 0, 7);
      ctx.fillStyle = GOLD;
      ctx.shadowColor = GOLD;
      ctx.shadowBlur = 24;
      ctx.fill();
      ctx.shadowBlur = 0;

      // Share branch-tip positions with the callout boxes (only when they changed enough to matter).
      const snapshot = JSON.stringify(Object.fromEntries(Object.entries(tips).map(([k, v]) => [k, [Math.round(v.p.x / 8), Math.round(v.p.y / 8)]])));
      if (snapshot !== lastTips) { lastTips = snapshot; setTips(Object.fromEntries(Object.entries(tips).map(([k, v]) => [k, v.p]))); }
      raf = requestAnimationFrame(frame);
    }
    raf = requestAnimationFrame(frame);
    return () => { cancelAnimationFrame(raf); ro.disconnect(); };
  }, [graph]);

  function nearest(evt) {
    const rect = canvas.current.getBoundingClientRect();
    const x = evt.clientX - rect.left;
    const y = evt.clientY - rect.top;
    let leaf = null;
    let bestD = 16;
    (geo.current?.leaves || []).forEach((lf) => {
      if (!lf.screen) return;
      const d = Math.hypot(lf.screen.x - x, lf.screen.y - y);
      if (d < bestD) { leaf = lf.node; bestD = d; }
    });
    let branch = null;
    (geo.current?.branches || []).forEach((br) => {
      if (br.screen && Math.hypot(br.screen.x - x, br.screen.y + 20 - y) < 46) branch = br.node;
    });
    return { leaf, branch };
  }

  const items = useMemo(() => {
    if (!graph || !focus) return [];
    const q = query.trim().toLowerCase();
    return graph.nodes.filter((n) => n.kind === 'leaf' && n.group === focus)
      .filter((n) => !q || `${n.label} ${n.detail || ''}`.toLowerCase().includes(q));
  }, [graph, focus, query]);
  const focusLabel = graph?.nodes.find((n) => n.id === `branch:${focus}`)?.label;
  const total = graph?.total || 0;
  const call = graph?.callouts || {};
  // Callouts sit in fixed spots; a thin line joins each to its branch.
  const SPOTS = {
    episodic: { style: { left: 18, top: 48 }, anchor: (r) => [18 + 215, 48 + 34], tip: 'episodic' },
    relations: { style: { left: 18, top: '58%' }, anchor: (r) => [18 + 215, r.h * 0.58 + 34], tip: 'concepts' },
    preferences: { style: { right: 18, top: 48 }, anchor: (r) => [r.w - 18 - 215, 48 + 34], tip: 'preference' },
    vectors: { style: { right: 18, bottom: 18 }, anchor: (r) => [r.w - 18 - 215, r.h - 70], tip: 'arch' },
  };
  const box = wrap.current ? { w: wrap.current.clientWidth, h: wrap.current.clientHeight } : { w: 0, h: 0 };
  const lines = Object.values(SPOTS).map((sp) => (tips[sp.tip] ? { a: sp.anchor(box), b: tips[sp.tip], k: sp.tip } : null)).filter(Boolean);

  return (
    <div ref={wrap} className="mt-wrap">
      <canvas
        ref={canvas}
        aria-label="Memory tree"
        style={{ display: 'block', cursor: 'pointer' }}
        onMouseMove={(e) => { const n = nearest(e); hoverRef.current = n.leaf ? n.leaf.id : null; }}
        onMouseLeave={() => { hoverRef.current = null; }}
        onClick={(e) => {
          const n = nearest(e);
          if (n.leaf) { setPicked(n.leaf); } else if (n.branch) { setFocus(n.branch.group); setPicked(null); setQuery(''); } else { setPicked(null); }
        }}
      />
      <div className="mt-title">MEMORY TREE <span>{graph ? `${total} remembered` : 'growing…'}</span></div>
      {error && <div role="alert" className="mt-error">{error}</div>}

      {graph && !focus && (
        <>
          <svg className="mt-lines" width={box.w} height={box.h} aria-hidden="true">
            {lines.map((l) => <line key={l.k} x1={l.a[0]} y1={l.a[1]} x2={l.b.x} y2={l.b.y} />)}
          </svg>
          {call.episodic?.length > 0 && (
            <Callout title="EPISODIC MEMORIES" style={SPOTS.episodic.style}>
              {call.episodic.map((e, i) => <div key={i}>{e.time ? `${new Date(e.time).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}: ` : ''}{e.label}</div>)}
            </Callout>
          )}
          {call.relations?.length > 0 && (
            <Callout title="ENTITY RELATIONS" style={SPOTS.relations.style}>
              {call.relations.map((r, i) => <div key={i}>{r.b} ({r.rel}) → {r.a}</div>)}
            </Callout>
          )}
          {call.preferences?.length > 0 && (
            <Callout title="USER PREFERENCES" style={SPOTS.preferences.style}>
              {call.preferences.map((p, i) => <div key={i}>{p}</div>)}
            </Callout>
          )}
          {call.vectors > 0 && (
            <Callout title="SEMANTIC REFLECTION VECTORS" style={SPOTS.vectors.style}>
              <VectorDots count={call.vectors} />
              <div>{call.vectors} stored vectors</div>
            </Callout>
          )}
        </>
      )}

      {graph && total === 0 && (
        <div className="mt-empty">
          <p>Nothing here yet.</p>
          <p>Tell Atulya about yourself, e.g. “my wife is Priya” or “I live in Delhi”, and watch it grow.</p>
        </div>
      )}

      {focus && (
        <aside className="mt-drawer" aria-label={focusLabel}>
          <header>
            <button type="button" onClick={() => { setFocus(null); setQuery(''); }} aria-label="Back to the tree">← Tree</button>
            <strong>{focusLabel}</strong>
            <span>{items.length}</span>
          </header>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search this branch" />
          <ul>
            {items.map((n) => (
              <li key={n.id} className={picked?.id === n.id ? 'on' : ''} onClick={() => setPicked(n)}>
                <b>{n.label}</b>
                {n.detail && n.detail !== n.label && <span>{n.detail}</span>}
                {n.time && <small>{new Date(n.time).toLocaleString()}</small>}
              </li>
            ))}
            {!items.length && <li className="none">Nothing matches.</li>}
          </ul>
        </aside>
      )}

      {picked && !focus && (
        <div className="mt-card">
          <strong>{picked.label}</strong>
          {picked.detail && picked.detail !== picked.label && <div>{picked.detail}</div>}
          {picked.time && <small>{new Date(picked.time).toLocaleString()}</small>}
          <button type="button" onClick={() => setPicked(null)} aria-label="Close">×</button>
        </div>
      )}
    </div>
  );
}

export default MemoryTree;
