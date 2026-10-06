import React, { useEffect, useState } from 'react';
import { api } from './api.js';

// Link any brain: paste a key, pick a model, press Test. Keys are saved to .env on this computer and are
// never shown again (only the last four characters).

const BADGE = { free: 'Free', 'free tier': 'Free tier', paid: 'Paid', local: 'Your own server' };

function Card({ p, toast, onChange, fast }) {
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
    <div className={`prov-card${fast ? ' fast' : ''}`} id={`prov-${p.id}`}>
      <div className="prov-head">
        <strong>{p.label}</strong>
        {fast && <span className="prov-badge fast">Fast and free</span>}
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

// How long each brain really took to answer, and what to do about slow answers.
function Speed({ brains, advice, recommended, rows }) {
  const slowest = Math.max(1, ...brains.map((b) => b.seconds));
  const first = recommended.map((id) => rows.find((r) => r.id === id)).find((r) => r && !r.configured);
  const go = (id) => document.getElementById(`prov-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  return (
    <section className="prov-speed">
      <h3>Speed</h3>
      {brains.length ? (
        <div className="prov-bars">
          {brains.map((b) => (
            <div key={b.name} className="prov-bar">
              <span title={b.name}>{b.name}</span>
              <i className={b.local ? 'local' : ''} style={{ width: `${Math.max(6, (b.seconds / slowest) * 100)}%` }} />
              <em>{b.seconds} s</em>
            </div>
          ))}
        </div>
      ) : <p className="muted">Nothing measured yet. Each answer Atulya gives adds a number here.</p>}
      {advice && (
        <div className="prov-advice">
          <p>{advice.message}</p>
          {advice.kind === 'slow_local' && first && (
            <ol>
              <li>Get a free key: <a href={first.docs} target="_blank" rel="noreferrer">{first.label.split(' (')[0]} ↗</a></li>
              <li>Paste it in the {first.label.split(' (')[0]} card below and press <b>Save</b>, then <b>Test</b>.</li>
              <li>Atulya measures every brain and tries the fastest first. Your questions then go to that company; the local model stays as the offline fallback.</li>
            </ol>
          )}
          {advice.kind === 'slow_local' && first && <button type="button" onClick={() => go(first.id)}>Take me to the {first.label.split(' (')[0]} card</button>}
        </div>
      )}
    </section>
  );
}

export function Providers({ toast }) {
  const [data, setData] = useState(null);
  useEffect(() => { api.get('/api/providers').then(setData).catch((e) => toast('error', e.message)); }, []);
  if (!data) return <p className="lazy-loading">Loading brains…</p>;
  const rows = data.providers;
  const update = (row) => setData((d) => ({ ...d, providers: d.providers.map((r) => (r.id === row.id ? row : r)) }));
  const linked = rows.filter((r) => r.configured).length;
  const rank = (r) => { const i = data.recommended.indexOf(r.id); return i < 0 ? 99 : i; };
  const ordered = [...rows].sort((a, b) => rank(a) - rank(b));   // the fast free ones first, the rest in catalogue order
  return (
    <div className="prov">
      <Speed brains={data.brains} advice={data.advice} recommended={data.recommended} rows={rows} />
      <p className="muted">
        {linked ? `${linked} linked.` : 'None linked yet.'} Atulya tries the fastest working brain first and falls back to the next.
        Keys are saved in <code>.env</code> on this computer and are never shown again.
      </p>
      {ordered.map((p) => <Card key={p.id} p={p} toast={toast} onChange={update} fast={data.recommended.includes(p.id)} />)}
    </div>
  );
}

export default Providers;
