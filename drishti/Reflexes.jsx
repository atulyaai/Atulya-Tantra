import React, { useEffect, useState } from 'react';
import { api } from './api.js';

// Events the backend publishes (see granth/COGNITIVE_ARCHITECTURE.md).
const KNOWN_EVENTS = [
  ['reminder.due', 'A reminder comes due'],
  ['health.warning', 'A system check turns to warning'],
  ['health.error', 'A system check fails'],
  ['health.ok', 'A system check recovers'],
  ['automation.completed', 'A scheduled job finishes'],
  ['automation.failed', 'A scheduled job fails'],
  ['action.executed', 'Atulya performs an action'],
  ['action.pending', 'An action waits for confirmation'],
  ['action.denied', 'An action is refused'],
  ['vision.person', 'A camera or sensor sees someone'],
  ['vision.motion', 'A camera or sensor sees movement'],
  ['doorbell.pressed', 'The doorbell rings'],
  ['home.sensor', 'A Home Assistant sensor changes'],
  ['habit.due', 'A usual habit hasn\'t happened yet today'],
  ['plan.completed', 'A routine or plan finishes'],
  ['profile.learned', 'Atulya learns something about you'],
];

const EMPTY_DRAFT = {
  name: '', event: 'reminder.due', matchField: '', matchValue: '',
  notify: '', command: '', allow_risky: false, cooldown_seconds: 60,
};

const eventsOf = (rule) => (Array.isArray(rule.event) ? rule.event : [rule.event]);

function timeAgo(seconds) {
  if (!seconds) return 'never';
  const delta = Math.max(0, Date.now() / 1000 - seconds);
  if (delta < 60) return `${Math.round(delta)}s ago`;
  if (delta < 3600) return `${Math.round(delta / 60)}m ago`;
  if (delta < 86400) return `${Math.round(delta / 3600)}h ago`;
  return `${Math.round(delta / 86400)}d ago`;
}

function summarize(payload = {}) {
  const keys = ['message', 'title', 'tool', 'check', 'job', 'result', 'reason', 'error'];
  return keys.filter((k) => payload[k]).map((k) => `${k}: ${String(payload[k]).slice(0, 60)}`).join(' · ');
}

function Stat({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value ?? '--'}</strong>
    </div>
  );
}

export function Reflexes({ toast }) {
  const [rules, setRules] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [brain, setBrain] = useState(null);
  const [recent, setRecent] = useState([]);
  const [draft, setDraft] = useState(EMPTY_DRAFT);
  const [jobDraft, setJobDraft] = useState({ name: '', schedule: '3600', command: '' });
  const [saving, setSaving] = useState(false);

  const loadRules = () => api.get('/api/triggers')
    .then((res) => setRules(res.triggers || []))
    .catch((err) => toast('error', `Couldn't load reflexes: ${err.message}`));
  const loadRecent = () => api.get('/api/events/recent?limit=25')
    .then((res) => setRecent((res.events || []).slice().reverse()))
    .catch(() => {});
  const loadJobs = () => api.get('/api/cron/jobs')
    .then((res) => setJobs(res.jobs || []))
    .catch((err) => toast('error', `Couldn't load scheduled jobs: ${err.message}`));

  useEffect(() => {
    loadRules();
    loadRecent();
    loadJobs();
    api.get('/api/brain').then(setBrain).catch(() => {});
    const timer = setInterval(() => { loadRecent(); loadJobs(); }, 3000);
    return () => clearInterval(timer);
  }, []);

  async function createJob(e) {
    e.preventDefault();
    if (!jobDraft.name.trim() || !jobDraft.schedule.trim() || !jobDraft.command.trim()) {
      toast('error', 'Add a name, schedule, and command.');
      return;
    }
    if (!window.confirm('This job will run automatically on its schedule. Commands may perform actions. Add it?')) return;
    setSaving(true);
    try {
      await api.post('/api/cron/jobs', { ...jobDraft, enabled: true });
      setJobDraft({ name: '', schedule: '3600', command: '' });
      await loadJobs();
      toast('success', 'Scheduled job added');
    } catch (err) {
      toast('error', err.message);
    } finally {
      setSaving(false);
    }
  }

  async function runJob(job) {
    if (!window.confirm(`Run "${job.name}" now? The command may perform actions.`)) return;
    try {
      await api.post(`/api/cron/jobs/${encodeURIComponent(job.id)}/run`, {});
      await loadJobs();
      toast('info', `Started ${job.name}`);
    } catch (err) {
      toast('error', err.message);
    }
  }

  async function cancelJob(job) {
    if (!window.confirm(`Cancel the active run of "${job.name}"?`)) return;
    try {
      await api.post(`/api/cron/jobs/${encodeURIComponent(job.id)}/cancel`, {});
      await loadJobs();
      toast('info', `Cancelled ${job.name}`);
    } catch (err) {
      toast('error', err.message);
    }
  }

  async function toggleJob(job) {
    try {
      await api.patch(`/api/cron/jobs/${encodeURIComponent(job.id)}`, { enabled: job.enabled === false });
      await loadJobs();
    } catch (err) {
      toast('error', err.message);
    }
  }

  const update = (field) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    setDraft((prev) => ({ ...prev, [field]: value }));
  };

  async function addRule(e) {
    e.preventDefault();
    if (!draft.notify.trim() && !draft.command.trim()) {
      toast('error', 'Give the reflex a notification, a command, or both.');
      return;
    }
    const rule = {
      event: draft.event.trim(),
      notify: draft.notify.trim(),
      command: draft.command.trim(),
      allow_risky: draft.allow_risky,
      cooldown_seconds: Number(draft.cooldown_seconds) || 0,
    };
    if (draft.name.trim()) rule.name = draft.name.trim();
    if (draft.matchField.trim() && draft.matchValue.trim()) rule.match = { [draft.matchField.trim()]: draft.matchValue.trim() };
    setSaving(true);
    try {
      await api.post('/api/triggers', rule);
      setDraft(EMPTY_DRAFT);
      await loadRules();
      toast('success', 'Reflex added');
    } catch (err) {
      toast('error', err.message);
    } finally {
      setSaving(false);
    }
  }

  async function toggle(rule) {
    try {
      await api.post('/api/triggers', { ...rule, enabled: !rule.enabled });
      await loadRules();
    } catch (err) {
      toast('error', err.message);
    }
  }

  async function remove(rule) {
    if (!window.confirm(`Delete the reflex "${rule.name}"?`)) return;
    try {
      await api.delete(`/api/triggers/${encodeURIComponent(rule.id)}`);
      await loadRules();
    } catch (err) {
      toast('error', err.message);
    }
  }

  async function test(rule) {
    // Fire a sample event this rule listens for (globs get a concrete name).
    const type = eventsOf(rule)[0].replace('*', 'test');
    const payload = {
      message: 'test from the Reflexes screen', check: 'test', job: 'test', tool: 'test',
      ...(rule.match || {}),
      source: 'reflexes-test',
    };
    try {
      await api.post('/api/events/emit', { type, payload });
      toast('info', `Sent a test "${type}" event`);
      setTimeout(() => { loadRecent(); loadRules(); }, 700);
    } catch (err) {
      toast('error', err.message);
    }
  }

  return (
    <div className="reflexes">
      {brain && (
        <section className="panel">
          <div className="panel-title">
            <h2>Brain</h2>
            <span className="badge good">{brain.tier}</span>
          </div>
          <div className="metrics">
            <Stat label="Local model" value={brain.local_model?.label} />
            <Stat label="Download" value={brain.local_model?.size} />
            <Stat label="RAM" value={brain.local_model?.ram} />
            <Stat label="Routing" value={brain.cloud_first ? 'Cloud first' : 'Local first'} />
          </div>
          <p className="muted reflex-hint">
            Set <code>ATULYA_BRAIN</code> in <code>.env</code> and restart:{' '}
            {Object.entries(brain.tiers || {}).map(([name, info]) => `${name} (${info.label}${info.size ? `, ${info.size}` : ''})`).join(' · ')}
          </p>
        </section>
      )}

      <section className="panel">
        <div className="panel-title">
          <h2>Scheduled jobs</h2>
          <span className="muted">Run on a schedule, inspect the latest state, or cancel an active run.</span>
        </div>
        <div className="reflex-list">
          {jobs.length === 0 && <p className="muted">No scheduled jobs yet.</p>}
          {jobs.map((job) => (
            <div className="reflex-card" key={job.id}>
              <div className="reflex-head">
                <strong>{job.name}</strong>
                <span className="reflex-badges">
                  <span className={`badge ${job.run_status === 'failed' ? 'warn' : job.run_status === 'completed' ? 'good' : ''}`}>{job.run_status || (job.enabled === false ? 'paused' : 'scheduled')}</span>
                </span>
              </div>
              <div className="reflex-body">
                <div><small>SCHEDULE</small> {job.schedule} · {job.enabled === false ? 'paused' : 'enabled'}</div>
                <div><small>COMMAND</small> {job.command}</div>
                {job.run_status && <div><small>RUN</small> {job.run_phase || job.run_status} · {job.run_progress || 0}%
                  {job.run_updated_at ? ` · ${timeAgo(job.run_updated_at)}` : ''}</div>}
                {job.last_result && <div><small>RESULT</small> {String(job.last_result).slice(0, 300)}</div>}
                {job.last_error && <div className="muted"><small>ERROR</small> {String(job.last_error).slice(0, 240)}</div>}
              </div>
              {job.run_status === 'running' && <div className="db-progress"><i style={{ width: `${Math.min(100, Math.max(0, job.run_progress || 0))}%` }} /></div>}
              <div className="reflex-actions">
                {job.run_status === 'running'
                  ? <button type="button" className="danger" onClick={() => cancelJob(job)}>Cancel run</button>
                  : <button type="button" onClick={() => runJob(job)}>Run now</button>}
                <button type="button" onClick={() => toggleJob(job)}>{job.enabled === false ? 'Resume schedule' : 'Pause schedule'}</button>
              </div>
            </div>
          ))}
        </div>
        <form className="reflex-form" onSubmit={createJob}>
          <h3>New scheduled job</h3>
          <label>Name<input value={jobDraft.name} onChange={(e) => setJobDraft((prev) => ({ ...prev, name: e.target.value }))} maxLength={80} /></label>
          <label>Schedule (seconds or cron)<input value={jobDraft.schedule} onChange={(e) => setJobDraft((prev) => ({ ...prev, schedule: e.target.value }))} placeholder="3600" /></label>
          <label>Command<input value={jobDraft.command} onChange={(e) => setJobDraft((prev) => ({ ...prev, command: e.target.value }))} maxLength={1000} /></label>
          <p className="muted reflex-hint">Scheduled commands may perform actions without asking again. Only schedule commands you authorize to run unattended. Each run is limited to five minutes.</p>
          <button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Add scheduled job'}</button>
        </form>
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Reflexes</h2>
          <span className="muted">When something happens, Atulya notifies you and/or acts.</span>
        </div>
        <div className="reflex-list">
          {rules.length === 0 && <p className="muted">No reflexes yet.</p>}
          {rules.map((rule) => (
            <div className={`reflex-card${rule.enabled === false ? ' paused' : ''}`} key={rule.id}>
              <div className="reflex-head">
                <strong>{rule.name}</strong>
                <span className="reflex-badges">
                  {rule.enabled === false ? <span className="badge">paused</span> : <span className="badge good">on</span>}
                  {rule.allow_risky && <span className="badge warn">risky allowed</span>}
                </span>
              </div>
              <div className="reflex-body">
                <div><small>WHEN</small> {eventsOf(rule).join(', ')}
                  {rule.match && Object.keys(rule.match).length > 0 && (
                    <> where {Object.entries(rule.match).map(([k, v]) => `${k} ~ "${v}"`).join(', ')}</>
                  )}
                </div>
                {rule.notify && <div><small>NOTIFY</small> {rule.notify}</div>}
                {rule.command && <div><small>DO</small> {rule.command}</div>}
                <div className="muted">
                  Fired {rule.fire_count || 0}× · last {timeAgo(rule.last_fired)}
                  {rule.cooldown_seconds ? ` · cooldown ${rule.cooldown_seconds}s` : ''}
                  {rule.last_result?.blocked ? ' · last run blocked (risky)' : ''}
                  {rule.last_result?.error ? ` · last error: ${rule.last_result.error}` : ''}
                </div>
              </div>
              <div className="reflex-actions">
                <button type="button" onClick={() => test(rule)}>Test</button>
                <button type="button" onClick={() => toggle(rule)}>{rule.enabled === false ? 'Resume' : 'Pause'}</button>
                <button type="button" className="danger" onClick={() => remove(rule)}>Delete</button>
              </div>
            </div>
          ))}
        </div>

        <form className="reflex-form" onSubmit={addRule}>
          <h3>New reflex</h3>
          <label>Name<input value={draft.name} onChange={update('name')} placeholder="Porch light at dusk" /></label>
          <label>When
            <select value={draft.event} onChange={update('event')}>
              {KNOWN_EVENTS.map(([type, label]) => <option key={type} value={type}>{label} ({type})</option>)}
            </select>
          </label>
          <div className="reflex-row">
            <label>Only if field<input value={draft.matchField} onChange={update('matchField')} placeholder="message" /></label>
            <label>contains<input value={draft.matchValue} onChange={update('matchValue')} placeholder="dusk" /></label>
          </div>
          <label>Notify me with<input value={draft.notify} onChange={update('notify')} placeholder="Reminder: {message}" /></label>
          <label>And do<input value={draft.command} onChange={update('command')} placeholder="turn on the living room light" /></label>
          <div className="reflex-row">
            <label>Cooldown (s)<input type="number" min="0" value={draft.cooldown_seconds} onChange={update('cooldown_seconds')} /></label>
            <label className="check"><input type="checkbox" checked={draft.allow_risky} onChange={update('allow_risky')} /> Allow risky actions (unlock, email…)</label>
          </div>
          <p className="muted reflex-hint">
            <code>{'{field}'}</code> in the notification is filled from the event. Commands run exactly as written —
            event data never goes into a command.
          </p>
          <button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Add reflex'}</button>
        </form>
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Nervous system</h2>
          <span className="muted">Live events · refreshes every 5s</span>
        </div>
        <div className="reflex-feed">
          {recent.length === 0 && <p className="muted">No events yet.</p>}
          {recent.map((event, idx) => (
            <div className="reflex-event" key={`${event.timestamp}-${idx}`}>
              <span className="reflex-time">{event.timestamp ? new Date(event.timestamp * 1000).toLocaleTimeString() : ''}</span>
              <strong>{event.type}</strong>
              <span className="muted">{summarize(event.payload)}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
