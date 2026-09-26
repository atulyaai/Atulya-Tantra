const TOKEN_KEY = 'atulya-dashboard-token';
const LEGACY_TOKEN_KEY = 'ai-dashboard-token';

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
  const response = await fetch(path, { ...options, headers });
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
    const res = await fetch('/api/voice/stt', { method: 'POST', headers, body: form });
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
    fetch('/api/chat/stream', {
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
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    let ws = null;
    let reconnectTimer = null;
    let stopped = false;
    let attempts = 0;

    const open = () => {
      const token = getToken();
      if (stopped || !token) return;
      ws = new WebSocket(`${protocol}//${window.location.host}/api/ws?token=${encodeURIComponent(token)}`);
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
