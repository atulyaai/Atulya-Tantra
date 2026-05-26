import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api, clearToken, getToken, setToken } from './api.js';
import './styles.css';

function Metric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value ?? '--'}</strong>
    </div>
  );
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

function Chat({ bootstrap }) {
  const checkpoints = bootstrap?.checkpoints || [];
  const [model, setModel] = useState('latest');
  const [prompt, setPrompt] = useState('');
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  useEffect(() => endRef.current?.scrollIntoView({ behavior: 'smooth' }), [messages]);

  function send(event) {
    event.preventDefault();
    if (!prompt.trim() || busy) return;
    const id = Date.now();
    const text = prompt;
    setPrompt('');
    setBusy(true);
    setMessages((prev) => [...prev, { role: 'user', text }, { role: 'assistant', text: '', id }]);
    api.streamChat(
      { prompt: text, model_id: model, max_tokens: 256, temperature: 0.7 },
      (token) => setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: msg.text + token } : msg)),
      () => setBusy(false),
      (err) => {
        setBusy(false);
        setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: `Error: ${err.message}` } : msg));
      },
    );
  }

  return (
    <section className="panel chat">
      <div className="panel-title">
        <h2>Neural Playground</h2>
        <select value={model} onChange={(e) => setModel(e.target.value)}>
          {checkpoints.map((item) => <option key={item.id} value={item.id}>{item.label || item.id}</option>)}
        </select>
      </div>
      <div className="messages">
        {messages.map((msg, idx) => <div className={`message ${msg.role}`} key={msg.id || idx}>{msg.text}</div>)}
        <div ref={endRef} />
      </div>
      <form className="composer" onSubmit={send}>
        <input value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Send a prompt..." />
        <button className="primary" disabled={busy}>{busy ? 'Streaming...' : 'Send'}</button>
      </form>
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
  const [token, setTokenInput] = useState('');
  const [error, setError] = useState('');
  async function submit(event) {
    event.preventDefault();
    setError('');
    try {
      const res = await api.post('/api/auth/login', { token });
      setToken(res.token);
      onLogin();
    } catch (err) {
      setError(err.message);
    }
  }
  return (
    <main className="login-shell">
      <form className="login-card" onSubmit={submit}>
        <h1>Atulya Tantra</h1>
        <p className="muted">Enter the dashboard token from <code>ATULYA_DASHBOARD_TOKEN</code>.</p>
        {error && <div className="alert">{error}</div>}
        <input value={token} onChange={(e) => setTokenInput(e.target.value)} placeholder="Dashboard token" autoFocus />
        <button className="primary">Login</button>
      </form>
    </main>
  );
}

function App() {
  const [tab, setTab] = useState('training');
  const [bootstrap, setBootstrap] = useState(null);
  const [error, setError] = useState('');
  const [authenticated, setAuthenticated] = useState(Boolean(getToken()));
  const [toasts, setToasts] = useState([]);

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
    } catch (err) {
      if (err.message.includes('Unauthorized') || err.message.includes('401')) {
        clearToken();
        setAuthenticated(false);
      }
      throw err;
    }
  }

  useEffect(() => {
    if (authenticated) load().catch((err) => setError(err.message));
  }, [authenticated]);

  const content = useMemo(() => {
    if (tab === 'dashboard') return <Dashboard bootstrap={bootstrap} load={load} />;
    if (tab === 'model') return <ModelInspector bootstrap={bootstrap} toast={toast} />;
    if (tab === 'chat') return <Chat bootstrap={bootstrap} />;
    return <Training bootstrap={bootstrap} load={load} toast={toast} />;
  }, [tab, bootstrap]);

  if (!authenticated) return <Login onLogin={() => { setAuthenticated(true); load().catch((err) => setError(err.message)); }} />;

  return (
    <main>
      <aside>
        <h1>Atulya Tantra</h1>
        <button className={tab === 'training' ? 'active' : ''} onClick={() => setTab('training')}>Training</button>
        <button className={tab === 'chat' ? 'active' : ''} onClick={() => setTab('chat')}>Chat</button>
        <button className={tab === 'model' ? 'active' : ''} onClick={() => setTab('model')}>Model</button>
        <button className={tab === 'dashboard' ? 'active' : ''} onClick={() => setTab('dashboard')}>Dashboard</button>
        <button className="logout" onClick={() => { clearToken(); setAuthenticated(false); }}>Logout</button>
      </aside>
      <section className="content">
        {error && <div className="alert">{error}</div>}
        {content}
      </section>
      <div className="toasts">
        {toasts.map((item) => <div className={`toast ${item.type}`} key={item.id}>{item.message}</div>)}
      </div>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
