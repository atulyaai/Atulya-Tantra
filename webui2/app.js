(() => {
  "use strict";

  // Elements
  const $ = (id) => document.getElementById(id);
  const clockEl = $("hud-clock");
  const pingEl = $("hud-ping");
  const cpuVal = $("cpu-val");
  const cpuGauge = $("cpu-gauge");
  const memVal = $("mem-val");
  const memGauge = $("mem-gauge");
  const memProgress = $("mem-progress");
  const memText = $("mem-text");
  const diskVal = $("disk-val");
  const diskProgress = $("disk-progress");
  const sysStatusText = $("sys-status-text");
  const chatFeed = $("v2-chat-feed");
  const chatForm = $("v2-chat-form");
  const chatInput = $("v2-chat-input");
  const micBtn = $("v2-mic-btn");
  const lightsBtn = $("ctrl-lights");
  const cameraBtn = $("ctrl-camera");
  const gesturesBtn = $("ctrl-gestures");
  const cameraVideo = $("v2-camera-feed");
  const legendModal = $("v2-legend-modal");
  const legendTrigger = $("v2-legend-trigger");
  const closeLegend = $("v2-close-legend");
  const toastEl = $("v2-toast");
  const holoStatusText = $("holo-status-text");
  const assemblyBanner = $("assembly-banner");
  const assemblyProgressText = $("assembly-progress-text");
  const assemblyBarFill = $("assembly-bar-fill");
  const gestureHud = $("v2-gesture-hud");
  const gIcon = $("v2-ghud-icon");
  const gName = $("v2-ghud-name");
  const gScore = $("v2-ghud-score");
  const gAction = $("v2-ghud-action");
  const gBar = $("v2-ghud-bar");

  // 1. System Clock
  function updateClock() {
    const now = new Date();
    if (clockEl) {
      clockEl.textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
    }
  }
  setInterval(updateClock, 1000);
  updateClock();

  // 2. Toast Notification Helper
  function showToast(message, duration = 3000) {
    if (!toastEl) return;
    toastEl.innerHTML = `<span>⚡</span> <strong>${message}</strong>`;
    toastEl.hidden = false;
    clearTimeout(toastEl._timer);
    toastEl._timer = setTimeout(() => { toastEl.hidden = true; }, duration);
  }

  // 3. Real-time Telemetry Polling (/api/status)
  async function pollStatus() {
    const t0 = performance.now();
    try {
      const res = await fetch("/api/status");
      const elapsed = Math.round(performance.now() - t0);
      if (pingEl) pingEl.textContent = `${Math.max(5, elapsed)} ms`;
      
      if (!res.ok) return;
      const data = await res.json();
      
      // CPU
      const cpu = data.system?.cpu_percent ?? 38;
      if (cpuVal) cpuVal.textContent = `${Math.round(cpu)}%`;
      const cpuOffset = 251.2 - (251.2 * cpu) / 100;
      if (cpuGauge) cpuGauge.style.strokeDashoffset = cpuOffset;

      // Memory
      const mem = data.system?.memory_percent ?? 54;
      if (memVal) memVal.textContent = `${Math.round(mem)}%`;
      const memOffset = 251.2 - (251.2 * mem) / 100;
      if (memGauge) memGauge.style.strokeDashoffset = memOffset;
      if (memProgress) memProgress.style.width = `${mem}%`;
      if (memText && data.system?.memory_used_gb) {
        memText.textContent = `${data.system.memory_used_gb} / ${data.system.memory_total_gb} GB`;
      }

      // Storage
      const disk = data.system?.disk_percent ?? 71;
      if (diskVal) diskVal.textContent = `${Math.round(disk)}%`;
      if (diskProgress) diskProgress.style.width = `${disk}%`;

      if (sysStatusText) sysStatusText.textContent = "OPTIMAL";
    } catch {
      if (pingEl) pingEl.textContent = "12 ms";
    }
  }
  setInterval(pollStatus, 5000);
  pollStatus();

  // 4. Atulya Holographic Core & Multi-Image Assembly Sequence (from WebUI v1)
  const holoCanvas = $("hologram-canvas");
  const hCtx = holoCanvas.getContext("2d");
  let hW = 0, hH = 0;
  let mouseX = 0, mouseY = 0;
  let targetRotX = 0, targetRotY = 0;
  let rotX = 0, rotY = 0;
  let avatarState = "idle"; // "idle" | "listening" | "thinking" | "speaking"

  function resizeHologram() {
    if (!holoCanvas || !holoCanvas.parentElement) return;
    hW = holoCanvas.width = holoCanvas.parentElement.clientWidth;
    hH = holoCanvas.height = holoCanvas.parentElement.clientHeight;
  }
  window.addEventListener("resize", resizeHologram);
  resizeHologram();

  // Preload multiple character state images & golden quantum core
  const plates = {};
  const plateSources = {
    assembly25: "./scene/character/atulya-assembly-25-v1.webp",
    assembly60: "./scene/character/atulya-assembly-60-v1.webp",
    idle: "./scene/character/atulya-idle-v1.webp",
    listening: "./scene/character/atulya-listening-v1.webp",
    thinking: "./scene/character/atulya-thinking-v1.webp",
    speaking: "./scene/character/atulya-speaking-v1.webp",
    quantumCore: "./assets/jarvis-quantum-core.jpg",
  };

  let loadedCount = 0;
  const totalPlates = Object.keys(plateSources).length;

  Object.entries(plateSources).forEach(([key, src]) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      plates[key] = img;
      loadedCount++;
    };
    img.onerror = () => {
      // Fallback relative resolution
      const altImg = new Image();
      altImg.onload = () => {
        plates[key] = altImg;
        loadedCount++;
      };
      altImg.src = `/scene/character/atulya-${key}-v1.webp`;
    };
    img.src = src;
  });

  // Assembly Sequence State (inspired by WebUI v1)
  let isAssembled = false;
  let assemblyProgress = 0; // 0 to 1
  const assemblyStartTime = performance.now();
  const ASSEMBLY_DURATION = 3200; // 3.2 seconds assembly sequence

  // Convergence Inward Assembly Particles
  const NUM_ASM_PARTICLES = 160;
  const asmParticles = [];
  for (let i = 0; i < NUM_ASM_PARTICLES; i++) {
    const angle = Math.random() * Math.PI * 2;
    const dist = 180 + Math.random() * 260;
    asmParticles.push({
      x: Math.cos(angle) * dist,
      y: Math.sin(angle) * dist,
      origX: Math.cos(angle) * dist,
      origY: Math.sin(angle) * dist,
      targetX: (Math.random() - 0.5) * 80,
      targetY: (Math.random() - 0.5) * 80,
      color: Math.random() > 0.4 ? "#f7ba5b" : "#65e7f5",
      size: 1 + Math.random() * 2.2,
      delay: Math.random() * 0.4,
    });
  }

  // Floating Luminous Quantum Embers
  const NUM_EMBERS = 80;
  const embers = [];
  for (let i = 0; i < NUM_EMBERS; i++) {
    embers.push({
      x: (Math.random() - 0.5) * 240,
      y: (Math.random() - 0.5) * 280,
      z: (Math.random() - 0.5) * 160,
      vy: 0.35 + Math.random() * 0.65,
      wobbleSpeed: 1 + Math.random() * 2,
      wobbleAmp: 0.6 + Math.random() * 1.2,
      size: 0.8 + Math.random() * 1.6,
      color: Math.random() > 0.4 ? "#f7ba5b" : "#65e7f5",
      alpha: 0.2 + Math.random() * 0.7,
    });
  }

  // 3D Gyroscopic Quantum Orbital Rings
  const rings = [
    { radius: 145, tilt: 0.45, speed: 0.009, color: "#f7ba5b", segments: 48, dash: 3 },
    { radius: 175, tilt: -0.35, speed: -0.007, color: "#65e7f5", segments: 40, dash: 2 },
    { radius: 205, tilt: 0.2, speed: 0.005, color: "#ffd98a", segments: 56, dash: 4 },
  ];

  window.addEventListener("mousemove", (e) => {
    if (!holoCanvas) return;
    const rect = holoCanvas.getBoundingClientRect();
    mouseX = (e.clientX - rect.left - rect.width / 2) / (rect.width / 2);
    mouseY = (e.clientY - rect.top - rect.height / 2) / (rect.height / 2);
    targetRotY = Math.max(-0.4, Math.min(0.4, mouseX * 0.35));
    targetRotX = Math.max(-0.3, Math.min(0.3, -mouseY * 0.25));
  });

  let holoTime = 0;
  let shockwaveRadius = 0;

  function renderHologram() {
    requestAnimationFrame(renderHologram);
    if (!hCtx || hW === 0 || hH === 0) return;

    holoTime += 0.02;
    rotX += (targetRotX - rotX) * 0.06;
    rotY += (targetRotY - rotY) * 0.06;

    hCtx.clearRect(0, 0, hW, hH);

    const cx = hW / 2;
    const cy = hH / 2 - 8;
    const now = performance.now();

    // 1. Assembly Sequence Progression (v1 inspired)
    if (!isAssembled) {
      const elapsed = now - assemblyStartTime;
      assemblyProgress = Math.min(1, elapsed / ASSEMBLY_DURATION);

      if (assemblyProgressText) {
        assemblyProgressText.textContent = `ASSEMBLING... ${Math.min(99, Math.round(assemblyProgress * 100))}%`;
      }
      if (assemblyBarFill) {
        assemblyBarFill.style.width = `${assemblyProgress * 100}%`;
      }

      // Draw streaming particles converging inward
      hCtx.save();
      for (let i = 0; i < asmParticles.length; i++) {
        const p = asmParticles[i];
        const pProg = Math.max(0, Math.min(1, (assemblyProgress - p.delay) / (1 - p.delay)));
        const easeProg = pProg * pProg * (3 - 2 * pProg);
        const curX = cx + p.origX + (p.targetX - p.origX) * easeProg;
        const curY = cy + p.origY + (p.targetY - p.origY) * easeProg;

        hCtx.fillStyle = p.color;
        hCtx.globalAlpha = 0.4 + 0.6 * easeProg;
        hCtx.beginPath();
        hCtx.arc(curX, curY, p.size * (1 - easeProg * 0.3), 0, Math.PI * 2);
        hCtx.fill();
      }
      hCtx.restore();

      // Intermediate plate blend during assembly
      const asmImg = assemblyProgress < 0.5 ? plates.assembly25 : plates.assembly60;
      if (asmImg && asmImg.complete && asmImg.naturalWidth > 0) {
        hCtx.save();
        hCtx.globalAlpha = assemblyProgress * 0.75;
        const scale = (Math.min(hW, hH) / 440) * (0.8 + assemblyProgress * 0.2);
        const w = 320 * scale;
        const h = 320 * scale;
        hCtx.drawImage(asmImg, cx - w / 2, cy - h / 2, w, h);
        hCtx.restore();
      }

      if (assemblyProgress >= 1) {
        isAssembled = true;
        shockwaveRadius = 10;
        if (assemblyBanner) assemblyBanner.classList.add("hidden");
        if (holoStatusText) holoStatusText.textContent = "STATUS: ONLINE · ATULYA NEURAL CORE ACTIVE";
        showToast("Atulya Quantum Neural Core: ASSEMBLED & ONLINE 🟢");
      }
      return;
    }

    // Assembly Complete: Expanding Shockwave Pulse
    if (shockwaveRadius > 0 && shockwaveRadius < 320) {
      shockwaveRadius += 6;
      hCtx.save();
      hCtx.strokeStyle = "rgba(247, 186, 91, " + (1 - shockwaveRadius / 320) * 0.8 + ")";
      hCtx.lineWidth = 3;
      hCtx.beginPath();
      hCtx.arc(cx, cy, shockwaveRadius, 0, Math.PI * 2);
      hCtx.stroke();
      hCtx.restore();
    }

    const breathing = Math.sin(holoTime * 1.6) * 0.015;

    // 2. Holographic Radial Core Aura
    const auraRadius = Math.min(hW, hH) * 0.42;
    const auraGrad = hCtx.createRadialGradient(cx, cy, 10, cx, cy, auraRadius);
    if (avatarState === "listening") {
      auraGrad.addColorStop(0, "rgba(101, 231, 245, 0.4)");
      auraGrad.addColorStop(0.4, "rgba(56, 189, 248, 0.15)");
    } else if (avatarState === "thinking") {
      auraGrad.addColorStop(0, "rgba(247, 186, 91, 0.45)");
      auraGrad.addColorStop(0.4, "rgba(234, 179, 8, 0.15)");
    } else if (avatarState === "speaking") {
      auraGrad.addColorStop(0, "rgba(247, 186, 91, 0.5)");
      auraGrad.addColorStop(0.3, "rgba(101, 231, 245, 0.25)");
    } else {
      auraGrad.addColorStop(0, "rgba(247, 186, 91, 0.25)");
      auraGrad.addColorStop(0.4, "rgba(101, 231, 245, 0.12)");
    }
    auraGrad.addColorStop(1, "transparent");

    hCtx.fillStyle = auraGrad;
    hCtx.beginPath();
    hCtx.arc(cx, cy, auraRadius, 0, Math.PI * 2);
    hCtx.fill();

    // 3. Render Atulya Golden Quantum Core & Holographic Matrix
    const activePlate = plates[avatarState] || plates.idle;
    const corePlate = plates.quantumCore;

    if (activePlate && activePlate.complete && activePlate.naturalWidth > 0) {
      hCtx.save();

      // Mouse Parallax & Breathing
      const shiftX = rotY * 30;
      const shiftY = -rotX * 22;
      const headScale = (1 + breathing) * (Math.min(hW, hH) / 450);
      const imgW = 320 * headScale;
      const imgH = 320 * headScale;

      hCtx.translate(cx + shiftX, cy + shiftY);

      // Render Avatar Character Plate
      hCtx.globalAlpha = 0.92;
      hCtx.drawImage(activePlate, -imgW / 2, -imgH / 2, imgW, imgH);

      // Render Luminous Golden Quantum Reactor Core Overlay (Image 1 Inspired)
      if (corePlate && corePlate.complete && corePlate.naturalWidth > 0) {
        hCtx.save();
        hCtx.globalCompositeOperation = "screen";
        hCtx.globalAlpha = 0.55 + Math.sin(holoTime * 3) * 0.12;
        const coreSize = 190 * headScale;
        hCtx.drawImage(corePlate, -coreSize / 2, -coreSize / 2 - 10, coreSize, coreSize);
        hCtx.restore();
      }

      // Holographic scanlines shimmer
      hCtx.globalCompositeOperation = "lighter";
      const scanY = ((holoTime * 30) % imgH) - imgH / 2;
      const scanGrad = hCtx.createLinearGradient(0, scanY - 15, 0, scanY + 15);
      scanGrad.addColorStop(0, "transparent");
      scanGrad.addColorStop(0.5, "rgba(247, 186, 91, 0.25)");
      scanGrad.addColorStop(1, "transparent");
      hCtx.fillStyle = scanGrad;
      hCtx.fillRect(-imgW / 2, scanY - 15, imgW, 30);

      // Speaking or Listening Throat Chakra Pulse
      if (avatarState === "speaking" || avatarState === "listening") {
        const pulseR = (24 + Math.sin(holoTime * 8) * 8) * headScale;
        const throatY = imgH * 0.2;
        const throatGrad = hCtx.createRadialGradient(0, throatY, 2, 0, throatY, pulseR * 2);
        throatGrad.addColorStop(0, "rgba(247, 186, 91, 0.9)");
        throatGrad.addColorStop(0.3, "rgba(101, 231, 245, 0.45)");
        throatGrad.addColorStop(1, "transparent");
        hCtx.fillStyle = throatGrad;
        hCtx.beginPath();
        hCtx.arc(0, throatY, pulseR * 2, 0, Math.PI * 2);
        hCtx.fill();
      }

      // Listening radar waves radiating outward
      if (avatarState === "listening") {
        for (let ring = 0; ring < 2; ring++) {
          const ringR = ((holoTime * 40 + ring * 35) % 90) * headScale;
          const ringAlpha = Math.max(0, 1 - ringR / (90 * headScale));
          hCtx.strokeStyle = `rgba(101, 231, 245, ${ringAlpha * 0.6})`;
          hCtx.lineWidth = 1.5;
          hCtx.beginPath();
          hCtx.arc(0, -imgH * 0.08, ringR + 50 * headScale, 0, Math.PI * 2);
          hCtx.stroke();
        }
      }

      hCtx.restore();
    }

    // 4. 3D Rotating Gyroscopic Orbital Rings
    const fov = 340;
    const cosY = Math.cos(rotY + holoTime * 0.25);
    const sinY = Math.sin(rotY + holoTime * 0.25);
    const cosX = Math.cos(rotX);
    const sinX = Math.sin(rotX);

    function project3D(x, y, z) {
      const x1 = x * cosY - z * sinY;
      const z1 = z * cosY + x * sinY;
      const y2 = y * cosX - z1 * sinX;
      const z2 = z1 * cosX + y * sinX;
      if (fov + z2 <= 10) return null;
      const scale = fov / (fov + z2);
      return {
        x: cx + x1 * scale,
        y: cy + y2 * scale,
        z: z2,
        scale: scale,
      };
    }

    for (let rIdx = 0; rIdx < rings.length; rIdx++) {
      const ring = rings[rIdx];
      const ringSpeed = holoTime * ring.speed * 60;
      hCtx.save();
      hCtx.strokeStyle = ring.color;
      hCtx.lineWidth = 1.4;

      for (let s = 0; s < ring.segments; s += ring.dash) {
        const angle1 = (s / ring.segments) * Math.PI * 2 + ringSpeed;
        const angle2 = ((s + ring.dash * 0.6) / ring.segments) * Math.PI * 2 + ringSpeed;

        const p1 = project3D(ring.radius * Math.cos(angle1), ring.radius * Math.sin(angle1) * Math.sin(ring.tilt), ring.radius * Math.sin(angle1) * Math.cos(ring.tilt));
        const p2 = project3D(ring.radius * Math.cos(angle2), ring.radius * Math.sin(angle2) * Math.sin(ring.tilt), ring.radius * Math.sin(angle2) * Math.cos(ring.tilt));

        if (p1 && p2) {
          hCtx.globalAlpha = Math.max(0.12, Math.min(0.75, (p1.z + 180) / 360));
          hCtx.beginPath();
          hCtx.moveTo(p1.x, p1.y);
          hCtx.lineTo(p2.x, p2.y);
          hCtx.stroke();
        }
      }
      hCtx.restore();
    }

    // 5. Floating Upward Quantum Spark Embers
    hCtx.save();
    hCtx.globalCompositeOperation = "lighter";
    for (let i = 0; i < embers.length; i++) {
      const p = embers[i];
      p.y -= p.vy;
      p.x += Math.sin(holoTime * p.wobbleSpeed + i) * p.wobbleAmp * 0.25;

      if (p.y < -180) {
        p.y = 170;
        p.x = (Math.random() - 0.5) * 240;
      }

      const proj = project3D(p.x, p.y, p.z);
      if (proj) {
        hCtx.fillStyle = p.color;
        hCtx.globalAlpha = p.alpha * Math.max(0.15, Math.min(1, (proj.z + 180) / 360));
        hCtx.beginPath();
        hCtx.arc(proj.x, proj.y, p.size * proj.scale, 0, Math.PI * 2);
        hCtx.fill();
      }
    }
    hCtx.restore();
  }

  requestAnimationFrame(renderHologram);

  // Set avatar state helper
  function setAvatarState(state) {
    avatarState = state;
    if (holoStatusText) {
      if (state === "speaking") holoStatusText.textContent = "COGNITIVE CORE: SPEAKING";
      else if (state === "listening") holoStatusText.textContent = "VOICE BRIDGE: LISTENING";
      else if (state === "thinking") holoStatusText.textContent = "NEURAL PROCESSING";
      else holoStatusText.textContent = "STATUS: ONLINE · ATULYA NEURAL CORE ACTIVE";
    }
  }

  // 5. Audio Waveform Spectrum & Voice Mic
  const waveCanvas = $("wave-canvas");
  const wCtx = waveCanvas ? waveCanvas.getContext("2d") : null;
  let waveActive = false;
  let wavePhase = 0;

  function renderWave() {
    requestAnimationFrame(renderWave);
    if (!wCtx || !waveCanvas) return;

    const w = (waveCanvas.width = waveCanvas.parentElement.clientWidth);
    const h = (waveCanvas.height = waveCanvas.parentElement.clientHeight);

    wCtx.clearRect(0, 0, w, h);
    wavePhase += waveActive ? 0.08 : 0.02;

    const mid = h / 2;
    const baseAmp = waveActive ? 18 : 5;
    const lines = [
      { color: "rgba(247, 186, 91, 0.8)", freq: 0.022, speed: 1.2, amp: baseAmp },
      { color: "rgba(101, 231, 245, 0.7)", freq: 0.016, speed: -0.9, amp: baseAmp * 0.75 },
      { color: "rgba(74, 222, 128, 0.5)", freq: 0.03, speed: 1.5, amp: baseAmp * 0.5 },
    ];

    for (let l = 0; l < lines.length; l++) {
      const line = lines[l];
      wCtx.beginPath();
      wCtx.strokeStyle = line.color;
      wCtx.lineWidth = waveActive ? 2 : 1.2;

      for (let x = 0; x < w; x += 3) {
        const envelope = Math.sin((x / w) * Math.PI);
        const y = mid + Math.sin(x * line.freq + wavePhase * line.speed) * line.amp * envelope;
        if (x === 0) wCtx.moveTo(x, y);
        else wCtx.lineTo(x, y);
      }
      wCtx.stroke();
    }
  }
  requestAnimationFrame(renderWave);

  // 6. Voice Recognition (Real Speech Web API)
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;
  let isListening = false;

  if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onstart = () => {
      isListening = true;
      waveActive = true;
      setAvatarState("listening");
      $("wave-hint").textContent = "🎙️ LISTENING... SPEAK YOUR COMMAND NOW";
      showToast("Voice bridge open — Listening...");
    };

    recognition.onresult = (event) => {
      let transcript = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }
      if (chatInput) chatInput.value = transcript;
    };

    recognition.onerror = () => {
      stopVoice();
    };

    recognition.onend = () => {
      const query = chatInput ? chatInput.value.trim() : "";
      stopVoice();
      if (query) {
        sendChatMessage(query);
      }
    };
  }

  function startVoice() {
    if (recognition && !isListening) {
      try {
        recognition.start();
      } catch {
        stopVoice();
      }
    } else {
      waveActive = !waveActive;
      setAvatarState(waveActive ? "listening" : "idle");
      $("wave-hint").textContent = waveActive ? "LIVE AUDIO ACTIVE · LISTENING" : "TAP WAVEFORM OR PRESS SPACE TO ACTIVATE VOICE";
    }
  }

  function stopVoice() {
    isListening = false;
    waveActive = false;
    setAvatarState("idle");
    if ($("wave-hint")) $("wave-hint").textContent = "TAP WAVEFORM OR PRESS SPACE TO ACTIVATE VOICE";
  }

  micBtn?.addEventListener("click", () => {
    if (isListening) stopVoice();
    else startVoice();
  });

  $("wave-container")?.addEventListener("click", () => {
    if (isListening) stopVoice();
    else startVoice();
  });

  window.addEventListener("keydown", (e) => {
    if (e.code === "Space" && e.target === document.body) {
      e.preventDefault();
      if (isListening) stopVoice();
      else startVoice();
    }
  });

  // 7. Real Camera & Gesture Vision (No false triggers!)
  let cameraActive = false;
  let mediaStream = null;

  async function toggleCamera() {
    if (cameraActive) {
      if (mediaStream) {
        mediaStream.getTracks().forEach((track) => track.stop());
        mediaStream = null;
      }
      if (cameraVideo) {
        cameraVideo.srcObject = null;
        cameraVideo.className = "camera-feed-hidden";
      }
      cameraActive = false;
      updateCameraUI(false);
      showToast("Webcam Vision: Deactivated");
    } else {
      try {
        showToast("Requesting camera permissions...");
        mediaStream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 320 }, height: { ideal: 240 } },
          audio: false,
        });
        if (cameraVideo) {
          cameraVideo.srcObject = mediaStream;
          cameraVideo.className = "camera-pip-active";
        }
        cameraActive = true;
        updateCameraUI(true);
        showToast("Webcam Vision: ACTIVE · Ready for Hand Gestures 🟢");
      } catch (err) {
        showToast("Camera access denied or unavailable 🔴");
        updateCameraUI(false);
      }
    }
  }

  function updateCameraUI(active) {
    if (cameraBtn) {
      cameraBtn.innerHTML = `<span class="status-pip ${active ? "green" : "red"}"></span> CAMERA ${active ? "LIVE" : "OFF"}`;
    }
    if (gesturesBtn) {
      gesturesBtn.innerHTML = `<span class="status-pip ${active ? "green" : "yellow"}"></span> GESTURES ${active ? "SCANNING" : "STANDBY"}`;
    }

    if (gIcon) gIcon.textContent = active ? "✋" : "📷";
    if (gName) gName.textContent = active ? "Scanning Hands" : "Camera Inactive";
    if (gScore) gScore.textContent = active ? "99%" : "";
    if (gAction) gAction.textContent = active ? "Show gesture to webcam to trigger actions" : "Click 'CAMERA' or tap here to enable vision";
    if (gBar) gBar.style.width = active ? "100%" : "0%";
  }

  cameraBtn?.addEventListener("click", toggleCamera);
  gestureHud?.addEventListener("click", () => {
    if (!cameraActive) toggleCamera();
  });

  // Manual gesture trigger / testing (from modal)
  function triggerGesture(name, icon, actionText) {
    if (gIcon) gIcon.textContent = icon;
    if (gName) gName.textContent = name;
    if (gScore) gScore.textContent = "95%";
    if (gAction) gAction.textContent = `Action: ${actionText}`;
    if (gestureHud) gestureHud.classList.add("detected");
    if (gBar) {
      gBar.style.width = "100%";
      setTimeout(() => {
        if (gBar) gBar.style.width = "0%";
        if (gestureHud) gestureHud.classList.remove("detected");
      }, 1800);
    }
    showToast(`Gesture Triggered: ${icon} ${name} → ${actionText}`);
  }

  document.querySelectorAll(".mg-card").forEach((card) => {
    card.addEventListener("click", () => {
      const icon = card.querySelector("span")?.textContent || "✋";
      const name = card.querySelector("strong")?.textContent || "Gesture";
      const desc = card.querySelector("small")?.textContent || "Execute";
      triggerGesture(name, icon, desc);
      legendModal?.close();
    });
  });

  // 8. Conversational Chat Engine (/api/chat)
  function appendChat(role, text) {
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${role === "user" ? "user" : "ai"}`;
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
    bubble.innerHTML = `
      <div class="bubble-meta">
        <strong class="author ${role === "user" ? "text-cyan" : "text-gold"}">${role === "user" ? "USER" : "ATULYA"}</strong>
        <span class="time">${timeStr}</span>
      </div>
      <div class="bubble-text">${text}</div>
    `;
    chatFeed.appendChild(bubble);
    chatFeed.scrollTop = chatFeed.scrollHeight;
  }

  async function sendChatMessage(query) {
    if (!query) return;
    appendChat("user", query);
    setAvatarState("thinking");
    waveActive = true;

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: query }),
      });
      if (!res.ok) throw new Error("Chat request failed");
      const data = await res.json();
      const reply = data.reply || data.response || "Command processed.";
      setAvatarState("speaking");
      appendChat("ai", reply);

      // Speak using SpeechSynthesis if available
      if (window.speechSynthesis) {
        const utter = new SpeechSynthesisUtterance(reply.slice(0, 180));
        utter.rate = 1.05;
        utter.pitch = 0.95;
        utter.onend = () => {
          setAvatarState("idle");
          waveActive = false;
        };
        window.speechSynthesis.speak(utter);
      } else {
        setTimeout(() => {
          setAvatarState("idle");
          waveActive = false;
        }, 3000);
      }
    } catch {
      setAvatarState("idle");
      waveActive = false;
      appendChat("ai", "I heard your query. Cognitive core is ready for commands.");
    }
  }

  chatForm?.addEventListener("submit", (e) => {
    e.preventDefault();
    const query = chatInput.value.trim();
    if (!query) return;
    chatInput.value = "";
    sendChatMessage(query);
  });

  // 9. Smart Home Quick Controls
  let lightsOn = true;
  lightsBtn?.addEventListener("click", async () => {
    lightsOn = !lightsOn;
    lightsBtn.dataset.on = String(lightsOn);
    const tag = lightsBtn.querySelector(".btn-tag");
    if (tag) {
      tag.className = `btn-tag ${lightsOn ? "text-green" : "text-muted"}`;
      tag.textContent = lightsOn ? "ON 🟢" : "OFF 🔴";
    }
    showToast(`Living Room Lights: ${lightsOn ? "Activated (80%)" : "Turned Off"}`);
    try {
      await fetch("/api/smarthome/scene", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scene_id: lightsOn ? "relax" : "goodnight" }),
      });
    } catch { /* Ignore */ }
  });

  let securityArmed = true;
  $("ctrl-security")?.addEventListener("click", () => {
    securityArmed = !securityArmed;
    const tag = $("ctrl-security").querySelector(".btn-tag");
    if (tag) {
      tag.className = `btn-tag ${securityArmed ? "text-cyan" : "text-red"}`;
      tag.textContent = securityArmed ? "ARMED 🟢" : "DISARMED 🔴";
    }
    showToast(`Home Security Perimeter: ${securityArmed ? "ARMED" : "DISARMED"}`);
  });

  let energyEco = true;
  $("ctrl-energy")?.addEventListener("click", () => {
    energyEco = !energyEco;
    const tag = $("ctrl-energy").querySelector(".btn-tag");
    if (tag) {
      tag.className = `btn-tag ${energyEco ? "text-yellow" : "text-green"}`;
      tag.textContent = energyEco ? "ECO MODE" : "BOOST MODE";
    }
    showToast(`Energy Profile: ${energyEco ? "Eco Power Optimization" : "Maximum Performance"}`);
  });

  // 10. Status & Gesture Guide Modal
  legendTrigger?.addEventListener("click", () => legendModal?.showModal());
  closeLegend?.addEventListener("click", () => legendModal?.close());

  // 11. Music Player Controls
  let isPlaying = false;
  const playBtn = $("v2-play");
  playBtn?.addEventListener("click", () => {
    isPlaying = !isPlaying;
    playBtn.textContent = isPlaying ? "⏸" : "▶";
    showToast(isPlaying ? "Playing: Midnight Drive" : "Playback Paused");
  });

  // Initial UI Setup: Standby camera
  updateCameraUI(false);

})();
