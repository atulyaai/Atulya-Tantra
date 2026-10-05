const TOKEN_KEY = 'atulya-dashboard-token';
const LEGACY_TOKEN_KEY = 'ai-dashboard-token';
const SERVER_URL_KEY = 'atulya-server-url';
const DEFAULT_SERVER_URL = 'https://atulya.atulvij.com';

export function getServerUrl() {
  try { return (localStorage.getItem(SERVER_URL_KEY) || DEFAULT_SERVER_URL).replace(/\/$/, ''); }
  catch { return DEFAULT_SERVER_URL; }
}

export function setServerUrl(value) {
  const parsed = new URL(value);
  if (!['http:', 'https:'].includes(parsed.protocol) || parsed.pathname !== '/' || parsed.search || parsed.hash) {
    throw new Error('Enter a server address such as https://atulya.atulvij.com');
  }
  try {
    const previous = localStorage.getItem(SERVER_URL_KEY);
    if (previous && previous.replace(/\/$/, '') !== parsed.origin) clearToken();
    localStorage.setItem(SERVER_URL_KEY, parsed.origin);
  } catch {}
  return parsed.origin;
}

export function apiUrl(path) {
  return new URL(path, `${getServerUrl()}/`).toString();
}
export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || localStorage.getItem(LEGACY_TOKEN_KEY) || '';
  } catch {
    return '';
  }
}

export function getUser() {
  try {
    const raw = localStorage.getItem('atulya-user');
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setUser(user) {
  try {
    localStorage.setItem('atulya-user', JSON.stringify(user));
  } catch {}
}

export function setToken(token) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(LEGACY_TOKEN_KEY, token);
  } catch {}
}

export function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(LEGACY_TOKEN_KEY);
    localStorage.removeItem('atulya-user');
  } catch {}
}

async function request(path, options = {}) {
  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
    headers['X-Atulya-Token'] = token;
  }
  const response = await fetch(apiUrl(path), { ...options, headers });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail || body.error || message;
    } catch {}
    throw new Error(message);
  }
  const type = response.headers.get('content-type') || '';
  return type.includes('json') ? response.json() : response.text();
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body: JSON.stringify(body || {}) }),
  delete: (path) => request(path, { method: 'DELETE' }),
  async getVoices() {
    return this.get('/api/voice/voices');
  },
  async tts(text, voice) {
    return this.post('/api/voice/tts', { text, voice });
  },
  async stt(blob, language = 'en') {
    // Local, private speech-to-text via the backend faster-whisper endpoint.
    // Works in any browser (unlike webkitSpeechRecognition) and stays offline.
    const token = getToken();
    const form = new FormData();
    form.append('file', blob, 'speech.webm');
    form.append('language', language);
    const headers = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
      headers['X-Atulya-Token'] = token;
    }
    const res = await fetch(apiUrl('/api/voice/stt'), { method: 'POST', headers, body: form });
    if (!res.ok) throw new Error(`Local transcription failed (${res.status})`);
    return res.json();
  },
  async voiceChat(prompt, voice, model_id) {
    return this.post('/api/voice/chat', { prompt, voice, model_id });
  },
  streamChat(payload, onToken, onDone, onError, onTool) {
    const token = getToken();
    const headers = { 'Content-Type': 'application/json' };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
      headers['X-Atulya-Token'] = token;
    }
    fetch(apiUrl('/api/chat/stream'), {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    })
      .then(async (response) => {
        if (!response.ok) throw new Error((await response.text()) || 'Chat stream failed');
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finished = false;
        let errored = false;
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const events = buffer.split('\n\n');
          buffer = events.pop() || '';
          for (const event of events) {
            const line = event.split('\n').find((item) => item.startsWith('data: '));
            if (!line) continue;
            let data;
            try {
              data = JSON.parse(line.slice(6));
            } catch {
              continue;
            }
            if (data.error) {
              errored = true;
              onError(new Error(data.error));
            }
            else if (data.done) {
              finished = true;
              onDone(data);
            }
            else if (data.tool) {
              if (onTool) onTool(data.tool);
            }
            else if (data.token !== undefined) onToken(data.token);
          }
        }
        if (!finished && !errored) onDone({});
      })
      .catch(onError);
  },
  connectWebSocket(onMessage) {
    // Live server push (notifications, reminders, alerts). The server requires
    // the session token as a query param — browsers can't set WebSocket headers.
    // Returns a stop() that also cancels any pending reconnect.
    const server = new URL(getServerUrl());
    const protocol = server.protocol === 'https:' ? 'wss:' : 'ws:';
    let ws = null;
    let reconnectTimer = null;
    let stopped = false;
    let attempts = 0;

    const open = () => {
      const token = getToken();
      if (stopped || !token) return;
      ws = new WebSocket(`${protocol}//${server.host}/api/ws?token=${encodeURIComponent(token)}`);
      ws.onopen = () => {
        attempts = 0;
        ws.send(JSON.stringify({ type: 'ping' }));
      };
      ws.onmessage = (event) => {
        try { onMessage(JSON.parse(event.data)); } catch {}
      };
      ws.onclose = () => {
        if (stopped) return;
        attempts += 1;
        const delay = Math.min(30000, 1000 * 2 ** Math.min(attempts, 5));
        reconnectTimer = setTimeout(open, delay);
      };
    };
    open();
    return () => {
      stopped = true;
      clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  },
  async subscribePush() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      return { ok: false, error: 'Push not supported' };
    }
    try {
      const registration = await navigator.serviceWorker.ready;
      let sub = await registration.pushManager.getSubscription();
      if (!sub) {
        sub = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: null,
        });
      }
      return this.post('/api/notifications/subscribe', { subscription: sub.toJSON() });
    } catch (err) {
      return { ok: false, error: err.message };
    }
  },
};

// ── Voice volume ──────────────────────────────────────────────────────────
// Browsers cap an <audio> element at 100%. Routing it through a gain node lets
// Atulya be louder (up to 300%); a compressor keeps loud peaks from crackling.
const BOOST_KEY = 'atulya-volume-boost';
let boostCtx = null;

export function getBoost() {
  try {
    const value = parseFloat(localStorage.getItem(BOOST_KEY) || '');
    return value >= 1 && value <= 3 ? value : 2.5;
  } catch {
    return 2.5;
  }
}

export function setBoost(value) {
  try { localStorage.setItem(BOOST_KEY, String(value)); } catch {}
}

// Plays `audio` louder. Returns an AnalyserNode (unboosted level) or null if Web Audio is unavailable.
export function boostAudio(audio, ctx) {
  try {
    boostCtx = ctx || boostCtx || new (window.AudioContext || window.webkitAudioContext)();
    if (boostCtx.state === 'suspended') boostCtx.resume().catch(() => {});
    const source = boostCtx.createMediaElementSource(audio);
    const analyser = boostCtx.createAnalyser();
    analyser.fftSize = 256;
    const gain = boostCtx.createGain();
    gain.gain.value = getBoost();
    const limiter = boostCtx.createDynamicsCompressor();
    limiter.threshold.value = -14;
    limiter.knee.value = 12;
    limiter.ratio.value = 12;
    limiter.attack.value = 0.003;
    limiter.release.value = 0.15;
    source.connect(analyser);
    source.connect(gain);
    gain.connect(limiter);
    limiter.connect(boostCtx.destination);
    return analyser;
  } catch {
    return null;
  }
}
