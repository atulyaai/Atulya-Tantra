(() => {
  "use strict";

  // Elements
  const $ = (id) => document.getElementById(id);
  const clockEl = $("hud-clock");
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
  const legendModal = $("v2-legend-modal");
  const legendTrigger = $("v2-legend-trigger");
  const closeLegend = $("v2-close-legend");
  const toastEl = $("v2-toast");

  // 1. System Clock
  function updateClock() {
    const now = new Date();
    clockEl.textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
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
    try {
      const res = await fetch("/api/status");
      if (!res.ok) return;
      const data = await res.json();
      
      // CPU
      const cpu = data.system?.cpu_percent ?? 38;
      cpuVal.textContent = `${Math.round(cpu)}%`;
      const cpuOffset = 251.2 - (251.2 * cpu) / 100;
      cpuGauge.style.strokeDashoffset = cpuOffset;

      // Memory
      const mem = data.system?.memory_percent ?? 54;
      memVal.textContent = `${Math.round(mem)}%`;
      const memOffset = 251.2 - (251.2 * mem) / 100;
      memGauge.style.strokeDashoffset = memOffset;
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
      // Fallback display
    }
  }
  setInterval(pollStatus, 4000);
  pollStatus();

  // 4. Interactive 3D Particle Hologram Head
  const holoCanvas = $("hologram-canvas");
  const hCtx = holoCanvas.getContext("2d");
  let hW, hH;
  let mouseX = 0, mouseY = 0;
  let targetRotX = 0, targetRotY = 0;
  let rotX = 0, rotY = 0;

  function resizeHologram() {
    hW = holoCanvas.width = holoCanvas.parentElement.clientWidth;
    hH = holoCanvas.height = holoCanvas.parentElement.clientHeight;
  }
  window.addEventListener("resize", resizeHologram);
  resizeHologram();

  // Generate 3D point cloud resembling cybernetic head & orbital rings
  const particles = [];
  const NUM_PARTICLES = 500;
  for (let i = 0; i < NUM_PARTICLES; i++) {
    const theta = Math.acos(2 * Math.random() - 1);
    const phi = 2 * Math.PI * Math.random();
    const r = 130 + Math.random() * 20;
    particles.push({
      x: r * Math.sin(theta) * Math.cos(phi) * 0.75,
      y: r * Math.cos(theta) * 1.15,
      z: r * Math.sin(theta) * Math.sin(phi) * 0.75,
      baseR: r,
      color: Math.random() > 0.3 ? "#65e7f5" : "#f7ba5b",
      size: 1 + Math.random() * 2,
    });
  }

  // Orbital Rings
  const ringPoints = [];
  for (let ring = 0; ring < 3; ring++) {
    const rRadius = 180 + ring * 35;
    const tilt = (ring - 1) * 0.45;
    for (let j = 0; j < 60; j++) {
      const angle = (j / 60) * Math.PI * 2;
      ringPoints.push({
        x: rRadius * Math.cos(angle),
        y: rRadius * Math.sin(angle) * Math.sin(tilt),
        z: rRadius * Math.sin(angle) * Math.cos(tilt),
        color: ring === 1 ? "#f7ba5b" : "#65e7f5",
        size: 1.5,
        speed: 0.005 * (ring % 2 === 0 ? 1 : -1),
      });
    }
  }

  window.addEventListener("mousemove", (e) => {
    const rect = holoCanvas.getBoundingClientRect();
    mouseX = (e.clientX - rect.left - rect.width / 2) / (rect.width / 2);
    mouseY = (e.clientY - rect.top - rect.height / 2) / (rect.height / 2);
    targetRotY = mouseX * 0.4;
    targetRotX = -mouseY * 0.3;
  });

  let holoTime = 0;
  function renderHologram() {
    holoTime += 0.015;
    rotX += (targetRotX - rotX) * 0.05;
    rotY += (targetRotY - rotY) * 0.05;

    hCtx.clearRect(0, 0, hW, hH);

    const cx = hW / 2;
    const cy = hH / 2 - 10;
    const fov = 380;

    // Draw central energy core glow
    const coreGrad = hCtx.createRadialGradient(cx, cy, 10, cx, cy, 140);
    coreGrad.addColorStop(0, "rgba(247, 186, 91, 0.25)");
    coreGrad.addColorStop(0.5, "rgba(101, 231, 245, 0.1)");
    coreGrad.addColorStop(1, "transparent");
    hCtx.fillStyle = coreGrad;
    hCtx.beginPath();
    hCtx.arc(cx, cy, 140, 0, Math.PI * 2);
    hCtx.fill();

    // Render & Rotate Particles
    const cosY = Math.cos(rotY + holoTime * 0.2);
    const sinY = Math.sin(rotY + holoTime * 0.2);
    const cosX = Math.cos(rotX);
    const sinX = Math.sin(rotX);

    for (let i = 0; i < particles.length; i++) {
      const p = particles[i];
      // Y rotation
      const x1 = p.x * cosY - p.z * sinY;
      const z1 = p.z * cosY + p.x * sinY;
      // X rotation
      const y2 = p.y * cosX - z1 * sinX;
      const z2 = z1 * cosX + p.y * sinX;

      const scale = fov / (fov + z2);
      const px = cx + x1 * scale;
      const py = cy + y2 * scale;
      const alpha = Math.max(0.15, Math.min(1, (z2 + 200) / 400));

      hCtx.fillStyle = p.color;
      hCtx.globalAlpha = alpha;
      hCtx.beginPath();
      hCtx.arc(px, py, p.size * scale, 0, Math.PI * 2);
      hCtx.fill();
    }

    // Render Orbital Rings
    for (let k = 0; k < ringPoints.length; k++) {
      const rp = ringPoints[k];
      const rCos = Math.cos(rotY + holoTime * 0.5);
      const rSin = Math.sin(rotY + holoTime * 0.5);
      const rx1 = rp.x * rCos - rp.z * rSin;
      const rz1 = rp.z * rCos + rp.x * rSin;
      const ry2 = rp.y * cosX - rz1 * sinX;
      const rz2 = rz1 * cosX + rp.y * sinX;

      const scale = fov / (fov + rz2);
      const px = cx + rx1 * scale;
      const py = cy + ry2 * scale;

      hCtx.fillStyle = rp.color;
      hCtx.globalAlpha = Math.max(0.1, (rz2 + 200) / 400);
      hCtx.beginPath();
      hCtx.arc(px, py, rp.size * scale, 0, Math.PI * 2);
      hCtx.fill();
    }

    hCtx.globalAlpha = 1;
    requestAnimationFrame(renderHologram);
  }
  renderHologram();

  // 5. Luminous Cybernetic Audio Waveform
  const waveCanvas = $("wave-canvas");
  const wCtx = waveCanvas.getContext("2d");
  let wW, wH;
  let waveActive = false;

  function resizeWave() {
    wW = waveCanvas.width = waveCanvas.parentElement.clientWidth;
    wH = waveCanvas.height = waveCanvas.parentElement.clientHeight;
  }
  window.addEventListener("resize", resizeWave);
  resizeWave();

  let waveStep = 0;
  function renderWave() {
    waveStep += 0.04;
    wCtx.clearRect(0, 0, wW, wH);

    const centerY = wH / 2;
    const baseAmp = waveActive ? 28 : 10;

    // Cyan Harmonic Wave
    wCtx.beginPath();
    wCtx.strokeStyle = "#65e7f5";
    wCtx.lineWidth = 2.5;
    wCtx.shadowColor = "rgba(101, 231, 245, 0.8)";
    wCtx.shadowBlur = 12;

    for (let x = 0; x < wW; x += 4) {
      const env = Math.sin((x / wW) * Math.PI);
      const y = centerY + Math.sin(x * 0.02 + waveStep) * baseAmp * env + Math.sin(x * 0.05 - waveStep * 1.5) * (baseAmp * 0.4) * env;
      if (x === 0) wCtx.moveTo(x, y);
      else wCtx.lineTo(x, y);
    }
    wCtx.stroke();

    // Amber Harmonic Wave
    wCtx.beginPath();
    wCtx.strokeStyle = "#f7ba5b";
    wCtx.lineWidth = 2;
    wCtx.shadowColor = "rgba(247, 186, 91, 0.8)";
    wCtx.shadowBlur = 10;

    for (let x = 0; x < wW; x += 4) {
      const env = Math.sin((x / wW) * Math.PI);
      const y = centerY + Math.sin(x * 0.03 - waveStep * 1.2) * (baseAmp * 0.8) * env + Math.cos(x * 0.06 + waveStep) * (baseAmp * 0.3) * env;
      if (x === 0) wCtx.moveTo(x, y);
      else wCtx.lineTo(x, y);
    }
    wCtx.stroke();
    wCtx.shadowBlur = 0;

    requestAnimationFrame(renderWave);
  }
  renderWave();

  // Click wave to toggle active speaking/listening animation
  $("wave-container")?.addEventListener("click", () => {
    waveActive = !waveActive;
    $("wave-hint").textContent = waveActive ? "LIVE AUDIO STREAM ACTIVE · LISTENING" : "TAP WAVEFORM OR PRESS SPACE TO ACTIVATE VOICE";
  });

  // 6. Conversational Chat Engine (/api/chat)
  function appendChat(role, text) {
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${role === "user" ? "user" : "ai"}`;
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
    bubble.innerHTML = `
      <div class="bubble-meta">
        <strong class="author ${role === "user" ? "text-gold" : "text-cyan"}">${role === "user" ? "USER" : "ATULYA"}</strong>
        <span class="time">${timeStr}</span>
      </div>
      <div class="bubble-text">${text}</div>
    `;
    chatFeed.appendChild(bubble);
    chatFeed.scrollTop = chatFeed.scrollHeight;
  }

  chatForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = chatInput.value.trim();
    if (!query) return;
    chatInput.value = "";
    appendChat("user", query);

    waveActive = true;
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: query }),
      });
      if (!res.ok) throw new Error("Chat request failed");
      const data = await res.json();
      appendChat("ai", data.reply || data.response || "Command processed.");
    } catch {
      appendChat("ai", "I heard you, but brain response timed out. Tools and local memory remain operational.");
    } finally {
      setTimeout(() => { waveActive = false; }, 2000);
    }
  });

  // 7. Smart Home Scene Toggle
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

  // 8. Security Arm Toggle
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

  // 9. Status & Gesture Guide Modal
  legendTrigger?.addEventListener("click", () => legendModal?.showModal());
  closeLegend?.addEventListener("click", () => legendModal?.close());

  // 10. Music Player Interactivity
  let isPlaying = false;
  const playBtn = $("v2-play");
  playBtn?.addEventListener("click", () => {
    isPlaying = !isPlaying;
    playBtn.textContent = isPlaying ? "⏸" : "▶";
    showToast(isPlaying ? "Playing: Midnight Drive" : "Playback Paused");
  });

  // 11. Gesture HUD Demonstration Simulation
  const gestureHud = $("v2-gesture-hud");
  const gName = $("v2-ghud-name");
  const gScore = $("v2-ghud-score");
  const gAction = $("v2-ghud-action");
  const gBar = $("v2-ghud-bar");

  const sampleGestures = [
    { icon: "✋", name: "Open Palm", score: "92%", action: "Stop Speech & Audio" },
    { icon: "👍", name: "Thumbs Up", score: "88%", action: "Confirm / Send 'Yes'" },
    { icon: "✌️", name: "Victory", score: "95%", action: "Camera Snapshot & Inspect" },
  ];
  let gIndex = 0;
  setInterval(() => {
    const g = sampleGestures[gIndex % sampleGestures.length];
    gIndex++;
    if (gName) gName.textContent = g.name;
    if (gScore) gScore.textContent = g.score;
    if (gAction) gAction.textContent = `Action: ${g.action}`;
    if (gBar) {
      gBar.style.width = "100%";
      setTimeout(() => { if (gBar) gBar.style.width = "0%"; }, 1500);
    }
  }, 5000);

})();
