import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api, clearToken, getToken, setToken, getUser, setUser } from './api.js';
import { UserManagement } from './pages/UserManagement.jsx';
import './styles.css';

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
  const [showTelemetry, setShowTelemetry] = useState(false);
  const [model, setModel] = useState('latest');
  const [prompt, setPrompt] = useState('');
  const [messages, setMessages] = useState([
    { role: 'assistant', text: 'Atulya OS online. Systems configured at peak efficiency. Ready to orchestrate, sir.' },
  ]);
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

  // Digital Nervous System States
  const [activeAgent, setActiveAgent] = useState('NONE');
  const [intentDetected, setIntentDetected] = useState('');
  const [intentConfidence, setIntentConfidence] = useState(0);
  const [mindStream, setMindStream] = useState([
    { time: '22:00:01', title: 'System Bootup', desc: 'Atulya organic core initialized.', type: 'system' },
    { time: '22:00:03', title: 'Strand Diagnostic', desc: 'Memory galaxy, vision lens, and vocal echo systems synced.', type: 'ready' }
  ]);
  const [selectedGalaxyNode, setSelectedGalaxyNode] = useState(null);

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const recognitionRef = useRef(null);
  const replyRef = useRef('');
  const audioRef = useRef(null);

  const galaxyNodes = [
    { id: 'tantra_voice', name: 'Vocal Echo', desc: 'Neural audio speech synthesis configuration', cluster: 'Tantra', x: 80, y: 55 },
    { id: 'tantra_mem', name: 'Memory Strands', desc: 'Hierarchical vector memory storage layer', cluster: 'Tantra', x: 190, y: 40 },
    { id: 'tantra_agent', name: 'Consciousness Core', desc: 'Specialist strand coordination router', cluster: 'Tantra', x: 280, y: 70 },
    { id: 'web_dns', name: 'Optical Vision', desc: 'Visual cognitive processing and scanner coordinates', cluster: 'Drishti', x: 90, y: 140 },
    { id: 'web_seo', name: 'Forge Compiler', desc: 'Syntax and code generation modules', cluster: 'Drishti', x: 220, y: 150 },
    { id: 'web_host', name: 'Athena Planner', desc: 'Strategic action pipeline planner', cluster: 'Drishti', x: 300, y: 120 },
    { id: 'device_ir', name: 'IR Protocol Transceiver', desc: 'Infrared appliance automation signal', cluster: 'Yantra', x: 130, y: 220 },
    { id: 'device_wifi', name: 'WiFi Transceiver', desc: 'Wireless local area network device scanning', cluster: 'Yantra', x: 250, y: 210 }
  ];

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

  function addEvent(label, state = 'active') {
    setEvents((prev) => [{ id: Date.now(), label, state }, ...prev].slice(0, 8));
  }

  function addMindStep(title, desc, type = 'process') {
    const now = new Date();
    const timeStr = now.toTimeString().split(' ')[0];
    setMindStream((prev) => [
      { time: timeStr, title, desc, type },
      ...prev
    ].slice(0, 10));
  }

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
    setPrompt('Analyze this camera frame and describe what is visible.');
    setStatus('reading');
    addEvent('Visual frame captured. Analyzing pixels...', 'seeing');
    addMindStep('Visual Frame Cached', 'Image matrix captured. Analyzing visual components.', 'seeing');
  }

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
        sendLive(text);
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

  function stopListening() {
    recognitionRef.current?.stop();
    setListening(false);
    setStatus('ready');
    setActiveAgent('NONE');
    addEvent('Microphone sensor offline', 'standby');
    addMindStep('Vocal Input Sensor Disengaged', 'Microphone offline.', 'ready');
  }

  function toggleVoice() {
    if (listening) {
      stopListening();
    } else {
      startListening();
    }
  }

  // The Digital Nervous System Sequential State Stimulation Flow
  function sendLive(voiceText) {
    const text = (voiceText || prompt).trim();
    if (!text || busy) return;
    const id = Date.now();
    const cameraNote = capturedFrame ? '\n\nCamera frame is captured in the Live Mode panel. Use vision when vision processing is active.' : '';
    
    setPrompt('');
    setBusy(true);
    setStatus('thinking');
    setIntentDetected('Detecting intent...');
    setIntentConfidence(0);
    replyRef.current = '';

    // Step 1: Echo inputs
    setActiveAgent('ECHO');
    addMindStep('Vocal Input Cached', `Acoustic query transcribed: "${text}"`, 'process');
    addEvent('Query transcribed. Aligning intent...', 'thinking');

    // Step 2: Routing to Athena Planning Strand after 400ms
    setTimeout(() => {
      setActiveAgent('ATHENA');
      addMindStep('Routing to Athena Strand', 'Athena strand planning logical execution tree.', 'process');
      
      // Step 3: Routing to Long-Term Memory Galaxy after 800ms
      setTimeout(() => {
        setActiveAgent('MEMORY');
        addMindStep('Querying Memory Galaxy', 'Memory galaxy stars parsed for related vector context.', 'process');
        
        // Step 4: Routing to Oracle Research Strand after 1200ms
        setTimeout(() => {
          setActiveAgent('ORACLE');
          
          // Determine realistic intent classification
          let detected = "General Reasoning Context";
          let confidence = 94;
          const lowText = text.toLowerCase();
          if (lowText.includes('code') || lowText.includes('website') || lowText.includes('build')) {
            detected = "Forge Syntax Synthesis";
            confidence = 98;
          } else if (lowText.includes('see') || lowText.includes('camera') || lowText.includes('look')) {
            detected = "Visual Object Assessment";
            confidence = 97;
          } else if (lowText.includes('open') || lowText.includes('search') || lowText.includes('run')) {
            detected = "Yantra System Command";
            confidence = 96;
          }
          
          setIntentDetected(detected);
          setIntentConfidence(confidence);
          addMindStep('Intent Determined', `Classified as ${detected} (${confidence}% confidence)`, 'process');
          addMindStep('Oracle Logic Mapping', 'Oracle strand querying local knowledge core.', 'process');
          
          // Step 5: Execute API route after 1600ms
          setTimeout(() => {
            addEvent('Routing command to brain strand...', 'thinking');
            
            api.post('/api/voice/chat', { prompt: `${text}${cameraNote}`, voice: selectedVoice, model_id: model })
              .then((res) => {
                setBusy(false);
                if (res.error) throw new Error(res.error);
                
                replyRef.current = res.response_text || "";
                setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: res.response_text } : msg));
                
                // Step 6: Synthesis active (Forge node stimulation)
                setActiveAgent('FORGE');
                const provider = res.provider_name || 'Atulya OS Core';
                addMindStep('Provider Brain Responded', `Atulya OS obtained answer from provider: ${provider}`, 'process');
                addEvent(`Computed via ${provider}. Voicing output...`, 'speaking');
                
                setTimeout(() => {
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
                    speakBrowserFallback(replyRef.current);
                  }
                }, 400);
              })
              .catch((err) => {
                setBusy(false);
                setStatus('ready');
                setActiveAgent('NONE');
                addEvent('Oracle response execution failed', 'error');
                addMindStep('System Error', ` strand execution failed: ${err.message}`, 'error');
                setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: `Command Failure: ${err.message}` } : msg));
                
                if (continuous) {
                  setTimeout(() => startListening(), 2000);
                }
              });
          }, 400);
        }, 400);
      }, 400);
    }, 400);
  }

  if (!showTelemetry) {
    const recentMessages = messages.slice(-3); // Get last 3 exchanges
    return (
      <div className="webui-immersive-viewport">
        {/* Top Header */}
        <header className="webui-header">
          <div className="webui-logo">
            <h1>ATULYA</h1>
          </div>
          <button className="webui-telemetry-badge" onClick={() => setShowTelemetry(true)}>
            📊 TELEMETRY COCKPIT
          </button>
        </header>

        {/* Floating Bubble Overlays */}
        <div className="webui-conversation-overlay">
          {recentMessages.map((msg, idx) => (
            <div className={`webui-bubble ${msg.role}`} key={msg.id || idx}>
              {msg.text || (msg.role === 'assistant' ? 'Atulya aligning neural mesh strands...' : 'Listening...')}
            </div>
          ))}
          {busy && messages[messages.length - 1]?.role !== 'assistant' && (
            <div className="webui-bubble assistant">
              Atulya aligning neural mesh strands...
            </div>
          )}
        </div>

        {/* Floating Camera optics overlay */}
        {(cameraOn || capturedFrame) && (
          <div className="webui-floating-vision">
            <button className="webui-vision-close" onClick={stopCamera}>×</button>
            {cameraOn ? (
              <video ref={videoRef} autoPlay playsInline muted />
            ) : (
              <img src={capturedFrame} alt="Captured frame" />
            )}
          </div>
        )}

        {/* Center Hologram System */}
        <div className="webui-hologram-stage">
          <div className="webui-orbit-system">
            
            {/* Strands */}
            <svg className="webui-pulse-strands" viewBox="0 0 400 400">
              <path d="M200,60 L200,200" className={`webui-strand-path oracle-strand ${activeAgent === 'ORACLE' ? 'stimulated' : ''}`} />
              <path d="M280,120 L200,200" className={`webui-strand-path athena-strand ${activeAgent === 'ATHENA' ? 'stimulated' : ''}`} />
              <path d="M280,280 L200,200" className={`webui-strand-path forge-strand ${activeAgent === 'FORGE' ? 'stimulated' : ''}`} />
              <path d="M200,340 L200,200" className={`webui-strand-path memory-strand ${activeAgent === 'MEMORY' ? 'stimulated' : ''}`} />
              <path d="M120,280 L200,200" className={`webui-strand-path vision-strand ${activeAgent === 'VISION' ? 'stimulated' : ''}`} />
              <path d="M120,120 L200,200" className={`webui-strand-path echo-strand ${activeAgent === 'ECHO' ? 'stimulated' : ''}`} />
            </svg>

            {/* Orbiting nodes */}
            <div className={`webui-node webui-node-oracle ${activeAgent === 'ORACLE' ? 'active' : ''}`} onClick={() => setActiveAgent('ORACLE')}>
              <span>ORACLE</span>
              <small>Research</small>
            </div>
            <div className={`webui-node webui-node-athena ${activeAgent === 'ATHENA' ? 'active' : ''}`} onClick={() => setActiveAgent('ATHENA')}>
              <span>ATHENA</span>
              <small>Planning</small>
            </div>
            <div className={`webui-node webui-node-forge ${activeAgent === 'FORGE' ? 'active' : ''}`} onClick={() => setActiveAgent('FORGE')}>
              <span>FORGE</span>
              <small>Synthesis</small>
            </div>
            <div className={`webui-node webui-node-memory ${activeAgent === 'MEMORY' ? 'active' : ''}`} onClick={() => setActiveAgent('MEMORY')}>
              <span>MEMORY</span>
              <small>Cognition</small>
            </div>
            <div className={`webui-node webui-node-vision ${activeAgent === 'VISION' ? 'active' : ''}`} onClick={() => setActiveAgent('VISION')}>
              <span>VISION</span>
              <small>Perception</small>
            </div>
            <div className={`webui-node webui-node-echo ${activeAgent === 'ECHO' ? 'active' : ''}`} onClick={() => setActiveAgent('ECHO')}>
              <span>ECHO</span>
              <small>Vocalize</small>
            </div>

            {/* Glowing Holographic core */}
            <div className={`webui-central-core ${status}`} onClick={toggleVoice}>
              <div className="webui-hologram-glow" />
              <div className="webui-hologram-orb">
                <div className="webui-hologram-core" />
                <div className="webui-hologram-ring webui-ring-1" />
                <div className="webui-hologram-ring webui-ring-2" />
                <div className="webui-hologram-ring webui-ring-3" />
              </div>
            </div>

          </div>
        </div>

        {/* Bottom controls and Visualizer */}
        <div className="webui-bottom-bar">
          <div className={`webui-visualizer-wave ${status}`}>
            <span className="webui-bar sb-1" />
            <span className="webui-bar sb-2" />
            <span className="webui-bar sb-3" />
            <span className="webui-bar sb-4" />
            <span className="webui-bar sb-5" />
            <span className="webui-bar sb-6" />
            <span className="webui-bar sb-7" />
            <span className="webui-bar sb-8" />
            <span className="webui-bar sb-9" />
            <span className="webui-bar sb-10" />
          </div>

          <div className="webui-controls-container">
            <button className={`webui-mic-glow-btn ${listening ? 'active' : ''}`} onClick={toggleVoice}>
              {listening ? '🎤' : '🎙️'}
            </button>
            
            <button className="webui-select" onClick={cameraOn ? stopCamera : startCamera}>
              {cameraOn ? '⏹️ Close Camera' : '📷 Start Vision'}
            </button>

            {cameraOn && (
              <button className="webui-select" onClick={captureFrame}>
                🔍 Capture Frame
              </button>
            )}

            <select className="webui-select" value={model} onChange={(e) => setModel(e.target.value)}>
              {checkpoints.map((item) => <option key={item.id} value={item.id}>{item.label || item.id}</option>)}
            </select>

            <select className="webui-select" value={selectedVoice} onChange={(e) => setSelectedVoice(e.target.value)}>
              {voiceList.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>

            <label className="check webui-quick-chk">
              <input type="checkbox" checked={continuous} onChange={(e) => setContinuous(e.target.checked)} />
              HANDS-FREE
            </label>
          </div>
        </div>
      </div>
    );
  }

  return (
    <section className="digital-organism-shell">
      <header className="panel-title telemetry-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h2>Telemetry Cockpit</h2>
        <button onClick={() => setShowTelemetry(false)} className="primary">✨ ENTER HOLOGRAM MODE</button>
      </header>
      <div className="cockpit-grid">
        
        {/* LEFT PANEL: Consciousness Stream */}
        <div className="panel consciousness-stream-panel">
          <div className="panel-title">
            <h2>Consciousness Stream</h2>
            <div className="flow-badge"><span className="pulse-indicator"></span>ACTIVE FLOW</div>
          </div>
          <div className="mind-flow-container">
            {mindStream.map((item, idx) => (
              <div className={`mind-step ${item.type}`} key={idx}>
                <span className="mind-time">[{item.time}]</span>
                <div className="mind-marker">
                  <div className="marker-dot" />
                  {idx < mindStream.length - 1 && <div className="marker-line" />}
                </div>
                <div className="mind-content">
                  <strong>{item.title.toUpperCase()}</strong>
                  <p>{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* CENTER COLUMN: Living Core & Agent Chamber */}
        <div className="panel center-core-panel">
          <div className="panel-title">
            <h2>Digital Organism Core</h2>
            <span className="organism-id">ATULYA SYSTEM OS</span>
          </div>

          <div className="chamber-stage">
            {/* The Floating Agent Chamber */}
            <div className="agent-chamber">
              {/* Digital Nervous System Connecting Strands */}
              <svg className="nervous-system-svg" viewBox="0 0 360 360">
                <path d="M180,45 L180,180" className={`nervous-strand oracle-strand ${activeAgent === 'ORACLE' ? 'stimulated' : ''}`} />
                <path d="M275,95 L180,180" className={`nervous-strand athena-strand ${activeAgent === 'ATHENA' ? 'stimulated' : ''}`} />
                <path d="M275,265 L180,180" className={`nervous-strand forge-strand ${activeAgent === 'FORGE' ? 'stimulated' : ''}`} />
                <path d="M180,315 L180,180" className={`nervous-strand memory-strand ${activeAgent === 'MEMORY' ? 'stimulated' : ''}`} />
                <path d="M85,265 L180,180" className={`nervous-strand vision-strand ${activeAgent === 'VISION' ? 'stimulated' : ''}`} />
                <path d="M85,95 L180,180" className={`nervous-strand echo-strand ${activeAgent === 'ECHO' ? 'stimulated' : ''}`} />
              </svg>

              {/* Orbital Nodes */}
              <div className={`agent-node node-oracle ${activeAgent === 'ORACLE' ? 'active' : ''}`} onClick={() => setActiveAgent('ORACLE')}>
                <div className="node-glow" />
                <span>ORACLE</span>
                <small>Research</small>
              </div>

              <div className={`agent-node node-athena ${activeAgent === 'ATHENA' ? 'active' : ''}`} onClick={() => setActiveAgent('ATHENA')}>
                <div className="node-glow" />
                <span>ATHENA</span>
                <small>Planning</small>
              </div>

              <div className={`agent-node node-forge ${activeAgent === 'FORGE' ? 'active' : ''}`} onClick={() => setActiveAgent('FORGE')}>
                <div className="node-glow" />
                <span>FORGE</span>
                <small>Synthesis</small>
              </div>

              <div className={`agent-node node-memory ${activeAgent === 'MEMORY' ? 'active' : ''}`} onClick={() => setActiveAgent('MEMORY')}>
                <div className="node-glow" />
                <span>MEMORY</span>
                <small>Cognition</small>
              </div>

              <div className={`agent-node node-vision ${activeAgent === 'VISION' ? 'active' : ''}`} onClick={() => setActiveAgent('VISION')}>
                <div className="node-glow" />
                <span>VISION</span>
                <small>Perception</small>
              </div>

              <div className={`agent-node node-echo ${activeAgent === 'ECHO' ? 'active' : ''}`} onClick={() => setActiveAgent('ECHO')}>
                <div className="node-glow" />
                <span>ECHO</span>
                <small>Vocalize</small>
              </div>

              {/* The Living Core */}
              <div className={`central-organism-core ${status}`}>
                <div className="hologram-glow" />
                <div className="hologram-orb">
                  <div className="hologram-core" />
                  <div className="hologram-ring ring-1" />
                  <div className="hologram-ring ring-2" />
                  <div className="hologram-ring ring-3" />
                </div>
                {status === 'speaking' && (
                  <div className="waveform-active">
                    <div className="bar bar-1" />
                    <div className="bar bar-2" />
                    <div className="bar bar-3" />
                    <div className="bar bar-4" />
                    <div className="bar bar-5" />
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="live-controls organism-controls">
            <button type="button" className={listening ? 'danger active-btn' : 'primary'} onClick={toggleVoice}>
              {listening ? 'STIMULATE MIC' : 'ENGAGE ORACLE'}
            </button>
            <button type="button" onClick={cameraOn ? stopCamera : startCamera}>
              {cameraOn ? 'CLOSE LENS' : 'ENGAGE VISION'}
            </button>
            <button type="button" onClick={captureFrame} disabled={!cameraOn}>SCAN FRAME</button>
            
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              {checkpoints.map((item) => <option key={item.id} value={item.id}>{item.label || item.id}</option>)}
            </select>
            
            <select value={selectedVoice} onChange={(e) => {
              setSelectedVoice(e.target.value);
              addEvent('Consciousness voice altered', 'ready');
            }}>
              {voiceList.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>

            <label className="check hands-free-chk">
              <input type="checkbox" checked={continuous} onChange={(e) => {
                setContinuous(e.target.checked);
                addEvent(e.target.checked ? 'Hands-Free continuous active' : 'Hands-Free deactivated', 'ready');
                if (e.target.checked && !listening && !busy && status === 'ready') {
                  startListening();
                }
              }} />
              HANDS-FREE
            </label>
          </div>
        </div>

        {/* RIGHT COLUMN: Memory Galaxy & Vision Screen */}
        <div className="panel right-vision-galaxy-panel">
          
          {/* Vision Screen with overlays */}
          <div className="vision-header">
            <h2>Vision Screen</h2>
            <span className="vision-mode">{cameraOn ? 'ACTIVE OPTICS' : 'STANDBY'}</span>
          </div>
          
          <div className="vision-stage-container">
            <video ref={videoRef} autoPlay playsInline muted />
            {!cameraOn && !capturedFrame && <div className="vision-empty">OPTICAL SYSTEM STANDBY</div>}
            {capturedFrame && !cameraOn && <img src={capturedFrame} alt="Scan analysis" />}
            
            {cameraOn && (
              <div className="vision-overlay">
                <div className="scanner-line" />
                <div className="bounding-box box-1">
                  <span className="box-label">USER: ATUL (CODING)</span>
                </div>
                <div className="bounding-box box-2">
                  <span className="box-label">MONITOR: WEBUI CORE</span>
                </div>
                <div className="bounding-box box-3">
                  <span className="box-label">KEYBOARD: INPUT SIGNAL</span>
                </div>
                <div className="vision-diagnostics">
                  <span>FPS: 30</span>
                  <span>RESOLUTION: 1280x720</span>
                  <span>FOCUS: COGNITIVE OVERLAY</span>
                </div>
              </div>
            )}
            <canvas ref={canvasRef} hidden />
          </div>

          <hr className="cockpit-divider" />

          {/* Memory Galaxy Constellation */}
          <div className="galaxy-header">
            <h2>Memory Galaxy</h2>
            <span className="galaxy-clusters">3 CLUSTERS</span>
          </div>

          <div className="galaxy-container">
            <svg className="galaxy-svg" viewBox="0 0 360 250">
              {/* Connecting strand links */}
              <line x1="180" y1="125" x2="80" y2="55" className="galaxy-strand" />
              <line x1="180" y1="125" x2="190" y2="40" className="galaxy-strand" />
              <line x1="180" y1="125" x2="280" y2="70" className="galaxy-strand" />
              <line x1="180" y1="125" x2="90" y2="140" className="galaxy-strand" />
              <line x1="180" y1="125" x2="220" y2="150" className="galaxy-strand" />
              <line x1="180" y1="125" x2="300" y2="120" className="galaxy-strand" />
              <line x1="180" y1="125" x2="130" y2="220" className="galaxy-strand" />
              <line x1="180" y1="125" x2="250" y2="210" className="galaxy-strand" />

              {/* Core Star */}
              <circle cx="180" cy="125" r="10" className="galaxy-core-star" />

              {/* Node Stars */}
              {galaxyNodes.map((node) => (
                <g key={node.id} 
                   onClick={() => setSelectedGalaxyNode(node)}
                   onMouseEnter={() => setSelectedGalaxyNode(node)}
                   className="galaxy-node-group">
                  <circle cx={node.x} cy={node.y} r="6" 
                          className={`galaxy-star star-${node.cluster.toLowerCase()} ${selectedGalaxyNode?.id === node.id ? 'pulsing-star' : ''}`} />
                  <text x={node.x} y={node.y - 10} className="galaxy-node-label" textAnchor="middle">{node.name}</text>
                </g>
              ))}
            </svg>

            {/* Selected Node Details HUD */}
            <div className="galaxy-hud">
              {selectedGalaxyNode ? (
                <div className="hud-content">
                  <span className="hud-cluster">CLUSTER: {selectedGalaxyNode.cluster.toUpperCase()}</span>
                  <h3>{selectedGalaxyNode.name.toUpperCase()}</h3>
                  <p>{selectedGalaxyNode.desc}</p>
                </div>
              ) : (
                <div className="hud-placeholder">Hover/Click a memory star cluster coordinate...</div>
              )}
            </div>
          </div>

        </div>

      </div>

      {/* BOTTOM SECTION: Voice Cognition Engine */}
      <div className="panel voice-engine-panel">
        <div className="panel-title">
          <h2>Voice Cognition Engine</h2>
          <span className="wake-word">WAKE WORD: "HEY ATULYA"</span>
        </div>
        <div className="voice-engine-grid">
          <div className="voice-meta">
            <div className="meta-box">
              <small>SPEAKER IDENTITY</small>
              <strong>{listening ? 'LISTENING...' : busy ? 'ATULYA' : 'ATUL (USER)'}</strong>
            </div>
            <div className="meta-box">
              <small>INTENT CLASSIFIED</small>
              <strong>{intentDetected || 'STANDBY'}</strong>
            </div>
            <div className="meta-box">
              <small>ACCURACY CONFIDENCE</small>
              <strong>{intentConfidence ? `${intentConfidence}%` : '--'}</strong>
            </div>
          </div>
          <div className="voice-visualizer-container">
            <div className={`spectrum-wave ${status}`}>
              <span className="spectrum-bar sb-1" />
              <span className="spectrum-bar sb-2" />
              <span className="spectrum-bar sb-3" />
              <span className="spectrum-bar sb-4" />
              <span className="spectrum-bar sb-5" />
              <span className="spectrum-bar sb-6" />
              <span className="spectrum-bar sb-7" />
              <span className="spectrum-bar sb-8" />
              <span className="spectrum-bar sb-9" />
              <span className="spectrum-bar sb-10" />
            </div>
          </div>
        </div>
      </div>

      {/* Hidden Chat Stream Component for reference */}
      <div className="messages" style={{ display: 'none' }}>
        {messages.slice(-8).map((msg, idx) => <div className={`message ${msg.role}`} key={msg.id || idx}>{msg.text}</div>)}
      </div>
    </section>
  );
}

function Chat({ bootstrap }) {
  const checkpoints = bootstrap?.checkpoints || [];
  const [model, setModel] = useState('latest');
  const [prompt, setPrompt] = useState('');
  const [messages, setMessages] = useState([]);
  const [toolSteps, setToolSteps] = useState([]);
  const [pendingApproval, setPendingApproval] = useState(null);
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  useEffect(() => endRef.current?.scrollIntoView({ behavior: 'smooth' }), [messages]);

  function historyPayload(items = messages) {
    return items
      .filter((msg) => msg.text)
      .slice(-10)
      .map((msg) => ({ role: msg.role, content: msg.text }));
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
      { prompt: text, model_id: model, max_tokens: 256, temperature: 0.7, history: historyPayload(messages) },
      (token) => setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: msg.text + token } : msg)),
      (done) => {
        if (done?.steps) setToolSteps(done.steps);
        if (done?.needs_approval) {
          setPendingApproval({
            prompt: text,
            tool: done.tool,
            tool_args: done.tool_args,
            pending_tool: done.pending_tool || { tool: done.tool, arguments: done.tool_args || {} },
          });
        }
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
        <h2>Neural Playground</h2>
        <select value={model} onChange={(e) => setModel(e.target.value)}>
          {checkpoints.map((item) => <option key={item.id} value={item.id}>{item.label || item.id}</option>)}
        </select>
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
            <p className="muted">Review this tool call before Atulya runs it.</p>
            <pre className="terminal">{JSON.stringify({ tool: pendingApproval.tool, args: pendingApproval.tool_args }, null, 2)}</pre>
            <div className="terminal-actions">
              <button type="button" onClick={() => setPendingApproval(null)}>Cancel</button>
              <button
                type="button"
                className="primary"
                onClick={() => {
                  const approved = pendingApproval.prompt;
                  const id = Date.now();
                  setPendingApproval(null);
                  setBusy(true);
                  setMessages((prev) => [...prev, { role: 'assistant', text: '', id }]);
                  api.streamChat(
                    {
                      prompt: approved,
                      model_id: model,
                      history: historyPayload(),
                      approved_tool: pendingApproval.pending_tool,
                    },
                    (token) => setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: msg.text + token } : msg)),
                    (done) => {
                      if (done?.steps) setToolSteps(done.steps);
                      setBusy(false);
                    },
                    (err) => {
                      setBusy(false);
                      setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: `Error: ${err.message}` } : msg));
                    },
                    (tool) => setToolSteps((prev) => [...prev, tool]),
                  );
                }}
              >
                Approve and run
              </button>
            </div>
          </div>
        </div>
      )}
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

function App() {
  const [tab, setTab] = useState('live');
  const [adminOpen, setAdminOpen] = useState(false);
  const [bootstrap, setBootstrap] = useState(null);
  const [error, setError] = useState('');
  const [authenticated, setAuthenticated] = useState(Boolean(getToken()));
  const [toasts, setToasts] = useState([]);
  
  const currentUser = getUser();
  const isAdmin = currentUser?.role === 'admin';

  function toast(type, message) {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => setToasts((prev) => prev.filter((item) => item.id !== id)), 3500);
  }

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

  const content = useMemo(() => {
    if (tab === 'live') return <LiveMode bootstrap={bootstrap} toast={toast} />;
    if (tab === 'chat') return <Chat bootstrap={bootstrap} />;
    if (!isAdmin) return <LiveMode bootstrap={bootstrap} toast={toast} />; // Fallback for normal users
    
    // Admin-only views
    if (tab === 'dashboard') return <Dashboard bootstrap={bootstrap} load={load} />;
    if (tab === 'model') return <ModelInspector bootstrap={bootstrap} toast={toast} />;
    if (tab === 'training') return <Training bootstrap={bootstrap} load={load} toast={toast} />;
    if (tab === 'users') return <UserManagement toast={toast} />;
    return <Dashboard bootstrap={bootstrap} load={load} />;
  }, [tab, bootstrap, isAdmin]);

  async function handleLogout() {
    try {
      await api.post('/api/auth/logout').catch(() => {});
    } finally {
      clearToken();
      setAuthenticated(false);
      setAdminOpen(false);
      setTab('live');
    }
  }

  if (!authenticated) {
    return <Login onLogin={() => { setAuthenticated(true); load().catch((err) => setError(err.message)); }} />;
  }

  return (
    <main className={tab === 'live' ? 'immersive-layout' : ''}>
      <aside className={adminOpen ? 'admin-drawer open' : 'admin-drawer'}>
        <button className="drawer-close-btn" onClick={() => setAdminOpen(false)}>×</button>
        <h1>Atulya Tantra</h1>
        
        {/* User profile info */}
        <div className="user-profile-hud">
          <small>OPERATOR</small>
          <strong>{currentUser?.display_name || currentUser?.username}</strong>
          <span className="badge small">{currentUser?.role?.toUpperCase()}</span>
        </div>

        <button className={tab === 'live' ? 'active' : ''} onClick={() => { setTab('live'); setAdminOpen(false); }}>Live Mode</button>
        <button className={tab === 'chat' ? 'active' : ''} onClick={() => { setTab('chat'); setAdminOpen(false); }}>Chat</button>
        
        {isAdmin && (
          <>
            <div className="drawer-section-label">DEVELOPER STRANDS</div>
            <button className={tab === 'training' ? 'active' : ''} onClick={() => { setTab('training'); setAdminOpen(false); }}>Training</button>
            <button className={tab === 'model' ? 'active' : ''} onClick={() => { setTab('model'); setAdminOpen(false); }}>Model Inspector</button>
            <button className={tab === 'dashboard' ? 'active' : ''} onClick={() => { setTab('dashboard'); setAdminOpen(false); }}>Dashboard</button>
            <button className={tab === 'users' ? 'active' : ''} onClick={() => { setTab('users'); setAdminOpen(false); }}>Manage Users</button>
          </>
        )}
        
        <button className="logout" onClick={handleLogout}>Logout</button>
      </aside>
      
      <section className="content" style={tab === 'live' ? { padding: 0, overflow: 'hidden' } : {}}>
        {error && <div className="alert">{error}</div>}
        {content}
      </section>

      {/* Floating Gear Settings Toggle - Only show if admin */}
      {isAdmin && (
        <button className="gear-trigger" title="Developer Controls" onClick={() => setAdminOpen(!adminOpen)}>
          ⚙️
        </button>
      )}

      {/* For normal users, show a simple sidebar trigger if not in immersive mode or even in immersive mode to access chat/logout */}
      {!isAdmin && (
        <button className="gear-trigger" title="Navigation Menu" onClick={() => setAdminOpen(!adminOpen)}>
          ☰
        </button>
      )}

      <div className="toasts">
        {toasts.map((item) => <div className={`toast ${item.type}`} key={item.id}>{item.message}</div>)}
      </div>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
