import React, { useEffect, useState } from 'react';
import { api } from './api.js';

function GoogleCard({ toast }) {
  const [status, setStatus] = useState(null);
  const [client, setClient] = useState({ client_id: '', client_secret: '' });
  const [busy, setBusy] = useState(false);

  const load = () => api.get('/api/google/status').then(setStatus).catch(() => {});
  useEffect(() => { load(); }, []);

  async function saveClient(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post('/api/google/client', client);
      setClient({ client_id: '', client_secret: '' });
      await load();
      toast('success', 'Google is set up — now connect your account.');
    } catch (err) {
      toast('error', err.message);
    } finally {
      setBusy(false);
    }
  }

  async function connect() {
    setBusy(true);
    try {
      const res = await api.post('/api/google/connect', {});
      window.location.assign(res.url);
    } catch (err) {
      toast('error', err.message);
      setBusy(false);
    }
  }

  async function disconnect() {
    if (!window.confirm('Disconnect Google? Atulya will stop reading your Gmail and Calendar.')) return;
    await api.post('/api/google/disconnect', {}).catch((err) => toast('error', err.message));
    await load();
  }

  if (!status) return null;
  const account = status.account || {};
  return (
    <section className="panel">
      <div className="panel-title">
        <h2>Google account</h2>
        {account.connected ? <span className="badge good">connected</span> : <span className="badge">not connected</span>}
      </div>
      {account.connected ? (
        <>
          <p>Atulya uses <strong>{account.email || 'your Google account'}</strong> for “check my email”, “what's on my
            calendar” and “schedule a call with Rahul tomorrow at 3pm”. Sending mail and deleting events always ask first.</p>
          <button type="button" className="danger" onClick={disconnect}>Disconnect Google</button>
        </>
      ) : status.configured ? (
        <>
          <p>Connect Gmail and Google Calendar with one click. Only your own account is used for your requests.</p>
          <button type="button" className="primary" disabled={busy} onClick={connect}>{busy ? 'Opening Google…' : 'Connect Google'}</button>
        </>
      ) : status.is_admin ? (
        <form className="reflex-form" onSubmit={saveClient}>
          <h3>Set up Google (once, for everyone)</h3>
          <ol className="setup-steps">
            <li>In Google Cloud Console, create a project and enable the <strong>Gmail API</strong> and <strong>Google Calendar API</strong>.</li>
            <li>Create an <strong>OAuth client ID</strong> (Web application) and add this redirect URI:
              <code className="copyable">{status.redirect_uri}</code></li>
            <li>Paste the client ID and secret here.</li>
          </ol>
          <label>Client ID<input value={client.client_id} onChange={(e) => setClient({ ...client, client_id: e.target.value })}
            placeholder="1234…apps.googleusercontent.com" required /></label>
          <label>Client secret<input type="password" value={client.client_secret}
            onChange={(e) => setClient({ ...client, client_secret: e.target.value })} required /></label>
          <button type="submit" className="primary" disabled={busy}>Save</button>
        </form>
      ) : (
        <p className="muted">Ask an admin to set up Google sign-in, then connect your account here.</p>
      )}
    </section>
  );
}

export function AboutYou({ toast }) {
  const [profile, setProfile] = useState(null);
  const [teach, setTeach] = useState('');

  const load = () => api.get('/api/profile').then(setProfile).catch((err) => toast('error', err.message));
  useEffect(() => { load(); }, []);

  async function learn(e) {
    e.preventDefault();
    if (!teach.trim()) return;
    try {
      const res = await api.post('/api/profile/facts', { text: teach.trim() });
      toast('success', `I'll remember that ${res.facts.map((f) => f.text).join(' and ')}.`);
      setTeach('');
      await load();
    } catch (err) {
      toast('error', err.message);
    }
  }

  async function forget(fact) {
    await api.delete(`/api/profile/facts/${encodeURIComponent(fact.id)}`).catch((err) => toast('error', err.message));
    await load();
  }

  async function setTrusted(approval, trusted) {
    try {
      await api.post('/api/profile/trust', { key: approval.key, trusted });
      await load();
    } catch (err) {
      toast('error', err.message);
    }
  }

  async function forgetEverything() {
    if (!window.confirm('Forget everything Atulya has learned about you?')) return;
    await api.delete('/api/profile').catch((err) => toast('error', err.message));
    await load();
  }

  if (!profile) return <div className="lazy-loading">Loading…</div>;
  const approvals = (profile.approvals || []).filter((a) => a.learnable);
  return (
    <div className="reflexes">
      <section className="panel">
        <div className="panel-title">
          <h2>What Atulya knows about you</h2>
          <span className="muted">Stays on this machine. Say “what do you know about me?” or “forget …” anytime.</span>
        </div>
        <div className="fact-list">
          {profile.facts.length === 0 && <p className="muted">Nothing yet. Tell Atulya things like “my wife's name is Priya” or “I live in Delhi”.</p>}
          {profile.facts.map((fact) => (
            <div className="fact" key={fact.id}>
              <span>{fact.text[0].toUpperCase() + fact.text.slice(1)}</span>
              <button type="button" className="icon-btn" title="Forget this" aria-label={`Forget: ${fact.text}`} onClick={() => forget(fact)}>×</button>
            </div>
          ))}
        </div>
        <form className="inline-form" onSubmit={learn}>
          <input value={teach} onChange={(e) => setTeach(e.target.value)} placeholder="Teach Atulya: my son's name is Arjun" />
          <button type="submit">Remember</button>
        </form>
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Your habits</h2>
          <span className="muted">Things you do on three or more days around the same time.</span>
        </div>
        {profile.habits.length === 0 ? (
          <p className="muted">No habits yet — Atulya notices them as you use it.</p>
        ) : (
          <ul className="habit-list">
            {profile.habits.map((habit) => (
              <li key={habit.signature}>You usually <strong>{habit.label}</strong> {habit.when} <span className="muted">· seen on {habit.days} days</span></li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Asking before acting</h2>
          <span className="muted">After {profile.learn_after} yeses in a row Atulya offers to stop asking — only if you agree.</span>
        </div>
        {approvals.length === 0 ? (
          <p className="muted">Nothing yet. Risky actions like unlocking a door always ask first.</p>
        ) : (
          <div className="reflex-list">
            {approvals.map((a) => (
              <div className="reflex-card" key={a.key}>
                <div className="reflex-head">
                  <strong>{a.label}</strong>
                  {a.trusted ? <span className="badge warn">doesn't ask</span> : <span className="badge good">asks first</span>}
                </div>
                <div className="muted">Approved {a.approved || 0}× · declined {a.declined || 0}× · {a.streak || 0} in a row</div>
                <div className="reflex-actions">
                  {a.trusted
                    ? <button type="button" onClick={() => setTrusted(a, false)}>Ask me again</button>
                    : <button type="button" onClick={() => setTrusted(a, true)}>Stop asking</button>}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <GoogleCard toast={toast} />

      <section className="panel">
        <div className="panel-title"><h2>Start over</h2></div>
        <button type="button" className="danger" onClick={forgetEverything}>Forget everything about me</button>
      </section>
    </div>
  );
}
