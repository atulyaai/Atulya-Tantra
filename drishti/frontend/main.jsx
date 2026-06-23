import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api, clearToken, getToken, setToken, getUser, setUser } from './api.js';
import { HolographicSpirit } from './src/pages/HolographicSpirit.jsx';
import { UserManagement } from './src/pages/UserManagement.jsx';
import './styles.css';

function Metric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value ?? '--'}</strong>
    </div>
  );
}

function renderMarkdown(text) {
  const parts = String(text || '').split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
  return parts.map((part, idx) => {
    if (part.startsWith('`') && part.endsWith('`')) return <code key={idx}>{part.slice(1, -1)}</code>;
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={idx}>{part.slice(2, -2)}</strong>;
    return part.split('\n').map((line, lineIdx) => (
      <React.Fragment key={`${idx}-${lineIdx}`}>
        {lineIdx > 0 && <br />}
        {line}
      </React.Fragment>
    ));
  });
}

const CHAT_CACHE_KEY = 'atulya-chat-messages';
const LIVE_CACHE_KEY = 'atulya-live-messages';
const DEFAULT_LIVE_MESSAGES = [
  { role: 'assistant', text: 'Atulya OS online. Systems configured at peak efficiency. Ready to orchestrate, sir.' },
];
const WAKE_PHRASES = ['hey atulya', 'atulya'];

function loadCachedMessages(key, fallback = []) {
  try {
    const raw = localStorage.getItem(key);
    const parsed = raw ? JSON.parse(raw) : null;
    return Array.isArray(parsed) ? parsed : fallback;
  } catch {
    return fallback;
  }
}

function cacheMessages(key, messages) {
  try {
    localStorage.setItem(key, JSON.stringify(messages.slice(-120)));
  } catch {}
}

function normalizeHistoryMessages(messages = []) {
  return messages
    .filter((msg) => msg && (msg.role === 'user' || msg.role === 'assistant') && msg.text)
    .map((msg, idx) => ({
      id: msg.id || `${msg.created_at || 'history'}-${idx}`,
      role: msg.role,
      text: msg.text,
      provider: msg.provider,
      surface: msg.surface,
      created_at: msg.created_at,
    }));
}

function classifyIntent(text) {
  const input = String(text || '').toLowerCase().trim();
  if (!input) return { label: 'General Reasoning Context', agent: 'ORACLE', confidence: 50 };

  const intentPrototypes = {
    FORGE: {
      label: 'Forge Syntax Synthesis',
      examples: ['write code', 'build a website', 'fix this bug', 'create a function', 'write a script', 'debug this', 'implement a class', 'refactor this code', 'write a python program', 'make an app'],
      boost: ['code', 'build', 'fix', 'bug', 'website', 'app', 'function', 'script', 'test', 'implement', 'refactor', 'debug', 'class', 'module', 'api', 'database', 'sql', 'html', 'css', 'javascript', 'python'],
    },
    VISION: {
      label: 'Visual Object Assessment',
      examples: ['what do you see', 'look at this image', 'analyze this photo', 'describe the camera frame', 'scan this visual', 'what is in this picture'],
      boost: ['see', 'camera', 'look', 'image', 'photo', 'frame', 'scan', 'visual', 'picture', 'describe', 'analyze image', 'vision'],
    },
    ATHENA: {
      label: 'Yantra System Command',
      examples: ['open the browser', 'run the automation', 'search the web', 'start the device', 'stop the process', 'control the system', 'execute this command'],
      boost: ['open', 'run', 'search', 'start', 'stop', 'device', 'automation', 'control', 'execute', 'launch', 'deploy', 'schedule', 'automate'],
    },
    MEMORY: {
      label: 'Memory Retrieval',
      examples: ['what did we discuss before', 'recall our previous conversation', 'what do you remember', 'search my history', 'find saved information'],
      boost: ['remember', 'history', 'previous', 'recall', 'memory', 'saved', 'before', 'earlier', 'last time', 'forgot', 'forget'],
    },
    ORACLE: {
      label: 'General Reasoning Context',
      examples: ['explain quantum physics', 'what is the meaning of life', 'how does photosynthesis work', 'compare these options', 'summarize this article'],
      boost: [],
    },
  };

  const scores = {};
  for (const [agent, proto] of Object.entries(intentPrototypes)) {
    let score = 0;

    for (const word of proto.boost) {
      if (input.includes(word)) score += 2;
    }

    for (const example of proto.examples) {
      const exampleWords = example.split(/\s+/);
      const matched = exampleWords.filter((w) => input.includes(w)).length;
      if (matched > 0) score += (matched / exampleWords.length) * 4;
    }

    const inputWords = input.split(/\s+/);
    const commonWords = proto.examples.join(' ').split(/\s+/);
    const overlap = inputWords.filter((w) => commonWords.includes(w)).length;
    score += overlap * 0.5;

    scores[agent] = score;
  }

  const maxScore = Math.max(...Object.values(scores));
  const totalScore = Object.values(scores).reduce((a, b) => a + b, 0);
  const winnerAgent = Object.entries(scores).sort((a, b) => b[1] - a[1])[0][0];
  const winner = intentPrototypes[winnerAgent];

  const confidence = maxScore === 0
    ? 50
    : Math.min(98, 60 + (maxScore / Math.max(totalScore, 1)) * 30 + Math.min(8, Math.floor(input.length / 30)));

  return {
    label: winner.label,
    agent: winnerAgent,
    confidence: Math.round(confidence),
  };
}

function stripWakePhrase(text) {
  const trimmed = String(text || '').trim();
  const lower = trimmed.toLowerCase();
  const phrase = WAKE_PHRASES.find((item) => lower.startsWith(item));
  return phrase ? trimmed.slice(phrase.length).replace(/^[,.:;\s-]+/, '').trim() : trimmed;
}

function Dashboard({ bootstrap, load }) {
  const system = bootstrap?.system || {};
  const runs = bootstrap?.history?.runs || [];
  return (
    <section className="panel-grid">
      <div className="panel">
        <div className="panel-title">
          <h2>System</h2>
          <button onClick={load}>Refresh</button>
        </div>
        <div className="metrics">
          <Metric label="CPU" value={`${system.cpu_pct ?? '--'}%`} />
          <Metric label="RAM" value={`${system.ram_pct ?? '--'}%`} />
          <Metric label="Available RAM" value={`${system.ram_avail_gb ?? '--'} GB`} />
          <Metric label="Python" value={system.python_version || '--'} />
        </div>
      </div>
      <div className="panel">
        <div className="panel-title">
          <h2>Run History</h2>
          <span>{runs.length} runs</span>
        </div>
        <div className="table">
          {runs.slice(0, 8).map((run, idx) => (
            <div className="row" key={`${run.time}-${idx}`}>
              <span>{run.event}</span>
              <span>{run.config}</span>
              <span>{run.steps || '--'} steps</span>
            </div>
          ))}
          {runs.length === 0 && <p className="muted">No runs yet.</p>}
        </div>
      </div>
    </section>
  );
}

function LossChart({ metrics }) {
  const points = metrics.slice(-80).map((m, idx) => ({
    step: Number(m.step ?? m.run_step ?? idx),
    loss: Number(m.loss ?? m.train_loss ?? 0),
  })).filter((m) => Number.isFinite(m.loss) && m.loss > 0);
  if (!points.length) return <div className="chart empty">No loss metrics yet.</div>;
  const width = 560;
  const height = 160;
  const minLoss = Math.min(...points.map((p) => p.loss));
  const maxLoss = Math.max(...points.map((p) => p.loss));
  const minStep = Math.min(...points.map((p) => p.step));
  const maxStep = Math.max(...points.map((p) => p.step));
  const sx = (step) => maxStep === minStep ? 0 : ((step - minStep) / (maxStep - minStep)) * width;
  const sy = (loss) => maxLoss === minLoss ? height / 2 : height - ((loss - minLoss) / (maxLoss - minLoss)) * height;
  const d = points.map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${sx(p.step).toFixed(1)} ${sy(p.loss).toFixed(1)}`).join(' ');
  const bestY = sy(minLoss).toFixed(1);
  return (
    <div className="chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Loss chart">
        <line x1="0" y1={bestY} x2={width} y2={bestY} className="best-line" />
        <path d={d} />
      </svg>
      <div className="chart-meta">
        <span>Best {minLoss.toFixed(4)}</span>
        <span>Last {points[points.length - 1].loss.toFixed(4)}</span>
      </div>
    </div>
  );
}

function Training({ bootstrap, load, toast }) {
  const datasets = bootstrap?.datasets || [];
  const configs = bootstrap?.configs?.configs || [];
  const checkpoints = bootstrap?.checkpoints || [];
  const [status, setStatus] = useState(null);
  const [log, setLog] = useState([]);
  const [metrics, setMetrics] = useState([]);
  const [busy, setBusy] = useState(false);
  const terminalEndRef = useRef(null);
  const [form, setForm] = useState({
    config: configs[0]?.name || 'atulya_seed',
    dataset: datasets[0]?.id || '',
    steps: 50000,
    lr: 0.0005,
    seq_limit: 128,
    checkpoint_every: 500,
    resume_id: 'latest',
    all_datasets: true,
    stream: true,
    train_all: true,
    device: 'auto',
  });

  useEffect(() => {
    setForm((prev) => ({
      ...prev,
      config: prev.config || configs[0]?.name || 'atulya_seed',
      dataset: prev.dataset || datasets[0]?.id || '',
    }));
  }, [configs, datasets]);

  async function refreshStatus() {
    const res = await api.get('/api/training-status');
    setStatus(res);
    setLog(res.log_tail || []);
    const metricRes = await api.get('/api/training-metrics').catch(() => ({ metrics: [] }));
    setMetrics(metricRes.metrics || []);
  }

  useEffect(() => terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' }), [log]);

  useEffect(() => {
    refreshStatus().catch(() => {});
    const id = setInterval(() => refreshStatus().catch(() => {}), 4000);
    return () => clearInterval(id);
  }, []);

  async function startTraining(event) {
    event.preventDefault();
    setBusy(true);
    const payload = {
      ...form,
      data_id: form.all_datasets ? 'all' : form.dataset,
      stream_dataset: form.stream,
      train_all: form.train_all,
    };
    try {
      const res = await api.post('/api/train/start', payload);
      if (res.error) throw new Error(res.error);
      toast('success', `Training started: PID ${res.pid}`);
      await refreshStatus();
      await load();
    } catch (err) {
      toast('error', err.message);
    } finally {
      setBusy(false);
    }
  }

  async function stopTraining() {
    setBusy(true);
    try {
      const res = await api.post('/api/train/stop');
      toast('success', res.message || 'Training stopped');
      await refreshStatus();
    } catch (err) {
      toast('error', err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel-grid">
      <div className="panel">
        <div className="panel-title">
          <h2>Active Training</h2>
          <span className={status?.running ? 'badge good' : 'badge'}>{status?.running ? 'Running' : 'Idle'}</span>
        </div>
        <div className="metrics">
          <Metric label="Phase" value={status?.status?.phase} />
          <Metric label="Step" value={status?.last?.step ?? status?.last?.run_step} />
          <Metric label="Loss" value={status?.last?.loss?.toFixed?.(4)} />
          <Metric label="Backend Python" value={status?.train_python || 'current'} />
        </div>
        <LossChart metrics={metrics} />
        <div className="terminal-actions">
          <span>{log.length} lines</span>
          <button type="button" onClick={() => navigator.clipboard?.writeText(log.join('\n'))}>Copy all</button>
          <button type="button" onClick={() => setLog([])}>Clear</button>
          {status?.running && <button type="button" className="danger" disabled={busy} onClick={stopTraining}>Stop</button>}
        </div>
        <div className="terminal">
          {log.slice(-80).map((line, idx) => <div className={lineClass(line)} key={idx}>{line}</div>)}
          {!log.length && <div>No training output yet.</div>}
          <div ref={terminalEndRef} />
        </div>
      </div>
      <form className="panel form" onSubmit={startTraining}>
        <div className="panel-title"><h2>New Pipeline</h2></div>
        <label>Config<select value={form.config} onChange={(e) => setForm({ ...form, config: e.target.value })}>
          {configs.map((cfg) => <option key={cfg.name} value={cfg.name}>{cfg.name}</option>)}
        </select></label>
        <label className="check"><input type="checkbox" checked={form.all_datasets} onChange={(e) => setForm({ ...form, all_datasets: e.target.checked, stream: e.target.checked || form.stream, train_all: e.target.checked || form.train_all })} /> All Datasets</label>
        <label>Dataset<select disabled={form.all_datasets} value={form.dataset} onChange={(e) => setForm({ ...form, dataset: e.target.value })}>
          {datasets.map((ds) => <option key={ds.id} value={ds.id}>{ds.name} ({ds.size_label})</option>)}
        </select></label>
        <label>Resume<select value={form.resume_id} onChange={(e) => setForm({ ...form, resume_id: e.target.value })}>
          <option value="fresh">fresh</option>
          {checkpoints.map((item) => <option key={item.id} value={item.id}>{item.label || item.id}</option>)}
        </select></label>
        <label>Training Steps<input type="number" min="100" max="50000" value={form.steps} onChange={(e) => setForm({ ...form, steps: Number(e.target.value) })} /><small>Total optimizer steps across the selected stream, not per dataset.</small></label>
        <label>Learning Rate<input type="number" step="0.00001" value={form.lr} onChange={(e) => setForm({ ...form, lr: Number(e.target.value) })} /></label>
        <label>Sequence Limit<input type="number" value={form.seq_limit} onChange={(e) => setForm({ ...form, seq_limit: Number(e.target.value) })} /></label>
        <label>Checkpoint Every<input type="number" value={form.checkpoint_every} onChange={(e) => setForm({ ...form, checkpoint_every: Number(e.target.value) })} /></label>
        <label className="check"><input type="checkbox" checked={form.stream} disabled={form.all_datasets} onChange={(e) => setForm({ ...form, stream: e.target.checked })} /> Stream Dataset</label>
        <label className="check"><input type="checkbox" checked={form.train_all} disabled={form.all_datasets} onChange={(e) => setForm({ ...form, train_all: e.target.checked })} /> Train All Rows</label>
        <button className="primary" disabled={busy || status?.running}>{busy ? 'Working...' : 'Start Training'}</button>
      </form>
    </section>
  );
}

function lineClass(line) {
  const text = String(line).toLowerCase();
  if (text.includes('error') || text.includes('traceback')) return 'log-line bad';
  if (text.includes('warn')) return 'log-line warn';
  if (text.includes('loss')) return 'log-line good';
  return 'log-line';
}

const VORTEX_NODES = ['ECHO', 'ORACLE', 'ATHENA', 'VISION', 'FORGE', 'MEMORY'];

function HolographicVortex({ activeAgent, status, mode, onNodeSelect }) {
  const canvasRef = useRef(null);
  const particlesRef = useRef([]);
  const mouseRef = useRef({ x: 0.5, y: 0.5 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const ctx = canvas.getContext('2d');
    let raf = 0;
    let frame = 0;

    function resize() {
      const parent = canvas.parentElement;
      const rect = parent?.getBoundingClientRect();
      canvas.width = Math.max(320, Math.floor(rect?.width || 720));
      canvas.height = Math.max(280, Math.floor(rect?.height || 520));
      if (!particlesRef.current.length) {
        particlesRef.current = Array.from({ length: 1800 }, () => {
          const radius = 18 + Math.random() * 235;
          return {
            angle: Math.random() * Math.PI * 2,
            radius,
            baseRadius: radius,
            speed: (0.0015 + Math.random() * 0.0045) * (Math.random() > 0.5 ? 1 : -1),
            size: 0.45 + Math.random() * 1.35,
            alpha: 0.25 + Math.random() * 0.7,
            phase: Math.random() * Math.PI * 2,
            layer: Math.random(),
          };
        });
      }
    }

    function colorFor(particle) {
      if (mode === 'dna') {
        return `rgba(${220 + particle.layer * 35}, ${90 + particle.layer * 80}, 20, ${particle.alpha})`;
      }
      if (mode === 'chaos') {
        const r = Math.floor(120 + 100 * Math.sin(frame * 0.012 + particle.phase));
        const g = Math.floor(90 + 120 * particle.layer);
        const b = Math.floor(190 + 55 * Math.cos(frame * 0.01 + particle.phase));
        return `rgba(${r}, ${g}, ${b}, ${particle.alpha})`;
      }
      const heat = particle.radius / 255;
      const r = Math.floor(190 + 65 * Math.min(1, heat));
      const g = Math.floor(90 + 120 * Math.max(0, 1 - heat * 0.8));
      const b = Math.floor(45 + 120 * Math.max(0, 0.55 - heat));
      return `rgba(${r}, ${g}, ${b}, ${particle.alpha})`;
    }

    function draw() {
      raf = window.requestAnimationFrame(draw);
      frame += 1;
      const width = canvas.width;
      const height = canvas.height;
      const cx = width / 2;
      const cy = height / 2;
      const mouse = mouseRef.current;
      const statusBoost = status === 'thinking' ? 1.8 : status === 'speaking' ? 1.45 : status === 'listening' ? 1.25 : 1;
      const mouseX = (mouse.x - 0.5) * 70;
      const mouseY = (mouse.y - 0.5) * 45;

      ctx.fillStyle = 'rgba(2, 4, 10, 0.16)';
      ctx.fillRect(0, 0, width, height);

      const glow = ctx.createRadialGradient(cx + mouseX * 0.25, cy + mouseY * 0.25, 0, cx, cy, 230);
      glow.addColorStop(0, mode === 'gold' ? 'rgba(255, 196, 64, 0.26)' : mode === 'dna' ? 'rgba(255, 110, 30, 0.22)' : 'rgba(124, 92, 255, 0.24)');
      glow.addColorStop(0.45, 'rgba(0, 245, 255, 0.07)');
      glow.addColorStop(1, 'rgba(0, 0, 0, 0)');
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(cx, cy, 235, 0, Math.PI * 2);
      ctx.fill();

      for (let ring = 0; ring < 4; ring += 1) {
        ctx.beginPath();
        ctx.arc(cx, cy, 70 + ring * 58 + Math.sin(frame * 0.018 + ring) * 5, 0, Math.PI * 2);
        ctx.strokeStyle = ring % 2 ? 'rgba(168, 85, 247, 0.16)' : 'rgba(0, 245, 255, 0.15)';
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      particlesRef.current.forEach((particle) => {
        particle.angle += particle.speed * statusBoost;
        if (mode === 'dna') {
          particle.radius = particle.baseRadius + Math.sin(frame * 0.025 + particle.phase) * 35;
        } else {
          particle.radius += (particle.baseRadius - particle.radius) * 0.035 + Math.sin(frame * 0.012 + particle.phase) * 0.45;
        }
        const pull = 1 / Math.max(1, particle.radius / 72);
        const x = cx + Math.cos(particle.angle) * particle.radius + mouseX * pull;
        const y = cy + Math.sin(particle.angle) * particle.radius * 0.66 + mouseY * pull;
        ctx.beginPath();
        ctx.arc(x, y, particle.size, 0, Math.PI * 2);
        ctx.fillStyle = colorFor(particle);
        ctx.fill();
      });

      if (mode === 'dna') {
        for (let i = 0; i < 48; i += 1) {
          const t = i / 47;
          const x = cx - 145 + t * 290;
          const y1 = cy + Math.sin(t * Math.PI * 4 + frame * 0.035) * 46;
          const y2 = cy + Math.sin(t * Math.PI * 4 + frame * 0.035 + Math.PI) * 46;
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
          ctx.beginPath();
          ctx.moveTo(x, y1);
          ctx.lineTo(x, y2);
          ctx.stroke();
          ctx.fillStyle = 'rgba(255, 170, 0, 0.72)';
          ctx.beginPath();
          ctx.arc(x, y1, 2.4, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = 'rgba(0, 245, 255, 0.68)';
          ctx.beginPath();
          ctx.arc(x, y2, 2.4, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      VORTEX_NODES.forEach((name, index) => {
        const angle = frame * 0.004 + index * ((Math.PI * 2) / VORTEX_NODES.length);
        const x = cx + Math.cos(angle) * Math.min(width * 0.34, 270);
        const y = cy + Math.sin(angle) * Math.min(height * 0.26, 165);
        const active = name === activeAgent;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(x, y);
        ctx.strokeStyle = active ? 'rgba(0, 245, 255, 0.42)' : 'rgba(124, 92, 255, 0.13)';
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(x, y, active ? 11 : 7, 0, Math.PI * 2);
        ctx.fillStyle = active ? 'rgba(0, 245, 255, 0.82)' : 'rgba(168, 85, 247, 0.48)';
        ctx.fill();
        ctx.fillStyle = active ? '#ffffff' : 'rgba(218, 226, 255, 0.68)';
        ctx.font = '700 9px Orbitron, system-ui, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(name, x, y + 25);
      });
    }

    resize();
    window.addEventListener('resize', resize);
    raf = window.requestAnimationFrame(draw);
    return () => {
      window.cancelAnimationFrame(raf);
      window.removeEventListener('resize', resize);
    };
  }, [activeAgent, mode, status]);

  function handlePointerMove(event) {
    const rect = event.currentTarget.getBoundingClientRect();
    mouseRef.current = {
      x: (event.clientX - rect.left) / rect.width,
      y: (event.clientY - rect.top) / rect.height,
    };
  }

  function handleClick(event) {
    const rect = event.currentTarget.getBoundingClientRect();
    const rx = (event.clientX - rect.left) / rect.width;
    const ry = (event.clientY - rect.top) / rect.height;
    const angle = Math.atan2(ry - 0.5, rx - 0.5);
    const normalized = (angle + Math.PI * 2) % (Math.PI * 2);
    const index = Math.round(normalized / ((Math.PI * 2) / VORTEX_NODES.length)) % VORTEX_NODES.length;
    onNodeSelect?.(VORTEX_NODES[index]);
  }

  return (
    <canvas
      ref={canvasRef}
      className={`webui-vortex-canvas ${mode}`}
      onPointerMove={handlePointerMove}
      onClick={handleClick}
      aria-label="Interactive holographic particle field"
    />
  );
}

function LiveMode({ bootstrap, toast }) {
  const checkpoints = bootstrap?.checkpoints || [];
  const providerOptions = bootstrap?.providers || [{ id: 'auto', name: 'Auto Provider', available: true }];
  const [showTelemetry, setShowTelemetry] = useState(false);
  const [telemetry, setTelemetry] = useState(null);
  const [provider, setProvider] = useState('auto');
  const [vortexMode, setVortexMode] = useState('gold');
  const [prompt, setPrompt] = useState('');
  const [messages, setMessages] = useState(() => loadCachedMessages(LIVE_CACHE_KEY, DEFAULT_LIVE_MESSAGES));
  const [events, setEvents] = useState([
    { id: 1, label: 'Oracle Active Core online', state: 'ready' },
    { id: 2, label: 'Nervous system strands energized', state: 'standby' },
    { id: 3, label: 'Memory galaxy synchronized', state: 'ready' }
  ]);
  const [status, setStatus] = useState('ready');
  const [listening, setListening] = useState(false);
  const [cameraOn, setCameraOn] = useState(false);
  const [capturedFrame, setCapturedFrame] = useState('');
  const [busy, setBusy] = useState(false);
  
  const [voiceList, setVoiceList] = useState([
    {id: "en_male", name: "Atulya Neural (Male)", lang: "en"},
    {id: "en_female", name: "Atulya Neural (Female)", lang: "en"},
    {id: "hi_male", name: "Madhur Neural (Hindi)", lang: "hi"},
    {id: "hi_female", name: "Swara Neural (Hindi)", lang: "hi"},
  ]);

  const [selectedVoice, setSelectedVoice] = useState('en_male');
  const [continuous, setContinuous] = useState(false);

  // Digital Nervous System States
  const [activeAgent, setActiveAgent] = useState('NONE');
  const [intentDetected, setIntentDetected] = useState('');
  const [intentConfidence, setIntentConfidence] = useState(0);
  const [mindStream, setMindStream] = useState([
    { time: '22:00:01', title: 'System Bootup', desc: 'Atulya organic core initialized.', type: 'system' },
    { time: '22:00:03', title: 'Strand Diagnostic', desc: 'Memory galaxy, vision lens, and vocal echo systems synced.', type: 'ready' }
  ]);
  const [selectedGalaxyNode, setSelectedGalaxyNode] = useState(null);

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const recognitionRef = useRef(null);
  const replyRef = useRef('');
  const audioRef = useRef(null);

  const galaxyNodes = [
    { id: 'tantra_voice', name: 'Vocal Echo', desc: 'Neural audio speech synthesis configuration', cluster: 'Tantra', x: 80, y: 55 },
    { id: 'tantra_mem', name: 'Memory Strands', desc: 'Hierarchical vector memory storage layer', cluster: 'Tantra', x: 190, y: 40 },
    { id: 'tantra_agent', name: 'Consciousness Core', desc: 'Specialist strand coordination router', cluster: 'Tantra', x: 280, y: 70 },
    { id: 'web_dns', name: 'Optical Vision', desc: 'Visual cognitive processing and scanner coordinates', cluster: 'Drishti', x: 90, y: 140 },
    { id: 'web_seo', name: 'Forge Compiler', desc: 'Syntax and code generation modules', cluster: 'Drishti', x: 220, y: 150 },
    { id: 'web_host', name: 'Athena Planner', desc: 'Strategic action pipeline planner', cluster: 'Drishti', x: 300, y: 120 },
    { id: 'device_ir', name: 'IR Protocol Transceiver', desc: 'Infrared appliance automation signal', cluster: 'Yantra', x: 130, y: 220 },
    { id: 'device_wifi', name: 'WiFi Transceiver', desc: 'Wireless local area network device scanning', cluster: 'Yantra', x: 250, y: 210 }
  ];

  useEffect(() => {
    cacheMessages(LIVE_CACHE_KEY, messages);
  }, [messages]);

  useEffect(() => {
    api.get('/api/chat/history')
      .then((res) => {
        const liveMessages = normalizeHistoryMessages(res.messages || []).filter((msg) => msg.surface === 'live');
        if (liveMessages.length) setMessages(liveMessages.slice(-20));
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    async function loadVoices() {
      try {
        const res = await api.getVoices();
        if (res && res.voices) {
          setVoiceList(res.voices);
        }
      } catch (err) {
        console.error('Failed to load voice profiles', err);
      }
    }
    loadVoices();
  }, []);

  function addEvent(label, state = 'active') {
    setEvents((prev) => [{ id: Date.now(), label, state }, ...prev].slice(0, 8));
  }

  function addMindStep(title, desc, type = 'process') {
    const now = new Date();
    const timeStr = now.toTimeString().split(' ')[0];
    setMindStream((prev) => [
      { time: timeStr, title, desc, type },
      ...prev
    ].slice(0, 10));
  }

  function normalizeTelemetryEvent(item, idx) {
    const now = new Date();
    return {
      time: item.time || telemetry?.updated_at?.split(' ')?.[1] || now.toTimeString().split(' ')[0],
      title: item.title || `Telemetry ${idx + 1}`,
      desc: item.desc || item.label || 'No telemetry details reported.',
      type: item.type || item.state || 'ready',
    };
  }

  useEffect(() => {
    if (!showTelemetry) return undefined;
    let cancelled = false;

    async function loadTelemetry() {
      try {
        const res = await api.get('/api/telemetry');
        if (!cancelled) setTelemetry(res);
      } catch (err) {
        if (!cancelled) {
          setTelemetry((prev) => ({
            ...(prev || {}),
            error: err.message,
            events: [{ title: 'Telemetry Offline', desc: err.message, type: 'error' }],
          }));
        }
      }
    }

    loadTelemetry();
    const interval = window.setInterval(loadTelemetry, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [showTelemetry]);

  async function startCamera() {
    if (cameraOn) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
      setCameraOn(true);
      setStatus('seeing');
      setActiveAgent('VISION');
      addEvent('Optical scanner active', 'seeing');
      addMindStep('Optical Core Engaged', 'Camera scanner active and scanning spatial environment.', 'seeing');
    } catch (err) {
      toast('error', err.message);
      addEvent('Camera access blocked', 'error');
    }
  }

  function stopCamera() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setCameraOn(false);
    setStatus('ready');
    setActiveAgent('NONE');
    addEvent('Optical scanner offline', 'standby');
    addMindStep('Optical Core Standby', 'Camera scan stream stopped.', 'ready');
  }

  function captureFrame() {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 360;
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    const frame = canvas.toDataURL('image/jpeg', 0.8);
    setCapturedFrame(frame);
    setPrompt('Analyze this camera frame and describe what is visible.');
    setStatus('reading');
    addEvent('Visual frame captured. Analyzing pixels...', 'seeing');
    addMindStep('Visual Frame Cached', 'Image matrix captured. Analyzing visual components.', 'seeing');
  }

  function speakNeural(text) {
    if (!text.trim()) return;
    setStatus('speaking');
    setActiveAgent('ECHO');
    addEvent('Routing output to high-fidelity TTS synthesizer...', 'speaking');
    addMindStep('Vocal Synthesis Request', 'Sending output text to edge-tts neural voice compiler.', 'speaking');
    
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    
    if (audioRef.current) {
      try {
        audioRef.current.pause();
      } catch(e) {}
      audioRef.current = null;
    }
    
    api.tts(text, selectedVoice)
      .then((res) => {
        if (res.error) throw new Error(res.error);
        
        if (res.audio_base64) {
          addEvent('Streaming response through audio pipeline...', 'speaking');
          const audio = new Audio("data:audio/mp3;base64," + res.audio_base64);
          audioRef.current = audio;
          audio.onplay = () => {
            setStatus('speaking');
            setActiveAgent('ECHO');
            addMindStep('Consciousness Vocalizing', 'Streaming synthesized premium audio through speakers.', 'speaking');
          };
          audio.onended = () => {
            setStatus('ready');
            setActiveAgent('NONE');
            audioRef.current = null;
            addEvent('Vocalized response sequence complete', 'ready');
            addMindStep('Voice Flow Complete', 'Consciousness returned to standby.', 'ready');
            
            if (continuous) {
              setTimeout(() => {
                if (continuous && !listening && !busy) {
                  addEvent('Continuous Mode active. Opening microphone...', 'listening');
                  startListening();
                }
              }, 400);
            }
          };
          audio.onerror = (e) => {
            console.error('Audio play error, falling back', e);
            speakBrowserFallback(text);
          };
          audio.play().catch((err) => {
            console.error('Play action failed', err);
            speakBrowserFallback(text);
          });
        } else {
          speakBrowserFallback(text);
        }
      })
      .catch((err) => {
        console.error('Neural TTS synthesis failed, using browser fallback', err);
        speakBrowserFallback(text);
      });
  }

  function speakBrowserFallback(text) {
    if (!('speechSynthesis' in window) || !text.trim()) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.96;
    utterance.pitch = 1.02;
    utterance.onstart = () => {
      setStatus('speaking');
      setActiveAgent('ECHO');
    };
    utterance.onend = () => {
      setStatus('ready');
      setActiveAgent('NONE');
      addEvent('Vocalized fallback complete', 'ready');
      if (continuous) {
        setTimeout(() => startListening(), 400);
      }
    };
    window.speechSynthesis.speak(utterance);
    addEvent('Playing local synthetic voice fallback', 'speaking');
  }

  function startListening() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      toast('error', 'Speech recognition is not available in this browser.');
      addEvent('Speech recognition unavailable', 'error');
      return;
    }
    
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch(e) {}
    }
    
    if (audioRef.current) {
      try { audioRef.current.pause(); } catch(e) {}
      audioRef.current = null;
    }
    
    const recognition = new SpeechRecognition();
    recognition.lang = 'en-IN';
    recognition.interimResults = true;
    recognition.continuous = false;
    
    recognition.onstart = () => {
      setListening(true);
      setStatus('listening');
      setActiveAgent('ECHO');
      addEvent('Sensors active. Listening...', 'listening');
      addMindStep('Vocal Input Sensor Engaged', 'Microphone active. Listening for acoustic queries.', 'listening');
    };
    
    recognition.onresult = (event) => {
      const text = Array.from(event.results).map((result) => result[0].transcript).join(' ');
      setPrompt(text);
      if (event.results[event.results.length - 1].isFinal) {
        recognition.stop();
        const lower = text.trim().toLowerCase();
        if (continuous && !WAKE_PHRASES.some((phrase) => lower.includes(phrase))) {
          addEvent('Wake word not detected. Standing by...', 'ready');
          addMindStep('Wake Word Gate', 'Hands-free mode ignored ambient speech without wake phrase.', 'ready');
          setStatus('ready');
          setActiveAgent('NONE');
          setTimeout(() => {
            if (continuous && !busy) startListening();
          }, 700);
          return;
        }
        sendLive(stripWakePhrase(text));
      }
    };
    
    recognition.onerror = (event) => {
      setListening(false);
      setStatus('ready');
      setActiveAgent('NONE');
      if (event.error === 'no-speech' && continuous) {
        setTimeout(() => {
          if (continuous && !listening && !busy) {
            startListening();
          }
        }, 1000);
        return;
      }
      toast('error', event.error || 'Audio stream failed');
      addEvent('Mic pipeline error: ' + event.error, 'error');
    };
    
    recognition.onend = () => {
      setListening(false);
    };
    
    recognitionRef.current = recognition;
    recognition.start();
  }

  function stopListening() {
    recognitionRef.current?.stop();
    setListening(false);
    setStatus('ready');
    setActiveAgent('NONE');
    addEvent('Microphone sensor offline', 'standby');
    addMindStep('Vocal Input Sensor Disengaged', 'Microphone offline.', 'ready');
  }

  function toggleVoice() {
    if (listening) {
      stopListening();
    } else {
      startListening();
    }
  }

  function activateNode(agent, label, desc) {
    setActiveAgent(agent);
    addEvent(`${label} node selected`, 'ready');
    addMindStep(label, desc, 'ready');
    setMessages((prev) => [
      ...prev,
      {
        role: 'assistant',
        text: `${label} online. ${desc}`,
        id: `${Date.now()}-${agent}`,
      },
    ].slice(-40));
  }

  function handleVortexNode(agent) {
    const descriptions = {
      ORACLE: 'Research and general reasoning prompts route through this strand.',
      ATHENA: 'Planning state is active; requests will show routing and execution steps.',
      FORGE: 'Synthesis state is active after provider responses and tool results.',
      MEMORY: 'Persistent chat history is available; vector memory remains a deeper backend upgrade.',
      VISION: 'Camera capture can be opened from Start Vision; model vision analysis is limited.',
      ECHO: 'Voice input and speech output controls are available from the mic and hands-free controls.',
    };
    activateNode(agent, agent, descriptions[agent] || 'Node selected.');
  }

  function cycleVortexMode() {
    const modes = ['gold', 'dna', 'chaos'];
    const next = modes[(modes.indexOf(vortexMode) + 1) % modes.length];
    setVortexMode(next);
    addEvent(`Hologram mode set to ${next.toUpperCase()}`, 'ready');
    addMindStep('Hologram Mode', `Particle field renderer switched to ${next.toUpperCase()} mode.`, 'ready');
  }

  // The Digital Nervous System Sequential State Stimulation Flow
  function sendLive(voiceText) {
    const text = (voiceText || prompt).trim();
    if (!text || busy) return;
    const id = Date.now();
    const cameraNote = capturedFrame ? '\n\nCamera frame is captured in the Live Mode panel. Use vision when vision processing is active.' : '';
    const intent = classifyIntent(text);
    
    setPrompt('');
    setBusy(true);
    setStatus('thinking');
    setIntentDetected(intent.label);
    setIntentConfidence(intent.confidence);
    replyRef.current = '';
    setMessages((prev) => [
      ...prev,
      { role: 'user', text, id: `${id}-user` },
      { role: 'assistant', text: '', id },
    ]);

    // Step 1: Echo inputs
    setActiveAgent('ECHO');
    addMindStep('Vocal Input Cached', `Acoustic query transcribed: "${text}"`, 'process');
    addEvent('Query transcribed. Aligning intent...', 'thinking');

    // Step 2: Routing to Athena Planning Strand after 400ms
    setTimeout(() => {
      setActiveAgent('ATHENA');
      addMindStep('Routing to Athena Strand', 'Athena strand planning logical execution tree.', 'process');
      
      // Step 3: Routing to Long-Term Memory Galaxy after 800ms
      setTimeout(() => {
        setActiveAgent('MEMORY');
        addMindStep('Querying Memory Galaxy', 'Memory galaxy stars parsed for related vector context.', 'process');
        
        // Step 4: Routing to Oracle Research Strand after 1200ms
        setTimeout(() => {
          setActiveAgent(intent.agent);
          addMindStep('Intent Determined', `Classified as ${intent.label} (${intent.confidence}% confidence)`, 'process');
          addMindStep('Oracle Logic Mapping', 'Oracle strand querying local knowledge core.', 'process');
          
          // Step 5: Execute API route after 1600ms
          setTimeout(() => {
            addEvent('Routing command to brain strand...', 'thinking');
            
            api.post('/api/voice/chat', {
              prompt: `${text}${cameraNote}`,
              voice: selectedVoice,
              model_id: provider,
              provider,
              history: messages
                .filter((msg) => msg.text)
                .slice(-10)
                .map((msg) => ({ role: msg.role, content: msg.text })),
            })
              .then((res) => {
                setBusy(false);
                if (res.error && !res.response_text) throw new Error(res.error);
                
                replyRef.current = res.response_text || "";
                setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: res.response_text } : msg));
                
                // Step 6: Synthesis active (Forge node stimulation)
                setActiveAgent('FORGE');
                const provider = res.provider_name || 'Atulya OS Core';
                addMindStep('Provider Brain Responded', `Atulya OS obtained answer from provider: ${provider}`, 'process');
                addEvent(`Computed via ${provider}. Voicing output...`, 'speaking');
                
                setTimeout(() => {
                  if (res.audio_base64) {
                    const audio = new Audio("data:audio/mp3;base64," + res.audio_base64);
                    audioRef.current = audio;
                    setStatus('speaking');
                    setActiveAgent('ECHO');
                    audio.onplay = () => {
                      setStatus('speaking');
                      setActiveAgent('ECHO');
                      addMindStep('Consciousness Vocalizing', 'Streaming response through speakers.', 'speaking');
                    };
                    audio.onended = () => {
                      setStatus('ready');
                      setActiveAgent('NONE');
                      audioRef.current = null;
                      addEvent('Assistant reply vocalized successfully', 'ready');
                      addMindStep('Voice Flow Complete', 'Consciousness returned to standby.', 'ready');
                      
                      if (continuous) {
                        setTimeout(() => {
                          if (continuous && !listening && !busy) {
                            addEvent('Continuous Mode active. Opening microphone...', 'listening');
                            startListening();
                          }
                        }, 400);
                      }
                    };
                    audio.play().catch((err) => {
                      console.error('Play action failed', err);
                      speakBrowserFallback(replyRef.current);
                    });
                  } else {
                    if (res.error) addEvent(res.error, 'error');
                    speakBrowserFallback(replyRef.current);
                  }
                }, 400);
              })
              .catch((err) => {
                setBusy(false);
                setStatus('ready');
                setActiveAgent('NONE');
                addEvent('Oracle response execution failed', 'error');
                addMindStep('System Error', ` strand execution failed: ${err.message}`, 'error');
                setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: `Command Failure: ${err.message}` } : msg));
                
                if (continuous) {
                  setTimeout(() => startListening(), 2000);
                }
              });
          }, 400);
        }, 400);
      }, 400);
    }, 400);
  }

  if (!showTelemetry) {
    const visibleStream = mindStream.slice(0, 8);
    const galaxyPreviewNodes = galaxyNodes.slice(0, 8);
    const readyProviderCount = providerOptions.filter((item) => item.available && item.id !== 'auto').length;
    return (
      <div className="v3-shell">
        <header className="v3-topbar">
          <div className="v3-logo">ATULYA <span>NEURAL OS v3</span></div>
          <nav className="v3-topnav">
            <button className="on" type="button">Neural Core</button>
            <button type="button" onClick={() => setShowTelemetry(true)}>Telemetry</button>
            <button type="button" onClick={cycleVortexMode}>Hologram</button>
          </nav>
          <div className="v3-topright">
            <span>Gesture: {listening ? 'Listening' : 'Ready'}</span>
            <span>Providers: {readyProviderCount}</span>
            <span>Model: {provider.toUpperCase()}</span>
            <span className="v3-user-pill">{bootstrap?.user?.role?.toUpperCase?.() || 'USER'}</span>
          </div>
        </header>

        <main className="v3-main">
          <aside className="v3-panel v3-left-panel">
            <div className="v3-panel-hdr">
              <span>Consciousness Stream</span>
              <strong>{busy ? 'Active' : 'Ready'}</strong>
            </div>
            <div className="v3-stream-list">
              {visibleStream.map((item, idx) => (
                <button type="button" className={`v3-stream-item ${item.type}`} key={`${item.time}-${idx}`}>
                  <small>[{item.time}]</small>
                  <b>{item.title}</b>
                  <span>{item.desc}</span>
                </button>
              ))}
            </div>
            <div className="v3-gesture-panel">
              <div className="v3-subtitle">Gesture Control Map</div>
              <div className="v3-gesture-grid">
                {[
                  ['Open Palm', 'Expand Orb'],
                  ['Fist', 'Collapse'],
                  ['Point', 'Select Node'],
                  ['Peace', 'Oracle Mode'],
                  ['Pinch', 'Zoom Core'],
                  ['OK Sign', 'Confirm'],
                ].map(([name, action]) => (
                  <button type="button" key={name} onClick={cycleVortexMode}>
                    <b>{name}</b>
                    <span>{action}</span>
                  </button>
                ))}
              </div>
            </div>
          </aside>

          <section className="v3-holo-center">
            {cameraOn && <video className="v3-camera-feed" ref={videoRef} autoPlay playsInline muted />}
            <HolographicVortex activeAgent={activeAgent} status={status} mode={vortexMode} onNodeSelect={handleVortexNode} />
            <div className="v3-scan-line" />
            <div className="v3-corner tl" />
            <div className="v3-corner tr" />
            <div className="v3-corner bl" />
            <div className="v3-corner br" />

            <div className="v3-hud tl"><span>ATULYA OS v3.0</span><span>Neural Mesh: Active</span><span>Particles: 1800</span></div>
            <div className="v3-hud tr"><span>Status: {status.toUpperCase()}</span><span>Vortex: {vortexMode.toUpperCase()}</span><span>Provider: {provider.toUpperCase()}</span></div>
            <div className="v3-hud bl"><span>Node: {activeAgent}</span><span>Intent: {intentDetected || 'Standby'}</span></div>
            <div className="v3-hud br"><span>Wake: {continuous ? 'Hey Atulya' : 'Manual'}</span><span>Voice: {selectedVoice}</span></div>

            <div className="v3-float-panel oracle"><b>Oracle</b><span>Research: {activeAgent === 'ORACLE' ? 'Active' : 'Idle'}</span><span>Depth: {messages.length}</span></div>
            <div className="v3-float-panel neural"><b>Neural</b><span>Signal: {busy ? 'Routing' : 'Stable'}</span><span>Intent: {intentConfidence || '--'}%</span></div>
            <div className="v3-float-panel forge"><b>Forge</b><span>Output: {status === 'speaking' ? 'Vocal' : 'Text'}</span><span>Queue: {busy ? 1 : 0}</span></div>
            <div className="v3-float-panel echo"><b>Echo</b><span>Mic: {listening ? 'Live' : 'Idle'}</span><span>Wake: {continuous ? 'Ready' : 'Off'}</span></div>

            <div className="v3-node-ring">
              {VORTEX_NODES.map((node) => (
                <button key={node} type="button" className={activeAgent === node ? 'active' : ''} onClick={() => handleVortexNode(node)}>
                  {node}
                </button>
              ))}
            </div>

            <button type="button" className={`v3-core ${status}`} onClick={toggleVoice} aria-label="Toggle voice input"><span /></button>

            <div className="v3-engage-bar">
              <button type="button" onClick={() => handleVortexNode('ORACLE')}>Engage Oracle</button>
              <button type="button" onClick={toggleVoice}>{listening ? 'Stop Mic' : 'Enable Voice'}</button>
              <button type="button" onClick={cameraOn ? stopCamera : startCamera}>{cameraOn ? 'Close Lens' : 'Neural Lens'}</button>
              <button type="button" onClick={captureFrame} disabled={!cameraOn}>Scan</button>
              <button type="button" onClick={cycleVortexMode}>Vortex</button>
              <select value={provider} onChange={(event) => setProvider(event.target.value)}>
                {providerOptions.map((item) => (
                  <option key={item.id} value={item.id}>{item.available ? 'Ready - ' : 'Off - '}{item.name}</option>
                ))}
              </select>
              <select value={selectedVoice} onChange={(event) => setSelectedVoice(event.target.value)}>
                {voiceList.map((voice) => <option key={voice.id} value={voice.id}>{voice.name}</option>)}
              </select>
            </div>
          </section>

          <aside className="v3-panel v3-right-panel">
            <section className="v3-vision-wrap">
              <div className="v3-panel-hdr"><span>Vision / Hand Track</span><strong>{cameraOn ? 'Live' : capturedFrame ? 'Captured' : 'Standby'}</strong></div>
              <div className="v3-vision-inner" onClick={(event) => {
                const rect = event.currentTarget.getBoundingClientRect();
                const x = Math.round(((event.clientX - rect.left) / rect.width) * 100);
                const y = Math.round(((event.clientY - rect.top) / rect.height) * 100);
                addMindStep('Vision Coordinate', `Scanner coordinate selected at X ${x}%, Y ${y}%.`, 'seeing');
              }}>
                {cameraOn ? <video ref={videoRef} autoPlay playsInline muted /> : capturedFrame ? <img src={capturedFrame} alt="Captured visual frame" /> : <div className="v3-vision-empty">Optical System Standby</div>}
                <div className="v3-vision-overlay"><span className="box one">User</span><span className="box two">Display</span><span className="box three">Input</span></div>
                <canvas ref={canvasRef} hidden />
              </div>
            </section>

            <section className="v3-memory-wrap">
              <div className="v3-panel-hdr"><span>Memory Galaxy</span><strong>{galaxyPreviewNodes.length} Stars</strong></div>
              <div className="v3-memory-canvas">
                <svg viewBox="0 0 360 220" role="img" aria-label="Memory galaxy">
                  <circle cx="180" cy="110" r="8" className="core" />
                  {galaxyPreviewNodes.map((node) => (
                    <g key={node.id} onMouseEnter={() => setSelectedGalaxyNode(node)} onClick={() => {
                      setSelectedGalaxyNode(node);
                      setPrompt(`Recall memory node: ${node.name}. ${node.desc}`);
                      addMindStep('Memory Node Retrieved', `${node.name}: ${node.desc}`, 'ready');
                    }}>
                      <line x1="180" y1="110" x2={node.x} y2={node.y} />
                      <circle cx={node.x} cy={node.y} r={selectedGalaxyNode?.id === node.id ? 7 : 5} />
                      <text x={node.x} y={node.y - 9} textAnchor="middle">{node.name}</text>
                    </g>
                  ))}
                </svg>
                <div className="v3-memory-info">{selectedGalaxyNode ? `${selectedGalaxyNode.name}: ${selectedGalaxyNode.desc}` : 'Hover or click a memory node to inspect'}</div>
              </div>
            </section>

            <section className="v3-chat-wrap">
              <div className="v3-panel-hdr">
                <span>Atulya Chat</span>
                <div><strong>{busy ? 'Thinking' : 'Ready'}</strong><button type="button" onClick={() => { api.delete('/api/chat/history').catch(() => {}); setMessages(DEFAULT_LIVE_MESSAGES); }}>CLR</button></div>
              </div>
              <div className="v3-chat-msgs">
                {messages.map((msg, idx) => (
                  <div className={`v3-msg ${msg.role}`} key={msg.id || idx}>
                    <div>{renderMarkdown(msg.text || (msg.role === 'assistant' ? 'Atulya is thinking...' : ''))}</div>
                    <small>{msg.role === 'user' ? 'USER' : 'ATULYA'}</small>
                  </div>
                ))}
                {busy && <div className="v3-msg assistant thinking"><div>Atulya is thinking...</div></div>}
              </div>
              <form className="v3-chat-input" onSubmit={(event) => { event.preventDefault(); sendLive(); }}>
                <input value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder={continuous ? 'Say: Hey Atulya...' : 'Type or say: Hey Atulya...'} disabled={busy} />
                <button type="submit" disabled={busy || !prompt.trim()}>{busy ? '...' : 'Send'}</button>
              </form>
            </section>
          </aside>
        </main>

        <footer className="v3-bottom">
          <div><b>System Matrix</b><span>CPU {telemetry?.system?.cpu_pct ?? '--'}%</span><span>RAM {telemetry?.system?.ram_pct ?? '--'}%</span><span>Node {activeAgent}</span></div>
          <div className={`v3-waveform ${status}`}>{Array.from({ length: 22 }).map((_, idx) => <span key={idx} />)}</div>
          <div><b>Quick Actions</b><button type="button" onClick={() => setPrompt('Save this as a memory: ')}>+ Mem</button><button type="button" onClick={cycleVortexMode}>Vortex</button><label><input type="checkbox" checked={continuous} onChange={(e) => setContinuous(e.target.checked)} /> Hands-Free</label></div>
        </footer>
      </div>
    );
  }

  return (
    <section className="digital-organism-shell">
      <header className="panel-title telemetry-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h2>Telemetry Cockpit</h2>
        <button onClick={() => setShowTelemetry(false)} className="primary">✨ ENTER HOLOGRAM MODE</button>
      </header>
      <div className="telemetry-metrics-strip">
        <Metric label="CPU" value={`${telemetry?.system?.cpu_pct ?? '--'}%`} />
        <Metric label="RAM" value={`${telemetry?.system?.ram_pct ?? '--'}%`} />
        <Metric label="Disk Free" value={`${telemetry?.system?.disk_free_gb ?? '--'} GB`} />
        <Metric label="Uptime" value={telemetry?.system?.uptime || '--'} />
        <Metric label="Providers" value={`${(telemetry?.providers || providerOptions).filter((item) => item.available && item.id !== 'auto').length} ready`} />
      </div>
      <div className="cockpit-grid">
        
        {/* LEFT PANEL: Consciousness Stream */}
        <div className="panel consciousness-stream-panel">
          <div className="panel-title">
            <h2>Consciousness Stream</h2>
            <div className="flow-badge"><span className="pulse-indicator"></span>{telemetry?.error ? 'DEGRADED' : 'LIVE FLOW'}</div>
          </div>
          <div className="mind-flow-container">
            {(telemetry?.events?.length ? telemetry.events.map(normalizeTelemetryEvent) : mindStream).map((item, idx) => (
              <div className={`mind-step ${item.type}`} key={idx}>
                <span className="mind-time">[{item.time}]</span>
                <div className="mind-marker">
                  <div className="marker-dot" />
                  {idx < mindStream.length - 1 && <div className="marker-line" />}
                </div>
                <div className="mind-content">
                  <strong>{item.title.toUpperCase()}</strong>
                  <p>{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* CENTER COLUMN: Living Core & Agent Chamber */}
        <div className="panel center-core-panel">
          <div className="panel-title">
            <h2>Digital Organism Core</h2>
            <span className="organism-id">ATULYA SYSTEM OS</span>
          </div>

          <div className="chamber-stage">
            {/* The Floating Agent Chamber */}
            <div className="agent-chamber">
              {/* Digital Nervous System Connecting Strands */}
              <svg className="nervous-system-svg" viewBox="0 0 360 360">
                <path d="M180,45 L180,180" className={`nervous-strand oracle-strand ${activeAgent === 'ORACLE' ? 'stimulated' : ''}`} />
                <path d="M275,95 L180,180" className={`nervous-strand athena-strand ${activeAgent === 'ATHENA' ? 'stimulated' : ''}`} />
                <path d="M275,265 L180,180" className={`nervous-strand forge-strand ${activeAgent === 'FORGE' ? 'stimulated' : ''}`} />
                <path d="M180,315 L180,180" className={`nervous-strand memory-strand ${activeAgent === 'MEMORY' ? 'stimulated' : ''}`} />
                <path d="M85,265 L180,180" className={`nervous-strand vision-strand ${activeAgent === 'VISION' ? 'stimulated' : ''}`} />
                <path d="M85,95 L180,180" className={`nervous-strand echo-strand ${activeAgent === 'ECHO' ? 'stimulated' : ''}`} />
              </svg>

              {/* Orbital Nodes */}
              <div className={`agent-node node-oracle ${activeAgent === 'ORACLE' ? 'active' : ''}`} onClick={() => setActiveAgent('ORACLE')}>
                <div className="node-glow" />
                <span>ORACLE</span>
                <small>Research</small>
              </div>

              <div className={`agent-node node-athena ${activeAgent === 'ATHENA' ? 'active' : ''}`} onClick={() => setActiveAgent('ATHENA')}>
                <div className="node-glow" />
                <span>ATHENA</span>
                <small>Planning</small>
              </div>

              <div className={`agent-node node-forge ${activeAgent === 'FORGE' ? 'active' : ''}`} onClick={() => setActiveAgent('FORGE')}>
                <div className="node-glow" />
                <span>FORGE</span>
                <small>Synthesis</small>
              </div>

              <div className={`agent-node node-memory ${activeAgent === 'MEMORY' ? 'active' : ''}`} onClick={() => setActiveAgent('MEMORY')}>
                <div className="node-glow" />
                <span>MEMORY</span>
                <small>Cognition</small>
              </div>

              <div className={`agent-node node-vision ${activeAgent === 'VISION' ? 'active' : ''}`} onClick={() => setActiveAgent('VISION')}>
                <div className="node-glow" />
                <span>VISION</span>
                <small>Perception</small>
              </div>

              <div className={`agent-node node-echo ${activeAgent === 'ECHO' ? 'active' : ''}`} onClick={() => setActiveAgent('ECHO')}>
                <div className="node-glow" />
                <span>ECHO</span>
                <small>Vocalize</small>
              </div>

              {/* The Living Core */}
              <div className={`central-organism-core ${status}`}>
                <div className="hologram-glow" />
                <div className="hologram-orb">
                  <div className="hologram-core" />
                  <div className="hologram-ring ring-1" />
                  <div className="hologram-ring ring-2" />
                  <div className="hologram-ring ring-3" />
                </div>
                {status === 'speaking' && (
                  <div className="waveform-active">
                    <div className="bar bar-1" />
                    <div className="bar bar-2" />
                    <div className="bar bar-3" />
                    <div className="bar bar-4" />
                    <div className="bar bar-5" />
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="live-controls organism-controls">
            <button type="button" className={listening ? 'danger active-btn' : 'primary'} onClick={toggleVoice}>
              {listening ? 'STIMULATE MIC' : 'ENGAGE ORACLE'}
            </button>
            <button type="button" onClick={cameraOn ? stopCamera : startCamera}>
              {cameraOn ? 'CLOSE LENS' : 'ENGAGE VISION'}
            </button>
            <button type="button" onClick={captureFrame} disabled={!cameraOn}>SCAN FRAME</button>
            
            <select value={provider} onChange={(e) => setProvider(e.target.value)}>
              {providerOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.available ? 'Ready - ' : 'Off - '}{item.name}
                </option>
              ))}
            </select>
            
            <select value={selectedVoice} onChange={(e) => {
              setSelectedVoice(e.target.value);
              addEvent('Consciousness voice altered', 'ready');
            }}>
              {voiceList.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>

            <label className="check hands-free-chk">
              <input type="checkbox" checked={continuous} onChange={(e) => {
                setContinuous(e.target.checked);
                addEvent(e.target.checked ? 'Hands-Free continuous active' : 'Hands-Free deactivated', 'ready');
                if (e.target.checked && !listening && !busy && status === 'ready') {
                  startListening();
                }
              }} />
              HANDS-FREE
            </label>
          </div>
        </div>

        {/* RIGHT COLUMN: Memory Galaxy & Vision Screen */}
        <div className="panel right-vision-galaxy-panel">
          
          {/* Vision Screen with overlays */}
          <div className="vision-header">
            <h2>Vision Screen</h2>
            <span className="vision-mode">{cameraOn ? 'ACTIVE OPTICS' : 'STANDBY'}</span>
          </div>
          
          <div className="vision-stage-container">
            <video ref={videoRef} autoPlay playsInline muted />
            {!cameraOn && !capturedFrame && <div className="vision-empty">OPTICAL SYSTEM STANDBY</div>}
            {capturedFrame && !cameraOn && <img src={capturedFrame} alt="Scan analysis" />}
            
            {cameraOn && (
              <div className="vision-overlay">
                <div className="scanner-line" />
                <div className="bounding-box box-1">
                  <span className="box-label">USER: ATUL (CODING)</span>
                </div>
                <div className="bounding-box box-2">
                  <span className="box-label">MONITOR: WEBUI CORE</span>
                </div>
                <div className="bounding-box box-3">
                  <span className="box-label">KEYBOARD: INPUT SIGNAL</span>
                </div>
                <div className="vision-diagnostics">
                  <span>FPS: 30</span>
                  <span>RESOLUTION: 1280x720</span>
                  <span>FOCUS: COGNITIVE OVERLAY</span>
                </div>
              </div>
            )}
            <canvas ref={canvasRef} hidden />
          </div>

          <hr className="cockpit-divider" />

          {/* Memory Galaxy Constellation */}
          <div className="galaxy-header">
            <h2>Memory Galaxy</h2>
            <span className="galaxy-clusters">3 CLUSTERS</span>
          </div>

          <div className="galaxy-container">
            <svg className="galaxy-svg" viewBox="0 0 360 250">
              {/* Connecting strand links */}
              <line x1="180" y1="125" x2="80" y2="55" className="galaxy-strand" />
              <line x1="180" y1="125" x2="190" y2="40" className="galaxy-strand" />
              <line x1="180" y1="125" x2="280" y2="70" className="galaxy-strand" />
              <line x1="180" y1="125" x2="90" y2="140" className="galaxy-strand" />
              <line x1="180" y1="125" x2="220" y2="150" className="galaxy-strand" />
              <line x1="180" y1="125" x2="300" y2="120" className="galaxy-strand" />
              <line x1="180" y1="125" x2="130" y2="220" className="galaxy-strand" />
              <line x1="180" y1="125" x2="250" y2="210" className="galaxy-strand" />

              {/* Core Star */}
              <circle cx="180" cy="125" r="10" className="galaxy-core-star" />

              {/* Node Stars */}
              {galaxyNodes.map((node) => (
                <g key={node.id} 
                   onClick={() => setSelectedGalaxyNode(node)}
                   onMouseEnter={() => setSelectedGalaxyNode(node)}
                   className="galaxy-node-group">
                  <circle cx={node.x} cy={node.y} r="6" 
                          className={`galaxy-star star-${node.cluster.toLowerCase()} ${selectedGalaxyNode?.id === node.id ? 'pulsing-star' : ''}`} />
                  <text x={node.x} y={node.y - 10} className="galaxy-node-label" textAnchor="middle">{node.name}</text>
                </g>
              ))}
            </svg>

            {/* Selected Node Details HUD */}
            <div className="galaxy-hud">
              {selectedGalaxyNode ? (
                <div className="hud-content">
                  <span className="hud-cluster">CLUSTER: {selectedGalaxyNode.cluster.toUpperCase()}</span>
                  <h3>{selectedGalaxyNode.name.toUpperCase()}</h3>
                  <p>{selectedGalaxyNode.desc}</p>
                </div>
              ) : (
                <div className="hud-placeholder">Hover/Click a memory star cluster coordinate...</div>
              )}
            </div>
          </div>

        </div>

      </div>

      {/* BOTTOM SECTION: Voice Cognition Engine */}
      <div className="panel voice-engine-panel">
        <div className="panel-title">
          <h2>Voice Cognition Engine</h2>
          <span className="wake-word">WAKE WORD: "HEY ATULYA"</span>
        </div>
        <div className="voice-engine-grid">
          <div className="voice-meta">
            <div className="meta-box">
              <small>SPEAKER IDENTITY</small>
              <strong>{listening ? 'LISTENING...' : busy ? 'ATULYA' : 'ATUL (USER)'}</strong>
            </div>
            <div className="meta-box">
              <small>INTENT CLASSIFIED</small>
              <strong>{intentDetected || 'STANDBY'}</strong>
            </div>
            <div className="meta-box">
              <small>ACCURACY CONFIDENCE</small>
              <strong>{intentConfidence ? `${intentConfidence}%` : '--'}</strong>
            </div>
          </div>
          <div className="voice-visualizer-container">
            <div className={`spectrum-wave ${status}`}>
              <span className="spectrum-bar sb-1" />
              <span className="spectrum-bar sb-2" />
              <span className="spectrum-bar sb-3" />
              <span className="spectrum-bar sb-4" />
              <span className="spectrum-bar sb-5" />
              <span className="spectrum-bar sb-6" />
              <span className="spectrum-bar sb-7" />
              <span className="spectrum-bar sb-8" />
              <span className="spectrum-bar sb-9" />
              <span className="spectrum-bar sb-10" />
            </div>
          </div>
        </div>
      </div>

      {/* Hidden Chat Stream Component for reference */}
      <div className="messages" style={{ display: 'none' }}>
        {messages.slice(-8).map((msg, idx) => <div className={`message ${msg.role}`} key={msg.id || idx}>{msg.text}</div>)}
      </div>
    </section>
  );
}

function Chat({ bootstrap, toast }) {
  const providerOptions = bootstrap?.providers || [{ id: 'auto', name: 'Auto Provider', available: true }];
  const [provider, setProvider] = useState('auto');
  const [prompt, setPrompt] = useState('');
  const [messages, setMessages] = useState(() => loadCachedMessages(CHAT_CACHE_KEY, []));
  const [toolSteps, setToolSteps] = useState([]);
  const [maxContext, setMaxContext] = useState(10);
  const [pendingApproval, setPendingApproval] = useState(null);
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  useEffect(() => endRef.current?.scrollIntoView({ behavior: 'smooth' }), [messages]);

  useEffect(() => {
    cacheMessages(CHAT_CACHE_KEY, messages);
  }, [messages]);

  useEffect(() => {
    api.get('/api/chat/history')
      .then((res) => {
        const chatMessages = normalizeHistoryMessages(res.messages || []).filter((msg) => msg.surface !== 'live');
        if (chatMessages.length) setMessages(chatMessages);
      })
      .catch(() => {});
  }, []);

  function historyPayload(items = messages) {
    return items
      .filter((msg) => msg.text)
      .slice(-maxContext)
      .map((msg) => ({ role: msg.role, content: msg.text }));
  }

  function send(event) {
    event.preventDefault();
    if (!prompt.trim() || busy) return;
    const id = Date.now();
    const text = prompt;
    const nextMessages = [...messages, { role: 'user', text }, { role: 'assistant', text: '', id }];
    setPrompt('');
    setBusy(true);
    setToolSteps([]);
    setMessages(nextMessages);
    api.streamChat(
      { prompt: text, model_id: provider, provider, max_tokens: 256, temperature: 0.7, history: historyPayload(messages) },
      (token) => setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: msg.text + token } : msg)),
      (done) => {
        if (done?.steps) setToolSteps(done.steps);
        if (done?.needs_approval) {
          setPendingApproval({
            prompt: text,
            tool: done.tool,
            tool_args: done.tool_args,
            pending_tool: done.pending_tool || { tool: done.tool, arguments: done.tool_args || {} },
          });
        }
        setBusy(false);
      },
      (err) => {
        setBusy(false);
        setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: `Error: ${err.message}` } : msg));
      },
      (tool) => setToolSteps((prev) => [...prev, tool]),
    );
  }

  return (
    <section className="panel chat">
      <div className="panel-title">
        <h2>Atulya Chat</h2>
        <div className="panel-actions">
          <label style={{fontSize:12, display:'flex', alignItems:'center', gap:4, color:'var(--muted)'}}>
            Context:
            <select value={String(maxContext)} onChange={e => setMaxContext(Number(e.target.value))}>
              <option value="5">5 msgs</option>
              <option value="10">10 msgs</option>
              <option value="20">20 msgs</option>
              <option value="50">50 msgs</option>
            </select>
          </label>
          <button
            type="button"
            onClick={() => {
              api.delete('/api/chat/history').catch(() => {});
              setMessages([]);
              setToolSteps([]);
            }}
          >
            Clear
          </button>
          <select value={provider} onChange={(e) => setProvider(e.target.value)}>
            {providerOptions.map((item) => (
              <option key={item.id} value={item.id}>
                {item.available ? 'Ready - ' : 'Off - '}{item.name}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="messages">
        {toolSteps.map((step, idx) => (
          <div className="message assistant tool-step" key={`${step.tool}-${idx}`}>
            <strong>{step.tool}</strong>: {step.success ? 'done' : step.error || 'failed'}
          </div>
        ))}
        {messages.map((msg, idx) => <div className={`message ${msg.role}`} key={msg.id || idx}>{renderMarkdown(msg.text)}</div>)}
        <div ref={endRef} />
      </div>
      <form className="composer" onSubmit={send}>
        <input value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Send a prompt..." />
        <button className="primary" disabled={busy}>{busy ? 'Streaming...' : 'Send'}</button>
      </form>
      {pendingApproval && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Approve action">
          <div className="modal-card">
            <h2>Approve Action</h2>
            <p className="muted">Review this tool call before Atulya runs it.</p>
            <pre className="terminal">{JSON.stringify({ tool: pendingApproval.tool, args: pendingApproval.tool_args }, null, 2)}</pre>
            <div className="terminal-actions">
              <button type="button" onClick={() => setPendingApproval(null)}>Cancel</button>
              <button
                type="button"
                className="primary"
                onClick={() => {
                  const approved = pendingApproval.prompt;
                  const id = Date.now();
                  setPendingApproval(null);
                  setBusy(true);
                  setMessages((prev) => [...prev, { role: 'assistant', text: '', id }]);
                  api.streamChat(
                    {
                      prompt: approved,
                      model_id: provider,
                      provider,
                      history: historyPayload(),
                      approved_tool: pendingApproval.pending_tool,
                    },
                    (token) => setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: msg.text + token } : msg)),
                    (done) => {
                      if (done?.steps) setToolSteps(done.steps);
                      setBusy(false);
                    },
                    (err) => {
                      setBusy(false);
                      setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: `Error: ${err.message}` } : msg));
                    },
                    (tool) => setToolSteps((prev) => [...prev, tool]),
                  );
                }}
              >
                Approve and run
              </button>
            </div>
          </div>
        </div>
      )}
      <div style={{position:'relative'}}
        onDragOver={e => {e.preventDefault(); e.currentTarget.style.borderColor='var(--accent)';}}
        onDragLeave={e => {e.currentTarget.style.borderColor='';}}
        onDrop={async e => {
          e.preventDefault();
          e.currentTarget.style.borderColor='';
          const files = Array.from(e.dataTransfer.files);
          for (const f of files) {
            const formData = new FormData();
            formData.append('file', f);
            try {
              const res = await fetch('/api/upload', {
                method: 'POST',
                headers: { 'X-Atulya-Token': getToken() },
                body: formData,
              });
              const data = await res.json();
              if (data.ok) toast('success', `Uploaded ${f.name}`);
            } catch (err) {
              toast('error', `Upload failed: ${err.message}`);
            }
          }
        }}
        style={{border:'2px dashed var(--line)', borderRadius:8, padding:12, textAlign:'center', color:'var(--muted)', fontSize:12, marginTop:8}}>
        Drop files here to upload, or{' '}
        <label style={{cursor:'pointer', color:'var(--accent)'}}>
          browse
          <input type="file" hidden multiple onChange={async e => {
            const files = Array.from(e.target.files);
            for (const f of files) {
              const formData = new FormData();
              formData.append('file', f);
              try {
                const res = await fetch('/api/upload', {
                  method: 'POST',
                  headers: { 'X-Atulya-Token': getToken() },
                  body: formData,
                });
                const data = await res.json();
                if (data.ok) toast('success', `Uploaded ${f.name}`);
              } catch (err) {
                toast('error', `Upload failed: ${err.message}`);
              }
            }
          }} />
        </label>
      </div>
    </section>
  );
}

function ModelInspector({ bootstrap, toast }) {
  const checkpoints = bootstrap?.checkpoints || [];
  const [model, setModel] = useState('latest');
  const [info, setInfo] = useState(null);

  async function loadInfo(id = model) {
    try {
      const res = await api.post('/api/plasticity/check', { model_id: id });
      setInfo(res.model_info || {});
    } catch (err) {
      toast('error', err.message);
    }
  }

  useEffect(() => { loadInfo('latest'); }, []);
  const compression = info?.parameter_count && info?.active_parameter_count
    ? (info.parameter_count / info.active_parameter_count).toFixed(2)
    : '--';

  return (
    <section className="panel">
      <div className="panel-title">
        <h2>Model Inspector</h2>
        <select value={model} onChange={(e) => { setModel(e.target.value); loadInfo(e.target.value); }}>
          {checkpoints.map((item) => <option key={item.id} value={item.id}>{item.label || item.id}</option>)}
        </select>
      </div>
      <div className="metrics">
        <Metric label="Config" value={info?.config} />
        <Metric label="Params" value={info?.parameter_count?.toLocaleString?.()} />
        <Metric label="Active Params" value={info?.active_parameter_count?.toLocaleString?.()} />
        <Metric label="Compression" value={compression === '--' ? '--' : `${compression}x`} />
        <Metric label="Vocab" value={info?.vocab_size && info?.vocab_capacity ? `${info.vocab_size}/${info.vocab_capacity}` : '--'} />
        <Metric label="Cortex Entries" value={info?.cortex_entries ?? '--'} />
      </div>
      <div className="strand-grid">
        {(info?.layers || []).map((layer, idx) => (
          <div className="strand-row" key={`${layer.name}-${idx}`}>
            <span>{layer.name}</span>
            <strong>{layer.num_strands} strands</strong>
            <small>top-k {layer.top_k}</small>
          </div>
        ))}
      </div>
    </section>
  );
}

function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await api.post('/api/auth/login', { username, password });
      if (res.ok) {
        setToken(res.token);
        setUser(res.user);
        onLogin();
      } else {
        throw new Error(res.detail || 'Wrong username or password');
      }
    } catch (err) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-shell">
      <div className="login-orb" />
      <form className="login-card" onSubmit={submit}>
        <div className="login-logo-glow" />
        <h1>ATULYA</h1>
        <p className="muted">Digital Organism OS</p>
        
        {error && <div className="alert error-alert">{error}</div>}
        
        <div className="input-group">
          <input 
            type="text"
            value={username} 
            onChange={(e) => setUsername(e.target.value)} 
            placeholder="Username" 
            autoFocus 
            required 
          />
        </div>
        
        <div className="input-group">
          <input 
            type="password" 
            value={password} 
            onChange={(e) => setPassword(e.target.value)} 
            placeholder="Password" 
            required 
          />
        </div>
        
        <button className="primary login-btn" disabled={loading}>
          {loading ? 'SYNCHRONIZING...' : 'ENGAGE CORE'}
        </button>
      </form>
    </main>
  );
}

function App() {
  const [tab, setTab] = useState('live');
  const [adminOpen, setAdminOpen] = useState(false);
  const [bootstrap, setBootstrap] = useState(null);
  const [error, setError] = useState('');
  const [authenticated, setAuthenticated] = useState(Boolean(getToken()));
  const [toasts, setToasts] = useState([]);
  const [healthWarnings, setHealthWarnings] = useState([]);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem('atulya-theme') || 'dark'; } catch { return 'dark'; }
  });
  
  const currentUser = getUser();
  const isAdmin = currentUser?.role === 'admin';

  function toast(type, message) {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => setToasts((prev) => prev.filter((item) => item.id !== id)), 3500);
  }

  async function load() {
    setError('');
    try {
      const boot = await api.get('/api/dashboard/bootstrap');
      setAuthenticated(true);
      setBootstrap({ ...boot, datasets: boot.datasets || [] });
      if (boot.user) {
        setUser(boot.user);
      }
    } catch (err) {
      if (err.message.includes('Unauthorized') || err.message.includes('401')) {
        clearToken();
        setAuthenticated(false);
      }
      throw err;
    }
  }

  useEffect(() => {
    if (authenticated) {
      load().catch((err) => setError(err.message));
    }
  }, [authenticated]);

  useEffect(() => {
    api.get('/api/health')
      .then(res => { if (res.warnings) setHealthWarnings(res.warnings); })
      .catch(() => {});
    const hc = setInterval(() => {
      api.get('/api/health')
        .then(res => { if (res.warnings) setHealthWarnings(res.warnings); })
        .catch(() => {});
    }, 60000);
    return () => clearInterval(hc);
  }, [authenticated]);

  useEffect(() => {
    document.documentElement.className = theme === 'light' ? 'light' : '';
    try { localStorage.setItem('atulya-theme', theme); } catch {}
  }, [theme]);

  useEffect(() => {
    function handleKeyDown(event) {
      if (event.ctrlKey || event.metaKey) {
        switch (event.key) {
          case '1': event.preventDefault(); setTab('live'); break;
          case '2': event.preventDefault(); setTab('chat'); break;
          case '3': event.preventDefault(); setTab('spirit'); break;
        }
      }
      if (event.key === '?' && !event.ctrlKey && !event.metaKey) {
        setShowShortcuts(prev => !prev);
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const content = useMemo(() => {
    if (tab === 'live') return <LiveMode bootstrap={bootstrap} toast={toast} />;
    if (tab === 'chat') return <Chat bootstrap={bootstrap} toast={toast} />;
    if (tab === 'spirit') return <HolographicSpirit />;
    if (!isAdmin) return <LiveMode bootstrap={bootstrap} toast={toast} />; // Fallback for normal users
    
    // Admin-only views
    if (tab === 'dashboard') return <Dashboard bootstrap={bootstrap} load={load} />;
    if (tab === 'model') return <ModelInspector bootstrap={bootstrap} toast={toast} />;
    if (tab === 'training') return <Training bootstrap={bootstrap} load={load} toast={toast} />;
    if (tab === 'users') return <UserManagement toast={toast} />;
    return <Dashboard bootstrap={bootstrap} load={load} />;
  }, [tab, bootstrap, isAdmin]);

  async function handleLogout() {
    try {
      await api.post('/api/auth/logout').catch(() => {});
    } finally {
      clearToken();
      setAuthenticated(false);
      setAdminOpen(false);
      setTab('live');
    }
  }

  if (!authenticated) {
    return <Login onLogin={() => { setAuthenticated(true); load().catch((err) => setError(err.message)); }} />;
  }

  return (
    <main className={(tab === 'live' || tab === 'spirit') ? 'immersive-layout' : ''}>
      <aside className={adminOpen ? 'admin-drawer open' : 'admin-drawer'}>
        <button className="drawer-close-btn" onClick={() => setAdminOpen(false)}>×</button>
        <h1>Atulya Tantra</h1>
        
        {/* User profile info */}
        <div className="user-profile-hud">
          <small>OPERATOR</small>
          <strong>{currentUser?.display_name || currentUser?.username}</strong>
          <span className="badge small">{currentUser?.role?.toUpperCase()}</span>
        </div>

        <button className="theme-toggle" onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}>
          {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
        </button>

        <button className={tab === 'live' ? 'active' : ''} onClick={() => { setTab('live'); setAdminOpen(false); }}>Live Mode</button>
        <button className={tab === 'chat' ? 'active' : ''} onClick={() => { setTab('chat'); setAdminOpen(false); }}>Chat</button>
        <button className={tab === 'spirit' ? 'active' : ''} onClick={() => { setTab('spirit'); setAdminOpen(false); }}>⬡ Spirit UI</button>
        
        {isAdmin && (
          <>
            <div className="drawer-section-label">DEVELOPER STRANDS</div>
            <button className={tab === 'training' ? 'active' : ''} onClick={() => { setTab('training'); setAdminOpen(false); }}>Training</button>
            <button className={tab === 'model' ? 'active' : ''} onClick={() => { setTab('model'); setAdminOpen(false); }}>Model Inspector</button>
            <button className={tab === 'dashboard' ? 'active' : ''} onClick={() => { setTab('dashboard'); setAdminOpen(false); }}>Dashboard</button>
            <button className={tab === 'users' ? 'active' : ''} onClick={() => { setTab('users'); setAdminOpen(false); }}>Manage Users</button>
          </>
        )}
        
        <button className="logout" onClick={handleLogout}>Logout</button>
      </aside>
      
      <section className="content" style={(tab === 'live' || tab === 'spirit') ? { padding: 0, overflow: 'hidden' } : {}}>
        {error && <div className="alert">{error}</div>}
        {healthWarnings.filter(w => w.severity !== 'low').map((w, i) => (
          <div key={i} className="alert" style={{borderColor: w.severity === 'high' ? 'var(--bad)' : 'var(--warn)'}}>
            {w.message}
          </div>
        ))}
        {content}
      </section>

      {/* Floating Gear Settings Toggle - Only show if admin */}
      {isAdmin && (
        <button className="gear-trigger" title="Developer Controls" onClick={() => setAdminOpen(!adminOpen)}>
          ⚙️
        </button>
      )}

      {/* For normal users, show a simple sidebar trigger if not in immersive mode or even in immersive mode to access chat/logout */}
      {!isAdmin && (
        <button className="gear-trigger" title="Navigation Menu" onClick={() => setAdminOpen(!adminOpen)}>
          ☰
        </button>
      )}

      {showShortcuts && (
        <div className="modal-backdrop" onClick={() => setShowShortcuts(false)}>
          <div className="modal-card" onClick={e => e.stopPropagation()}>
            <h2>Keyboard Shortcuts</h2>
            <div className="table">
              <div className="row"><span>Ctrl+1</span><span>Live Mode</span></div>
              <div className="row"><span>Ctrl+2</span><span>Chat</span></div>
              <div className="row"><span>Ctrl+3</span><span>Spirit UI</span></div>
              <div className="row"><span>?</span><span>Toggle this menu</span></div>
            </div>
            <button onClick={() => setShowShortcuts(false)}>Close</button>
          </div>
        </div>
      )}

      <div className="toasts">
        {toasts.map((item) => <div className={`toast ${item.type}`} key={item.id}>{item.message}</div>)}
      </div>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
