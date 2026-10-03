import React, { useEffect, useRef, useState } from 'react';
import { api } from '../../api.js';

// The home screen: one glowing orb you talk to, Jarvis style. It wakes on
// "Hey Atulya" (or "Hi / Hello / Listen Atulya", or just "Atulya"), ripples to
// your voice, spins while thinking and pulses with its own voice. Everything
// else in the app sits behind the menu button.

// Whisper and browsers spell the name many ways: Atulya, Athulya, Atulia, a tulya…
const NAME = 'a\\s?th?(?:u|oo)l+(?:i|y|iy|ee)?a';
const WAKE_RE = new RegExp(`(?:^|[^a-z])${NAME}(?:[^a-z]|$)|अतुल्य`, 'i');
const WAKE_LEAD_RE = new RegExp(`^[\\s,.!?-]*(?:(?:hey|hi|hello|ok|okay|listen|suno)[\\s,.!?-]*)?(?:${NAME}|अतुल्या?)[\\s,.!?-]*(?:(?:listen|suno)[\\s,.!?-]*)?`, 'i');
const FOLLOW_UP_MS = 8000; // after Atulya speaks, answer without the wake word
const SETTINGS_KEY = 'atulya-orb-settings';

function loadSettings() {
  const defaults = { userGender: 'male', handsFree: true, engine: 'local' };
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

export function Orb({ onMenu, toast }) {
  const [settings, setSettings] = useState(loadSettings);
  const [state, setState] = useState('idle'); // idle | listening | thinking | speaking | error
  const [started, setStarted] = useState(false);
  const [heard, setHeard] = useState('');
  const [said, setSaid] = useState('');
  const [hint, setHint] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  const [typed, setTyped] = useState('');

  const canvasRef = useRef(null);
  const holoBoxRef = useRef(null);
  const holoRef = useRef(null); // the particle humanoid, once running
  const [holo, setHolo] = useState('loading'); // loading | ready | none (no WebGL: the orb shows)
  const [opening, setOpening] = useState(true);
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
      if (!SR) { reject(new Error('This browser has no speech recognition. Switch Listening to "On this PC".')); return; }
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
        ? 'Speech-to-text isn\u2019t installed. Run start.bat again, or set Listening to Browser in \u2699.'
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
        try {
          const ctx = audioCtx();
          const source = ctx.createMediaElementSource(audio);
          const analyser = ctx.createAnalyser();
          analyser.fftSize = 256;
          source.connect(analyser);
          analyser.connect(ctx.destination);
          analyserRef.current = analyser;
        } catch { analyserRef.current = null; }
        audio.onended = done;
        audio.onerror = done;
        audio.play().catch(() => speakInBrowser(text).then(done));
        return;
      }
      analyserRef.current = null;
      speakInBrowser(text).then(done);
    });
  }

  function speakInBrowser(text) {
    return new Promise((resolve) => {
      if (!('speechSynthesis' in window) || !text) { resolve(); return; }
      const u = new SpeechSynthesisUtterance(text);
      const hindi = /[ऀ-ॿ]/.test(text);
      u.lang = hindi ? 'hi-IN' : 'en-GB';
      // Some browsers never fire onend (no voices installed): don't hang on it.
      const timer = setTimeout(resolve, 2500 + text.split(/\s+/).length * 450);
      u.onend = () => { clearTimeout(timer); resolve(); };
      u.onerror = u.onend;
      window.speechSynthesis.speak(u);
    });
  }

  // ── One turn: send what was said, speak the answer ──────────────────────
  async function ask(text) {
    if (!text || busyRef.current) return;
    busyRef.current = true;
    setHeard(text);
    setSaid('');
    setHint('');
    setState('thinking');
    try {
      const res = await api.post('/api/voice/chat', {
        prompt: text,
        voice: voiceName(),
        history: historyRef.current.slice(-8),
      });
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
    const timer = setTimeout(() => setOpening(false), 5200);
    import('./Hologram.js')
      .then(({ createHologram }) => {
        if (cancelled) return;
        holoRef.current = createHologram(holoBoxRef.current, () => ({ level: levelRef.current, state: stateRef.current }));
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

  return (
    <div className={`orb-screen ${state}${holo === 'ready' ? ' with-holo' : ''}`}>
      <canvas ref={canvasRef} className={`orb-canvas${holo === 'ready' ? ' hidden' : ''}`} onClick={tapOrb}
        aria-label="Talk to Atulya" role="button" />
      <div ref={holoBoxRef} className={`orb-holo ${holo}`} onClick={tapOrb} />
      {holo === 'ready' && (
        <div className="orb-hud" aria-hidden="true">
          <span>ATULYA · {state === 'idle' && !started ? 'STANDBY' : 'ONLINE'}</span>
          <span>{state.toUpperCase()}</span>
        </div>
      )}
      {holo === 'ready' && opening && <div className="orb-opening">Opening humanoid view</div>}
      <div className="orb-top">
        <button type="button" className="orb-icon" onClick={onMenu} title="Menu" aria-label="Menu">☰</button>
        <div className="orb-name">ATULYA</div>
        <button type="button" className="orb-icon" onClick={() => setShowSettings((v) => !v)} title="Settings" aria-label="Settings">⚙</button>
      </div>

      <div className="orb-captions">
        <div className="orb-status">{STATUS[state]}</div>
        {heard && <div className="orb-heard">{heard}</div>}
        {said && <div className="orb-said">{said}</div>}
        {hint && <div className="orb-hint">{hint}</div>}
      </div>

      <form className="orb-type" onSubmit={(e) => { e.preventDefault(); const t = typed.trim(); setTyped(''); if (t) ask(t); }}>
        <input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="Or type to Atulya…" />
      </form>

      {showSettings && (
        <div className="orb-settings">
          <label>I am
            <select value={settings.userGender} onChange={(e) => setSettings((s) => ({ ...s, userGender: e.target.value }))}>
              <option value="male">A man (Atulya speaks as a woman)</option>
              <option value="female">A woman (Atulya speaks as a man)</option>
            </select>
          </label>
          <label>Listening
            <select value={settings.engine} onChange={(e) => setSettings((s) => ({ ...s, engine: e.target.value }))}>
              <option value="local">On this PC (private, English + Hindi)</option>
              <option value="browser">Browser (faster, Chrome/Edge)</option>
            </select>
          </label>
          <label className="check">
            <input type="checkbox" checked={settings.handsFree} onChange={(e) => setSettings((s) => ({ ...s, handsFree: e.target.checked }))} />
            Wake word (“Hey Atulya”)
          </label>
          <button type="button" onClick={() => { historyRef.current = []; setHeard(''); setSaid(''); }}>Forget this conversation</button>
          {started && Boolean(loopRef.current.active) && <button type="button" onClick={stopLoop}>Stop listening</button>}
        </div>
      )}
    </div>
  );
}
