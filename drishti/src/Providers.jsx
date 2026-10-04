import React, { useEffect, useState } from 'react';
import { api } from './api.js';

// Link any brain: paste a key, pick a model, press Test. Keys are saved to .env on this computer and are
// never shown again (only the last four characters).

const BADGE = { free: 'Free', 'free tier': 'Free tier', paid: 'Paid', local: 'Your own server' };

function Card({ p, toast, onChange }) {
  const [key, setKey] = useState('');
  const [model, setModel] = useState(p.model);
  const [url, setUrl] = useState(p.url || '');
  const [busy, setBusy] = useState('');
  const [result, setResult] = useState(null);

  async function save() {
    setBusy('save');
    try {
      const body = { model: model === p.default_model ? '' : model };
      if (key.trim()) body.key = key.trim();
      if (p.needs_url) body.url = url.trim();
      const row = await api.post(`/api/providers/${p.id}`, body);
      setKey('');
      onChange(row);
      toast('success', `${p.label.split(' (')[0]} saved.`);
    } catch (e) { toast('error', e.message); } finally { setBusy(''); }
  }
  async function remove() {
    if (!window.confirm(`Remove the ${p.label.split(' (')[0]} key?`)) return;
    setBusy('remove');
    try { onChange(await api.post(`/api/providers/${p.id}`, { key: '', ...(p.needs_url ? { url: '' } : {}) })); setResult(null); }
    catch (e) { toast('error', e.message); } finally { setBusy(''); }
  }
  async function test() {
    setBusy('test');
    setResult(null);
    try { setResult(await api.post(`/api/providers/${p.id}/test`, {})); }
    catch (e) { setResult({ ok: false, error: e.message }); } finally { setBusy(''); }
  }

  return (
    <div className="prov-card">
      <div className="prov-head">
        <strong>{p.label}</strong>
        <span className={`prov-badge ${p.free === 'paid' ? 'paid' : 'free'}`}>{BADGE[p.free] || p.free}</span>
        {p.configured && <span className="prov-badge on">Linked {p.key_hint}</span>}
      </div>
      {p.needs_url && <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="Server URL, e.g. http://localhost:1234/v1" />}
      <input type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)}
        placeholder={p.configured ? 'Paste a new key to replace it' : (p.needs_url ? 'Key (optional)' : 'Paste your API key')} />
      <input value={model} onChange={(e) => setModel(e.target.value)} placeholder="Model" title="Which model to use. Comma-separate several to try in turn." />
      <div className="prov-actions">
        <button type="button" onClick={save} disabled={Boolean(busy)}>{busy === 'save' ? 'Saving…' : 'Save'}</button>
        <button type="button" onClick={test} disabled={Boolean(busy) || !p.configured}>{busy === 'test' ? 'Testing…' : 'Test'}</button>
        {p.configured && <button type="button" onClick={remove} disabled={Boolean(busy)}>Remove</button>}
        {p.docs && <a href={p.docs} target="_blank" rel="noreferrer">Get a key ↗</a>}
      </div>
      {result && <small className={result.ok ? 'prov-ok' : 'prov-bad'}>{result.ok ? `Works (${result.seconds}s): ${result.reply}` : result.error}</small>}
    </div>
  );
}

export function Providers({ toast }) {
  const [rows, setRows] = useState(null);
  useEffect(() => { api.get('/api/providers').then((r) => setRows(r.providers)).catch((e) => toast('error', e.message)); }, []);
  if (!rows) return <p className="lazy-loading">Loading brains…</p>;
  const update = (row) => setRows((all) => all.map((r) => (r.id === row.id ? row : r)));
  const linked = rows.filter((r) => r.configured).length;
  return (
    <div className="prov">
      <p className="muted">
        {linked ? `${linked} linked.` : 'None linked yet.'} Atulya tries the fastest working brain first and falls back to the next.
        Keys are saved in <code>.env</code> on this computer and are never shown again.
      </p>
      {rows.map((p) => <Card key={p.id} p={p} toast={toast} onChange={update} />)}
    </div>
  );
}

export default Providers;
