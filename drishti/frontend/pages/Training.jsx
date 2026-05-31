import React, { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';
import { Metric } from '../components/Metric.jsx';
import { LossChart } from '../components/LossChart.jsx';

export function Training({ bootstrap, load, toast }) {
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
