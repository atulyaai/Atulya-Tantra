import React, { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api, clearToken, getToken, setToken, getUser, setUser } from './api.js';
import { UserManagement } from './src/pages/UserManagement.jsx';
import './styles.css';

// Lazy-load the heavy Spirit view so it is fetched only when opened, keeping
// the initial bundle (and first paint) small.
// Admin-only: trigger rules, brain tier, and live event feed.
const Reflexes = lazy(() => import('./src/pages/Reflexes.jsx').then((m) => ({ default: m.Reflexes })));
const Routines = lazy(() => import('./src/pages/Routines.jsx').then((m) => ({ default: m.Routines })));
const AboutYou = lazy(() => import('./src/pages/AboutYou.jsx').then((m) => ({ default: m.AboutYou })));
const Galaxy = lazy(() => import('./src/pages/Galaxy.jsx').then((m) => ({ default: m.Galaxy })));
const Senses = lazy(() => import('./src/pages/Senses.jsx').then((m) => ({ default: m.Senses })));

function Metric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value ?? '--'}</strong>
    </div>
  );
}

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
const LIVE_CACHE_KEY = 'atulya-live-messages';
const DEFAULT_LIVE_MESSAGES = [];
const WAKE_PHRASES = ['hey atulya', 'atulya'];
// Real pipeline stages (from the server's trace) -> the node the visual animates.
const STAGE_AGENT = {
  understand: 'ATHENA', plan: 'ATHENA', decide: 'ATHENA', act: 'FORGE', check: 'ORACLE', remember: 'MEMORY', think: 'ORACLE',
};
const TRACE_STEP_MS = 180;

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

function stripWakePhrase(text) {
  const trimmed = String(text || '').trim();
  const lower = trimmed.toLowerCase();
  const phrase = WAKE_PHRASES.find((item) => lower.startsWith(item));
  return phrase ? trimmed.slice(phrase.length).replace(/^[,.:;\s-]+/, '').trim() : trimmed;
}

function Dashboard({ bootstrap, load }) {
  const system = bootstrap?.system || {};
  const runs = bootstrap?.history?.runs || [];
  return (
    <section className="panel-grid">
      <div className="panel">
        <div className="panel-title">
          <h2>System</h2>
          <button onClick={load}>Refresh</button>
        </div>
        <div className="metrics">
          <Metric label="CPU" value={`${system.cpu_pct ?? '--'}%`} />
          <Metric label="RAM" value={`${system.ram_pct ?? '--'}%`} />
          <Metric label="Available RAM" value={`${system.ram_avail_gb ?? '--'} GB`} />
          <Metric label="Python" value={system.python_version || '--'} />
        </div>
      </div>
      <div className="panel">
        <div className="panel-title">
          <h2>Run History</h2>
          <span>{runs.length} runs</span>
        </div>
        <div className="table">
          {runs.slice(0, 8).map((run, idx) => (
            <div className="row" key={`${run.time}-${idx}`}>
              <span>{run.event}</span>
              <span>{run.config}</span>
              <span>{run.steps || '--'} steps</span>
            </div>
          ))}
          {runs.length === 0 && <p className="muted">No runs yet.</p>}
        </div>
      </div>
    </section>
  );
}

function LossChart({ metrics }) {
  const points = metrics.slice(-80).map((m, idx) => ({
    step: Number(m.step ?? m.run_step ?? idx),
    loss: Number(m.loss ?? m.train_loss ?? 0),
  })).filter((m) => Number.isFinite(m.loss) && m.loss > 0);
  if (!points.length) return <div className="chart empty">No loss metrics yet.</div>;
  const width = 560;
  const height = 160;
  const minLoss = Math.min(...points.map((p) => p.loss));
  const maxLoss = Math.max(...points.map((p) => p.loss));
  const minStep = Math.min(...points.map((p) => p.step));
  const maxStep = Math.max(...points.map((p) => p.step));
  const sx = (step) => maxStep === minStep ? 0 : ((step - minStep) / (maxStep - minStep)) * width;
  const sy = (loss) => maxLoss === minLoss ? height / 2 : height - ((loss - minLoss) / (maxLoss - minLoss)) * height;
  const d = points.map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${sx(p.step).toFixed(1)} ${sy(p.loss).toFixed(1)}`).join(' ');
  const bestY = sy(minLoss).toFixed(1);
  return (
    <div className="chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Loss chart">
        <line x1="0" y1={bestY} x2={width} y2={bestY} className="best-line" />
        <path d={d} />
      </svg>
      <div className="chart-meta">
        <span>Best {minLoss.toFixed(4)}</span>
        <span>Last {points[points.length - 1].loss.toFixed(4)}</span>
      </div>
    </div>
  );
}

function Training({ bootstrap, load, toast }) {
  const datasets = bootstrap?.datasets || [];
  const configs = bootstrap?.configs?.configs || [];
  const checkpoints = bootstrap?.checkpoints || [];
  const [status, setStatus] = useState(null);
  const [log, setLog] = useState([]);
  const [metrics, setMetrics] = useState([]);
  const [busy, setBusy] = useState(false);
  const terminalEndRef = useRef(null);
  const [form, setForm] = useState({
    config: configs[0]?.name || 'atulya_seed',
    dataset: datasets[0]?.id || '',
    steps: 50000,
    lr: 0.0005,
    seq_limit: 128,
    checkpoint_every: 500,
    resume_id: 'latest',
    all_datasets: true,
    stream: true,
    train_all: true,
    device: 'auto',
  });

  useEffect(() => {
    setForm((prev) => ({
      ...prev,
      config: prev.config || configs[0]?.name || 'atulya_seed',
      dataset: prev.dataset || datasets[0]?.id || '',
    }));
  }, [configs, datasets]);

  async function refreshStatus() {
    const res = await api.get('/api/training-status');
    setStatus(res);
    setLog(res.log_tail || []);
    const metricRes = await api.get('/api/training-metrics').catch(() => ({ metrics: [] }));
    setMetrics(metricRes.metrics || []);
  }

  useEffect(() => terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' }), [log]);

  useEffect(() => {
    refreshStatus().catch(() => {});
    const id = setInterval(() => refreshStatus().catch(() => {}), 4000);
    return () => clearInterval(id);
  }, []);

  async function startTraining(event) {
    event.preventDefault();
    setBusy(true);
    const payload = {
      ...form,
      data_id: form.all_datasets ? 'all' : form.dataset,
      stream_dataset: form.stream,
      train_all: form.train_all,
    };
    try {
      const res = await api.post('/api/train/start', payload);
      if (res.error) throw new Error(res.error);
      toast('success', `Training started: PID ${res.pid}`);
      await refreshStatus();
      await load();
    } catch (err) {
      toast('error', err.message);
    } finally {
      setBusy(false);
    }
  }

  async function stopTraining() {
    setBusy(true);
    try {
      const res = await api.post('/api/train/stop');
      toast('success', res.message || 'Training stopped');
      await refreshStatus();
    } catch (err) {
      toast('error', err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel-grid">
      <div className="panel">
        <div className="panel-title">
          <h2>Active Training</h2>
          <span className={status?.running ? 'badge good' : 'badge'}>{status?.running ? 'Running' : 'Idle'}</span>
        </div>
        <div className="metrics">
          <Metric label="Phase" value={status?.status?.phase} />
          <Metric label="Step" value={status?.last?.step ?? status?.last?.run_step} />
          <Metric label="Loss" value={status?.last?.loss?.toFixed?.(4)} />
          <Metric label="Backend Python" value={status?.train_python || 'current'} />
        </div>
        <LossChart metrics={metrics} />
        <div className="terminal-actions">
          <span>{log.length} lines</span>
          <button type="button" onClick={() => navigator.clipboard?.writeText(log.join('\n'))}>Copy all</button>
          <button type="button" onClick={() => setLog([])}>Clear</button>
          {status?.running && <button type="button" className="danger" disabled={busy} onClick={stopTraining}>Stop</button>}
        </div>
        <div className="terminal">
          {log.slice(-80).map((line, idx) => <div className={lineClass(line)} key={idx}>{line}</div>)}
          {!log.length && <div>No training output yet.</div>}
          <div ref={terminalEndRef} />
        </div>
      </div>
      <form className="panel form" onSubmit={startTraining}>
        <div className="panel-title"><h2>New Pipeline</h2></div>
        <label>Config<select value={form.config} onChange={(e) => setForm({ ...form, config: e.target.value })}>
          {configs.map((cfg) => <option key={cfg.name} value={cfg.name}>{cfg.name}</option>)}
        </select></label>
        <label className="check"><input type="checkbox" checked={form.all_datasets} onChange={(e) => setForm({ ...form, all_datasets: e.target.checked, stream: e.target.checked || form.stream, train_all: e.target.checked || form.train_all })} /> All Datasets</label>
        <label>Dataset<select disabled={form.all_datasets} value={form.dataset} onChange={(e) => setForm({ ...form, dataset: e.target.value })}>
          {datasets.map((ds) => <option key={ds.id} value={ds.id}>{ds.name} ({ds.size_label})</option>)}
        </select></label>
        <label>Resume<select value={form.resume_id} onChange={(e) => setForm({ ...form, resume_id: e.target.value })}>
          <option value="fresh">fresh</option>
          {checkpoints.map((item) => <option key={item.id} value={item.id}>{item.label || item.id}</option>)}
        </select></label>
        <label>Training Steps<input type="number" min="100" max="50000" value={form.steps} onChange={(e) => setForm({ ...form, steps: Number(e.target.value) })} /><small>Total optimizer steps across the selected stream, not per dataset.</small></label>
        <label>Learning Rate<input type="number" step="0.00001" value={form.lr} onChange={(e) => setForm({ ...form, lr: Number(e.target.value) })} /></label>
        <label>Sequence Limit<input type="number" value={form.seq_limit} onChange={(e) => setForm({ ...form, seq_limit: Number(e.target.value) })} /></label>
        <label>Checkpoint Every<input type="number" value={form.checkpoint_every} onChange={(e) => setForm({ ...form, checkpoint_every: Number(e.target.value) })} /></label>
        <label className="check"><input type="checkbox" checked={form.stream} disabled={form.all_datasets} onChange={(e) => setForm({ ...form, stream: e.target.checked })} /> Stream Dataset</label>
        <label className="check"><input type="checkbox" checked={form.train_all} disabled={form.all_datasets} onChange={(e) => setForm({ ...form, train_all: e.target.checked })} /> Train All Rows</label>
        <button className="primary" disabled={busy || status?.running}>{busy ? 'Working...' : 'Start Training'}</button>
      </form>
    </section>
  );
}

function lineClass(line) {
  const text = String(line).toLowerCase();
  if (text.includes('error') || text.includes('traceback')) return 'log-line bad';
  if (text.includes('warn')) return 'log-line warn';
  if (text.includes('loss')) return 'log-line good';
  return 'log-line';
}

function LiveMode({ bootstrap, toast }) {
  const checkpoints = bootstrap?.checkpoints || [];
  const providerOptions = bootstrap?.providers || [{ id: 'auto', name: 'Auto Provider', available: true }];
  const [showTelemetry, setShowTelemetry] = useState(false);
  const [telemetry, setTelemetry] = useState(null);
  const [provider, setProvider] = useState('auto');
  const [prompt, setPrompt] = useState('');
  const [messages, setMessages] = useState(() => loadCachedMessages(LIVE_CACHE_KEY, DEFAULT_LIVE_MESSAGES));
  const [events, setEvents] = useState([
    { id: 1, label: 'Oracle Active Core online', state: 'ready' },
    { id: 2, label: 'Nervous system strands energized', state: 'standby' },
    { id: 3, label: 'Memory galaxy synchronized', state: 'ready' }
  ]);
  const [status, setStatus] = useState('ready');
  const [listening, setListening] = useState(false);
  const [cameraOn, setCameraOn] = useState(false);
  const [capturedFrame, setCapturedFrame] = useState('');
  const [busy, setBusy] = useState(false);
  
  const [voiceList, setVoiceList] = useState([
    {id: "en_male", name: "Atulya Neural (Male)", lang: "en"},
    {id: "en_female", name: "Atulya Neural (Female)", lang: "en"},
    {id: "hi_male", name: "Madhur Neural (Hindi)", lang: "hi"},
    {id: "hi_female", name: "Swara Neural (Hindi)", lang: "hi"},
  ]);

  const [selectedVoice, setSelectedVoice] = useState('en_male');
  const [continuous, setContinuous] = useState(false);
  // Voice/conversation options
  const [sttEngine, setSttEngine] = useState('local'); // 'local' (Whisper on your PC, stops when you stop talking) | 'browser' (cloud)
  const [autoSpeak, setAutoSpeak] = useState(true);       // speak replies aloud
  const [showVoiceSettings, setShowVoiceSettings] = useState(false);

  // Digital Nervous System States
  const [activeAgent, setActiveAgent] = useState('NONE');
  const [intentDetected, setIntentDetected] = useState('');
  const [routePath, setRoutePath] = useState('');  // Direct action / Brain / Awaiting your OK
  const [mindStream, setMindStream] = useState([
    { time: '22:00:01', title: 'System Bootup', desc: 'Atulya organic core initialized.', type: 'system' },
    { time: '22:00:03', title: 'Strand Diagnostic', desc: 'Memory galaxy, vision lens, and vocal echo systems synced.', type: 'ready' }
  ]);

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const recognitionRef = useRef(null);
  const replyRef = useRef('');
  const audioRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  // Set when Atulya has just asked "should I…?": the next utterance is the
  // answer, so hands-free mode accepts it without the wake word.
  const awaitingConfirmRef = useRef(false);
  const awaitingTimerRef = useRef(null);
  // Latest state / speak function for listeners that are registered once.
  const liveStateRef = useRef({ status: 'ready', busy: false, listening: false, autoSpeak: true });
  const speakRef = useRef(null);


  useEffect(() => {
    cacheMessages(LIVE_CACHE_KEY, messages);
  }, [messages]);

  useEffect(() => {
    api.get('/api/chat/history')
      .then((res) => {
        const liveMessages = normalizeHistoryMessages(res.messages || []).filter((msg) => msg.surface === 'live');
        if (liveMessages.length) setMessages(liveMessages.slice(-20));
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    async function loadVoices() {
      try {
        const res = await api.getVoices();
        if (res && res.voices) {
          setVoiceList(res.voices);
        }
      } catch (err) {
        console.error('Failed to load voice profiles', err);
      }
    }
    loadVoices();
  }, []);

  const eventSeq = useRef(0);
  function addEvent(label, state = 'active') {
    eventSeq.current += 1;
    setEvents((prev) => [{ id: `${Date.now()}-${eventSeq.current}`, label, state }, ...prev].slice(0, 8));
  }

  function addMindStep(title, desc, type = 'process') {
    const now = new Date();
    const timeStr = now.toTimeString().split(' ')[0];
    setMindStream((prev) => [
      { time: timeStr, title, desc, type },
      ...prev
    ].slice(0, 10));
  }

  function setAwaitingConfirm(on) {
    awaitingConfirmRef.current = on;
    clearTimeout(awaitingTimerRef.current);
    // The server drops an unanswered hold after two minutes; stop waiting sooner.
    if (on) awaitingTimerRef.current = setTimeout(() => { awaitingConfirmRef.current = false; }, 60000);
  }

  useEffect(() => {
    liveStateRef.current = { status, busy, listening, autoSpeak };
  }, [status, busy, listening, autoSpeak]);

  // Proactive notifications from the server (reminders, alerts, trigger
  // results): log them, and say them aloud unless Atulya is busy, listening or
  // already speaking. Routine successes are shown but not spoken.
  useEffect(() => {
    function onNotification(event) {
      const data = event.detail || {};
      const text = data.desc || data.title || '';
      if (!text) return;
      addEvent(text, 'ready');
      addMindStep(data.title || 'Notification', text, 'system');
      const s = liveStateRef.current;
      if (s.autoSpeak && data.type !== 'success' && !s.busy && !s.listening && s.status !== 'speaking') {
        speakRef.current?.(text);
      }
    }
    window.addEventListener('atulya:notification', onNotification);
    return () => {
      window.removeEventListener('atulya:notification', onNotification);
      clearTimeout(awaitingTimerRef.current);
    };
  }, []);

  function normalizeTelemetryEvent(item, idx) {
    const now = new Date();
    return {
      time: item.time || telemetry?.updated_at?.split(' ')?.[1] || now.toTimeString().split(' ')[0],
      title: item.title || `Telemetry ${idx + 1}`,
      desc: item.desc || item.label || 'No telemetry details reported.',
      type: item.type || item.state || 'ready',
    };
  }

  useEffect(() => {
    if (!showTelemetry) return undefined;
    let cancelled = false;

    async function loadTelemetry() {
      try {
        const res = await api.get('/api/telemetry');
        if (!cancelled) setTelemetry(res);
      } catch (err) {
        if (!cancelled) {
          setTelemetry((prev) => ({
            ...(prev || {}),
            error: err.message,
            events: [{ title: 'Telemetry Offline', desc: err.message, type: 'error' }],
          }));
        }
      }
    }

    loadTelemetry();
    const interval = window.setInterval(loadTelemetry, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [showTelemetry]);

  async function startCamera() {
    if (cameraOn) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
      setCameraOn(true);
      setStatus('seeing');
      setActiveAgent('VISION');
      addEvent('Optical scanner active', 'seeing');
      addMindStep('Optical Core Engaged', 'Camera scanner active and scanning spatial environment.', 'seeing');
    } catch (err) {
      toast('error', err.message);
      addEvent('Camera access blocked', 'error');
    }
  }

  function stopCamera() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setCameraOn(false);
    setStatus('ready');
    setActiveAgent('NONE');
    addEvent('Optical scanner offline', 'standby');
    addMindStep('Optical Core Standby', 'Camera scan stream stopped.', 'ready');
  }

  function captureFrame() {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 360;
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    const frame = canvas.toDataURL('image/jpeg', 0.8);
    setCapturedFrame(frame);
    setPrompt((p) => p || 'What do you see?');
    setStatus('reading');
    addEvent('Visual frame captured. Analyzing pixels...', 'seeing');
    addMindStep('Visual Frame Cached', 'Image matrix captured. Analyzing visual components.', 'seeing');
  }

  speakRef.current = speakNeural;
  function speakNeural(text) {
    if (!text.trim()) return;
    setStatus('speaking');
    setActiveAgent('ECHO');
    addEvent('Routing output to high-fidelity TTS synthesizer...', 'speaking');
    addMindStep('Vocal Synthesis Request', 'Sending output text to edge-tts neural voice compiler.', 'speaking');
    
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    
    if (audioRef.current) {
      try {
        audioRef.current.pause();
      } catch(e) {}
      audioRef.current = null;
    }
    
    api.tts(text, selectedVoice)
      .then((res) => {
        if (res.error) throw new Error(res.error);
        
        if (res.audio_base64) {
          addEvent('Streaming response through audio pipeline...', 'speaking');
          const audio = new Audio("data:audio/mp3;base64," + res.audio_base64);
          audioRef.current = audio;
          audio.onplay = () => {
            setStatus('speaking');
            setActiveAgent('ECHO');
            addMindStep('Consciousness Vocalizing', 'Streaming synthesized premium audio through speakers.', 'speaking');
          };
          audio.onended = () => {
            setStatus('ready');
            setActiveAgent('NONE');
            audioRef.current = null;
            addEvent('Vocalized response sequence complete', 'ready');
            addMindStep('Voice Flow Complete', 'Consciousness returned to standby.', 'ready');
            
            if (continuous) {
              setTimeout(() => {
                if (continuous && !listening && !busy) {
                  addEvent('Continuous Mode active. Opening microphone...', 'listening');
                  startListening();
                }
              }, 400);
            }
          };
          audio.onerror = (e) => {
            console.error('Audio play error, falling back', e);
            speakBrowserFallback(text);
          };
          audio.play().catch((err) => {
            console.error('Play action failed', err);
            speakBrowserFallback(text);
          });
        } else {
          speakBrowserFallback(text);
        }
      })
      .catch((err) => {
        console.error('Neural TTS synthesis failed, using browser fallback', err);
        speakBrowserFallback(text);
      });
  }

  function speakBrowserFallback(text) {
    if (!('speechSynthesis' in window) || !text.trim()) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.96;
    utterance.pitch = 1.02;
    utterance.onstart = () => {
      setStatus('speaking');
      setActiveAgent('ECHO');
    };
    utterance.onend = () => {
      setStatus('ready');
      setActiveAgent('NONE');
      addEvent('Vocalized fallback complete', 'ready');
      if (continuous) {
        setTimeout(() => startListening(), 400);
      }
    };
    window.speechSynthesis.speak(utterance);
    addEvent('Playing local synthetic voice fallback', 'speaking');
  }

  function startListening() {
    if (sttEngine === 'local') { startListeningLocal(); return; } // every auto-restart honours the chosen engine
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      toast('error', 'Speech recognition is not available in this browser.');
      addEvent('Speech recognition unavailable', 'error');
      return;
    }
    
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch(e) {}
    }
    
    if (audioRef.current) {
      try { audioRef.current.pause(); } catch(e) {}
      audioRef.current = null;
    }
    
    const recognition = new SpeechRecognition();
    recognition.lang = 'en-IN';
    recognition.interimResults = true;
    recognition.continuous = false;
    
    recognition.onstart = () => {
      setListening(true);
      setStatus('listening');
      setActiveAgent('ECHO');
      addEvent('Sensors active. Listening...', 'listening');
      addMindStep('Vocal Input Sensor Engaged', 'Microphone active. Listening for acoustic queries.', 'listening');
    };
    
    recognition.onresult = (event) => {
      const text = Array.from(event.results).map((result) => result[0].transcript).join(' ');
      setPrompt(text);
      if (event.results[event.results.length - 1].isFinal) {
        recognition.stop();
        const lower = text.trim().toLowerCase();
        if (continuous && !awaitingConfirmRef.current && !WAKE_PHRASES.some((phrase) => lower.includes(phrase))) {
          addEvent('Wake word not detected. Standing by...', 'ready');
          addMindStep('Wake Word Gate', 'Hands-free mode ignored ambient speech without wake phrase.', 'ready');
          setStatus('ready');
          setActiveAgent('NONE');
          setTimeout(() => {
            if (continuous && !busy) startListening();
          }, 700);
          return;
        }
        sendLive(stripWakePhrase(text));
      }
    };
    
    recognition.onerror = (event) => {
      setListening(false);
      setStatus('ready');
      setActiveAgent('NONE');
      if (event.error === 'no-speech' && continuous) {
        setTimeout(() => {
          if (continuous && !listening && !busy) {
            startListening();
          }
        }, 1000);
        return;
      }
      toast('error', event.error || 'Audio stream failed');
      addEvent('Mic pipeline error: ' + event.error, 'error');
    };
    
    recognition.onend = () => {
      setListening(false);
    };
    
    recognitionRef.current = recognition;
    recognition.start();
  }

  // Local, private speech-to-text via backend Whisper. Push-to-talk: start
  // recording, then call stopListening() (tap the mic again) to transcribe.
  async function startListeningLocal() {
    if (audioRef.current) {
      try { audioRef.current.pause(); } catch (e) {}
      audioRef.current = null;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks = [];
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setListening(false);
        const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
        setStatus('thinking');
        addEvent('Transcribing locally (Whisper)…', 'thinking');
        try {
          const lang = (voiceList.find((v) => v.id === selectedVoice)?.lang) || 'en';
          const res = await api.stt(blob, lang);
          const text = String(res.text || '').trim();
          if (res.error) throw new Error(res.error);
          if (!text) {
            setStatus('ready');
            addEvent('No speech detected', 'ready');
            if (continuous) setTimeout(() => startListeningLocal(), 500);
            return;
          }
          setPrompt(text);
          const lower = text.toLowerCase();
          if (continuous && !awaitingConfirmRef.current && !WAKE_PHRASES.some((phrase) => lower.includes(phrase))) {
            setStatus('ready');
            addEvent('Wake word not detected. Standing by…', 'ready');
            if (continuous) setTimeout(() => startListeningLocal(), 500);
            return;
          }
          sendLive(stripWakePhrase(text));
        } catch (err) {
          setStatus('ready');
          setActiveAgent('NONE');
          toast('error', err.message || 'Local transcription failed');
          addEvent('Local STT failed: ' + (err.message || 'error'), 'error');
        }
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      // End of speech: stop by itself after ~1.2s of quiet once the user has
      // spoken, so talking is one tap — no second tap needed.
      try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 1024;
        audioCtx.createMediaStreamSource(stream).connect(analyser);
        const buf = new Uint8Array(analyser.fftSize);
        const started = Date.now();
        let heard = false; let quietSince = 0;
        const tick = setInterval(() => {
          if (recorder.state === 'inactive') { clearInterval(tick); audioCtx.close(); return; }
          analyser.getByteTimeDomainData(buf);
          let sum = 0;
          for (let i = 0; i < buf.length; i += 1) { const v = (buf[i] - 128) / 128; sum += v * v; }
          const loud = Math.sqrt(sum / buf.length) > 0.03;
          const now = Date.now();
          if (loud) { heard = true; quietSince = 0; } else if (!quietSince) quietSince = now;
          const silentFor = quietSince ? now - quietSince : 0;
          if ((heard && silentFor > 1200) || (!heard && now - started > 8000) || now - started > 30000) {
            clearInterval(tick); audioCtx.close();
            if (recorder.state !== 'inactive') recorder.stop();
          }
        }, 100);
      } catch (e) { /* no Web Audio: fall back to tap-to-stop */ }
      setListening(true);
      setStatus('listening');
      setActiveAgent('ECHO');
      addEvent('Listening… just talk, I’ll stop when you do.', 'listening');
      addMindStep('Local Vocal Capture', 'Recording audio for private on-device transcription.', 'listening');
    } catch (err) {
      toast('error', 'Microphone access denied');
      addEvent('Mic access denied', 'error');
    }
  }

  function stopListening() {
    try { recognitionRef.current?.stop(); } catch (e) {}
    try {
      const rec = mediaRecorderRef.current;
      if (rec && rec.state !== 'inactive') rec.stop(); // triggers onstop -> transcribe
    } catch (e) {}
    setListening(false);
    if (status === 'listening') setStatus('ready');
    addEvent('Microphone sensor offline', 'standby');
    addMindStep('Vocal Input Sensor Disengaged', 'Microphone offline.', 'ready');
  }

  // Barge-in: cut off Atulya mid-speech and immediately start a new turn.
  function bargeIn() {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    if (audioRef.current) {
      try { audioRef.current.pause(); } catch (e) {}
      audioRef.current = null;
    }
    setStatus('ready');
    setActiveAgent('NONE');
    addEvent('Interrupted — listening…', 'listening');
    if (sttEngine === 'local') startListeningLocal();
    else startListening();
  }

  function toggleVoice() {
    if (status === 'speaking') { bargeIn(); return; }
    if (listening) {
      stopListening();
    } else if (sttEngine === 'local') {
      startListeningLocal();
    } else {
      startListening();
    }
  }




  // The Digital Nervous System Sequential State Stimulation Flow
  // Render the server's real pipeline trace (understand → decide → act →
  // remember / think) into the mind stream, animating the matching node.
  // Steps are lightly staggered only so they're readable.
  function playTrace(trace) {
    trace.forEach((step, i) => {
      setTimeout(() => {
        setActiveAgent(STAGE_AGENT[step.stage] || 'ORACLE');
        const failed = /Refused|failed/i.test(step.title || '');
        addMindStep(step.title || step.stage, step.detail || '', failed ? 'error' : 'process');
      }, i * TRACE_STEP_MS);
    });
  }

  function sendLive(voiceText) {
    const text = (voiceText || prompt).trim();
    if (!text || busy) return;
    const id = Date.now();
    const cameraNote = capturedFrame ? '\n\nCamera frame is captured in the Live Mode panel. Use vision when vision processing is active.' : '';
    const answeringConfirmation = awaitingConfirmRef.current;
    setAwaitingConfirm(false);

    setPrompt('');
    setBusy(true);
    setStatus('thinking');
    replyRef.current = '';
    setMessages((prev) => [
      ...prev,
      { role: 'user', text, image, id: `${id}-user` },
      { role: 'assistant', text: '', id },
    ]);
    setCapturedFrame('');

    // The request goes out immediately; what the mind stream shows next is
    // what the server actually did (its trace), not a script.
    setActiveAgent('ECHO');
    addMindStep('Heard', `"${text}"`, 'process');
    addEvent(answeringConfirmation ? 'Answer received — checking…' : 'Understanding your request…', 'thinking');

    api.post('/api/voice/chat', {
      prompt: text,
      ...(image ? { image } : {}),
      voice: selectedVoice,
      model_id: provider,
      provider,
      history: messages
        .filter((msg) => msg.text)
        .slice(-10)
        .map((msg) => ({ role: msg.role, content: msg.text })),
    })
      .then((res) => {
        setBusy(false);
        if (res.error && !res.response_text) throw new Error(res.error);

        replyRef.current = res.response_text || "";
        setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: res.response_text } : msg));

        const trace = Array.isArray(res.trace) ? res.trace : [];
        playTrace(trace);
        const understood = trace.find((step) => step.stage === 'understand');
        setIntentDetected(
          understood ? (understood.title === 'Intent' ? understood.detail.split('(')[0] : understood.title)
            : (answeringConfirmation ? 'Confirmation' : ''),
        );
        const direct = res.provider_name === 'Atulya Kernel';
        setRoutePath(res.needs_approval ? 'Awaiting your OK' : direct ? 'Direct action' : 'Brain');
        // A confirmation question: the next utterance is the answer.
        setAwaitingConfirm(Boolean(res.needs_approval));
        addEvent(
          res.needs_approval ? 'Waiting for your yes or no…' : `Answered via ${res.provider_name || 'Atulya'}`,
          res.needs_approval ? 'listening' : 'speaking',
        );

        setTimeout(() => {
            if (!autoSpeak) {
              setStatus('ready');
              setActiveAgent('NONE');
              addEvent('Auto-speak off — reply shown as text.', 'ready');
              return;
            }
            if (res.audio_base64) {
              const audio = new Audio("data:audio/mp3;base64," + res.audio_base64);
              audioRef.current = audio;
              setStatus('speaking');
              setActiveAgent('ECHO');
              audio.onplay = () => {
                setStatus('speaking');
                setActiveAgent('ECHO');
                addMindStep('Consciousness Vocalizing', 'Streaming response through speakers.', 'speaking');
              };
              audio.onended = () => {
                setStatus('ready');
                setActiveAgent('NONE');
                audioRef.current = null;
                addEvent('Assistant reply vocalized successfully', 'ready');
                addMindStep('Voice Flow Complete', 'Consciousness returned to standby.', 'ready');
                
                if (continuous) {
                  setTimeout(() => {
                    if (continuous && !listening && !busy) {
                      addEvent('Continuous Mode active. Opening microphone...', 'listening');
                      startListening();
                    }
                  }, 400);
                }
              };
              audio.play().catch((err) => {
                console.error('Play action failed', err);
                speakBrowserFallback(replyRef.current);
              });
            } else {
              if (res.error) addEvent(res.error, 'error');
              speakBrowserFallback(replyRef.current);
            }
        }, Math.min(1200, trace.length * TRACE_STEP_MS));
      })
      .catch((err) => {
        setBusy(false);
        setStatus('ready');
        setActiveAgent('NONE');
        addEvent('Request failed', 'error');
        addMindStep('Error', err.message, 'error');
        setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: `Command Failure: ${err.message}` } : msg));

        if (continuous) {
          setTimeout(() => startListening(), 2000);
        }
      });
  }

  const STATUS_TEXT = {
    ready: continuous ? 'Say “Hey Atulya”…' : 'Tap the mic and talk',
    listening: 'Listening…', thinking: 'Thinking…', speaking: 'Speaking — tap to interrupt',
    seeing: 'Camera on', reading: 'Ready to ask about the picture',
  };
  const QUICK = ['What’s on my calendar today?', 'Turn off the lights', 'Remind me in 10 minutes to stretch', 'What do you know about me?'];

  return (
    <div className="talk">
      <div className="talk-thread">
        {messages.length === 0 && (
          <div className="talk-empty">
            <h2>Hi, I’m Atulya.</h2>
            <p>Tap the mic and talk, or type below.</p>
          </div>
        )}
        {messages.map((msg, idx) => (
          <div className={`talk-msg ${msg.role}`} key={msg.id || idx}>
            {msg.image && <img src={msg.image} alt="What you showed Atulya" />}
            <div>{renderMarkdown(msg.text || (msg.role === 'assistant' ? '…' : ''))}</div>
          </div>
        ))}
        {routePath && !busy && <div className="talk-route">{intentDetected ? `${intentDetected} · ` : ''}{routePath}</div>}
      </div>

      <div className="talk-dock">
        {(cameraOn || capturedFrame) && (
          <div className="talk-camera">
            {cameraOn ? <video ref={videoRef} autoPlay playsInline muted /> : <img src={capturedFrame} alt="Captured frame" />}
            <canvas ref={canvasRef} hidden />
            <div className="talk-camera-actions">
              {cameraOn && <button type="button" onClick={captureFrame}>Snap</button>}
              {capturedFrame && <button type="button" onClick={() => setCapturedFrame('')}>Discard</button>}
              {cameraOn && <button type="button" onClick={stopCamera}>Close camera</button>}
            </div>
          </div>
        )}

        <div className="talk-quick">
          {QUICK.map((q) => <button type="button" key={q} disabled={busy} onClick={() => sendLive(q)}>{q}</button>)}
        </div>

        <div className="talk-controls">
          <button type="button" className={`talk-mic ${status}${listening ? ' on' : ''}`} onClick={toggleVoice}
            aria-label={listening ? 'Stop listening' : 'Talk to Atulya'}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11z" /></svg>
          </button>
          <div className="talk-status">{STATUS_TEXT[status] || status}</div>
        </div>

        <form className="talk-input" onSubmit={(event) => { event.preventDefault(); sendLive(); }}>
          <button type="button" className="icon" title={cameraOn ? 'Close camera' : 'Show Atulya something'}
            onClick={cameraOn ? stopCamera : startCamera}>
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M9 3 7.2 5H4a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-3.2L15 3H9zm3 5a5 5 0 1 1 0 10 5 5 0 0 1 0-10zm0 2a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"/></svg>
          </button>
          <input value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Message Atulya…" disabled={busy} />
          <button type="submit" className="primary" disabled={busy || !prompt.trim()}>Send</button>
          <button type="button" className="icon" title="Voice settings" onClick={() => setShowVoiceSettings((v) => !v)}>⚙</button>
        </form>

        {showVoiceSettings && (
          <div className="talk-settings">
            <label>Voice
              <select value={selectedVoice} onChange={(e) => setSelectedVoice(e.target.value)}>
                {voiceList.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
              </select>
            </label>
            <label>Listening
              <select value={sttEngine} onChange={(e) => setSttEngine(e.target.value)}>
                <option value="local">On this PC (private)</option>
                <option value="browser">Browser (cloud)</option>
              </select>
            </label>
            <label>Brain
              <select value={provider} onChange={(e) => setProvider(e.target.value)}>
                {providerOptions.map((item) => <option key={item.id} value={item.id} disabled={!item.available}>{item.name}</option>)}
              </select>
            </label>
            <label className="check"><input type="checkbox" checked={autoSpeak} onChange={(e) => setAutoSpeak(e.target.checked)} /> Speak replies</label>
            <label className="check"><input type="checkbox" checked={continuous} onChange={(e) => setContinuous(e.target.checked)} /> Hands-free (“Hey Atulya”)</label>
            <button type="button" onClick={() => { api.delete('/api/chat/history').catch(() => {}); setMessages([]); }}>Clear conversation</button>
          </div>
        )}
      </div>
    </div>
  );
}

function Chat({ bootstrap, toast }) {
  const providerOptions = bootstrap?.providers || [{ id: 'auto', name: 'Auto Provider', available: true }];
  const [provider, setProvider] = useState('auto');
  const [prompt, setPrompt] = useState('');
  const [messages, setMessages] = useState(() => loadCachedMessages(CHAT_CACHE_KEY, []));
  const [toolSteps, setToolSteps] = useState([]);
  const [maxContext, setMaxContext] = useState(10);
  const [pendingApproval, setPendingApproval] = useState(null);
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  useEffect(() => endRef.current?.scrollIntoView({ behavior: 'smooth' }), [messages]);

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
          <select value={provider} onChange={(e) => setProvider(e.target.value)}>
            {providerOptions.map((item) => (
              <option key={item.id} value={item.id}>
                {item.available ? 'Ready - ' : 'Off - '}{item.name}
              </option>
            ))}
          </select>
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

function ModelInspector({ bootstrap, toast }) {
  const checkpoints = bootstrap?.checkpoints || [];
  const [model, setModel] = useState('latest');
  const [info, setInfo] = useState(null);

  async function loadInfo(id = model) {
    try {
      const res = await api.post('/api/plasticity/check', { model_id: id });
      setInfo(res.model_info || {});
    } catch (err) {
      toast('error', err.message);
    }
  }

  useEffect(() => { loadInfo('latest'); }, []);
  const compression = info?.parameter_count && info?.active_parameter_count
    ? (info.parameter_count / info.active_parameter_count).toFixed(2)
    : '--';

  return (
    <section className="panel">
      <div className="panel-title">
        <h2>Model Inspector</h2>
        <select value={model} onChange={(e) => { setModel(e.target.value); loadInfo(e.target.value); }}>
          {checkpoints.map((item) => <option key={item.id} value={item.id}>{item.label || item.id}</option>)}
        </select>
      </div>
      <div className="metrics">
        <Metric label="Config" value={info?.config} />
        <Metric label="Params" value={info?.parameter_count?.toLocaleString?.()} />
        <Metric label="Active Params" value={info?.active_parameter_count?.toLocaleString?.()} />
        <Metric label="Compression" value={compression === '--' ? '--' : `${compression}x`} />
        <Metric label="Vocab" value={info?.vocab_size && info?.vocab_capacity ? `${info.vocab_size}/${info.vocab_capacity}` : '--'} />
        <Metric label="Cortex Entries" value={info?.cortex_entries ?? '--'} />
      </div>
      <div className="strand-grid">
        {(info?.layers || []).map((layer, idx) => (
          <div className="strand-row" key={`${layer.name}-${idx}`}>
            <span>{layer.name}</span>
            <strong>{layer.num_strands} strands</strong>
            <small>top-k {layer.top_k}</small>
          </div>
        ))}
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

const NAV = [
  { label: 'Assistant', items: [
    { id: 'live', label: 'Talk', icon: '◉' },
    { id: 'chat', label: 'Chat', icon: '✎' },
  ] },
  { label: 'Knowledge', items: [
    { id: 'galaxy', label: 'Knowledge map', icon: '✦' },
    { id: 'about', label: 'About you', icon: '☺' },
  ] },
  { label: 'Home', admin: true, items: [
    { id: 'routines', label: 'Routines', icon: '↻' },
    { id: 'senses', label: 'Senses', icon: '◎' },
  ] },
  { label: 'System', admin: true, items: [
    { id: 'reflexes', label: 'Brain & reflexes', icon: '⚡' },
    { id: 'dashboard', label: 'Dashboard', icon: '▦' },
    { id: 'model', label: 'Model', icon: '⬡' },
    { id: 'training', label: 'Training', icon: '⚙' },
    { id: 'users', label: 'Users', icon: '👥' },
  ] },
];
const FULL_BLEED = new Set(['live', 'galaxy']);

function App() {
  const [tab, setTab] = useState('live');
  const [menuOpen, setMenuOpen] = useState(false);
  const [bootstrap, setBootstrap] = useState(null);
  const [error, setError] = useState('');
  const [authenticated, setAuthenticated] = useState(Boolean(getToken()));
  const [toasts, setToasts] = useState([]);
  const [healthWarnings, setHealthWarnings] = useState([]);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem('atulya-theme') || 'dark'; } catch { return 'dark'; }
  });
  
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
    setTab('about');
    if (google === 'connected') toast('success', 'Google connected — Gmail and Calendar are ready.');
    else toast('error', "Google wasn't connected.");
  }, [authenticated]);

  async function load() {
    setError('');
    try {
      const boot = await api.get('/api/dashboard/bootstrap');
      setAuthenticated(true);
      setBootstrap({ ...boot, datasets: boot.datasets || [] });
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

  useEffect(() => {
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
    document.documentElement.className = theme === 'light' ? 'light' : '';
    try { localStorage.setItem('atulya-theme', theme); } catch {}
  }, [theme]);

  useEffect(() => {
    function handleKeyDown(event) {
      if (event.ctrlKey || event.metaKey) {
        switch (event.key) {
          case '1': event.preventDefault(); setTab('live'); break;
          case '2': event.preventDefault(); setTab('chat'); break;
          case '3': event.preventDefault(); setTab('galaxy'); break;
        }
      }
      if (event.key === '?' && !event.ctrlKey && !event.metaKey) {
        setShowShortcuts(prev => !prev);
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const content = useMemo(() => {
    if (tab === 'live') return <LiveMode bootstrap={bootstrap} toast={toast} />;
    if (tab === 'chat') return <Chat bootstrap={bootstrap} toast={toast} />;
    if (tab === 'about') return (
      <Suspense fallback={<div className="lazy-loading">Loading…</div>}>
        <AboutYou toast={toast} />
      </Suspense>
    );
    if (tab === 'galaxy') return (
      <Suspense fallback={<div className="lazy-loading">Mapping the stars…</div>}>
        <Galaxy />
      </Suspense>
    );
    if (!isAdmin) return <LiveMode bootstrap={bootstrap} toast={toast} />; // Fallback for normal users
    
    // Admin-only views
    if (tab === 'dashboard') return <Dashboard bootstrap={bootstrap} load={load} />;
    if (tab === 'model') return <ModelInspector bootstrap={bootstrap} toast={toast} />;
    if (tab === 'training') return <Training bootstrap={bootstrap} load={load} toast={toast} />;
    if (tab === 'users') return <UserManagement toast={toast} />;
    if (tab === 'reflexes') return (
      <Suspense fallback={<div className="lazy-loading">Loading Reflexes…</div>}>
        <Reflexes toast={toast} />
      </Suspense>
    );
    if (tab === 'routines') return (
      <Suspense fallback={<div className="lazy-loading">Loading Routines…</div>}>
        <Routines toast={toast} />
      </Suspense>
    );
    if (tab === 'senses') return (
      <Suspense fallback={<div className="lazy-loading">Loading Senses…</div>}>
        <Senses toast={toast} />
      </Suspense>
    );
    return <Dashboard bootstrap={bootstrap} load={load} />;
  }, [tab, bootstrap, isAdmin]);

  async function handleLogout() {
    try {
      await api.post('/api/auth/logout').catch(() => {});
    } finally {
      clearToken();
      setAuthenticated(false);
      setMenuOpen(false);
      setTab('live');
    }
  }

  if (!authenticated) {
    return <Login onLogin={() => { setAuthenticated(true); load().catch((err) => setError(err.message)); }} />;
  }

  return (
    <main className={`shell${menuOpen ? ' menu-open' : ''}`}>
      <header className="mobile-bar">
        <button type="button" className="icon" aria-label="Menu" onClick={() => setMenuOpen((o) => !o)}>☰</button>
        <strong>{NAV.flatMap((g) => g.items).find((i) => i.id === tab)?.label || 'Atulya'}</strong>
      </header>
      <nav className="sidebar" aria-label="Main">
        <div className="brand"><span className="brand-mark" />Atulya</div>
        {NAV.filter((g) => !g.admin || isAdmin).map((group) => (
          <div className="nav-group" key={group.label}>
            <div className="nav-label">{group.label}</div>
            {group.items.map((item) => (
              <button type="button" key={item.id} className={tab === item.id ? 'active' : ''}
                onClick={() => { setTab(item.id); setMenuOpen(false); }}>
                <span className="nav-icon" aria-hidden="true">{item.icon}</span>{item.label}
              </button>
            ))}
          </div>
        ))}
        <div className="sidebar-foot">
          <div className="who">
            <strong>{currentUser?.display_name || currentUser?.username}</strong>
            <small>{currentUser?.role}</small>
          </div>
          <button type="button" className="icon" title="Theme" onClick={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}>{theme === 'dark' ? '☀' : '☾'}</button>
          <button type="button" className="icon" title="Sign out" onClick={handleLogout}>⏻</button>
        </div>
      </nav>
      {menuOpen && <div className="scrim" onClick={() => setMenuOpen(false)} />}

      <section className={`content${FULL_BLEED.has(tab) ? ' full' : ''}`}>
        {error && <div className="alert">{error}</div>}
        {healthWarnings.filter(w => w.severity !== 'low').map((w, i) => (
          <div key={i} className="alert" style={{borderColor: w.severity === 'high' ? 'var(--bad)' : 'var(--warn)'}}>
            {w.message}
          </div>
        ))}
        {content}
      </section>

      {showShortcuts && (
        <div className="modal-backdrop" onClick={() => setShowShortcuts(false)}>
          <div className="modal-card" onClick={e => e.stopPropagation()}>
            <h2>Keyboard Shortcuts</h2>
            <div className="table">
              <div className="row"><span>Ctrl+1</span><span>Talk</span></div>
              <div className="row"><span>Ctrl+2</span><span>Chat</span></div>
              <div className="row"><span>Ctrl+3</span><span>Knowledge</span></div>
              <div className="row"><span>?</span><span>Toggle this menu</span></div>
            </div>
            <button onClick={() => setShowShortcuts(false)}>Close</button>
          </div>
        </div>
      )}

      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((item) => (
          <div className={`toast ${item.type}`} key={item.id}>
            {item.title && <strong className="toast-title">{item.title}</strong>}
            {item.message}
          </div>
        ))}
      </div>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
