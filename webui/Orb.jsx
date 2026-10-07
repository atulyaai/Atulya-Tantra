import React, { useEffect, useRef, useState } from 'react';
import { api, boostAudio, getBoost, setBoost } from './api.js';
import { createWebcam, detectCameras, explainCameraError } from './webcam.js';

// The home screen: one glowing orb you talk to, Jarvis style. It wakes on
// "Hey Atulya" (or "Hi / Hello / Listen Atulya", or just "Atulya"), ripples to
// your voice, spins while thinking and pulses with its own voice. Everything
// else in the app sits behind the menu button.

// Whisper and browsers spell the name many ways: Atulya, Athulya, Atulia, a tulya…
const NAME = 'a\\s?th?(?:u|oo)l+(?:i|y|iy|ee)?a';
const WAKE_RE = new RegExp(`(?:^|[^a-z])${NAME}(?:[^a-z]|$)|अतुल्य`, 'i');
const WAKE_LEAD_RE = new RegExp(`^[\\s,.!?-]*(?:(?:hey|hi|hello|ok|okay|listen|suno)[\\s,.!?-]*)?(?:${NAME}|अतुल्या?)[\\s,.!?-]*(?:(?:listen|suno)[\\s,.!?-]*)?`, 'i');
const FOLLOW_UP_MS = 8000; // after Atulya speaks, answer without the wake word
const SETTINGS_KEY = 'atulya-orb-settings-v2';

const spoken = (t) => String(t || '').replace(/[\p{Extended_Pictographic}\uFE0E\uFE0F\u200D\u20E3]/gu, '').replace(/\s{2,}/g, ' ').trim();

const SUGGESTIONS = ['What can you do?', 'Give me my morning briefing', 'Play some music', 'Show my routines'];

function loadSettings() {
  // Keep recognition and speech on the device by default. Server Whisper is an explicit fallback.
  const defaults = { userGender: 'male', handsFree: false, engine: 'browser', serverTts: false };
  try {
    return { ...defaults, ...(JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}')) };
  } catch {
    return defaults;
  }
}

function hasWakeWord(text) {
  return WAKE_RE.test(` ${String(text || '').toLowerCase()} `);
}

function stripWake(text) {
  return String(text || '').replace(WAKE_LEAD_RE, '').trim();
}

const COLORS = {
  idle: [79, 209, 255],
  listening: [90, 230, 255],
  thinking: [150, 130, 255],
  speaking: [120, 240, 255],
  error: [255, 110, 110],
};

function AudioWaveform({ levelRef, stateRef }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return undefined;
    let raf = 0;
    let t = 0;
    const bars = 112;
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const { width, height } = canvas.getBoundingClientRect();
      canvas.width = Math.max(1, Math.round(width * dpr));
      canvas.height = Math.max(1, Math.round(height * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    window.addEventListener('resize', resize);

    function frame() {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      const mid = h * 0.52;
      const state = stateRef.current;
      const live = Math.max(0, Math.min(1, levelRef.current || 0));
      t += reduced ? 0 : 0.035;
      ctx.clearRect(0, 0, w, h);
      ctx.beginPath();
      ctx.moveTo(0, mid);
      ctx.lineTo(w, mid);
      ctx.strokeStyle = 'rgba(120,220,255,.32)';
      ctx.lineWidth = 1;
      ctx.stroke();
      const gap = 2;
      const step = w / bars;
      const barW = Math.max(1, step - gap);
      for (let i = 0; i < bars; i += 1) {
        const x = i * step + gap / 2;
        const fromCenter = Math.abs((i / (bars - 1)) * 2 - 1);
        const envelope = Math.pow(Math.max(0, 1 - fromCenter), 1.25);
        const voice = live * (0.12 + 0.88 * Math.abs(Math.sin(i * 1.74 + t * (state === 'thinking' ? 1.6 : 1))));
        const idle = (state === 'idle' || state === 'listening') ? 0.025 + 0.04 * Math.abs(Math.sin(i * 0.5 + t)) : 0.012;
        const amp = Math.min(h * 0.46, h * envelope * Math.max(idle, voice));
        const orange = Math.sin(i * 0.21 + t * 0.55) > 0.82;
        const grad = ctx.createLinearGradient(0, mid - amp, 0, mid + amp);
        grad.addColorStop(0, orange ? 'rgba(255,164,70,.32)' : 'rgba(62,197,255,.28)');
        grad.addColorStop(0.5, orange ? '#ffc06b' : '#9ff4ff');
        grad.addColorStop(1, orange ? 'rgba(255,164,70,.32)' : 'rgba(62,197,255,.28)');
        ctx.fillStyle = grad;
        ctx.shadowColor = orange ? '#ff9c42' : '#31cfff';
        ctx.shadowBlur = state === 'speaking' || state === 'listening' ? 9 : 5;
        ctx.fillRect(x, mid - amp, barW, Math.max(1, amp * 2));
      }
      ctx.shadowBlur = 0;
      if (!reduced) raf = requestAnimationFrame(frame);
    }
    frame();
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', resize); };
  }, [levelRef, stateRef]);

  return <div className="holo-wave" aria-label="Live audio waveform">
    <span className="holo-wave-bracket left" aria-hidden="true" />
    <canvas ref={canvasRef} />
    <span className="holo-wave-bracket right" aria-hidden="true" />
  </div>;
}

function formatPercent(value) {
  return Number.isFinite(Number(value)) ? `${Math.round(Number(value))}%` : '—';
}

export function Orb({ onMenu, toast, onCommand }) {
  const [settings, setSettings] = useState(loadSettings);
  const [state, setState] = useState('idle'); // idle | listening | thinking | speaking | error
  const [started, setStarted] = useState(false);
  const [heard, setHeard] = useState('');
  const [said, setSaid] = useState('');
  const captionsRef = useRef(null);
  const webcamRef = useRef(null);
  const previewRef = useRef(null);
  const [camOn, setCamOn] = useState(false);
  const [camPresence, setCamPresence] = useState(false);
  const [camError, setCamError] = useState('');
  const [cams, setCams] = useState({ state: 'prompt', devices: [] });
  const [camId, setCamId] = useState('');
  const [hint, setHint] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  const [typed, setTyped] = useState('');
  const [boost, setBoostState] = useState(getBoost());
  const [telemetry, setTelemetry] = useState(null);
  const [telemetryState, setTelemetryState] = useState('loading');
  const [telemetryHistory, setTelemetryHistory] = useState([]);
  const [apiRtt, setApiRtt] = useState(null);
  const [hudClock, setHudClock] = useState(() => new Date());

  const canvasRef = useRef(null);
  const holoBoxRef = useRef(null);
  const holoRef = useRef(null); // the particle humanoid, once running
  const [holo, setHolo] = useState('loading'); // loading | ready | none (no WebGL: the orb shows)
  const [typing, setTyping] = useState(false); // the text box is hidden until asked for
  const [capVisible, setCapVisible] = useState(true);
  const audioCtxRef = useRef(null);
  const analyserRef = useRef(null); // whichever source is live: mic or voice
  const micRef = useRef(null); // { stream, source, analyser }
  const levelRef = useRef(0);
  const stateRef = useRef('idle');
  const settingsRef = useRef(settings);
  const followUntilRef = useRef(0);
  const historyRef = useRef([]);
  const audioRef = useRef(null);
  const loopRef = useRef({ gen: 0, active: 0, stop: null }); // active = id of the running loop, 0 = stopped
  const busyRef = useRef(false);

  useEffect(() => { stateRef.current = state; }, [state]);

  useEffect(() => {
    let alive = true;
    const refresh = async () => {
      try {
        const requestStart = performance.now();
        const result = await api.get('/api/telemetry');
        if (!alive) return;
        setApiRtt(Math.round(performance.now() - requestStart));
        setTelemetry(result);
        const cpu = Number(result.system?.cpu_pct);
        const ram = Number(result.system?.ram_pct);
        if (Number.isFinite(cpu) && Number.isFinite(ram)) {
          setTelemetryHistory((history) => [...history, { cpu, ram }].slice(-24));
        }
        setTelemetryState('online');
      } catch (err) {
        if (!alive) return;
        const message = String(err?.message || '');
        setTelemetryState(/401|403|unauthorized|forbidden/i.test(message) ? 'restricted' : 'offline');
      }
    };
    refresh();
    const timerId = window.setInterval(refresh, 15000);
    return () => { alive = false; window.clearInterval(timerId); };
  }, []);
  useEffect(() => {
    const timerId = window.setInterval(() => setHudClock(new Date()), 1000);
    return () => window.clearInterval(timerId);
  }, []);
  useEffect(() => {
    settingsRef.current = settings;
    try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings)); } catch {}
  }, [settings]);

  // ── Drawing ──────────────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    let raf = 0;
    let t = 0;
    const freq = new Uint8Array(128);
    const particles = Array.from({ length: 70 }, () => ({
      a: Math.random() * Math.PI * 2, r: 1.25 + Math.random() * 0.9, s: 0.002 + Math.random() * 0.006, z: Math.random(),
    }));
    const color = [...COLORS.idle];

    function resize() {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = canvas.clientWidth * dpr;
      canvas.height = canvas.clientHeight * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    window.addEventListener('resize', resize);

    function frame() {
      t += 1;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      const cx = w / 2;
      const cy = h * 0.44;
      const R = Math.min(w, h) * 0.17;
      const st = stateRef.current;

      // Loudness of whatever is live (your voice while listening, Atulya's while speaking).
      let level = 0;
      const analyser = analyserRef.current;
      const live = analyser && (st === 'listening' || st === 'speaking');
      if (live) {
        analyser.getByteFrequencyData(freq);
        let sum = 0;
        for (let i = 2; i < 48; i += 1) sum += freq[i];
        level = Math.min(1, sum / (46 * 160));
      } else {
        freq.fill(0);
      }
      if (st === 'speaking' && !live) level = 0.35 + 0.25 * Math.sin(t / 4); // browser voice: no audio graph
      levelRef.current += (level - levelRef.current) * 0.25;
      const lv = levelRef.current;
      const breathe = 0.5 + 0.5 * Math.sin(t / 50);
      if (holoRef.current) { raf = requestAnimationFrame(frame); return; } // the hologram draws instead

      const target = COLORS[st] || COLORS.idle;
      for (let i = 0; i < 3; i += 1) color[i] += (target[i] - color[i]) * 0.08;
      const rgb = (a) => `rgba(${color[0] | 0},${color[1] | 0},${color[2] | 0},${a})`;

      ctx.clearRect(0, 0, w, h);

      // Halo
      const haloR = R * (2.4 + lv * 0.8 + breathe * 0.15);
      const halo = ctx.createRadialGradient(cx, cy, R * 0.4, cx, cy, haloR);
      halo.addColorStop(0, rgb(0.28 + lv * 0.3));
      halo.addColorStop(0.45, rgb(0.08 + lv * 0.1));
      halo.addColorStop(1, rgb(0));
      ctx.fillStyle = halo;
      ctx.beginPath(); ctx.arc(cx, cy, haloR, 0, Math.PI * 2); ctx.fill();

      // Orbiting particles
      const spin = st === 'thinking' ? 4 : 1;
      particles.forEach((p) => {
        p.a += p.s * spin;
        const pr = R * (p.r + lv * 0.3);
        const x = cx + Math.cos(p.a) * pr;
        const y = cy + Math.sin(p.a) * pr * 0.92;
        ctx.fillStyle = rgb(0.25 + p.z * 0.5);
        ctx.beginPath(); ctx.arc(x, y, 0.8 + p.z * 1.6, 0, Math.PI * 2); ctx.fill();
      });

      // Rotating arc segments (the "reactor" rings)
      const rings = [
        { r: 1.32, n: 3, len: 0.9, speed: 0.006, width: 2 },
        { r: 1.5, n: 5, len: 0.45, speed: -0.004, width: 1.5 },
        { r: 1.68, n: 2, len: 1.6, speed: 0.0025, width: 1 },
      ];
      rings.forEach((ring, idx) => {
        const rot = t * ring.speed * (st === 'thinking' ? 5 : 1) + idx;
        ctx.strokeStyle = rgb(0.55 - idx * 0.12 + lv * 0.3);
        ctx.lineWidth = ring.width;
        for (let k = 0; k < ring.n; k += 1) {
          const start = rot + (k * Math.PI * 2) / ring.n;
          ctx.beginPath(); ctx.arc(cx, cy, R * (ring.r + lv * 0.12), start, start + ring.len); ctx.stroke();
        }
      });

      // Voice ring: ripples with the sound
      ctx.beginPath();
      const pts = 96;
      for (let i = 0; i <= pts; i += 1) {
        const a = (i / pts) * Math.PI * 2;
        const bin = freq[(i % (pts / 2)) + 2] / 255;
        const wobble = Math.sin(a * 6 + t / 12) * 0.015 * (1 + breathe);
        const rr = R * (1.1 + wobble + bin * 0.35 * (live ? 1 : 0) + lv * 0.08);
        const x = cx + Math.cos(a) * rr;
        const y = cy + Math.sin(a) * rr;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.strokeStyle = rgb(0.85);
      ctx.lineWidth = 2;
      ctx.shadowColor = rgb(1);
      ctx.shadowBlur = 18 + lv * 30;
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Core
      const coreR = R * (0.62 + lv * 0.28 + breathe * 0.04);
      const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR);
      core.addColorStop(0, 'rgba(255,255,255,0.95)');
      core.addColorStop(0.25, rgb(0.9));
      core.addColorStop(0.7, rgb(0.25));
      core.addColorStop(1, rgb(0));
      ctx.fillStyle = core;
      ctx.beginPath(); ctx.arc(cx, cy, coreR, 0, Math.PI * 2); ctx.fill();

      raf = requestAnimationFrame(frame);
    }
    raf = requestAnimationFrame(frame);
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', resize); };
  }, []);

  // ── Audio plumbing ───────────────────────────────────────────────────────
  function audioCtx() {
    if (!audioCtxRef.current) audioCtxRef.current = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtxRef.current.state === 'suspended') audioCtxRef.current.resume().catch(() => {});
    return audioCtxRef.current;
  }

  async function mic() {
    if (micRef.current) return micRef.current;
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    const ctx = audioCtx();
    const source = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    micRef.current = { stream, analyser };
    return micRef.current;
  }

  function voiceName() {
    // A female voice for a male user and a male voice for a female user.
    return settingsRef.current.userGender === 'female' ? 'en_male' : 'en_female';
  }

  // Record one utterance from the open mic: starts listening at once, stops
  // ~0.9 s after you stop talking. Resolves to a Blob, or null if nobody spoke.
  function recordUtterance({ maxWaitMs = 8000 } = {}) {
    return new Promise((resolve) => {
      const { stream, analyser } = micRef.current;
      const chunks = [];
      let recorder;
      try { recorder = new MediaRecorder(stream); } catch { resolve(null); return; }
      const buf = new Uint8Array(analyser.fftSize);
      const started = Date.now();
      let heardAt = 0;
      let quietSince = 0;
      let done = false;
      recorder.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
      recorder.onstop = () => resolve(heardAt ? new Blob(chunks, { type: recorder.mimeType || 'audio/webm' }) : null);
      const finish = () => {
        if (done) return;
        done = true;
        clearInterval(tick);
        loopRef.current.stop = null;
        if (recorder.state !== 'inactive') recorder.stop();
      };
      const tick = setInterval(() => {
        analyser.getByteTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i += 1) { const v = (buf[i] - 128) / 128; sum += v * v; }
        const loud = Math.sqrt(sum / buf.length) > 0.035;
        const now = Date.now();
        if (loud) { if (!heardAt) heardAt = now; quietSince = 0; } else if (!quietSince) quietSince = now;
        const silentFor = quietSince ? now - quietSince : 0;
        if ((heardAt && silentFor > 900) || (!heardAt && now - started > maxWaitMs) || now - started > 15000) finish();
      }, 60);
      loopRef.current.stop = finish;
      recorder.start();
    });
  }

  // Browser speech recognition (Chrome/Edge): fast, but sends audio to the browser maker.
  function recognizeInBrowser() {
    return new Promise((resolve, reject) => {
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) { reject(new Error('This browser has no speech recognition. Choose "Atulya server Whisper" in Settings, or type your message.')); return; }
      const rec = new SR();
      rec.lang = 'en-IN';
      rec.interimResults = false;
      rec.continuous = false;
      let text = '';
      rec.onresult = (e) => { text = Array.from(e.results).map((r) => r[0].transcript).join(' '); };
      rec.onerror = (e) => (e.error === 'no-speech' || e.error === 'aborted' ? resolve('') : reject(new Error(e.error)));
      rec.onend = () => { loopRef.current.stop = null; resolve(text); };
      loopRef.current.stop = () => { try { rec.abort(); } catch {} };
      rec.start();
    });
  }

  async function listenOnce() {
    if (settingsRef.current.engine === 'browser') return recognizeInBrowser();
    const blob = await recordUtterance();
    if (!blob || !loopRef.current.active) return '';
    const res = await api.stt(blob, 'auto');
    if (res.error && !res.text) {
      throw new Error(/module named/i.test(res.error)
        ? 'Server Whisper is not installed. Install the server voice extra, or set Listening to Browser in \u2699.'
        : res.error);
    }
    return String(res.text || '').trim();
  }

  function stopVoice() {
    try { window.speechSynthesis?.cancel(); } catch {}
    if (audioRef.current) {
      try { audioRef.current.pause(); } catch {}
      audioRef.current = null;
    }
  }

  function speak(text, audioBase64) {
    stopVoice();
    return new Promise((resolve) => {
      const done = () => {
        if (micRef.current) analyserRef.current = micRef.current.analyser;
        followUntilRef.current = Date.now() + FOLLOW_UP_MS;
        resolve();
      };
      setState('speaking');
      if (audioBase64) {
        const audio = new Audio(`data:audio/mp3;base64,${audioBase64}`);
        audioRef.current = audio;
        // Browsers suspend AudioContext until a user gesture; resume it or
        // the analyser sees silence and audio.play() may be rejected too.
        try { const c = audioCtx(); if (c.state === 'suspended') c.resume(); } catch { /* no analyser, still play */ }
        analyserRef.current = boostAudio(audio, audioCtx());
        audio.onended = done;
        audio.onerror = done;
        const p = audio.play();
        if (p && p.catch) {
          p.catch(() => {
            // Autoplay blocked: wait for the first user gesture, then play.
            const unlock = () => {
              audio.play().then(done).catch(() => speakInBrowser(text).then(done));
              window.removeEventListener('pointerdown', unlock);
              window.removeEventListener('keydown', unlock);
            };
            window.addEventListener('pointerdown', unlock, { once: true });
            window.addEventListener('keydown', unlock, { once: true });
            // Safety: if no gesture comes, fall back to browser TTS.
            setTimeout(() => { if (audio.paused) { speakInBrowser(text).then(done); } }, 1200);
          });
        }
        return;
      }
      analyserRef.current = null;
      speakInBrowser(text).then(done);
    });
  }

  function speakInBrowser(text) {
    return new Promise((resolve) => {
      if (!('speechSynthesis' in window) || !text) { resolve(); return; }
      const u = new SpeechSynthesisUtterance(spoken(text));
      const hindi = /[ऀ-ॿ]/.test(text);
      u.lang = hindi ? 'hi-IN' : 'en-GB';
      // Some browsers never fire onend (no voices installed): don't hang on it.
      const timer = setTimeout(resolve, 2500 + text.split(/\s+/).length * 450);
      u.onend = () => { resolve(); };
      u.onerror = u.onend;
      window.speechSynthesis.speak(u);
    });
  }

  // ── One turn: send what was said, speak the answer ──────────────────────
  async function ask(text) {
    if (!text || busyRef.current) return;
    const local = onCommand?.(text); // "show routines", "close" … handled on screen, not by the brain
    if (local) { setHeard(text); setSaid(local); setHint(''); await speak(local); return; }
    busyRef.current = true;
    setHeard(text);
    setSaid('');
    setHint('');
    setState('thinking');
    try {
      // "What do you see?" with the webcam on: send one picture along with the question.
      const wantsLook = /\b(what (?:do|can) you see|what can you see|what do you see|look at (?:this|me)|what is this|what am i holding|can you see|describe (?:this|what'?s in front of you)|what is in front of you)\b/i.test(text);
      const image = wantsLook && webcamRef.current?.active ? webcamRef.current.snapshot() : null;
      const res = await api.post('/api/voice/chat', {
        prompt: text,
        voice: voiceName(),
        tts: Boolean(settingsRef.current.serverTts),
        history: historyRef.current.slice(-8),
        ...(image ? { image } : {}),
      });
      api.get('/api/mood').then((m) => holoRef.current?.setMood(m)).catch(() => {});
      const reply = String(res.response_text || res.error || '').trim();
      historyRef.current.push({ role: 'user', content: text }, { role: 'assistant', content: reply });
      setSaid(reply);
      await speak(reply, res.audio_base64);
    } catch (err) {
      const offline = /Failed to fetch|NetworkError|Load failed/i.test(err.message || '');
      const msg = offline ? "I can't reach the Atulya server. Is start.bat still running?" : `Sorry, that failed: ${err.message}`;
      setSaid(msg);
      setState('error');
      await speakInBrowser(msg);
    } finally {
      busyRef.current = false;
      setState(loopRef.current.active ? 'listening' : 'idle');
    }
  }

  // ── Hands-free loop: wait for the wake word, then answer ───────────────
  async function runLoop() {
    if (loopRef.current.active) return;
    loopRef.current.gen += 1;
    const me = loopRef.current.gen;
    loopRef.current.active = me;
    const alive = () => loopRef.current.active === me;
    let failures = 0;
    while (alive()) {
      if (busyRef.current) { await new Promise((r) => setTimeout(r, 200)); continue; }
      analyserRef.current = micRef.current?.analyser || null;
      setState('listening');
      let text = '';
      try {
        text = await listenOnce();
        failures = 0;
      } catch (err) {
        failures += 1;
        setHint(err.message || 'Listening failed');
        if (failures >= 3) { loopRef.current.active = 0; toast?.('error', err.message || 'Listening stopped'); break; }
        await new Promise((r) => setTimeout(r, 1500));
        continue;
      }
      if (!alive() || !text) continue;
      const following = Date.now() < followUntilRef.current;
      const awake = hasWakeWord(text);
      if (!following && !awake && settingsRef.current.handsFree) {
        setHint(`Heard “${text}”. Say “Hey Atulya” first.`);
        continue;
      }
      const command = awake ? stripWake(text) : text;
      if (!command) {
        // Just the wake word: answer, then take the next sentence without it.
        setHeard(text);
        setSaid('Yes?');
        await speak('Yes?');
        continue;
      }
      await ask(command);
    }
    if (!loopRef.current.active) setState('idle');
  }

  function stopLoop() {
    loopRef.current.active = 0;
    loopRef.current.stop?.();
  }

  async function start() {
    try {
      audioCtx();
      if (settingsRef.current.engine === 'local') await mic();
      setStarted(true);
      setHint('');
      runLoop();
    } catch (err) {
      setHint('Microphone blocked. Allow the mic for this page, then tap the orb.');
      toast?.('error', 'Microphone access denied');
    }
  }

  // Tap the orb: start, interrupt Atulya, or talk right now without the wake word.
  function tapOrb() {
    if (!started) { start(); return; }
    if (stateRef.current === 'speaking') { stopVoice(); followUntilRef.current = Date.now() + FOLLOW_UP_MS; return; }
    followUntilRef.current = Date.now() + FOLLOW_UP_MS;
    if (!loopRef.current.active) runLoop();
    setHint('Go ahead, I’m listening.');
  }

  useEffect(() => {
    function onKey(e) {
      if (e.code !== 'Space' || e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
      e.preventDefault();
      tapOrb();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  // Find cameras on load and whenever one is plugged in. If the browser already allows the camera it
  // starts by itself (unless you switched it off). The first time, it asks once on your first tap.
  useEffect(() => {
    let alive = true;
    const refresh = async () => {
      const found = await detectCameras();
      if (!alive) return;
      setCams(found);
      if (found.state === 'granted' && found.devices.length && !webcamRef.current?.active && localStorage.getItem('atulya-cam') !== 'off') {
        toggleWebcam(true, found.devices[0].id);
      }
    };
    refresh();
    const askOnce = async () => {
      let asked = '';
      try { asked = localStorage.getItem('atulya-cam') || ''; } catch { /* private mode */ }
      if (asked) return; // already on, off, or declined: never ask again by itself
      const found = await detectCameras();
      if (found.state === 'prompt' && found.devices.length && !webcamRef.current?.active) toggleWebcam(true, found.devices[0].id);
    };
    window.addEventListener('pointerdown', askOnce, { once: true });
    navigator.mediaDevices?.addEventListener?.('devicechange', refresh);
    return () => {
      alive = false;
      window.removeEventListener('pointerdown', askOnce);
      navigator.mediaDevices?.removeEventListener?.('devicechange', refresh);
    };
  }, []);

  const camVideoRef = useRef(null);

  async function toggleWebcam(on, deviceId) {
    setCamError('');
    if (!webcamRef.current) {
      webcamRef.current = createWebcam({ onPresence: setCamPresence, onGaze: (x, y) => holoRef.current?.setGaze(x, y), onLight: (l) => holoRef.current?.setAmbient(l) });
    }
    try {
      if (on) {
        const video = await webcamRef.current.start(deviceId || camId || undefined);
        setCamOn(true);
        try { localStorage.setItem('atulya-cam', 'on'); } catch { /* private mode */ }
        detectCameras().then(setCams); // after permission the real names appear
        camVideoRef.current = video; // the preview box mounts after this render; an effect below fills it
      } else {
        webcamRef.current.stop();
        setCamOn(false);
        try { localStorage.setItem('atulya-cam', 'off'); } catch { /* private mode */ }
      }
    } catch (err) {
      setCamOn(false);
      setCamError(explainCameraError(err));
      try { if (err?.name === 'NotAllowedError') localStorage.setItem('atulya-cam', 'off'); } catch { /* private mode */ }
    }
  }
  useEffect(() => () => webcamRef.current?.stop(), []);
  useEffect(() => {
    if (camOn && previewRef.current && camVideoRef.current) previewRef.current.replaceChildren(camVideoRef.current);
  }, [camOn]);

  // Keep the newest line of a long answer in view inside the fixed caption box.
  useEffect(() => {
    const box = captionsRef.current;
    if (box) box.scrollTop = box.scrollHeight;
  }, [said, heard]);

  // Reminders and alerts from the server are said aloud when Atulya is free.
  useEffect(() => {
    function onNotification(event) {
      const data = event.detail || {};
      const text = data.desc || data.title || '';
      if (!text || data.type === 'success' || busyRef.current || stateRef.current === 'speaking' || !started) return;
      setSaid(text);
      speak(text);
    }
    window.addEventListener('atulya:notification', onNotification);
    return () => window.removeEventListener('atulya:notification', onNotification);
  }, [started]);

  // Browsers only open the microphone after a click the first time. Once it has been
  // allowed for this page, start listening by itself on every later visit.
  useEffect(() => {
    let cancelled = false;
    const resume = () => { audioCtxRef.current?.resume?.().catch(() => {}); };
    window.addEventListener('pointerdown', resume, { once: true });
    window.addEventListener('keydown', resume, { once: true });
    (async () => {
      try {
        const perm = await navigator.permissions.query({ name: 'microphone' });
        if (cancelled) return;
        if (perm.state === 'granted') start();
        else if (perm.state === 'denied') setHint('The microphone is blocked in this window. Open http://localhost:8501 in Chrome or Edge and allow the mic, or type below.');
        else setHint('Tap once to allow the microphone — browsers require a click the first time.');
      } catch { /* no Permissions API: wait for a tap */ }
    })();
    return () => { cancelled = true; };
  }, []);

  // Switching the listening engine restarts the loop with the new one.
  useEffect(() => {
    if (!started) return;
    stopLoop();
    const id = setTimeout(() => start(), 300);
    return () => clearTimeout(id);
  }, [settings.engine]);

  // The holographic humanoid (three.js), loaded lazily; the orb is the fallback.
  useEffect(() => {
    let cancelled = false;
    import('./Hologram.js')
      .then(async ({ createHologram }) => {
        if (cancelled) return;
        const h = await createHologram(holoBoxRef.current, () => ({ level: levelRef.current, state: stateRef.current }));
        if (cancelled) { h.dispose(); return; }
        holoRef.current = h;
        setHolo('ready');
      })
      .catch((err) => {
        console.warn('Hologram unavailable, showing the orb:', err);
        if (!cancelled) setHolo('none');
      });
    return () => { cancelled = true; clearTimeout(timer); holoRef.current?.dispose(); holoRef.current = null; };
  }, []);

  useEffect(() => () => {
    stopLoop();
    stopVoice();
    micRef.current?.stream.getTracks().forEach((track) => track.stop());
    audioCtxRef.current?.close().catch(() => {});
  }, []);

  const STATUS = {
    idle: started ? 'Paused' : `Tap ${holo === 'ready' ? 'anywhere' : 'the orb'} to wake Atulya`,
    listening: settings.handsFree && Date.now() >= followUntilRef.current ? 'Say “Hey Atulya”' : 'Listening…',
    thinking: 'Thinking…',
    speaking: 'Speaking — tap to interrupt',
    error: 'Something went wrong',
  };

  // With the hologram the screen stays free of text: replies appear in the right-hand corner, and only for a while.
  const quiet = holo === 'ready';
  const immersive = holo !== 'none';
  useEffect(() => {
    setCapVisible(true);
    const id = setTimeout(() => setCapVisible(false), 16000);
    return () => clearTimeout(id);
  }, [said, heard, hint, state]);

  return (
    <div className={`orb-screen ${state}${immersive ? ' with-holo' : ''}${typing ? ' typing' : ''}`}>
      <canvas ref={canvasRef} className={`orb-canvas${immersive ? ' hidden' : ''}`} onClick={tapOrb}
        aria-label="Talk to Atulya" role="button" />
      <div ref={holoBoxRef} className={`orb-holo ${holo}`} onClick={tapOrb} />
      <div className="orb-top">
        <button type="button" className="orb-icon" onClick={onMenu} title="Menu" aria-label="Menu">☰</button>
        <div className="orb-name"><strong>ATULYA</strong><span>// PERSONAL AI</span></div>
        {immersive && <div className="holo-meta" aria-label="Connection telemetry">
          <span>API RTT <b>{apiRtt == null ? '—' : `${apiRtt} ms`}</b></span>
          <span>TIME <b>{hudClock.toLocaleTimeString('en-GB', { hour12: false })}</b></span>
          <span className={window.location.protocol === 'https:' ? 'secure' : 'local'}>
            <b>{window.location.protocol === 'https:' ? 'SECURE CONNECTION' : 'LOCAL HTTP'}</b><i />
          </span>
        </div>}
        <div className="orb-icons">
          {!immersive && cams.state !== 'unsupported' && cams.state !== 'none' && (
            <button type="button" className={`orb-icon ${camOn ? 'on' : ''}`} onClick={() => toggleWebcam(!camOn)}
              title={camOn ? 'Turn the camera off' : cams.state === 'denied' ? 'Camera is blocked' : 'Turn the camera on (the browser will ask permission)'}
              aria-label="Camera">📷</button>
          )}
          <button type="button" className="orb-icon" onClick={() => setShowSettings((v) => !v)} title="Settings" aria-label="Settings">⚙</button>
        </div>
      </div>

      {immersive && <>
        <div className="holo-hud holo-left" aria-label="System status">
          <section className="hud-card hud-status">
            <h2><i /> SYSTEM STATUS</h2>
            <div className="hud-status-line"><span>NEURAL CORE</span><b className={`hud-state ${state}`}>{state === 'idle' ? 'STANDBY' : state.toUpperCase()}</b></div>
            <div className="hud-status-line"><span>SERVER LINK</span><b className={`hud-state ${telemetryState}`}>{telemetryState === 'online' ? 'CONNECTED' : telemetryState === 'restricted' ? 'ADMIN ONLY' : telemetryState === 'loading' ? 'CHECKING' : 'OFFLINE'}</b></div>
            <div className="hud-status-line"><span>SYSTEM HEALTH</span><b className={telemetry?.events?.some((event) => event.type === 'warning') ? 'hud-state error' : 'hud-state online'}>{telemetry ? (telemetry.events?.some((event) => event.type === 'warning') ? 'REVIEW' : 'NOMINAL') : 'CHECKING'}</b></div>
            <div className="hud-status-line"><span>VOICE INPUT</span><b>{started ? 'READY' : 'TAP TO START'}</b></div>
            <div className="hud-status-line"><span>CAMERA</span><b>{camOn ? (camPresence ? 'MOTION' : 'STREAM ON') : 'STANDBY'}</b></div>
            <div className="hud-status-line"><span>UPTIME</span><b>{telemetry?.system?.uptime || '—'}</b></div>
          </section>
          <section className="hud-card hud-metrics">
            <h2>CPU / MEMORY BUFFER</h2>
            <div className="hud-gauges">
              <div className="hud-gauge" style={{ '--gauge': `${Number(telemetry?.system?.cpu_pct) || 0}%` }}><span>{telemetry ? formatPercent(telemetry.system?.cpu_pct) : '—'}</span><small>CPU</small></div>
              <div className="hud-gauge warm" style={{ '--gauge': `${Number(telemetry?.system?.ram_pct) || 0}%` }}><span>{telemetry ? formatPercent(telemetry.system?.ram_pct) : '—'}</span><small>RAM</small></div>
            </div>
            <small>{telemetry ? `${telemetry.system?.ram_avail_gb ?? '—'} GB RAM available · ${telemetry.system?.disk_free_gb ?? '—'} GB disk free` : telemetryState === 'restricted' ? 'Sign in as admin to view server metrics' : 'Server metrics unavailable'}</small>
          </section>
          <section className="hud-card hud-brain">
            <h2>COGNITIVE SYNAPSE</h2>
            {telemetry?.providers?.filter((p) => p.id !== 'auto').slice(0, 3).map((p) => (
              <div className="hud-provider" key={p.id}><span className={p.available ? 'provider-dot on' : 'provider-dot'} />{p.name}<b>{p.available ? 'READY' : 'OFF'}</b></div>
            )) || <small>{telemetryState === 'restricted' ? 'Provider health requires admin access' : 'Checking configured brains…'}</small>}
          </section>
        </div>
        <div className="holo-hud holo-right" aria-label="Environment and connection status">
          <section className="hud-card hud-sensors">
            <h2>ENVIRONMENT CONTROL</h2>
            <button type="button" onClick={() => toggleWebcam(!camOn)}><span>CAMERA SENSOR</span><b className={camOn ? 'sensor-on' : ''}>{camOn ? 'ON' : 'OFF'}</b></button>
            {camOn && <button type="button" onClick={() => ask('What can you see in front of you?')}><span>DESCRIBE CAMERA VIEW</span><b className="sensor-on">ASK</b></button>}
            <button type="button" onClick={tapOrb}><span>VOICE INTERFACE</span><b className={started ? 'sensor-on' : ''}>{started ? 'READY' : 'START'}</b></button>
            <button type="button" onClick={() => setTyping((v) => !v)}><span>TEXT INPUT</span><b className={typing ? 'sensor-on' : ''}>{typing ? 'OPEN' : 'CLOSED'}</b></button>
          </section>
          <section className="hud-card hud-link">
            <h2>NETWORK / SECURITY</h2>
            <div className="hud-link-light"><span className={telemetryState === 'online' ? 'provider-dot on' : 'provider-dot'} />
              <div><strong>{telemetryState === 'online' ? 'ATULYA SERVER' : telemetryState === 'restricted' ? 'TELEMETRY LOCKED' : telemetryState === 'loading' ? 'CHECKING LINK' : 'SERVER UNREACHABLE'}</strong>
                <small>{window.location.protocol === 'https:' ? 'HTTPS ENCRYPTED' : ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname) ? 'LOCAL CONNECTION' : 'HTTP CONNECTION'}</small></div>
            </div>
            {telemetry?.system?.uptime && <div className="hud-status-line"><span>UPTIME</span><b>{telemetry.system.uptime}</b></div>}
          </section>
          <section className="hud-card hud-history">
            <h2>RESOURCE HISTORY</h2>
            <div className="hud-chart-label"><span>CPU</span><span>RAM</span></div>
            {telemetryHistory.length > 1 ? (
              <svg viewBox="0 0 100 32" preserveAspectRatio="none" role="img" aria-label="Recent CPU and RAM readings">
                <polyline points={telemetryHistory.map((p, i) => `${i * (100 / (telemetryHistory.length - 1))},${30 - p.cpu * 0.28}`).join(' ')} />
                <polyline className="ram-line" points={telemetryHistory.map((p, i) => `${i * (100 / (telemetryHistory.length - 1))},${30 - p.ram * 0.28}`).join(' ')} />
              </svg>
            ) : <small>Collecting live samples every 15 seconds</small>}
          </section>
          <section className="hud-card hud-utilities">
            <h2>AI UTILITY MODULES</h2>
            <label className="hud-toggle"><span>WAKE WORD</span><input type="checkbox" checked={settings.handsFree} onChange={(e) => setSettings((s) => ({ ...s, handsFree: e.target.checked }))} /></label>
            <label className="hud-toggle"><span>SERVER VOICE</span><input type="checkbox" checked={settings.serverTts} onChange={(e) => setSettings((s) => ({ ...s, serverTts: e.target.checked }))} /></label>
            <small>{settings.handsFree ? (started ? 'Wake phrase active' : 'Tap voice to activate listening') : 'Wake phrase disabled'} · {settings.engine === 'browser' ? 'Recognition on this device' : 'Recognition on Atulya server'}</small>
          </section>
          <section className="hud-card hud-events">
            <h2>SYSTEM DIAGNOSTICS</h2>
            {telemetry?.events?.length ? telemetry.events.slice(0, 3).map((event) => (
              <div className="hud-event" key={event.title}><i className={event.type} /><span><b>{event.title}</b><small>{event.desc}</small></span></div>
            )) : <small>{telemetryState === 'restricted' ? 'Admin access required for diagnostics' : 'Waiting for live diagnostics'}</small>}
          </section>
          <section className="hud-card hud-response">
            <h2>VOICE PATTERN</h2>
            <strong>{state === 'speaking' ? 'SPEAKING' : state === 'listening' ? 'LISTENING' : state === 'thinking' ? 'PROCESSING' : 'READY'}</strong>
            <small>{said ? 'Response active' : 'Neural bridge ' + (telemetryState === 'online' ? 'connected' : 'awaiting connection')}</small>
          </section>
        </div>
        <div className="holo-bottom">
          <AudioWaveform levelRef={levelRef} stateRef={stateRef} />
          <div className="holo-controls">
            <span className="holo-control-label">ATULYA // VOICE CONSOLE</span>
            <button type="button" className={`holo-control-mic ${started ? 'active' : ''}`} onClick={tapOrb} aria-label={started ? 'Talk to Atulya' : 'Start voice'} title={started ? 'Talk to Atulya' : 'Start voice'}>◉</button>
          </div>
        </div>
      </>}

      {(holo === 'none' || ((capVisible || state === 'speaking') && (heard || said || hint))) && (
      <div className="orb-captions" ref={captionsRef}>
        {!quiet && <div className="orb-status">{STATUS[state]}</div>}
        {heard && <div className="orb-heard">“{heard}”</div>}
        {said && <div className="orb-said">{said}</div>}
        {hint && <div className="orb-hint">{hint}</div>}
        {holo === 'none' && !said && !heard && state !== 'thinking' && (
          <div className="orb-chips">
            {SUGGESTIONS.map((text) => (
              <button type="button" key={text} onClick={() => ask(text)}>{text}</button>
            ))}
          </div>
        )}
      </div>
      )}

      {camOn && <div className="orb-cam" ref={previewRef} title="Your camera is on. Everything stays in this browser unless you ask me to look at something." />}

      {(holo === 'none' || typing) && (
      <form className="orb-type" onSubmit={(e) => { e.preventDefault(); const t = typed.trim(); setTyped(''); if (t) ask(t); }}>
        <input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="Or type to Atulya…" autoFocus={quiet} />
      </form>
      )}

      {showSettings && (
        <div className="orb-settings" role="dialog" aria-label="Atulya settings" aria-modal="true">
          <div className="orb-settings-heading"><strong>SETTINGS</strong><button type="button" onClick={() => setShowSettings(false)} aria-label="Close settings">×</button></div>
          <label>I am
            <select value={settings.userGender} onChange={(e) => setSettings((s) => ({ ...s, userGender: e.target.value }))}>
              <option value="male">A man (Atulya speaks as a woman)</option>
              <option value="female">A woman (Atulya speaks as a man)</option>
            </select>
          </label>
          <label>Listening
            <select value={settings.engine} onChange={(e) => setSettings((s) => ({ ...s, engine: e.target.value }))}>
              <option value="browser">On this device (browser speech)</option>
              <option value="local">Atulya server Whisper (uploads audio)</option>
            </select>
          </label>
          <label className="check">
            <input type="checkbox" checked={settings.serverTts} onChange={(e) => setSettings((s) => ({ ...s, serverTts: e.target.checked }))} />
            Use server neural voice (sends reply text to server)
          </label>
          <label>Volume
            <select value={String(boost)} onChange={(e) => { const v = parseFloat(e.target.value); setBoost(v); setBoostState(v); }}>
              <option value="1">100% (normal)</option>
              <option value="2">200%</option>
              <option value="2.5">250%</option>
              <option value="3">300% (loudest)</option>
            </select>
          </label>
          <label className="check">
            <input type="checkbox" checked={settings.handsFree} onChange={(e) => setSettings((s) => ({ ...s, handsFree: e.target.checked }))} />
            Wake word (“Hey Atulya”)
          </label>
          <label className="check">
            <input type="checkbox" checked={camOn} onChange={(e) => toggleWebcam(e.target.checked)} />
            Let Atulya see me (webcam)
          </label>
          <small className="orb-hint" style={{ color: '#9fd8d0' }}>
            {cams.state === 'unsupported' ? 'This browser cannot use a camera here.'
              : cams.devices.length ? `${cams.devices.length} camera${cams.devices.length > 1 ? 's' : ''} found${cams.state === 'granted' ? ', allowed' : cams.state === 'denied' ? ', blocked' : ', not allowed yet'}.`
              : 'No camera detected. Plug one in and it will appear here.'}
          </small>
          {camOn && <small className="orb-camera-note">Camera stays in this browser. Atulya uses one frame only when you choose “Describe camera view” or ask what is in front of the camera.</small>}
          {cams.devices.length > 1 && (
            <select value={camId} onChange={(e) => { setCamId(e.target.value); if (camOn) { webcamRef.current?.stop(); toggleWebcam(true, e.target.value); } }}>
              <option value="">Automatic</option>
              {cams.devices.map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}
            </select>
          )}
          {camError && <small className="orb-hint">{camError}</small>}
          <button type="button" onClick={() => { historyRef.current = []; setHeard(''); setSaid(''); }}>Forget this conversation</button>
          {started && Boolean(loopRef.current.active) && <button type="button" onClick={stopLoop}>Stop listening</button>}
        </div>
      )}
    </div>
  );
}
