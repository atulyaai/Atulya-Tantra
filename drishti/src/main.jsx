import React, { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api, boostAudio, clearToken, getToken, setToken, getUser, setUser } from './api.js';
import { UserManagement } from './pages/UserManagement.jsx';
import { Orb } from './pages/Orb.jsx';
import { MenuPopover, Panel } from './Panel.jsx';
import { selectSectionByText } from './sections.js';
import './styles.css';

// Lazy-load the heavy Spirit view so it is fetched only when opened, keeping
// the initial bundle (and first paint) small.
// Admin-only: trigger rules, brain tier, and live event feed.
const Reflexes = lazy(() => import('./pages/Reflexes.jsx').then((m) => ({ default: m.Reflexes })));
const Routines = lazy(() => import('./pages/Routines.jsx').then((m) => ({ default: m.Routines })));
const MemoryTree = lazy(() => import('./pages/MemoryTree.jsx').then((m) => ({ default: m.MemoryTree })));
const Providers = lazy(() => import('./pages/Providers.jsx').then((m) => ({ default: m.Providers })));
const Dashboard = lazy(() => import('./pages/Dashboard.jsx').then((m) => ({ default: m.Dashboard })));
const AboutYou = lazy(() => import('./pages/AboutYou.jsx').then((m) => ({ default: m.AboutYou })));
const Senses = lazy(() => import('./pages/Senses.jsx').then((m) => ({ default: m.Senses })));

function renderMarkdown(text) {
  const parts = String(text || '').split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
  return parts.map((part, idx) => {
    if (part.startsWith('`') && part.endsWith('`')) return <code key={idx}>{part.slice(1, -1)}</code>;
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={idx}>{part.slice(2, -2)}</strong>;
    return part.split('\n').map((line, lineIdx) => (
      <React.Fragment key={`${idx}-${lineIdx}`}>
        {lineIdx > 0 && <br />}
        {line}
      </React.Fragment>
    ));
  });
}

const CHAT_CACHE_KEY = 'atulya-chat-messages';

function loadCachedMessages(key, fallback = []) {
  try {
    const raw = localStorage.getItem(key);
    const parsed = raw ? JSON.parse(raw) : null;
    return Array.isArray(parsed) ? parsed : fallback;
  } catch {
    return fallback;
  }
}

function cacheMessages(key, messages) {
  try {
    localStorage.setItem(key, JSON.stringify(messages.slice(-120)));
  } catch {}
}

function normalizeHistoryMessages(messages = []) {
  return messages
    .filter((msg) => msg && (msg.role === 'user' || msg.role === 'assistant') && msg.text)
    .map((msg, idx) => ({
      id: msg.id || `${msg.created_at || 'history'}-${idx}`,
      role: msg.role,
      text: msg.text,
      provider: msg.provider,
      surface: msg.surface,
      created_at: msg.created_at,
    }));
}

function Chat({ bootstrap, toast }) {
  const isAdmin = getUser()?.role === 'admin';
  const providerOptions = bootstrap?.providers?.length ? bootstrap.providers : [{ id: 'auto', name: 'Auto Provider', available: true }];
  const [provider, setProvider] = useState('auto');
  const [prompt, setPrompt] = useState('');
  const [messages, setMessages] = useState(() => loadCachedMessages(CHAT_CACHE_KEY, []));
  const [toolSteps, setToolSteps] = useState([]);
  const [maxContext, setMaxContext] = useState(10);
  const [pendingApproval, setPendingApproval] = useState(null);
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  useEffect(() => {
    cacheMessages(CHAT_CACHE_KEY, messages);
  }, [messages]);

  useEffect(() => {
    api.get('/api/chat/history')
      .then((res) => {
        const chatMessages = normalizeHistoryMessages(res.messages || []).filter((msg) => msg.surface !== 'live');
        if (chatMessages.length) setMessages(chatMessages);
      })
      .catch(() => {});
  }, []);

  function historyPayload(items = messages) {
    return items
      .filter((msg) => msg.text)
      .slice(-maxContext)
      .map((msg) => ({ role: msg.role, content: msg.text }));
  }

  function holdForApproval(done, text) {
    if (!done?.needs_approval) return;
    setPendingApproval({
      prompt: text,
      tool: done.tool,
      tool_args: done.tool_args,
      pending_tool: done.pending_tool || { tool: done.tool, arguments: done.tool_args || {} },
    });
  }

  // A follow-up turn that answers a held action: Approve (approved_tool) or Cancel ("no").
  function answerApproval(body) {
    const id = Date.now();
    setPendingApproval(null);
    setBusy(true);
    setMessages((prev) => [...prev, { role: 'assistant', text: '', id }]);
    api.streamChat(
      { model_id: provider, provider, history: historyPayload(), ...body },
      (token) => setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: msg.text + token } : msg)),
      (done) => {
        if (done?.steps) setToolSteps(done.steps);
        holdForApproval(done, '');  // e.g. "want me to stop asking?" after the fifth yes
        setBusy(false);
      },
      (err) => {
        setBusy(false);
        setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: `Error: ${err.message}` } : msg));
      },
      (tool) => setToolSteps((prev) => [...prev, tool]),
    );
  }

  function send(event) {
    event.preventDefault();
    if (!prompt.trim() || busy) return;
    const id = Date.now();
    const text = prompt;
    const nextMessages = [...messages, { role: 'user', text }, { role: 'assistant', text: '', id }];
    setPrompt('');
    setBusy(true);
    setToolSteps([]);
    setMessages(nextMessages);
    api.streamChat(
      { prompt: text, model_id: provider, provider, max_tokens: 256, temperature: 0.7, history: historyPayload(messages) },
      (token) => setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: msg.text + token } : msg)),
      (done) => {
        if (done?.steps) setToolSteps(done.steps);
        holdForApproval(done, text);
        setBusy(false);
      },
      (err) => {
        setBusy(false);
        setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: `Error: ${err.message}` } : msg));
      },
      (tool) => setToolSteps((prev) => [...prev, tool]),
    );
  }

  return (
    <section className="panel chat">
      <div className="panel-title">
        <h2>Atulya Chat</h2>
        <div className="panel-actions">
          <label style={{fontSize:12, display:'flex', alignItems:'center', gap:4, color:'var(--muted)'}}>
            Context:
            <select value={String(maxContext)} onChange={e => setMaxContext(Number(e.target.value))}>
              <option value="5">5 msgs</option>
              <option value="10">10 msgs</option>
              <option value="20">20 msgs</option>
              <option value="50">50 msgs</option>
            </select>
          </label>
          <button
            type="button"
            onClick={() => {
              api.delete('/api/chat/history').catch(() => {});
              setMessages([]);
              setToolSteps([]);
            }}
          >
            Clear
          </button>
          {isAdmin && (
            <select value={provider} onChange={(e) => setProvider(e.target.value)}>
              {providerOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.available ? 'Ready - ' : 'Off - '}{item.name}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>
      <div className="messages">
        {toolSteps.map((step, idx) => (
          <div className="message assistant tool-step" key={`${step.tool}-${idx}`}>
            <strong>{step.tool}</strong>: {step.success ? 'done' : step.error || 'failed'}
          </div>
        ))}
        {messages.map((msg, idx) => <div className={`message ${msg.role}`} key={msg.id || idx}>{renderMarkdown(msg.text)}</div>)}
        <div ref={endRef} />
      </div>
      <form className="composer" onSubmit={send}>
        <input value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Send a prompt..." />
        <button className="primary" disabled={busy}>{busy ? 'Streaming...' : 'Send'}</button>
      </form>
      {pendingApproval && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Approve action">
          <div className="modal-card">
            <h2>Approve Action</h2>
            <p>{pendingApproval.pending_tool?.description
              ? `Should Atulya ${pendingApproval.pending_tool.description}?`
              : 'Review this action before Atulya runs it.'}</p>
            <details className="approval-details">
              <summary>Details</summary>
              <pre className="terminal">{JSON.stringify({ tool: pendingApproval.tool || pendingApproval.pending_tool?.tool, args: pendingApproval.tool_args || pendingApproval.pending_tool?.arguments }, null, 2)}</pre>
            </details>
            <div className="terminal-actions">
              <button type="button" onClick={() => answerApproval({ prompt: 'no' })}>Cancel</button>
              <button
                type="button"
                className="primary"
                onClick={() => answerApproval({ prompt: pendingApproval.prompt, approved_tool: pendingApproval.pending_tool })}
              >
                Approve and run
              </button>
            </div>
          </div>
        </div>
      )}
      <div style={{position:'relative'}}
        onDragOver={e => {e.preventDefault(); e.currentTarget.style.borderColor='var(--accent)';}}
        onDragLeave={e => {e.currentTarget.style.borderColor='';}}
        onDrop={async e => {
          e.preventDefault();
          e.currentTarget.style.borderColor='';
          const files = Array.from(e.dataTransfer.files);
          for (const f of files) {
            const formData = new FormData();
            formData.append('file', f);
            try {
              const res = await fetch('/api/upload', {
                method: 'POST',
                headers: { 'X-Atulya-Token': getToken() },
                body: formData,
              });
              const data = await res.json();
              if (data.ok) toast('success', `Uploaded ${f.name}`);
            } catch (err) {
              toast('error', `Upload failed: ${err.message}`);
            }
          }
        }}
        style={{border:'2px dashed var(--line)', borderRadius:8, padding:12, textAlign:'center', color:'var(--muted)', fontSize:12, marginTop:8}}>
        Drop files here to upload, or{' '}
        <label style={{cursor:'pointer', color:'var(--accent)'}}>
          browse
          <input type="file" hidden multiple onChange={async e => {
            const files = Array.from(e.target.files);
            for (const f of files) {
              const formData = new FormData();
              formData.append('file', f);
              try {
                const res = await fetch('/api/upload', {
                  method: 'POST',
                  headers: { 'X-Atulya-Token': getToken() },
                  body: formData,
                });
                const data = await res.json();
                if (data.ok) toast('success', `Uploaded ${f.name}`);
              } catch (err) {
                toast('error', `Upload failed: ${err.message}`);
              }
            }
          }} />
        </label>
      </div>
    </section>
  );
}

function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await api.post('/api/auth/login', { username, password });
      if (res.ok) {
        setToken(res.token);
        setUser(res.user);
        onLogin();
      } else {
        throw new Error(res.detail || 'Wrong username or password');
      }
    } catch (err) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-shell">
      <div className="login-orb" />
      <form className="login-card" onSubmit={submit}>
        <div className="login-logo-glow" />
        <h1>ATULYA</h1>
        <p className="muted">Digital Organism OS</p>
        
        {error && <div className="alert error-alert">{error}</div>}
        
        <div className="input-group">
          <input 
            type="text"
            value={username} 
            onChange={(e) => setUsername(e.target.value)} 
            placeholder="Username" 
            autoFocus 
            required 
          />
        </div>
        
        <div className="input-group">
          <input 
            type="password" 
            value={password} 
            onChange={(e) => setPassword(e.target.value)} 
            placeholder="Password" 
            required 
          />
        </div>
        
        <button className="primary login-btn" disabled={loading}>
          {loading ? 'SYNCHRONIZING...' : 'ENGAGE CORE'}
        </button>
      </form>
    </main>
  );
}

const MENU_ITEMS = [
  { id: 'chat', label: 'Chat history', icon: '✎' },
  { id: 'about', label: 'About you', icon: '☺' },
  { id: 'dashboard', label: 'Action engine', icon: '◈', wide: true },
  { id: 'memory', label: 'Memory tree', icon: '❋', wide: true },
  { id: 'routines', label: 'Routines', icon: '↻', admin: true },
  { id: 'senses', label: 'Senses', icon: '◎', admin: true },
  { id: 'brains', label: 'Brains & keys', icon: '🔑', admin: true },
  { id: 'reflexes', label: 'Brain & reflexes', icon: '⚡', admin: true },
  { id: 'users', label: 'Users', icon: '👥', admin: true },
];

// "show users", "open routines" … spoken or typed: open that pop-up instead of asking the brain.
const PANEL_WORDS = [
  ['users', /\b(users?|accounts?|people)\b/],
  ['routines', /\b(routines?|schedules?|automations?)\b/],
  ['senses', /\b(senses|sensors?|cameras?)\b/],
  ['brains', /\b(api keys?|brains?|providers?|models?)\b/],
  ['reflexes', /\b(reflexes|triggers?|brain settings)\b/],
  ['dashboard', /\b(dashboard|action engine|control cent(?:er|re)|command cent(?:er|re))\b/],
  ['memory', /\b(memory|memories|memory tree|what do you remember)\b/],
  ['about', /\b(about me|profile|my details)\b/],
  ['chat', /\b(chat|history|conversation|transcript)\b/],
];

function App() {
  const [panel, setPanel] = useState(null);
  const [bootstrap, setBootstrap] = useState(null);
  const [error, setError] = useState('');
  const [authenticated, setAuthenticated] = useState(Boolean(getToken()));
  const [toasts, setToasts] = useState([]);
  const [healthWarnings, setHealthWarnings] = useState([]);
  const [showShortcuts, setShowShortcuts] = useState(false);
  
  const currentUser = getUser();
  const isAdmin = currentUser?.role === 'admin';
  const toastSeq = useRef(0);

  function toast(type, message, { title = '', duration = 3500 } = {}) {
    toastSeq.current += 1;
    const id = `${Date.now()}-${toastSeq.current}`;
    setToasts((prev) => [...prev, { id, type, message, title }].slice(-5));
    setTimeout(() => setToasts((prev) => prev.filter((item) => item.id !== id)), duration);
  }

  // Live server push: reminders, health alerts, trigger results and automation
  // outcomes arrive here. Shown as notifications app-wide and re-broadcast as a
  // DOM event so Live mode can speak them. Replayed history is not re-alerted.
  useEffect(() => {
    if (!authenticated) return undefined;
    const stop = api.connectWebSocket((msg) => {
      if (msg?.type !== 'event' || msg.replay) return;
      const data = msg.data || {};
      const kind = data.type === 'error' ? 'error' : data.type === 'success' ? 'success' : 'info';
      toast(kind, data.desc || data.title || 'Notification', { title: data.desc ? data.title : '', duration: 8000 });
      window.dispatchEvent(new CustomEvent('atulya:notification', { detail: data }));
    });
    return stop;
  }, [authenticated]);

  useEffect(() => {
    if (!authenticated) return;
    const params = new URLSearchParams(window.location.search);
    const google = params.get('google');
    if (!google) return;
    window.history.replaceState({}, '', window.location.pathname);
    setPanel('about');
    if (google === 'connected') toast('success', 'Google connected — Gmail and Calendar are ready.');
    else toast('error', "Google wasn't connected.");
  }, [authenticated]);

  async function load() {
    setError('');
    try {
      const boot = await api.get('/api/dashboard/bootstrap');
      setAuthenticated(true);
      setBootstrap(boot);
      if (boot.user) {
        setUser(boot.user);
      }
    } catch (err) {
      if (err.message.includes('Unauthorized') || err.message.includes('401')) {
        clearToken();
        setAuthenticated(false);
      }
      throw err;
    }
  }

  useEffect(() => {
    if (authenticated) {
      load().catch((err) => setError(err.message));
    }
  }, [authenticated]);

  // On the computer Atulya runs on there is no login screen. Other devices still sign in.
  useEffect(() => {
    if (authenticated) return;
    try { if (sessionStorage.getItem('atulya-signed-out')) return; } catch {}
    fetch('/api/auth/local')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data?.token) return;
        setToken(data.token);
        if (data.user) setUser(data.user);
        setAuthenticated(true);
      })
      .catch(() => {});
  }, [authenticated]);

  useEffect(() => {
    if (!authenticated || getUser()?.role !== 'admin') return undefined; // server health is for the admin
    api.get('/api/health')
      .then(res => { if (res.warnings) setHealthWarnings(res.warnings); })
      .catch(() => {});
    const hc = setInterval(() => {
      api.get('/api/health')
        .then(res => { if (res.warnings) setHealthWarnings(res.warnings); })
        .catch(() => {});
    }, 60000);
    return () => clearInterval(hc);
  }, [authenticated]);

  useEffect(() => {
    function handleKeyDown(event) {
      if (event.ctrlKey || event.metaKey) {
        switch (event.key) {
          case '0': event.preventDefault(); setPanel(null); break;
          case '2': event.preventDefault(); setPanel('chat'); break;
          case '3': event.preventDefault(); setPanel('about'); break;
        }
      }
      if (event.key === '?' && !event.ctrlKey && !event.metaKey) {
        setShowShortcuts(prev => !prev);
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const lazyPage = (Page, label) => (
    <Suspense fallback={<div className="lazy-loading">Loading {label}…</div>}>
      <Page toast={toast} />
    </Suspense>
  );

  function panelContent() {
    if (panel === 'chat') return <Chat bootstrap={bootstrap} toast={toast} />;
    if (panel === 'about') return lazyPage(AboutYou, 'about you');
    if (panel === 'memory') return lazyPage(MemoryTree, 'memory tree');
    if (panel === 'dashboard') return lazyPage(Dashboard, 'action engine');
    if (!isAdmin) return <p className="lazy-loading">That area is for the admin.</p>;
    if (panel === 'users') return <UserManagement toast={toast} />;
    if (panel === 'brains') return lazyPage(Providers, 'brains');
    if (panel === 'reflexes') return lazyPage(Reflexes, 'reflexes');
    if (panel === 'routines') return lazyPage(Routines, 'routines');
    if (panel === 'senses') return lazyPage(Senses, 'senses');
    return null;
  }

  // Returns what Atulya should say if the text was a "show …" command, else null.
  function openByVoice(text) {
    const t = String(text || '').toLowerCase().trim();
    if (/^(?:please )?(?:close|hide|go back|dismiss)(?: (?:this|that|it|the panel|the window))?$/.test(t)) {
      if (!panel) return null;
      setPanel(null);
      return 'Closed.';
    }
    const inside = panel ? selectSectionByText(t) : null; // "open episodic memories" inside the open window
    if (inside) return inside;
    if (!/\b(show|open|go to|take me to|display)\b/.test(t)) return null;
    for (const [id, pattern] of PANEL_WORDS) {
      if (!pattern.test(t)) continue;
      const item = MENU_ITEMS.find((entry) => entry.id === id);
      if (item?.admin && !isAdmin) return 'That area is for the admin.';
      setPanel(id);
      return `Opening ${item.label.toLowerCase()}.`;
    }
    return null;
  }

  async function handleLogout() {
    try {
      await api.post('/api/auth/logout').catch(() => {});
    } finally {
      clearToken();
      try { sessionStorage.setItem('atulya-signed-out', '1'); } catch {}
      setAuthenticated(false);
      setPanel(null);
    }
  }

  if (!authenticated) {
    return <Login onLogin={() => { try { sessionStorage.removeItem('atulya-signed-out'); } catch {} setAuthenticated(true); load().catch((err) => setError(err.message)); }} />;
  }

  const toastStack = (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((item) => (
        <div className={`toast ${item.type}`} key={item.id}>
          {item.title && <strong className="toast-title">{item.title}</strong>}
          {item.message}
        </div>
      ))}
    </div>
  );

  // One screen: the orb. Everything else is a pop-up over it.
  const titles = Object.fromEntries(MENU_ITEMS.map((item) => [item.id, item.label]));
  const visibleItems = MENU_ITEMS.filter((item) => !item.admin || isAdmin);
  return (
    <>
      <Orb toast={toast} onMenu={() => setPanel((p) => (p === 'menu' ? null : 'menu'))} onCommand={openByVoice} />
      {panel === 'menu' && (
        <MenuPopover items={visibleItems} user={currentUser} onClose={() => setPanel(null)}
          onPick={(id) => setPanel(id)} onSignOut={handleLogout} />
      )}
      {panel && panel !== 'menu' && (
        <Panel title={titles[panel] || 'Atulya'} wide={Boolean(MENU_ITEMS.find((m) => m.id === panel)?.wide)} onClose={() => setPanel(null)}>{panelContent()}</Panel>
      )}
      {(error || healthWarnings.some((w) => w.severity === 'high')) && (
        <div className="orb-alert" role="alert">
          {error || healthWarnings.find((w) => w.severity === 'high')?.message}
        </div>
      )}
      {showShortcuts && (
        <div className="modal-backdrop" onClick={() => setShowShortcuts(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h2>Shortcuts</h2>
            <div className="table">
              <div className="row"><span>Space</span><span>Talk to Atulya</span></div>
              <div className="row"><span>Esc / Ctrl+0</span><span>Close a pop-up</span></div>
              <div className="row"><span>Ctrl+2</span><span>Chat history</span></div>
              <div className="row"><span>Ctrl+3</span><span>About you</span></div>
              <div className="row"><span>?</span><span>This list</span></div>
            </div>
            <button onClick={() => setShowShortcuts(false)}>Close</button>
          </div>
        </div>
      )}
      {toastStack}
    </>
  );
}

// Never a blank page: if something fails to load (server stopped, or an old
// cached page asking for files a rebuild replaced), say so and offer a reload.
class Recover extends React.Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  render() {
    if (!this.state.error) return this.props.children;
    const stale = /dynamically imported module|Loading chunk|Failed to fetch/i.test(String(this.state.error?.message));
    return (
      <div className="recover">
        <h2>{stale ? 'Atulya was updated or restarted' : 'Something went wrong'}</h2>
        <p>{stale ? 'This page is out of date or the server is not reachable. Make sure Atulya is running (start.bat), then reload.'
          : String(this.state.error?.message || this.state.error)}</p>
        <button type="button" className="primary" onClick={() => window.location.reload()}>Reload</button>
      </div>
    );
  }
}

createRoot(document.getElementById('root')).render(<Recover><App /></Recover>);
