import React, { useEffect, useState } from 'react';
import { api, getToken } from '../../api.js';

function ago(seconds) {
  if (!seconds) return 'never';
  const delta = Math.max(0, Date.now() / 1000 - seconds);
  if (delta < 60) return 'just now';
  if (delta < 3600) return `${Math.round(delta / 60)}m ago`;
  if (delta < 86400) return `${Math.round(delta / 3600)}h ago`;
  return `${Math.round(delta / 86400)}d ago`;
}

export function Senses({ toast }) {
  const [senses, setSenses] = useState(null);
  const [draft, setDraft] = useState({ name: '', source: '' });
  const [saving, setSaving] = useState(false);

  const load = () => api.get('/api/senses').then(setSenses).catch((err) => toast('error', err.message));

  useEffect(() => {
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, []);

  async function add(e) {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post('/api/senses/cameras', draft);
      setDraft({ name: '', source: '' });
      await load();
      toast('success', 'Camera added');
    } catch (err) {
      toast('error', err.message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(camera) {
    if (!window.confirm(`Remove the ${camera.camera} camera?`)) return;
    await api.delete(`/api/senses/cameras/${encodeURIComponent(camera.name)}`).catch((err) => toast('error', err.message));
    await load();
  }

  if (!senses) return <div className="lazy-loading">Loading senses…</div>;
  const origin = window.location.origin;
  return (
    <div className="reflexes">
      <section className="panel">
        <div className="panel-title">
          <h2>Cameras</h2>
          <span className="muted">Motion and people become events — “Someone is at the front door.”</span>
        </div>
        {!senses.opencv && (
          <p className="alert">Person detection needs OpenCV: <code>pip install -e ".[vision]"</code>. Without it cameras can't be read.</p>
        )}
        <div className="reflex-list">
          {senses.cameras.length === 0 && <p className="muted">No cameras yet.</p>}
          {senses.cameras.map((cam) => (
            <div className="reflex-card camera-card" key={cam.name}>
              <div className="reflex-head">
                <strong>{cam.camera}</strong>
                <span className="reflex-badges">
                  {cam.running && !cam.error ? <span className="badge good">watching</span> : <span className="badge warn">{cam.running ? 'trouble' : 'off'}</span>}
                  <span className="badge">{cam.detector || 'motion only'}</span>
                </span>
              </div>
              <div className="reflex-body">
                <div><small>SOURCE</small> <code>{cam.source}</code></div>
                <div><small>PERSON</small> {ago(cam.last_person)} · <small>MOTION</small> {ago(cam.last_motion)}</div>
                {cam.error && <div className="bad-text">{cam.error}</div>}
              </div>
              {cam.snapshot && (
                <img className="camera-snapshot" alt={`Last person seen at the ${cam.camera}`}
                  src={`/api/senses/cameras/${encodeURIComponent(cam.name)}/snapshot?token=${encodeURIComponent(getToken())}&t=${cam.last_person}`} />
              )}
              <div className="reflex-actions">
                <button type="button" className="danger" onClick={() => remove(cam)}>Remove</button>
              </div>
            </div>
          ))}
        </div>
        <form className="reflex-form" onSubmit={add}>
          <h3>Add a camera</h3>
          <div className="reflex-row">
            <label>Where is it?<input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder="front door" required /></label>
            <label>Source<input value={draft.source} onChange={(e) => setDraft({ ...draft, source: e.target.value })} placeholder="rtsp://user:pass@192.168.1.20/stream" required /></label>
          </div>
          <p className="muted reflex-hint">
            A webcam number (<code>0</code>), an RTSP/HTTP stream, a snapshot URL (<code>http://…/snapshot.jpg</code>) or a
            Home Assistant camera (<code>ha:camera.front_door</code>). Frames never leave this machine.
          </p>
          <button type="submit" className="primary" disabled={saving}>{saving ? 'Adding…' : 'Add camera'}</button>
        </form>
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Home Assistant sensors</h2>
          {senses.home ? <span className="badge good">watching {senses.home.watching}</span> : <span className="badge">off</span>}
        </div>
        {senses.home ? (
          <>
            <p className="muted">Doorbells, people, motion, doors and alarms from Home Assistant raise the same events.</p>
            {senses.home.error && <p className="bad-text">{senses.home.error}</p>}
            <div className="reflex-feed">
              {(senses.home.recent || []).map((e, i) => (
                <div className="reflex-event" key={i}>
                  <span className="reflex-time">{e.at ? new Date(e.at * 1000).toLocaleTimeString() : ''}</span>
                  <strong>{e.type}</strong>
                  <span className="muted">{e.name}{e.state ? ` → ${e.state}` : ''}</span>
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className="muted">Set <code>HOME_ASSISTANT_URL</code> and <code>HOME_ASSISTANT_TOKEN</code> and restart: Ring, Nest,
            Frigate and other doorbells and sensors then work with the “Someone at the door” reflex.</p>
        )}
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Always listening</h2>
          <span className="muted">Rooms where Atulya can hear “Hey Atulya”, even with this page closed.</span>
        </div>
        <div className="reflex-list">
          {senses.listeners.length === 0 && <p className="muted">No listening devices yet.</p>}
          {senses.listeners.map((l) => (
            <div className="reflex-card" key={l.device}>
              <div className="reflex-head">
                <strong>{l.device}</strong>
                <span className="reflex-badges">
                  {l.online ? <span className="badge good">{l.muted ? 'muted' : l.state}</span> : <span className="badge">offline</span>}
                </span>
              </div>
              <div className="muted">Signed in as {l.user || '—'} · wake word “{l.wake_word || 'hey atulya'}”
                {l.stt ? ` · ${l.stt}` : ''} · last heard {ago(l.last_heard)}</div>
            </div>
          ))}
        </div>
        <div className="setup-box">
          <h3>Add a listening device</h3>
          <p className="muted">On any computer or Raspberry Pi with a microphone:</p>
          <pre className="terminal">{`pip install -e ".[ambient]"
atulya listen --url ${origin} --login
atulya listen --install-autostart`}</pre>
          <p className="muted reflex-hint">A tray icon shows when it's listening (saffron), thinking, speaking (green) or muted.
            Use <code>--no-tray</code> on a headless device, and <code>--install-autostart systemd</code> to start it at boot.</p>
        </div>
      </section>
    </div>
  );
}
