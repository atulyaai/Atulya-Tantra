import React, { useEffect, useState } from 'react';
import { api } from './api.js';

export function PairingManager({ toast }) {
  const [devices, setDevices] = useState([]);
  const [telegramLinks, setTelegramLinks] = useState([]);
  const [code, setCode] = useState(null);
  const [telegramCode, setTelegramCode] = useState(null);
  const [inboxKind, setInboxKind] = useState('all');
  const [inboxItems, setInboxItems] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function load() {
    try {
      setDevices((await api.get('/api/pairing/devices')).devices || []);
      setTelegramLinks((await api.get('/api/pairing/telegram')).links || []);
      setError('');
    }
    catch (err) { setError(err.message); }
  }
  useEffect(() => {
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, []);

  async function makeCode(kind) {
    setBusy(true);
    try {
      const result = await api.post('/api/pairing/code', { permission: 'full' });
      setCode({ ...result, kind });
    } catch (err) { toast('error', err.message); }
    finally { setBusy(false); }
  }

  async function revoke(device) {
    if (!window.confirm(`Disconnect ${device.name}? It will stop syncing and cannot use its old token again.`)) return;
    try {
      await api.post(`/api/pairing/devices/${device.id}/revoke`, {});
      toast('success', `${device.name} disconnected.`);
      await load();
    } catch (err) { toast('error', err.message); }
  }

  async function makeTelegramCode() {
    setBusy(true);
    try { setTelegramCode(await api.post('/api/pairing/telegram/code', {})); }
    catch (err) { toast('error', err.message); }
    finally { setBusy(false); }
  }

  async function revokeTelegram(link) {
    const name = link.display_name || link.username;
    if (!window.confirm(`Unlink Telegram account ${name}? Its Telegram chat history will stay separate.`)) return;
    try {
      await api.post(`/api/pairing/telegram/${encodeURIComponent(link.telegram_id)}/revoke`, {});
      toast('success', 'Telegram account unlinked.');
      await load();
    } catch (err) { toast('error', err.message); }
  }

  async function loadInbox() {
    try { setInboxItems((await api.get(`/api/phone/inbox?kind=${encodeURIComponent(inboxKind)}&limit=50`)).items || []); }
    catch (err) { toast('error', err.message); }
  }

  async function clearInbox() {
    if (!window.confirm(`Delete all stored ${inboxKind === 'all' ? 'phone' : inboxKind} data? This cannot be undone.`)) return;
    try {
      await api.delete(`/api/phone/inbox?kind=${encodeURIComponent(inboxKind)}`);
      setInboxItems([]);
      toast('success', 'Phone data cleared.');
    } catch (err) { toast('error', err.message); }
  }

  return (
    <section className="panel">
      <div className="panel-title"><h2>Paired phones and computers</h2></div>
      <p className="muted">A pairing code works once for ten minutes and links the device to the signed-in account. A device ID is only a label, never an admin credential. Full permission allows requested phone actions or computer tasks. You can disconnect a device here at any time.</p>
      {error && <p role="alert">{error === 'Admin access required' ? 'Only the owner can manage paired devices.' : error}</p>}
      <div className="db-fbtns">
        <button type="button" disabled={busy} onClick={() => makeCode('phone')}>Pair a phone</button>
        <button type="button" disabled={busy} onClick={() => makeCode('computer')}>Pair another computer</button>
        <button type="button" disabled={busy} onClick={makeTelegramCode}>Link Telegram to this profile</button>
      </div>
      {code && <div className="db-phone">
        <h4>Enter this one-time code in the {code.kind} companion</h4>
        <code>{code.code}</code>
        <p>Expires in ten minutes. Use it only on a device you own. The device receives full permission for its selected companion features.</p>
      </div>}
      {telegramCode && <div className="db-phone">
        <h4>Link your Telegram account</h4>
        <p>Send this one-time command to your Atulya Telegram bot from a Telegram account already on the allowlist:</p>
        <code>/link {telegramCode.code}</code>
        <p>Expires in ten minutes. After linking, Telegram uses this account's saved profile and personal memory.</p>
      </div>}
      {telegramLinks.map((link) => (
        <div className="db-fdev" key={link.telegram_id}>
          <b>Owner profile: {ownerLabel(link.display_name, link.username)}</b>
          <small>Telegram sender ID {link.telegram_id} · linked {ago(link.created)}</small>
          <div className="db-fbtns"><button type="button" className="danger" onClick={() => revokeTelegram(link)}>Unlink</button></div>
        </div>
      ))}
      {!error && telegramLinks.length === 0 && <p className="muted">Telegram is not linked to an account profile. Create a link code and send the `/link` command from an allowlisted Telegram account.</p>}
      {devices.filter((device) => !device.revoked).map((device) => (
        <div className="db-fdev" key={device.id}>
          <b>{device.name}</b> <small>{device.kind} · {device.permission} access · profile: {ownerLabel(device.owner_display_name, device.owner_username)} · {device.last_seen ? `last seen ${ago(device.last_seen)}` : 'not connected yet'}</small>
          <div className="db-fbtns"><button type="button" className="danger" onClick={() => revoke(device)}>Disconnect</button></div>
        </div>
      ))}
      {!error && devices.every((device) => device.revoked) && <p className="muted">No devices are paired yet.</p>}
      <div className="db-phone">
        <h4>Phone inbox</h4>
        <p><small>SMS, notifications, and location are visible to the owner. They are encrypted at rest only when the vault passphrase is enabled.</small></p>
        <label>Show <select value={inboxKind} onChange={(event) => setInboxKind(event.target.value)}>
          {['all', 'sms', 'notifications', 'location'].map((kind) => <option key={kind} value={kind}>{kind}</option>)}
        </select></label>{' '}
        <button type="button" onClick={loadInbox}>Load recent data</button>{' '}
        <button type="button" className="danger" disabled={!inboxItems.length} onClick={clearInbox}>Clear</button>
        {inboxItems.map((row) => <p className="db-item" key={row.id}>
          <b>{row.kind}</b> · {new Date(row.received_at * 1000).toLocaleString()}<br />
          <small>{JSON.stringify(row.item)}</small>
        </p>)}
        {!inboxItems.length && <p className="muted">Phone data appears here after you load it.</p>}
      </div>
    </section>
  );
}

const ago = (stamp) => {
  const seconds = Math.max(0, Date.now() / 1000 - Number(stamp || 0));
  return seconds < 60 ? 'just now' : seconds < 3600 ? `${Math.round(seconds / 60)} min ago` : `${Math.round(seconds / 3600)} h ago`;
};

const ownerLabel = (displayName, username) => {
  if (!username) return 'unlinked';
  return displayName && displayName !== username ? `${displayName} (${username})` : username;
};
