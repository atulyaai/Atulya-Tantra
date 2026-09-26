import React, { useEffect, useState } from 'react';
import { api } from '../../api.js';

const EMPTY = { id: '', name: '', phrases: '', steps: '' };

export function Routines({ toast }) {
  const [routines, setRoutines] = useState([]);
  const [draft, setDraft] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState('');
  const [confirm, setConfirm] = useState(null);
  const [sentence, setSentence] = useState('');
  const [preview, setPreview] = useState(null);

  const load = () => api.get('/api/routines')
    .then((res) => setRoutines(res.routines || []))
    .catch((err) => toast('error', `Couldn't load routines: ${err.message}`));

  useEffect(() => { load(); }, []);

  const update = (field) => (e) => setDraft((prev) => ({ ...prev, [field]: e.target.value }));

  async function save(e) {
    e.preventDefault();
    const body = {
      name: draft.name.trim(),
      phrases: draft.phrases.split(',').map((p) => p.trim()).filter(Boolean),
      steps: draft.steps.split('\n').map((s) => s.trim()).filter(Boolean),
    };
    if (draft.id) body.id = draft.id;
    setSaving(true);
    try {
      await api.post('/api/routines', body);
      setDraft(EMPTY);
      await load();
      toast('success', draft.id ? 'Routine updated' : 'Routine added');
    } catch (err) {
      toast('error', err.message);
    } finally {
      setSaving(false);
    }
  }

  function edit(routine) {
    setDraft({ id: routine.id, name: routine.name, phrases: (routine.phrases || []).join(', '), steps: (routine.steps || []).join('\n') });
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
  }

  async function toggle(routine) {
    try {
      await api.post('/api/routines', { ...routine, enabled: routine.enabled === false });
      await load();
    } catch (err) {
      toast('error', err.message);
    }
  }

  async function remove(routine) {
    if (!window.confirm(`Delete the routine "${routine.name}"?`)) return;
    try {
      await api.delete(`/api/routines/${encodeURIComponent(routine.id)}`);
      await load();
    } catch (err) {
      toast('error', err.message);
    }
  }

  async function run(routine) {
    setRunning(routine.id);
    try {
      const res = await api.post(`/api/routines/${encodeURIComponent(routine.id)}/run`, {});
      if (res.needs_approval) setConfirm(res);
      else toast('success', res.response, { title: routine.name, duration: 9000 });
    } catch (err) {
      toast('error', err.message);
    } finally {
      setRunning('');
    }
  }

  async function approve() {
    const held = confirm;
    setConfirm(null);
    try {
      const res = await api.post('/api/chat', { prompt: '', approved_tool: held.pending_tool });
      toast('success', res.response, { duration: 9000 });
    } catch (err) {
      toast('error', err.message);
    }
  }

  async function tryIt(e) {
    e.preventDefault();
    if (!sentence.trim()) return;
    try {
      const res = await api.post('/api/plan/preview', { text: sentence.trim() });
      setPreview(res.plan);
    } catch (err) {
      toast('error', err.message);
    }
  }

  return (
    <div className="reflexes">
      <section className="panel">
        <div className="panel-title">
          <h2>Routines</h2>
          <span className="muted">Say a phrase and Atulya does several things, checking each one.</span>
        </div>
        <div className="reflex-list">
          {routines.length === 0 && <p className="muted">No routines yet.</p>}
          {routines.map((routine) => (
            <div className={`reflex-card${routine.enabled === false ? ' paused' : ''}`} key={routine.id}>
              <div className="reflex-head">
                <strong>{routine.name}</strong>
                <span className="reflex-badges">
                  {routine.enabled === false ? <span className="badge">paused</span> : <span className="badge good">on</span>}
                  <span className="badge">{(routine.plan || []).length} steps</span>
                </span>
              </div>
              <div className="reflex-body">
                <div><small>SAY</small> {(routine.phrases || []).map((p) => `“${p}”`).join(' · ')}</div>
                <ol className="routine-steps">
                  {(routine.plan || []).map((step, i) => <li key={i}>{step}</li>)}
                </ol>
              </div>
              <div className="reflex-actions">
                <button type="button" className="primary" disabled={running === routine.id} onClick={() => run(routine)}>
                  {running === routine.id ? 'Running…' : 'Run now'}
                </button>
                <button type="button" onClick={() => edit(routine)}>Edit</button>
                <button type="button" onClick={() => toggle(routine)}>{routine.enabled === false ? 'Resume' : 'Pause'}</button>
                <button type="button" className="danger" onClick={() => remove(routine)}>Delete</button>
              </div>
            </div>
          ))}
        </div>

        <form className="reflex-form" onSubmit={save}>
          <h3>{draft.id ? `Edit “${draft.name}”` : 'New routine'}</h3>
          <label>Name<input value={draft.name} onChange={update('name')} placeholder="Movie night" required /></label>
          <label>Phrases that start it (comma-separated)
            <input value={draft.phrases} onChange={update('phrases')} placeholder="movie night, movie time" />
          </label>
          <label>Steps — one command per line
            <textarea rows={4} value={draft.steps} onChange={update('steps')}
              placeholder={'turn off the living room light\nset the thermostat to 21'} required />
          </label>
          <p className="muted reflex-hint">
            Each step must be a command Atulya understands on its own, like <code>turn off all the lights</code>,{' '}
            <code>lock the front door</code> or <code>what's on my calendar</code>. Risky steps (unlocking a door,
            sending email) ask once before the routine runs.
          </p>
          <div className="reflex-actions">
            <button type="submit" className="primary" disabled={saving}>{saving ? 'Saving…' : draft.id ? 'Save changes' : 'Add routine'}</button>
            {draft.id && <button type="button" onClick={() => setDraft(EMPTY)}>Cancel</button>}
          </div>
        </form>
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Try a sentence</h2>
          <span className="muted">See the plan Atulya would follow, without doing it.</span>
        </div>
        <form className="inline-form" onSubmit={tryIt}>
          <input value={sentence} onChange={(e) => setSentence(e.target.value)}
            placeholder="turn off the kitchen light and lock the door" />
          <button type="submit">Show plan</button>
        </form>
        {preview && (
          <div className="reflex-card preview-card">
            <div className="reflex-head">
              <strong>{preview.title}</strong>
              <span className="badge">{preview.source === 'brain' ? 'the brain decides' : preview.source}</span>
            </div>
            {preview.steps.length ? (
              <ol className="routine-steps">{preview.steps.map((s, i) => <li key={i}>{s.command}</li>)}</ol>
            ) : <p className="muted">No direct command here — Atulya's brain will answer or plan it.</p>}
          </div>
        )}
      </section>

      {confirm && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Confirm routine">
          <div className="modal-card">
            <h2>Confirm routine</h2>
            <p className="pre-line">{confirm.response}</p>
            <div className="terminal-actions">
              <button type="button" onClick={() => setConfirm(null)}>Cancel</button>
              <button type="button" className="primary" onClick={approve}>Go ahead</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
