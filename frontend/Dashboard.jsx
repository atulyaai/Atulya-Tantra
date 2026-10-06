import React, { useCallback, useEffect, useState } from 'react';
import { api } from './api.js';
import { registerSections } from './sections.js';
import { PairingManager } from './Pairing.jsx';

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

function PhoneLink({ toast }) {
  const [inbox, setInbox] = useState(null);
  const url = inbox ? `${inbox.origin}${inbox.path}?key=${inbox.key}` : '';
  async function show() { try { setInbox(await api.get('/api/money/inbox')); } catch (e) { toast('error', e.message); } }
  async function rotate() {
    if (!window.confirm('Make a new key? Your phone stops working until you paste the new one.')) return;
    try { setInbox({ ...inbox, ...(await api.post('/api/money/inbox/rotate', {})) }); } catch (e) { toast('error', e.message); }
  }
  return (
    <div className="db-phone" onClick={(e) => e.stopPropagation()}>
      <h4>Record bank SMS from your phone</h4>
      {!inbox ? <button type="button" onClick={show}>Link my phone</button> : (
        <>
          <p>In an SMS-forwarding app (Android: SMS Forwarder, MacroDroid or Tasker; iPhone: a Shortcuts “When I get a message” automation), filter on your bank’s sender and POST the message text to:</p>
          <code>{url}</code>
          <p><small>Use this computer’s address instead of “localhost” (see README: Phone and other devices). The key can only add bank alerts; it opens nothing else.</small></p>
          <button type="button" onClick={() => navigator.clipboard?.writeText(url).then(() => toast('success', 'Copied'))}>Copy</button>{' '}
          <button type="button" onClick={rotate}>New key</button>
        </>
      )}
    </div>
  );
}

const QUICK = ['power_on', 'power_off', 'toggle', 'volume_up', 'volume_down', 'mute', 'play_pause', 'home', 'lock', 'open', 'close'];

function Fabric({ devices, admin, toast, reload, full }) {
  const [found, setFound] = useState(null);
  const [busy, setBusy] = useState('');

  async function run(dev, action) {
    let confirmed = false;
    try {
      await api.post(`/api/fabric/${dev.id}/do`, { action });
    } catch (e) {
      if (/confirmation/i.test(e.message)) {
        if (!window.confirm(`${action.replace(/_/g, ' ')} on ${dev.name}?`)) return;
        confirmed = true;
        try { await api.post(`/api/fabric/${dev.id}/do`, { action, confirmed }); } catch (e2) { toast('error', e2.message); return; }
      } else { toast('error', e.message); return; }
    }
    toast('success', `${action.replace(/_/g, ' ')}: ${dev.name}`);
    reload();
  }
  async function scan() {
    setBusy('scan');
    try { setFound((await api.post('/api/fabric/discover', {})).found); } catch (e) { toast('error', e.message); } finally { setBusy(''); }
  }
  async function add(c) {
    try { await api.post('/api/fabric/add', { candidate: c.id, name: c.label }); toast('success', `Added ${c.label}`); setFound((f) => f.filter((x) => x.id !== c.id)); reload(); }
    catch (e) { toast('error', e.message); }
  }
  async function forget(dev) {
    if (!window.confirm(`Forget ${dev.name}?`)) return;
    try { await api.delete(`/api/fabric/${dev.id}`); reload(); } catch (e) { toast('error', e.message); }
  }

  return (
    <div onClick={(e) => e.stopPropagation()}>
      {devices.map((dev) => (
        <div key={dev.id} className="db-fdev">
          <b>{dev.name}</b> <small>{dev.kind}{dev.room ? ` · ${dev.room}` : ''} · {dev.driver}</small>
          <div className="db-fbtns">
            {QUICK.filter((a) => dev.can.includes(a)).slice(0, full ? 11 : 5).map((a) => <button key={a} type="button" onClick={() => run(dev, a)}>{a.replace(/_/g, ' ')}</button>)}
            {full && <button type="button" className="danger" onClick={() => forget(dev)}>forget</button>}
          </div>
        </div>
      ))}
      {admin && <button type="button" className="db-scan" disabled={busy === 'scan'} onClick={scan}>{busy === 'scan' ? 'Scanning your network…' : 'Scan network for devices'}</button>}
      {found && (found.length ? found.map((c) => (
        <div key={c.id} className="db-fdev"><b>{c.label}</b> <small>{c.host} · {c.evidence}</small>
          <div className="db-fbtns"><button type="button" disabled={c.driver === 'unknown'} onClick={() => add(c)}>{c.driver === 'unknown' ? 'say “learn this device”' : 'Add'}</button></div></div>
      )) : <small>Nothing new found.</small>)}
    </div>
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
        <p>Private data: <b>{sys.vault?.on ? 'encrypted' : 'not encrypted'}</b>{!sys.vault?.on && full('system') && <small> · set ATULYA_VAULT_PASSPHRASE in .env, restart, then it protects money, chats, calendar, reminders and your profile</small>}</p>
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
        badge={d.home.simulated && !d.home.devices.length ? null : <span className="db-chip ok">LIVE</span>}>
        <div className="db-devices">
          {d.home.devices.map((v) => (
            <div key={v.id} className={`db-dev ${v.state === 'on' ? 'on' : ''}`}>
              <span>{v.name}</span>
              <b>{v.type === 'thermostat' ? `${v.temperature}°C` : v.type === 'light' && v.state === 'on' ? `${v.brightness || 100}%` : v.state}</b>
              {v.type !== 'lock' && <Toggle on={v.state === 'on'} label={v.name} onChange={(on) => act('/api/dashboard/home', { device_id: v.id, action: on ? 'on' : 'off' })} />}
            </div>
          ))}
        </div>
        <h4>Your devices</h4>
        {!d.fabric.length && <small>None added yet. Scan, or say “scan for devices”.</small>}
        <Fabric devices={d.fabric} admin={Boolean(d.system)} toast={toast} reload={load} full={full('home')} />
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
    money: d.money && d.money.month && (
      <Tile id="money" area="money" title="Money" open={full('money')} onOpen={pick}
        badge={<span className="db-chip">{d.money.month.label.toUpperCase()}</span>}>
        <p className="db-big">{d.money.currency}{Math.round(d.money.month.total).toLocaleString()}
          {d.money.last_month_total > 0 && <small> vs {d.money.currency}{Math.round(d.money.last_month_total).toLocaleString()} last month</small>}</p>
        <div className="db-bars">
          {d.money.month.by_category.slice(0, full('money') ? 12 : 3).map(([c, v]) => (
            <div key={c}><span>{c}</span><i style={{ width: `${Math.min(100, (v / Math.max(1, d.money.month.total)) * 100)}%` }} /><em>{Math.round(v).toLocaleString()}</em></div>
          ))}
          {!d.money.month.by_category.length && <small>No spending yet. Say “I spent 500 on groceries”.</small>}
        </div>
        {(full('money') || d.money.budgets.length > 0) && d.money.budgets.slice(0, full('money') ? 12 : 2).map((b) => (
          <p key={b.category} className="db-item" style={b.spent > b.limit ? { color: '#ff9a9a' } : undefined}>
            {b.category}: {Math.round(b.spent).toLocaleString()} / {Math.round(b.limit).toLocaleString()}{b.spent > b.limit ? ' (over)' : ''}</p>
        ))}
        {d.money.bills.length > 0 && <h4>Bills due</h4>}
        {d.money.income_month > 0 && <p className="db-item">Money in this month: <b>{d.money.currency}{Math.round(d.money.income_month).toLocaleString()}</b></p>}
        {full('money') && <PhoneLink toast={toast} />}
        {d.money.bills.slice(0, full('money') ? 10 : 2).map((b) => <p key={b.id} className="db-item">{b.name} <small>{d.money.currency}{Math.round(b.amount).toLocaleString()} · {b.days === 0 ? 'today' : `in ${b.days}d`}</small></p>)}
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
      {!open && d.system && <PairingManager toast={toast} />}
    </div>
  );
}

export default Dashboard;
