import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../api.js';
import { registerSections } from '../sections.js';

// The action engine: one window for what Atulya is doing. Every tile reads real data (/api/dashboard).
// Tap a tile, or say "open the calendar", to see it in full.

const ago = (t) => { if (!t) return ''; const s = Math.max(0, Date.now() / 1000 - t); return s < 90 ? 'just now' : s < 3600 ? `${Math.round(s / 60)} min ago` : `${Math.round(s / 3600)} h ago`; };
const when = (t) => (t ? new Date(t * 1000).toLocaleString([], { weekday: 'short', hour: '2-digit', minute: '2-digit' }) : '');

function Tile({ id, title, area, open, onOpen, children, badge }) {
  return (
    <section className={`db-tile ${open ? 'open' : ''}`} style={{ gridArea: area }} onClick={() => onOpen(id)} aria-label={title}>
      <header><h3>{title}</h3>{badge}</header>
      {children}
    </section>
  );
}

function Toggle({ on, onChange, label, disabled }) {
  return (
    <button type="button" className={`db-toggle ${on ? 'on' : ''}`} disabled={disabled} role="switch" aria-checked={on} aria-label={label}
      onClick={(e) => { e.stopPropagation(); onChange(!on); }}><i /></button>
  );
}

export function Dashboard({ toast }) {
  const [d, setD] = useState(null);
  const [open, setOpen] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(() => api.get('/api/dashboard').then((x) => { setD(x); setError(''); }).catch((e) => setError(e.message)), []);
  useEffect(() => { load(); const t = setInterval(load, 4000); return () => clearInterval(t); }, [load]);
  useEffect(() => (d ? registerSections('dashboard', d.sections.filter((s) => d[s.id]), (id) => setOpen(id)) : undefined), [d]);

  async function act(path, body, ok) {
    try { const r = await api.post(path, body); if (ok) toast('success', ok(r)); await load(); } catch (e) { toast('error', e.message); }
  }

  if (!d) return <p className="lazy-loading">{error || 'Starting the action engine…'}</p>;
  const sys = d.system;
  const pick = (id) => setOpen((cur) => (cur === id ? null : id));
  const full = (id) => open === id;
  const hidden = (id) => open && open !== id;

  const tiles = {
    system: sys && (
      <Tile id="system" area="sys" title="System status" open={full('system')} onOpen={pick}
        badge={<span className="db-chip ok">ACTIVE</span>}>
        <p>Agent: <b>{sys.agent}</b></p>
        <p>Fastest brain: <b>{sys.fastest}</b>{sys.latency != null && <> · {sys.latency}s</>}</p>
        <div className="db-bars">
          {sys.brains.slice(0, full('system') ? 20 : 3).map((b) => (
            <div key={b.name}><span>{b.name}</span><i style={{ width: `${Math.min(100, 100 / (1 + b.seconds))}%` }} /><em>{b.seconds}s</em></div>
          ))}
          {!sys.brains.length && <small>Speeds appear after the first answers.</small>}
        </div>
        {full('system') && <p className="db-note">Linked: {sys.ready.join(', ') || 'none'}. Add more under Menu → Brains &amp; keys.</p>}
      </Tile>
    ),
    pc: d.pc && (
      <Tile id="pc" area="pc" title="PC desktop automation" open={full('pc')} onOpen={pick}>
        <div className="db-row"><span>PC control</span>
          <Toggle on={d.pc.control} label="PC control" onChange={(on) => act('/api/dashboard/pc-control', { on }, (r) => `PC control ${r.control ? 'on: I still ask before each action' : 'off'}.`)} /></div>
        <h4>Recent actions</h4>
        {d.pc.recent.length ? d.pc.recent.slice().reverse().map((r, i) => <p key={i} className="db-item">{String(r.name).replace('pc_', '').replace('_', ' ')} <small>{ago(r.t)}</small></p>)
          : <small>Nothing yet. With PC control on, ask me to open an app.</small>}
      </Tile>
    ),
    web: d.web && (
      <Tile id="web" area="web" title="Web browser automation" open={full('web')} onOpen={pick}
        badge={<span className={`db-chip ${d.web.state === 'running' ? 'run' : ''}`}>{d.web.state.toUpperCase()}</span>}>
        {d.web.goal ? <p className="db-goal">{d.web.goal}</p> : <small>No web task yet. Try “add running shoes to my cart on amazon.in”.</small>}
        <div className="db-flow">
          {d.web.steps.map((s, i) => (
            <React.Fragment key={i}>
              {i > 0 && <span className="db-arrow">→</span>}
              <div className={`db-node ${s.end ? 'end' : ''}`}><b>{s.label}</b>{full('web') && s.url && <small>{s.url.slice(0, 40)}</small>}{s.note && <small>{s.note}</small>}</div>
            </React.Fragment>
          ))}
        </div>
        {d.web.steps.length > 0 && <div className="db-progress"><i style={{ width: `${Math.min(100, (d.web.steps.length / 15) * 100)}%` }} /></div>}
      </Tile>
    ),
    home: (
      <Tile id="home" area="home" title="Smart home hub" open={full('home')} onOpen={pick}
        badge={d.home.simulated ? <span className="db-chip">SIMULATED</span> : <span className="db-chip ok">LIVE</span>}>
        <div className="db-devices">
          {d.home.devices.map((v) => (
            <div key={v.id} className={`db-dev ${v.state === 'on' ? 'on' : ''}`}>
              <span>{v.name}</span>
              <b>{v.type === 'thermostat' ? `${v.temperature}°C` : v.type === 'light' && v.state === 'on' ? `${v.brightness || 100}%` : v.state}</b>
              {v.type !== 'lock' && <Toggle on={v.state === 'on'} label={v.name} onChange={(on) => act('/api/dashboard/home', { device_id: v.id, action: on ? 'on' : 'off' })} />}
            </div>
          ))}
        </div>
        {d.home.simulated && <small>No Home Assistant connected, so these are practice devices.</small>}
      </Tile>
    ),
    calendar: (
      <Tile id="calendar" area="cal" title="Calendar & reminders" open={full('calendar')} onOpen={pick}>
        <div className="db-cols">
          <div><h4>Next up</h4>
            {d.calendar.events.length ? d.calendar.events.slice(0, full('calendar') ? 8 : 3).map((e, i) => <p key={i} className="db-item"><b>{e.title}</b> <small>{when(e.time)} · {e.minutes} min</small></p>)
              : <small>Nothing in the next 7 days.</small>}</div>
          <div><h4>Reminders</h4>
            {d.calendar.reminders.length ? d.calendar.reminders.slice(0, full('calendar') ? 8 : 3).map((r, i) => <p key={i} className="db-item">{r.message} <small>{when(r.time)}</small></p>)
              : <small>No reminders set.</small>}</div>
        </div>
      </Tile>
    ),
    media: (
      <Tile id="media" area="media" title="Audio media player" open={full('media')} onOpen={pick}>
        <p className="db-now">{d.media.now_playing ? <>Now playing: <b>{d.media.now_playing}</b> <small>{ago(d.media.at)}</small></> : <small>Nothing played yet. Say “play some music”.</small>}</p>
        <div className="db-controls">
          {[['previous', '⏮'], ['play_pause', '⏯'], ['next', '⏭'], ['volume_down', '🔉'], ['volume_up', '🔊']].map(([a, icon]) => (
            <button key={a} type="button" aria-label={a.replace('_', ' ')} onClick={(e) => { e.stopPropagation(); act('/api/dashboard/media', { action: a }, (r) => r.message); }}>{icon}</button>
          ))}
        </div>
      </Tile>
    ),
  };

  return (
    <div className="db">
      <header className="db-head">
        <div className="db-logo">ATULYA</div>
        <div><b>ACTION ENGINE</b><span>AI AUTOMATION SYSTEM</span></div>
        {open && <button type="button" className="db-back" onClick={() => setOpen(null)}>← All tiles</button>}
      </header>
      <div className={`db-grid ${open ? 'one' : ''}`}>
        {Object.entries(tiles).filter(([id, t]) => t && !hidden(id)).map(([id, t]) => <React.Fragment key={id}>{t}</React.Fragment>)}
      </div>
    </div>
  );
}

export default Dashboard;
