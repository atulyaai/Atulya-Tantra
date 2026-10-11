(() => {
  const $ = (selector) => document.querySelector(selector);
  const canvas = $("#voice-wave");
  const ctx = canvas.getContext("2d");
  const waveform = $("#wave-control");
  const status = $("#assistant-status");
  const statusDetail = $("#assistant-detail");
  const sessionState = $("#session-state");
  const historyStatus = $("#history-status");
  const connectionDot = $("#connection-dot");
  const textChannel = $("#text-channel");
  const voiceChannel = $("#voice-channel");
  const visionChannel = $("#vision-channel");
  const waveHelp = $("#wave-help");
  const cameraPreview = $("#camera-preview");
  const cameraFeed = $("#camera-feed");
  const cameraToggle = $("#camera-toggle");
  const cameraDevice = $("#camera-device");
  const form = $("#chat-form");
  const prompt = $("#chat-prompt");
  const messagesNode = $("#chat-messages");
  const systemDashboard = $("#system-dashboard");
  const systemOverview = $("#system-overview");
  const layoutToast = $("#layout-toast");
  const layoutFocusExit = $("#layout-focus-exit");
  const layoutVoiceToggle = $("#layout-voice-toggle");
  const cameraBus = "BroadcastChannel" in window ? new BroadcastChannel("atulya-camera") : null;
  const pageId = crypto.randomUUID?.() || `camera_${Date.now()}_${Math.random().toString(36).slice(2)}`;
  const conversation = [];
  let conversationId = getConversationId();
  const historyDialog = $("#history-dialog");
  const historyList = $("#history-list");
  const pluginDialog = $("#plugin-dialog");
  const pluginList = $("#plugin-list");
  const authDialog = $("#auth-dialog");
  const authMessage = $("#auth-message");
  const authActivate = $("#auth-activate");
  const authJoin = $("#auth-join");
  const addPasskeyButton = $("#add-passkey");
  const manageUsersButton = $("#manage-users");
  const authSetupTokenWrap = $("#auth-setup-token-wrap");
  const authSetupToken = $("#auth-setup-token");
  const authInviteWrap = $("#auth-invite-wrap");
  const authInviteToken = $("#auth-invite-token");
  const signOutButton = $("#sign-out");
  const usersDialog = $("#users-dialog");
  const usersList = $("#users-list");
  const inviteUserForm = $("#invite-user-form");
  const inviteDisplayName = $("#invite-display-name");
  const inviteResult = $("#invite-result");
  let authSetupRequired = false;
  let applicationStarted = false;
  let selectedArchiveId = conversationId;
  let historyWrites = Promise.resolve();
  let historyReady = false;
  let healthLoaded = false;
  let sceneReady = false;
  let greeted = false;
  let listening = false;
  let voiceSessionActive = false;
  let speechDetected = false;
  let lastSpeechAt = 0;
  let noiseFloor = 0.003;
  let speaking = false;
  let microphoneStream;
  let cameraStream;
  let cameraStartPromise;
  let gestureRecognizer;
  let gestureFrame = 0;
  let lastGestureFrameAt = 0;
  let gestureCurrent = "";
  let gestureModelReady = false;
  let gestureAssetsReady = false;
  let gestureCommandCandidate = "";
  let gestureCommandCandidateSince = 0;
  let gestureNeutralSince = 0;
  let gestureCommandsArmed = true;
  let lastGestureCommandAt = 0;
  const gestureCommandThreshold = 0.82;
  const gestureCommandHoldMs = 900;
  const gestureCommandCooldownMs = 2800;
  const gestureReleaseMs = 550;
  let cameraFormat = "";
  let cameraFocus = "";
  let cameraDeviceLabel = "";
  let selectedCameraDeviceId = "";
  let cameraIssue = "";
  let layoutToastTimer = 0;
  let lastMeetingNotifiedId = "";

  function showGestureResult(label) {
    const result = $("#gesture-result");
    if (result) result.textContent = label;
  }
  let microphoneContext;
  let microphoneAnalyser;
  let speechAnalyser;
  let speechAudioContext;
  let activeAudio;
  let activeAudioUrl;
  let activeAudioRequest = 0;
  let animationFrame = 0;
  let recorder;
  let recorderChunks = [];
  let recordingMime = "audio/webm";
  let voiceRequest = 0;
  let voiceReady = false;
  let localTtsReady = false;
  let voiceBrowserBlocked = false;
  let phase = "idle";
  let syntheticPhase = 0;
  let brainReady = false;
  let visionReady = false;
  const voiceHistory = [];
  let speakingBubble;
  let activeUtterance;

  function setSystemTile(name, state, label) {
    const tile = document.querySelector(`[data-status-key="${name}"]`);
    if (!tile) return;
    tile.dataset.state = state;
    tile.querySelector("strong").textContent = label;
    const level = Number(arguments[3]);
    if (Number.isFinite(level)) tile.style.setProperty("--level", `${Math.max(0, Math.min(100, level))}%`);
  }

  async function refreshSystemStatus() {
    try {
      const response = await fetch(`/api/status?conversation_id=${encodeURIComponent(conversationId)}`, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error("Status unavailable");
      const data = await response.json();
      gestureAssetsReady = data.gesture?.state === "ready" || gestureModelReady;
      systemDashboard.dataset.state = "online";
      systemOverview.textContent = "LIVE · ON THIS DEVICE";
      for (const key of ["service", "model", "cpu", "memory", "network", "host", "tools", "voice", "vision", "gesture", "telegram", "reminder", "calendar", "issue"]) {
        const item = data[key] || {};
        let label = item.label || "Unavailable";
        if (key === "issue" && cameraIssue) {
          item.state = "error";
          label = cameraIssue;
        }
        if (key === "service" && item.state === "ready") label = "Online";
        if (key === "telegram" && item.state === "setup" && /pair/i.test(label)) label = "Pairing needed";
        if (key === "reminder" && item.due_at) {
          const due = new Date(item.due_at);
          const time = Number.isNaN(due.getTime()) ? "" : `${due.toLocaleDateString([], { month: "short", day: "numeric" })} ${due.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })} · `;
          label = `${time}${label}`;
        }
        if (key === "calendar" && item.starts_at) {
          const starts = new Date(item.starts_at);
          const time = Number.isNaN(starts.getTime()) ? "" : `${starts.toLocaleDateString([], { month: "short", day: "numeric" })} ${starts.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })} · `;
          label = `${time}${label}`;
        }
        if (key === "gesture" && gestureModelReady) {
          item.state = cameraStream ? "live" : "ready";
          label = gestureCurrent || (cameraStream ? "Scanning for hand" : "Model ready · awaiting camera");
        }
        if (key === "vision" && cameraStream) {
          item.state = "live";
          label = `Camera live${cameraFormat ? ` · ${cameraFormat}` : " · on device"}${cameraFocus ? ` · ${cameraFocus}` : ""}${cameraDeviceLabel ? ` · ${cameraDeviceLabel}` : ""}`;
        }
        setSystemTile(key, item.state || "setup", label, item.level);
      }
      const meeting = data.calendar?.due;
      if (meeting?.id) {
        const key = `atulya.meeting.reminded.${meeting.id}`;
        let alreadyReminded = lastMeetingNotifiedId === String(meeting.id);
        try { alreadyReminded = alreadyReminded || sessionStorage.getItem(key) === "1"; } catch { /* Use the in-page fallback when storage is unavailable. */ }
        if (!alreadyReminded) {
          lastMeetingNotifiedId = String(meeting.id);
          try { sessionStorage.setItem(key, "1"); } catch { /* Continue with this page's notification. */ }
          const notice = `Meeting reminder: ${meeting.title}`;
          appendMessage("notice", notice);
          if (voiceSessionActive && !speaking) speak(notice);
        }
      }
      const speechWorks = "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
      const speechState = data.speech?.state || (speechWorks ? "ready" : "setup");
      const speechLabel = data.speech?.label || (speechWorks ? "Browser voice" : "Unavailable");
      setSystemTile("speech", speechState, speechLabel);
    } catch {
      systemDashboard.dataset.state = "offline";
      systemOverview.textContent = "SERVICE UNREACHABLE";
      setSystemTile("service", "off", "Offline");
      setSystemTile("issue", "error", "Cannot reach Atulya service");
    }
  }

  function setChannelState(node, state) {
    if (!node) return;
    for (const name of ["state-ready", "state-live", "state-setup", "state-off", "active", "live", "busy", "setup", "unavailable"]) {
      node.classList.remove(name);
    }
    node.classList.add(`state-${state}`);
    const channelName = node.dataset.channelName || node.textContent.trim();
    const stateLabel = { ready: "ready", live: "active", setup: "setup required", off: "off" }[state] || state;
    node.setAttribute("aria-label", `${channelName} channel ${stateLabel}`);
  }

  function setPhase(next, label, detail = "") {
    phase = next;
    status.textContent = label;
    statusDetail.textContent = detail;
    if (next === "listening" || next === "speaking") voiceHistory.length = 0;
    const tone = /UNAVAILABLE|ERROR|OFFLINE|FAILED|MISSED/i.test(label)
      ? "error"
      : /CONNECTING|ALLOW MICROPHONE|THINKING|UNDERSTANDING|PREPARING|SETUP/i.test(label)
        ? "busy"
        : next === "listening" || next === "speaking"
          ? "live"
          : "ready";
    if (sessionState) sessionState.dataset.tone = tone;
    if (typeof window.__HUM_SET_STATE === "function") window.__HUM_SET_STATE(next);
    else window.dispatchEvent(new CustomEvent("atulya:state", { detail: next }));
    waveform.dataset.phase = next;
    waveform.setAttribute("aria-label", voiceSessionActive ? "Stop live voice conversation" : "Start live voice conversation");
    waveform.title = voiceSessionActive
      ? "Live voice is on. Each phrase sends after a pause. Activate here or press Escape to stop."
      : "Microphone starts automatically after browser permission. Each phrase then sends after a pause.";
    waveHelp.textContent = listening
      ? "LIVE VOICE · AUTO SEND AFTER A PAUSE"
      : speaking ? "ATULYA SPEAKING · MIC PAUSED"
        : voiceSessionActive ? "PROCESSING · LISTENING RESUMES AUTOMATICALLY"
          : voiceBrowserBlocked ? "MIC ACCESS NEEDED · ALLOW IN BROWSER"
            : "AUTO START · WAITING FOR PERMISSION";
    if (voiceChannel) {
      const voiceBusy = /ALLOW MICROPHONE|PREPARING|UNDERSTANDING/i.test(label);
      const voiceLive = (listening && label === "Listening") || (speaking && label === "Speaking");
      const state = voiceLive ? "live" : voiceBusy && voiceReady ? "setup" : voiceReady && !voiceBrowserBlocked ? "ready" : voiceReady ? "off" : "setup";
      setChannelState(voiceChannel, state);
    }
    if (textChannel) {
      setChannelState(textChannel, brainReady ? "ready" : "setup");
    }
    if (connectionDot) {
      connectionDot.classList.toggle("offline", label === "Service unavailable");
      connectionDot.setAttribute("aria-label", label === "Service unavailable" ? "Atulya service unavailable" : "Atulya service online");
    }
    syncLayoutControls();
  }

  function resizeWave() {
    const bounds = canvas.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.max(1, Math.floor(bounds.width * dpr));
    canvas.height = Math.max(1, Math.floor(bounds.height * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function syntheticLevel(position, time) {
    const bursts = [
      [0.12, 0.06, 0.34], [0.21, 0.035, 0.72], [0.29, 0.055, 0.47],
      [0.39, 0.035, 0.88], [0.47, 0.06, 0.55], [0.57, 0.045, 0.73],
      [0.68, 0.04, 0.94], [0.77, 0.06, 0.43], [0.88, 0.035, 0.67],
    ];
    let level = 0.025;
    for (const [center, spread, peak] of bursts) {
      const distance = (position - center) / spread;
      level += peak * Math.exp(-distance * distance * 1.8);
    }
    const ripple = 0.72 + Math.abs(Math.sin(position * 119 + time * 2.4)) * 0.28;
    return Math.min(1, level * ripple);
  }

  function drawWave() {
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    if (!width || !height) return;
    const center = height / 2;
    const time = performance.now() / 1000;
    const analyser = listening ? microphoneAnalyser : speaking ? speechAnalyser : null;
    let levelHistory = null;
    if (analyser) {
      const samples = new Uint8Array(analyser.fftSize);
      analyser.getByteTimeDomainData(samples);
      let sumSquares = 0;
      for (const sample of samples) {
        const amplitude = (sample - 128) / 128;
        sumSquares += amplitude * amplitude;
      }
      const rms = Math.sqrt(sumSquares / samples.length);
      voiceHistory.push(Math.max(0, Math.min(1, (rms - 0.004) * 18)));
      if (voiceHistory.length > countForWidth(width)) voiceHistory.shift();
      levelHistory = voiceHistory;
      if (speaking) window.__HUM_ENERGY = 0.34 + Math.min(0.65, rms * 5);
      if (listening) {
        const now = performance.now();
        if (!speechDetected) noiseFloor = noiseFloor * 0.98 + Math.min(rms, 0.012) * 0.02;
        if (rms > Math.max(0.010, noiseFloor * 2.5)) {
          speechDetected = true;
          lastSpeechAt = now;
        } else if (speechDetected && now - lastSpeechAt >= 1100) {
          speechDetected = false;
          finishListening();
        }
      }
    }
    if (speaking && !analyser) {
      window.__HUM_ENERGY = 0.48 + Math.abs(Math.sin(time * 5.4)) * 0.38;
    } else if (!speaking) window.__HUM_ENERGY = 0;

    ctx.clearRect(0, 0, width, height);
    const gradient = ctx.createLinearGradient(0, 0, width, 0);
    gradient.addColorStop(0, "#139de8");
    gradient.addColorStop(0.1, "#13caff");
    gradient.addColorStop(0.28, "#70eeff");
    gradient.addColorStop(0.38, "#70eeff");
    gradient.addColorStop(0.43, "#ffd17a");
    gradient.addColorStop(0.58, "#ffad48");
    gradient.addColorStop(0.66, "#21dcff");
    gradient.addColorStop(0.72, "#21dcff");
    gradient.addColorStop(0.78, "#ffad48");
    gradient.addColorStop(0.94, "#ffd17a");
    gradient.addColorStop(1, "#28cfff");
    const count = Math.max(32, Math.floor(width / 5));
    const barWidth = Math.max(1, width / count * 0.58);
    const maxHeight = Math.max(5, height * 0.45);

    ctx.beginPath();
    ctx.moveTo(0, center);
    ctx.lineTo(width, center);
    ctx.strokeStyle = gradient;
    ctx.lineWidth = 1;
    ctx.shadowColor = "#24dfff";
    ctx.shadowBlur = 2;
    ctx.stroke();

    const upper = [];
    const lower = [];
    for (let index = 0; index < count; index += 1) {
      const position = (index + 0.5) / count;
      const envelope = Math.pow(Math.sin(Math.PI * position), 0.42);
      let level;
      if (levelHistory) {
        const historyIndex = index - (count - levelHistory.length);
        level = historyIndex >= 0 ? levelHistory[historyIndex] : 0;
      } else if (speaking) {
        level = syntheticLevel(position, time + syntheticPhase);
      } else {
        level = 0;
      }
      const asymmetry = 0.88 + Math.abs(Math.sin(index * 1.71 + 0.9)) * 0.2;
      const barHeight = maxHeight * level * envelope * asymmetry;
      const x = position * width;
      upper.push([x, center - barHeight]);
      lower.push([x, center + barHeight]);
    }
    // Mirrored, softly filled waveform follows the supplied cyan-to-gold reference.
    ctx.beginPath();
    upper.forEach(([x, y], index) => index ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
    for (let index = lower.length - 1; index >= 0; index -= 1) ctx.lineTo(lower[index][0], lower[index][1]);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.globalAlpha = listening || speaking ? 0.58 : 0.92;
    ctx.shadowColor = "#29dfff";
    ctx.shadowBlur = listening || speaking ? 11 : 5;
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.beginPath();
    upper.forEach(([x, y], index) => index ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
    ctx.strokeStyle = gradient;
    ctx.lineWidth = 1.4;
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Bracket marks echo the supplied reference waveform.
    ctx.beginPath();
    ctx.moveTo(10, center - height * 0.32);
    ctx.quadraticCurveTo(2, center, 10, center + height * 0.32);
    ctx.moveTo(width - 10, center - height * 0.32);
    ctx.quadraticCurveTo(width - 2, center, width - 10, center + height * 0.32);
    ctx.strokeStyle = "rgba(110,210,255,.66)";
    ctx.lineWidth = 1.2;
    ctx.stroke();
    animationFrame = requestAnimationFrame(drawWave);
  }

  function countForWidth(width) {
    return Math.max(32, Math.floor(width / 5));
  }

  function refreshWave() {
    cancelAnimationFrame(animationFrame);
    animationFrame = requestAnimationFrame(drawWave);
  }

  function getConversationId() {
    const key = "atulya.conversation.id";
    try {
      let id = localStorage.getItem(key);
      if (!id) {
        id = crypto.randomUUID?.() || `c_${Date.now()}_${Math.random().toString(36).slice(2)}`;
        localStorage.setItem(key, id);
      }
      return id;
    } catch {
      return `c_${Date.now()}_${Math.random().toString(36).slice(2)}`;
    }
  }

  function readArchiveIndex() {
    try {
      const entries = JSON.parse(localStorage.getItem("atulya.conversations.index") || "[]");
      return Array.isArray(entries) ? entries.filter((item) => item && /^[A-Za-z0-9_-]{1,80}$/.test(item.id)).slice(0, 50) : [];
    } catch { return []; }
  }

  function rememberArchive(id, title = "") {
    const entries = readArchiveIndex();
    const existing = entries.find((item) => item.id === id);
    const next = { id, title: title || existing?.title || "New conversation", updated: new Date().toISOString() };
    try { localStorage.setItem("atulya.conversations.index", JSON.stringify([next, ...entries.filter((item) => item.id !== id)].slice(0, 50))); } catch { /* The current page can continue without an archive index. */ }
  }

  function drawArchiveList() {
    if (!historyList) return;
    historyList.replaceChildren();
    const entries = readArchiveIndex();
    if (!entries.length) {
      const empty = document.createElement("p");
      empty.className = "history-warning";
      empty.textContent = "No saved conversations in this browser yet.";
      historyList.append(empty);
      return;
    }
    for (const entry of entries) {
      const row = document.createElement("div");
      row.className = "history-entry";
      const choose = document.createElement("button");
      choose.type = "button";
      choose.textContent = entry.title || "Saved conversation";
      choose.setAttribute("aria-current", String(entry.id === selectedArchiveId));
      choose.addEventListener("click", () => { selectedArchiveId = entry.id; drawArchiveList(); });
      choose.addEventListener("dblclick", () => { void openArchiveConversation(); });
      const date = document.createElement("small");
      const parsed = new Date(entry.updated);
      date.textContent = Number.isNaN(parsed.getTime()) ? "LOCAL" : parsed.toLocaleString([], { dateStyle: "short", timeStyle: "short" });
      row.append(choose, date);
      historyList.append(row);
    }
  }

  function startNewConversation() {
    conversationId = crypto.randomUUID?.() || `c_${Date.now()}_${Math.random().toString(36).slice(2)}`;
    selectedArchiveId = conversationId;
    conversation.length = 0;
    messagesNode.replaceChildren();
    try { localStorage.setItem("atulya.conversation.id", conversationId); } catch { /* Keep the generated ID for this page only. */ }
    historyReady = true;
    historyStatus.textContent = "NEW LOCAL CONVERSATION";
    historyStatus.dataset.state = "saved";
    rememberArchive(conversationId);
    historyDialog?.close();
    prompt?.focus();
  }

  async function openArchiveConversation() {
    if (!selectedArchiveId || selectedArchiveId === conversationId) { historyDialog?.close(); return; }
    const response = await fetch(`/api/conversations/${encodeURIComponent(selectedArchiveId)}`, { headers: { Accept: "application/json" } });
    if (!response.ok) { showLayoutToast("That saved conversation could not be opened."); return; }
    const body = await response.json();
    conversationId = selectedArchiveId;
    try { localStorage.setItem("atulya.conversation.id", conversationId); } catch { /* Continue in memory only. */ }
    conversation.length = 0;
    messagesNode.replaceChildren();
    for (const message of body.messages || []) {
      if (message.role === "notice") continue;
      appendMessage(message.role, message.content, message.message_id, false);
      conversation.push({ role: message.role, content: message.content });
    }
    historyDialog?.close();
  }

  async function exportArchive() {
    if (!selectedArchiveId) return;
    const response = await fetch(`/api/conversations/${encodeURIComponent(selectedArchiveId)}`, { headers: { Accept: "application/json" } });
    if (!response.ok) { showLayoutToast("Conversation export failed."); return; }
    const payload = await response.json();
    const blob = new Blob([JSON.stringify({ app: "Atulya", exported_at: new Date().toISOString(), conversation_id: selectedArchiveId, messages: payload.messages }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `atulya-conversation-${selectedArchiveId}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function deleteArchive() {
    if (!selectedArchiveId || !window.confirm("Permanently delete this saved conversation from the local archive?")) return;
    const response = await fetch(`/api/conversations/${encodeURIComponent(selectedArchiveId)}`, { method: "DELETE" });
    if (!response.ok) { showLayoutToast("Conversation deletion failed."); return; }
    try { localStorage.setItem("atulya.conversations.index", JSON.stringify(readArchiveIndex().filter((item) => item.id !== selectedArchiveId))); } catch { /* The server archive has still been deleted. */ }
    if (selectedArchiveId === conversationId) startNewConversation();
    else { selectedArchiveId = conversationId; drawArchiveList(); }
  }

  async function showPluginSettings() {
    if (!pluginList || !pluginDialog) return;
    pluginList.replaceChildren();
    const response = await fetch("/api/plugins", { headers: { Accept: "application/json" } });
    if (!response.ok) { showLayoutToast("Built-in tool settings are unavailable."); return; }
    const { plugins = [] } = await response.json();
    for (const plugin of plugins) {
      const row = document.createElement("label");
      row.className = "plugin-entry";
      const description = document.createElement("span");
      const title = document.createElement("strong");
      title.textContent = `${plugin.category.toUpperCase()} · ${plugin.name}`;
      const detail = document.createElement("small");
      detail.textContent = `Commands: ${(plugin.commands || []).join(", ")}${plugin.permissions?.includes("network") ? " · Internet access" : " · Local only"}`;
      description.append(title, detail);
      const toggle = document.createElement("input");
      toggle.type = "checkbox";
      toggle.checked = Boolean(plugin.enabled);
      toggle.setAttribute("aria-label", `${plugin.enabled ? "Disable" : "Enable"} ${plugin.name}`);
      toggle.addEventListener("change", async () => {
        toggle.disabled = true;
        try {
          const result = await fetch(`/api/plugins/${encodeURIComponent(plugin.id)}`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ enabled: toggle.checked }),
          });
          if (!result.ok) throw new Error("Save failed");
          const body = await result.json();
          plugin.enabled = body.plugin.enabled;
          toggle.setAttribute("aria-label", `${plugin.enabled ? "Disable" : "Enable"} ${plugin.name}`);
        } catch {
          toggle.checked = !toggle.checked;
          showLayoutToast(`Could not update ${plugin.name}.`);
        } finally { toggle.disabled = false; }
      });
      row.append(description, toggle);
      pluginList.append(row);
    }
    pluginDialog.showModal();
  }

  function saveMessage(message) {
    if (!historyReady) return;
    historyStatus.textContent = "SAVING CONVERSATION…";
    historyWrites = historyWrites.catch(() => {}).then(async () => {
      const response = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message_id: message.dataset.messageId, role: message.classList.contains("notice") ? "notice" : message.classList.contains("user") ? "user" : "assistant", content: message.textContent }),
      keepalive: true,
      });
      if (!response.ok) throw new Error("History save failed");
      historyStatus.textContent = "CONVERSATION SAVED ON THIS DEVICE";
      historyStatus.dataset.state = "saved";
    }).catch(() => {
      historyStatus.textContent = "LOCAL HISTORY UNAVAILABLE";
      historyStatus.dataset.state = "error";
    });
  }

  function appendMessage(role, text, messageId = null, persist = true) {
    const item = document.createElement("p");
    item.className = `chat-message ${role}`;
    item.dataset.messageId = messageId || (crypto.randomUUID?.() || `m_${Date.now()}_${Math.random().toString(36).slice(2)}`);
    item.textContent = text;
    messagesNode.append(item);
    while (messagesNode.children.length > 60) messagesNode.firstElementChild.remove();
    messagesNode.scrollTop = messagesNode.scrollHeight;
    // Notices describe transient failures, not conversation turns. Keep them
    // visible for this page session, but don't restore stale errors next time.
    if (persist && role !== "notice") saveMessage(item);
    if (role === "user") {
      const priorUser = [...messagesNode.querySelectorAll(".chat-message.user")].find((message) => message !== item);
      rememberArchive(conversationId, (priorUser?.textContent || text).slice(0, 72));
    }
    return item;
  }


  // ---- Computer-action approvals -------------------------------------------
  // The model can only *request* PC actions; they run after the user taps
  // Approve or answers "yes" by voice/text while a request is waiting.
  const pendingActions = new Map();

  function showActionRequest(action) {
    if (!action?.id || pendingActions.has(action.id)) return;
    const card = document.createElement("div");
    card.className = "chat-message action-card";
    card.setAttribute("role", "group");
    card.setAttribute("aria-label", "Approval needed");
    const title = document.createElement("strong");
    title.textContent = "APPROVAL NEEDED";
    const summary = document.createElement("span");
    summary.textContent = action.summary;
    const buttons = document.createElement("div");
    const approve = document.createElement("button");
    approve.type = "button";
    approve.textContent = "APPROVE";
    approve.className = "approve";
    const deny = document.createElement("button");
    deny.type = "button";
    deny.textContent = "DENY";
    approve.addEventListener("click", () => decideAction(action.id, true));
    deny.addEventListener("click", () => decideAction(action.id, false));
    buttons.append(approve, deny);
    card.append(title, summary, buttons);
    messagesNode.append(card);
    messagesNode.scrollTop = messagesNode.scrollHeight;
    card.dataset.created = String(Date.now());
    pendingActions.set(action.id, card);
  }

  async function decideAction(id, approve) {
    const card = pendingActions.get(id);
    if (!card) return;
    pendingActions.delete(id);
    card.querySelectorAll("button").forEach((button) => { button.disabled = true; });
    card.dataset.state = approve ? "approved" : "denied";
    let text;
    try {
      const response = await fetch(`/api/actions/${encodeURIComponent(id)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ approve }),
      });
      const body = await response.json().catch(() => ({}));
      text = response.ok ? String(body.text || "Done.") : String(body.detail || "That request could not be completed.");
    } catch {
      text = "Atulya couldn't reach the computer to do that.";
    }
    appendMessage("assistant", text);
    conversation.push({ role: "assistant", content: text });
    return text;
  }

  // "yes" / "approve" / "haan" and "no" / "cancel" answer the newest waiting request.
  function approvalAnswer(text) {
    if (!pendingActions.size) return null;
    // Spoken/typed "yes" only counts for a fresh request; older ones need a tap,
    // so a stray "yes" from a TV or another person can't approve something stale.
    const [latestCard] = [...pendingActions.values()].slice(-1);
    if (Date.now() - Number(latestCard?.dataset.created || 0) > 60000) return null;
    const value = text.toLowerCase().replace(/[.!?,]/g, " ").trim();
    if (/^(?:yes|yeah|yep|sure|ok|okay|approve|approved|do it|go ahead|haan|ha|ji haan|confirm)(?: please| it)?$/.test(value)) return true;
    if (/^(?:no|nope|deny|cancel|stop|don't|do not|nahi|na)(?: please| it)?$/.test(value)) return false;
    return null;
  }

  async function restoreConversation() {
    try {
      const response = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}`, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error("History could not be loaded");
      const body = await response.json();
      rememberArchive(conversationId, (body.messages || []).find((message) => message.role === "user")?.content?.slice(0, 72) || "New conversation");
      for (const message of body.messages || []) {
        if (message.role === "notice") continue;
        appendMessage(message.role, message.content, message.message_id, false);
        if (message.role === "user" || message.role === "assistant") conversation.push({ role: message.role, content: message.content });
      }
      if (conversation.length > 38) conversation.splice(0, conversation.length - 38);
      historyReady = true;
      historyStatus.textContent = "CONVERSATION HISTORY · ON THIS DEVICE";
      historyStatus.dataset.state = "saved";
    } catch {
      historyReady = true;
      historyStatus.textContent = "LOCAL HISTORY UNAVAILABLE";
      historyStatus.dataset.state = "error";
    }
  }

  $("#new-conversation")?.addEventListener("click", startNewConversation);
  $("#open-history")?.addEventListener("click", () => {
    selectedArchiveId = conversationId;
    rememberArchive(conversationId);
    drawArchiveList();
    historyDialog?.showModal();
  });
  $("#close-history")?.addEventListener("click", () => historyDialog?.close());
  $("#open-history-selected")?.addEventListener("click", openArchiveConversation);
  $("#export-history")?.addEventListener("click", exportArchive);
  $("#delete-history")?.addEventListener("click", deleteArchive);
  $("#open-plugins")?.addEventListener("click", showPluginSettings);
  $("#close-plugins")?.addEventListener("click", () => pluginDialog?.close());

  function highlightSpokenReply(item) {
    if (speakingBubble) speakingBubble.classList.remove("is-speaking");
    speakingBubble = item;
    if (speakingBubble) {
      speakingBubble.classList.add("is-speaking");
      speakingBubble.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }

  function clearSpokenReply() {
    if (speakingBubble) speakingBubble.classList.remove("is-speaking");
    speakingBubble = undefined;
  }

  function restoreIdlePhase(detailOverride = "") {
    speaking = false;
    clearSpokenReply();
    if (!brainReady) setPhase("idle", "Chat unavailable", detailOverride || "Text chat is offline right now. The scene remains available.");
    else if (!voiceReady) setPhase("idle", "Voice unavailable", detailOverride || "Text chat is ready. Voice input and speech are currently offline.");
    else setPhase("idle", "Ready", detailOverride || "Atulya is ready for your next message.");
    refreshWave();
  }

  function stopCamera() {
    if (gestureFrame) cancelAnimationFrame(gestureFrame);
    gestureFrame = 0;
    gestureCurrent = "";
    const gestureRegion = $("#gesture-region");
    if (gestureRegion) gestureRegion.dataset.state = gestureAssetsReady ? "ready" : "setup";
    showGestureResult(gestureAssetsReady ? "CAMERA OFF" : "PREPARING");
    if (cameraStream) cameraStream.getTracks().forEach((track) => track.stop());
    cameraStream = undefined;
    if (cameraFeed) cameraFeed.srcObject = null;
    cameraPreview?.classList.remove("is-live");
    cameraToggle?.setAttribute("aria-pressed", "false");
    cameraToggle?.setAttribute("aria-label", "Start camera preview");
    const label = cameraToggle?.querySelector(".preview-label b");
    if (label) label.innerHTML = "<i></i> CAMERA OFF · RETRY";
    if (visionChannel) setChannelState(visionChannel, "off");
    const gestureChannel = $("#gesture-channel");
    if (gestureChannel) setChannelState(gestureChannel, gestureAssetsReady ? "ready" : "setup");
    setSystemTile("vision", "off", "Camera off");
    setSystemTile("gesture", gestureAssetsReady ? "ready" : "setup", gestureAssetsReady ? "Model ready · camera off" : "Gesture model needs setup");
  }

  cameraBus?.addEventListener("message", (event) => {
    if (event.data?.type === "claim" && event.data.pageId !== pageId && cameraStream) stopCamera();
  });

  async function refreshCameraDevices(activeDeviceId = "") {
    if (!cameraDevice || !navigator.mediaDevices?.enumerateDevices) return;
    try {
      const devices = (await navigator.mediaDevices.enumerateDevices()).filter((device) => device.kind === "videoinput");
      const savedDeviceId = selectedCameraDeviceId || (() => {
        try { return localStorage.getItem("atulya.camera.deviceId") || ""; } catch { return ""; }
      })();
      const preferred = activeDeviceId || savedDeviceId;
      cameraDevice.replaceChildren();
      for (const [index, device] of devices.entries()) {
        const option = document.createElement("option");
        option.value = device.deviceId;
        option.textContent = device.label || `Camera ${index + 1}`;
        cameraDevice.append(option);
      }
      cameraDevice.hidden = devices.length < 2;
      if (devices.some((device) => device.deviceId === preferred)) {
        cameraDevice.value = preferred;
        selectedCameraDeviceId = preferred;
      } else if (activeDeviceId) {
        selectedCameraDeviceId = activeDeviceId;
      }
    } catch { /* Keep the default browser-selected camera if enumeration is unavailable. */ }
  }

  async function startCamera(retry = 0) {
    if (cameraStream) {
      return true;
    }
    if (cameraStartPromise) return cameraStartPromise;
    if (!navigator.mediaDevices?.getUserMedia) {
      const detail = window.isSecureContext ? "This browser cannot access a camera. Try a current desktop browser." : "Camera access requires localhost or a secure HTTPS page.";
      setCameraError("This browser cannot access a camera", detail);
      return false;
    }
    cameraStartPromise = (async () => {
      try {
        cameraBus?.postMessage({ type: "claim", pageId });
        // Give another Atulya tab time to release the device before requesting it.
        await new Promise((resolve) => window.setTimeout(resolve, 180));
        let stream;
        let cameraError;
        const requestedDevice = selectedCameraDeviceId
          || (() => { try { return localStorage.getItem("atulya.camera.deviceId") || ""; } catch { return ""; } })();
        const deviceConstraint = requestedDevice ? { deviceId: { exact: requestedDevice } } : { facingMode: { ideal: "user" } };
        const videoProfiles = [
          { ...deviceConstraint, width: { min: 1920, ideal: 1920 }, height: { min: 1080, ideal: 1080 }, frameRate: { ideal: 30 } },
          { ...deviceConstraint, width: { ideal: 1920 }, height: { ideal: 1080 }, frameRate: { ideal: 30 } },
          { ...deviceConstraint, width: { ideal: 1280 }, height: { ideal: 720 } },
          deviceConstraint,
          ...(requestedDevice ? [] : [true]),
        ];
        for (const video of videoProfiles) {
          try {
            stream = await navigator.mediaDevices.getUserMedia({ video, audio: false });
            break;
          } catch (error) {
            cameraError = error;
            if (["NotAllowedError", "PermissionDeniedError", "NotFoundError", "SecurityError"].includes(error.name)) throw error;
          }
        }
        if (!stream) throw cameraError || new Error("No camera profile could be opened.");
        cameraStream = stream;
        for (const track of stream.getVideoTracks()) {
          let capabilities = {};
          try { capabilities = track.getCapabilities?.() || {}; } catch { /* Use the camera's default controls. */ }
          const cameraControls = {};
          if (capabilities.focusMode?.includes("continuous")) cameraControls.focusMode = "continuous";
          if (capabilities.exposureMode?.includes("continuous")) cameraControls.exposureMode = "continuous";
          if (Object.keys(cameraControls).length) {
            try { await track.applyConstraints({ advanced: [cameraControls] }); } catch { /* Unsupported control: keep browser defaults. */ }
          }
        }
        cameraFeed.srcObject = stream;
        await cameraFeed.play();
        cameraPreview.classList.add("is-live");
        if (visionChannel) setChannelState(visionChannel, "live");
        if (cameraToggle) {
          cameraToggle.setAttribute("aria-pressed", "true");
          cameraToggle.setAttribute("aria-label", "Stop camera preview");
          const label = cameraToggle.querySelector(".preview-label b");
          if (label) label.innerHTML = "<i></i> CAMERA LIVE";
        }
        stream.getVideoTracks().forEach((track) => track.addEventListener("ended", stopCamera, { once: true }));
        const cameraSettings = stream.getVideoTracks()[0]?.getSettings?.() || {};
        cameraFormat = cameraSettings.width && cameraSettings.height ? `${cameraSettings.width}×${cameraSettings.height}` : "";
        cameraFocus = cameraSettings.focusMode || "";
        selectedCameraDeviceId = cameraSettings.deviceId || selectedCameraDeviceId;
        try { if (selectedCameraDeviceId) localStorage.setItem("atulya.camera.deviceId", selectedCameraDeviceId); } catch { /* Session still works without local preferences. */ }
        await refreshCameraDevices(selectedCameraDeviceId);
        const activeDevice = (await navigator.mediaDevices.enumerateDevices().catch(() => []))
          .find((device) => device.kind === "videoinput" && device.deviceId === selectedCameraDeviceId);
        cameraDeviceLabel = activeDevice?.label || "";
        const resolvedCameraIssue = cameraIssue;
        cameraIssue = "";
        const issueLabel = document.querySelector('[data-status-key="issue"] strong');
        if (resolvedCameraIssue && issueLabel?.textContent === resolvedCameraIssue) setSystemTile("issue", "ready", "No active issues");
        const label = cameraToggle?.querySelector(".preview-label b");
        if (label) label.textContent = `CAMERA LIVE${cameraFormat ? ` · ${cameraFormat}` : ""}`;
        setSystemTile("vision", "live", `Camera live${cameraFormat ? ` · ${cameraFormat}` : " · on device"}${cameraFocus ? ` · focus ${cameraFocus}` : ""}${cameraDeviceLabel ? ` · ${cameraDeviceLabel}` : ""}`);
        if (status.textContent === "Camera unavailable") restoreIdlePhase();
        await initializeGestureRecognition();
        return true;
      } catch (error) {
        stopCamera();
        cameraFormat = "";
        cameraFocus = "";
        const deviceBusy = error.name === "NotReadableError" || error.name === "AbortError";
        const detail = error.name === "NotAllowedError" || error.name === "PermissionDeniedError"
          ? "Camera access was denied. Allow it for this site in browser settings, then reload."
          : error.name === "NotFoundError"
            ? "No camera was found. Connect one or continue without the preview."
            : error.name === "NotReadableError" || error.name === "AbortError"
              ? "The camera is busy or failed to start. Close other apps using it, then retry."
              : "The camera could not start. Check this site's camera permission and try again.";
        setCameraError("Camera unavailable", detail);
        if (deviceBusy && retry < 2) window.setTimeout(() => { void startCamera(retry + 1); }, 1200);
        return false;
      } finally {
        cameraStartPromise = undefined;
      }
    })();
    return cameraStartPromise;
  }

  async function toggleCamera() {
    if (cameraStream) {
      stopCamera();
      return false;
    }
    return startCamera();
  }

  function setCameraError(label, detail) {
    cameraIssue = detail;
    const cameraLabel = cameraToggle?.querySelector(".preview-label b");
    if (cameraLabel) cameraLabel.innerHTML = "<i></i> CAMERA NEEDS ACCESS";
    setSystemTile("vision", "error", label);
    setSystemTile("issue", "error", detail);
    if (visionChannel) setChannelState(visionChannel, "off");
    setPhase("idle", label, detail);
  }

  async function initializeGestureRecognition() {
    if (!cameraStream || !cameraFeed.videoWidth || !cameraFeed.videoHeight) {
      await new Promise((resolve) => cameraFeed.addEventListener("loadedmetadata", resolve, { once: true }));
    }
    try {
      const { FilesetResolver, GestureRecognizer } = await import("/api/runtime/mediapipe/vision_bundle.mjs");
      const vision = await FilesetResolver.forVisionTasks("/api/runtime/mediapipe/wasm");
      const options = {
        baseOptions: { modelAssetPath: "/api/models/gesture/gesture_recognizer.task", delegate: "GPU" },
        runningMode: "VIDEO",
        numHands: 1,
        minHandDetectionConfidence: 0.55,
        minHandPresenceConfidence: 0.55,
        minTrackingConfidence: 0.55,
      };
      try {
        gestureRecognizer = await GestureRecognizer.createFromOptions(vision, options);
      } catch {
        options.baseOptions.delegate = "CPU";
        gestureRecognizer = await GestureRecognizer.createFromOptions(vision, options);
      }
      gestureModelReady = true;
      const gestureRegion = $("#gesture-region");
      const gestureChannel = $("#gesture-channel");
      if (gestureRegion) {
        gestureRegion.dataset.state = "live";
        gestureRegion.setAttribute("aria-label", "Gesture recognition active. Hold thumbs up to send Yes, thumbs down to send No, or open palm to stop voice.");
      }
      showGestureResult("SCANNING");
      if (gestureChannel) setChannelState(gestureChannel, "live");
      setSystemTile("gesture", "live", "Scanning for hand");
      scanGestures();
    } catch {
      gestureModelReady = false;
      const gestureRegion = $("#gesture-region");
      const gestureChannel = $("#gesture-channel");
      showGestureResult("MODEL ERROR");
      if (gestureRegion) gestureRegion.dataset.state = "error";
      if (gestureChannel) setChannelState(gestureChannel, "setup");
      setSystemTile("gesture", "error", "Recognizer could not start");
    }
  }

  function scanGestures() {
    if (!cameraStream || !gestureRecognizer) return;
    const now = performance.now();
    if (now - lastGestureFrameAt >= 125 && cameraFeed.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
      lastGestureFrameAt = now;
      try {
        const result = gestureRecognizer.recognizeForVideo(cameraFeed, now);
        const category = result.gestures?.[0]?.[0];
        const categoryName = category && category.categoryName !== "None" && category.score >= 0.58 ? category.categoryName : "";
        updateGestureCommand(categoryName, category?.score || 0, now);
        const recognized = category && category.categoryName !== "None" && category.score >= 0.58
          ? `${category.categoryName.replaceAll("_", " ")} · ${Math.round(category.score * 100)}%` : "Scanning for hand";
        if (recognized !== (gestureCurrent || "Scanning for hand")) {
          gestureCurrent = recognized === "Scanning for hand" ? "" : recognized;
          const gestureRegion = $("#gesture-region");
          showGestureResult(recognized);
          if (gestureRegion) gestureRegion.dataset.state = gestureCurrent ? "detected" : "live";
          setSystemTile("gesture", "live", recognized);
        }
      } catch {
        setSystemTile("gesture", "error", "Frame recognition failed");
      }
    }
    gestureFrame = requestAnimationFrame(scanGestures);
  }

  function updateGestureCommand(categoryName, score, now) {
    if (!categoryName) {
      if (!gestureNeutralSince) gestureNeutralSince = now;
      gestureCommandCandidate = "";
      gestureCommandCandidateSince = 0;
      if (now - gestureNeutralSince >= gestureReleaseMs) gestureCommandsArmed = true;
      return;
    }
    gestureNeutralSince = 0;
    if (!["Thumb_Up", "Thumb_Down", "Open_Palm"].includes(categoryName) || score < gestureCommandThreshold) {
      gestureCommandCandidate = "";
      gestureCommandCandidateSince = 0;
      return;
    }
    if (categoryName !== gestureCommandCandidate) {
      gestureCommandCandidate = categoryName;
      gestureCommandCandidateSince = now;
      return;
    }
    if (!gestureCommandsArmed || now - gestureCommandCandidateSince < gestureCommandHoldMs || now - lastGestureCommandAt < gestureCommandCooldownMs) return;
    gestureCommandsArmed = false;
    lastGestureCommandAt = now;
    runGestureCommand(categoryName);
  }

  function runGestureCommand(categoryName) {
    if (categoryName === "Open_Palm") {
      if (voiceSessionActive || listening) {
        void cancelListening("Voice stopped by open palm.");
      } else if (speaking) {
        window.speechSynthesis?.cancel?.();
        speaking = false;
        clearSpokenReply();
        restoreIdlePhase("Speech stopped by open palm.");
      }
      return;
    }
    if (!brainReady || phase !== "idle") return;
    const affirmative = categoryName === "Thumb_Up";
    void sendMessage(affirmative ? "Yes" : "No", voiceSessionActive, false);
  }

  async function enableCamera() {
    if (cameraStream) return true;
    return Boolean(await toggleCamera());
  }

  function cameraCommand(text) {
    const match = text.trim().toLowerCase().match(/^(?:(?:please\s+)?(?:turn|switch|activate|enable|deactivate|disable)\s+)?camera\s+(on|off|activate|deactivate|enable|disable)$/);
    return match ? ["on", "activate", "enable"].includes(match[1]) : null;
  }

  function captureCameraFrame() {
    if (!visionReady || !cameraStream || !cameraFeed.videoWidth || !cameraFeed.videoHeight) return null;
    const scale = Math.min(1, 1280 / cameraFeed.videoWidth, 720 / cameraFeed.videoHeight);
    const frame = document.createElement("canvas");
    frame.width = Math.max(1, Math.round(cameraFeed.videoWidth * scale));
    frame.height = Math.max(1, Math.round(cameraFeed.videoHeight * scale));
    frame.getContext("2d", { alpha: false }).drawImage(cameraFeed, 0, 0, frame.width, frame.height);
    return frame.toDataURL("image/jpeg", 0.72);
  }


  // ---- Wake word and barge-in -------------------------------------------
  // Wake word: while live voice is on, utterances are transcribed locally and
  // ignored unless they start with "Hey Atulya" (or arrive within a short
  // follow-up window after Atulya spoke). Barge-in: while Atulya speaks, the
  // mic is monitored (with echo cancellation); talking over it stops speech
  // and starts listening immediately.
  const WAKE_PATTERN = /^\s*(?:(?:hey|hi|hello|ok|okay|ai|he|hay)[\s,]+)?(?:atulya|atuliya|atulia|athulya|atulyaa|atul ya|a tulya)\b[\s,.!?:-]*/i;
  const FOLLOW_UP_MS = 8000;
  const readFlag = (key, fallback) => {
    try { const value = localStorage.getItem(key); return value === null ? fallback : value === "1"; } catch { return fallback; }
  };
  let wakeWordEnabled = readFlag("atulya.voice.wake", true);
  let bargeInEnabled = readFlag("atulya.voice.bargein", true);
  let awakeUntil = 0;

  function setVoiceOption(key, enabled) {
    try { localStorage.setItem(key, enabled ? "1" : "0"); } catch { /* storage unavailable */ }
  }

  // Returns the text to send, or null when the utterance should be ignored.
  function applyWakeWord(transcript) {
    if (!wakeWordEnabled) return transcript;
    const match = transcript.match(WAKE_PATTERN);
    if (match) {
      const rest = transcript.slice(match[0].length).trim();
      if (rest) return rest;
      awakeUntil = Date.now() + FOLLOW_UP_MS;
      return "";
    }
    if (Date.now() < awakeUntil) return transcript;
    return null;
  }

  function markFollowUpWindow() {
    if (wakeWordEnabled) awakeUntil = Date.now() + FOLLOW_UP_MS;
  }

  let bargeMonitor = null;
  async function startBargeMonitor() {
    if (bargeMonitor || !navigator.mediaDevices?.getUserMedia) return;
    const monitor = { stopped: false, stream: null, context: null };
    bargeMonitor = monitor;
    try {
      monitor.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      if (monitor.stopped) { monitor.stream.getTracks().forEach((track) => track.stop()); return; }
      const AudioContextType = window.AudioContext || window.webkitAudioContext;
      monitor.context = new AudioContextType();
      const analyser = monitor.context.createAnalyser();
      analyser.fftSize = 512;
      monitor.context.createMediaStreamSource(monitor.stream).connect(analyser);
      const samples = new Uint8Array(analyser.fftSize);
      let floor = 0.01;
      let loudSince = 0;
      const started = performance.now();
      const tick = () => {
        if (monitor.stopped) return;
        analyser.getByteTimeDomainData(samples);
        let sum = 0;
        for (const sample of samples) { const a = (sample - 128) / 128; sum += a * a; }
        const rms = Math.sqrt(sum / samples.length);
        const now = performance.now();
        // Learn the residual echo level for the first half second, then require
        // clearly louder speech held for 300 ms before interrupting.
        if (now - started < 500) floor = Math.max(floor, rms);
        else if (rms > Math.max(0.045, floor * 3)) {
          loudSince ||= now;
          if (now - loudSince > 300) { interruptSpeech(); return; }
        } else loudSince = 0;
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    } catch {
      stopBargeMonitor();
    }
  }

  function stopBargeMonitor() {
    const monitor = bargeMonitor;
    bargeMonitor = null;
    if (!monitor) return;
    monitor.stopped = true;
    monitor.stream?.getTracks().forEach((track) => track.stop());
    monitor.context?.close().catch(() => {});
  }

  function interruptSpeech() {
    stopBargeMonitor();
    if (!speaking) return;
    releaseSpeech();
    clearSpokenReply();
    awakeUntil = Date.now() + FOLLOW_UP_MS;
    setPhase("listening", "Listening", "Interrupted. Go ahead.");
    voiceSessionActive = true;
    startListening(true);
  }

  // Keep the monitor running exactly while Atulya is speaking in a live session.
  window.setInterval(() => {
    const wanted = bargeInEnabled && voiceSessionActive && speaking && !listening;
    if (wanted && !bargeMonitor) startBargeMonitor();
    else if (!wanted && bargeMonitor) stopBargeMonitor();
  }, 120);

  function resumeLiveVoice() {
    if (!voiceSessionActive || listening) return;
    if (!voiceReady) {
      voiceSessionActive = false;
      return;
    }
    window.setTimeout(() => {
      if (voiceSessionActive && !listening && !speaking) startListening(true);
    }, 350);
  }

  // Never read emoji, markdown symbols or links aloud.
  function speakableText(text) {
    return String(text || "")
      .replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}\u{200D}]/gu, "")
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
      .replace(/https?:\/\/\S+/g, "")
      .replace(/[*_`#>|~]+/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function speakWithBrowser(rawText, detail = "Using the browser's built-in speech voice.") {
    const text = speakableText(rawText);
    if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) {
      speaking = false;
      clearSpokenReply();
      setPhase("idle", "Voice unavailable", "This browser cannot play the reply aloud. The text reply is still here.");
      resumeLiveVoice();
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    const hindi = /\p{Script=Devanagari}/u.test(text);
    const targetLanguage = hindi ? "hi-IN" : "en-IN";
    utterance.lang = targetLanguage;
    activeUtterance = utterance;
    preferMaleVoice(utterance, targetLanguage);
    window.speechSynthesis.addEventListener?.("voiceschanged", () => {
      if (activeUtterance === utterance) preferMaleVoice(utterance, targetLanguage);
    }, { once: true });
    utterance.onstart = () => {
      speaking = true;
      setPhase("speaking", "Speaking", detail);
      refreshWave();
    };
    utterance.onerror = () => {
      if (activeUtterance !== utterance) return;
      activeUtterance = undefined;
      speaking = false;
      clearSpokenReply();
      setPhase("idle", "Voice unavailable", "The browser couldn't play the reply aloud. The text reply is still here.");
      resumeLiveVoice();
    };
    utterance.onend = () => {
      if (activeUtterance !== utterance) return;
      activeUtterance = undefined;
      speaking = false;
      clearSpokenReply();
      restoreIdlePhase();
      markFollowUpWindow();
      resumeLiveVoice();
      refreshWave();
    };
    window.speechSynthesis.cancel();
    try {
      window.speechSynthesis.speak(utterance);
    } catch {
      activeUtterance = undefined;
      speaking = false;
      setPhase("idle", "Voice unavailable", "The browser couldn't start speech playback. The text reply is still here.");
    }
  }

  function preferMaleVoice(utterance, targetLanguage) {
    const voices = window.speechSynthesis?.getVoices?.() || [];
    const language = targetLanguage.split("-")[0].toLowerCase();
    const matching = voices.filter((voice) => voice.lang?.toLowerCase().startsWith(language));
    const maleNames = language === "hi"
      ? /male|hemant|madhur|ravi|amit|arjun|rahul|aditya/i
      : /male|david|mark|ryan|guy|eric|brian|daniel|george|james|thomas|alex|fred|aaron/i;
    const preferred = matching.find((voice) => maleNames.test(voice.name));
    if (preferred) {
      utterance.voice = preferred;
      utterance.lang = preferred.lang;
    } else if (matching[0]) {
      utterance.lang = matching[0].lang;
    }
  }

  function greet() {
    if (greeted || !healthLoaded || !brainReady || !sceneReady || !historyReady) return;
    greeted = true;
    const greeting = "Hi, I'm Atulya. How can I help?";
    const returningSession = messagesNode.children.length > 0;
    const greetingBubble = appendMessage("assistant", greeting, null, !returningSession);
    if (!returningSession) conversation.push({ role: "assistant", content: greeting });
    highlightSpokenReply(greetingBubble);
    // Speak only after the scene is ready, then open the mic automatically.
    // The browser still owns the permission prompt; Atulya never bypasses it.
    voiceSessionActive = voiceReady;
    speak(greeting);
    deliverMorningBriefing();
  }

  // First visit of the day: show and read the morning briefing once the greeting ends.
  async function deliverMorningBriefing() {
    let body;
    try {
      const response = await fetch("/api/briefing", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ conversation_id: conversationId }),
      });
      if (!response.ok) return;
      body = await response.json();
    } catch {
      return;
    }
    const text = String(body?.text || "").trim();
    if (!text) return;
    const deadline = Date.now() + 20000;
    while ((speaking || phase === "thinking") && Date.now() < deadline) await new Promise((resolve) => setTimeout(resolve, 300));
    const bubble = appendMessage("assistant", text);
    conversation.push({ role: "assistant", content: text });
    if (listening) return; // the user already started talking; leave it on screen
    highlightSpokenReply(bubble);
    await speak(text);
  }

  function releaseSpeech() {
    activeAudioRequest += 1;
    activeAudio?.pause();
    activeAudio = undefined;
    speechAnalyser = undefined;
    if (activeAudioUrl) URL.revokeObjectURL(activeAudioUrl);
    activeAudioUrl = undefined;
    speaking = false;
    activeUtterance = undefined;
    window.speechSynthesis?.cancel();
    refreshWave();
  }

  // Sentence-pipelined speech: each sentence is synthesized as soon as it is
  // pushed (while earlier ones play), so the first words start almost
  // immediately instead of after the whole reply has been generated.
  function createSpeechStream() {
    const requestId = ++activeAudioRequest;
    const pending = [];
    let closed = false;
    let wake;
    let failedText = "";
    const cancelled = () => requestId !== activeAudioRequest;
    const synthesize = (text) => fetch("/api/voice/synthesize", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "audio/wav" },
      body: JSON.stringify({ text, language: "auto" }),
    }).then((response) => {
      if (!response.ok) throw new Error("Local speech generation failed");
      return response.blob();
    });
    const playBlob = (blob) => new Promise((resolve, reject) => {
      activeAudioUrl = URL.createObjectURL(blob);
      activeAudio = new Audio(activeAudioUrl);
      speechAudioContext ||= new (window.AudioContext || window.webkitAudioContext)();
      speechAudioContext.resume().then(() => {
        const source = speechAudioContext.createMediaElementSource(activeAudio);
        speechAnalyser = speechAudioContext.createAnalyser();
        speechAnalyser.fftSize = 512;
        source.connect(speechAnalyser);
        speechAnalyser.connect(speechAudioContext.destination);
        activeAudio.onplay = () => {
          speaking = true;
          setPhase("speaking", "Speaking", "Speaking with Atulya's local Hindi/English voice.");
          refreshWave();
        };
        const cleanup = () => {
          activeAudio = undefined;
          speechAnalyser = undefined;
          if (activeAudioUrl) URL.revokeObjectURL(activeAudioUrl);
          activeAudioUrl = undefined;
        };
        activeAudio.onended = () => { cleanup(); resolve(); };
        activeAudio.onerror = () => { cleanup(); reject(new Error("playback failed")); };
        return activeAudio.play();
      }).catch(reject);
    });
    const done = (async () => {
      while (true) {
        if (!pending.length) {
          if (closed) break;
          await new Promise((resolve) => { wake = resolve; });
          continue;
        }
        const item = pending.shift();
        if (cancelled()) return;
        if (failedText) { failedText += ` ${item.text}`; continue; }
        try {
          const blob = await item.audio;
          if (cancelled()) return;
          await playBlob(blob);
        } catch {
          if (cancelled()) return;
          failedText = item.text;
        }
      }
      if (cancelled()) return;
      if (failedText) {
        speakWithBrowser(failedText, "Local voice is unavailable; using the browser voice.");
        return;
      }
      speaking = false;
      clearSpokenReply();
      restoreIdlePhase();
      markFollowUpWindow();
      resumeLiveVoice();
      refreshWave();
    })();
    return {
      push(text) {
        const clean = String(text || "").trim();
        if (!clean || closed || cancelled()) return;
        const item = { text: clean, audio: synthesize(clean) };
        item.audio.catch(() => {});
        pending.push(item);
        wake?.();
      },
      finish() {
        closed = true;
        wake?.();
        return done;
      },
    };
  }

  // Split streamed text into speakable sentences; returns [complete sentences, remainder].
  function takeSentences(buffer, flush = false) {
    const sentences = [];
    const pattern = /[^.!?।\n]*[.!?।\n]+["')\]]*\s+/g;
    let consumed = 0;
    let match;
    while ((match = pattern.exec(buffer))) {
      if (match[0].trim().length < 2) continue;
      sentences.push(match[0].trim());
      consumed = pattern.lastIndex;
    }
    let rest = buffer.slice(consumed);
    if (flush && rest.trim()) {
      sentences.push(rest.trim());
      rest = "";
    }
    return [sentences, rest];
  }

  function speak(text) {
    if (!localTtsReady) {
      speakWithBrowser(text, "Speaking with this browser's built-in voice.");
      return;
    }
    const stream = createSpeechStream();
    const [sentences] = takeSentences(`${text} `, true);
    sentences.forEach((sentence) => stream.push(sentence));
    return stream.finish();
  }

  function parseLayoutCommand(text) {
    const command = text.toLowerCase()
      .replace(/[.!?,]/g, " ")
      .replace(/^(?:(?:hey|okay|ok)\s+)?atulya\s+/, "")
      .replace(/^(?:can|could|would) you\s+/, "")
      .replace(/\b(the|my|side|right|left|please|box)\b/g, " ")
      .replace(/\s+/g, " ").trim();
    if (/^(restore|reset) (?:the )?layout$|^(show|restore) all (?:the )?(?:panels|sections)$/.test(command)) return { type: "restore" };
    if (/^(?:exit|leave|close) (?:the )?(?:camera )?(?:full ?screen|focus)(?: view)?$|^go back to (?:the )?normal layout$/.test(command)) return { type: "exit-focus" };
    if (/^(?:(?:show|open|go to|make) (?:it )?)?(?:full ?screen|fullscreen) (?:the )?(?:camera|camera preview)$|^(?:show|open) (?:the )?(?:camera|camera preview) (?:full ?screen|fullscreen)$/.test(command)) return { type: "focus-camera" };
    if (/^(?:(?:show|open|go to|make) (?:it )?)?(?:full ?screen|fullscreen) (?:the )?(?:system )?status(?: panel| section)?$|^(?:show|open) (?:the )?(?:system )?status(?: panel| section)? (?:full ?screen|fullscreen)$/.test(command)) return { type: "focus-status" };
    const panel = command.match(/^(show|open|display|add|hide|remove|close) (camera(?: preview)?|chat|conversation|system status|status|system)(?: (?:preview|panel|section))?$/);
    if (panel) {
      const name = panel[2].startsWith("camera") ? "camera" : ["chat", "conversation"].includes(panel[2]) ? "chat" : "status";
      return { type: "panel", name, visible: ["show", "open", "display", "add"].includes(panel[1]) };
    }
    if (/^(?:add|show) (?:a )?(?:new )?section\b/.test(command)) return { type: "unknown-section" };
    return null;
  }

  function showLayoutToast(message) {
    if (!layoutToast) return;
    layoutToast.textContent = message;
    layoutToast.hidden = false;
    window.clearTimeout(layoutToastTimer);
    layoutToastTimer = window.setTimeout(() => { layoutToast.hidden = true; }, 4200);
  }

  function exitFocusedLayout() {
    document.body.classList.remove("camera-focus", "status-focus");
    if (layoutFocusExit) layoutFocusExit.hidden = true;
  }

  function syncLayoutControls() {
    if (layoutVoiceToggle) {
      layoutVoiceToggle.hidden = !document.body.classList.contains("panel-chat-hidden");
      layoutVoiceToggle.textContent = voiceSessionActive ? "STOP VOICE" : "VOICE";
      layoutVoiceToggle.setAttribute("aria-label", voiceSessionActive ? "Stop live voice conversation" : "Start live voice conversation");
    }
  }

  async function applyLayoutCommand(command) {
    if (command.type === "unknown-section") return "I can show or hide the existing camera, chat, and system status panels. To add another section, tell me what information it should display.";
    if (command.type === "restore") {
      document.body.classList.remove("panel-camera-hidden", "panel-chat-hidden", "panel-status-hidden", "camera-focus", "status-focus");
      if (layoutFocusExit) layoutFocusExit.hidden = true;
      syncLayoutControls();
      return "All Atulya panels are back in their usual places.";
    }
    if (command.type === "exit-focus") {
      exitFocusedLayout();
      return "Back to the usual Atulya layout.";
    }
    if (command.type === "focus-camera") {
      if (!await enableCamera()) return "The camera could not start. Check camera access, then try again.";
      document.body.classList.remove("status-focus", "panel-camera-hidden");
      document.body.classList.add("camera-focus");
      if (layoutFocusExit) layoutFocusExit.hidden = false;
      return "Camera is full screen with gestures beside it. Say exit focus or press Escape to return.";
    }
    if (command.type === "focus-status") {
      document.body.classList.remove("camera-focus", "panel-status-hidden");
      document.body.classList.add("status-focus");
      if (layoutFocusExit) layoutFocusExit.hidden = false;
      return "System status is full screen. Say exit focus or press Escape to return.";
    }
    const className = { camera: "panel-camera-hidden", chat: "panel-chat-hidden", status: "panel-status-hidden" }[command.name];
    exitFocusedLayout();
    if (command.name === "camera" && command.visible) {
      document.body.classList.remove(className);
      const enabled = await enableCamera();
      return enabled ? "Camera preview shown." : "Camera panel shown, but the camera could not start. Check camera access and try again.";
    }
    document.body.classList.toggle(className, !command.visible);
    syncLayoutControls();
    const label = { camera: "camera preview", chat: "chat", status: "system status" }[command.name];
    if (command.name === "camera" && !command.visible) return "Camera preview hidden; the camera stays on for gestures. Say camera off to stop the camera.";
    return `${label[0].toUpperCase()}${label.slice(1)} ${command.visible ? "shown" : "hidden"}.`;
  }

  layoutFocusExit?.addEventListener("click", exitFocusedLayout);
  layoutVoiceToggle?.addEventListener("click", toggleListening);

  async function sendMessage(text, speakReply = false, includeVision = true) {
    const cleanText = text.trim();
    if (!cleanText) return;
    appendMessage("user", cleanText);
    conversation.push({ role: "user", content: cleanText });
    while (conversation.length > 38) conversation.shift();
    prompt.value = "";
    const layoutCommand = parseLayoutCommand(cleanText);
    if (layoutCommand) {
      const reply = await applyLayoutCommand(layoutCommand);
      const assistantMessage = appendMessage("assistant", reply);
      conversation.push({ role: "assistant", content: reply });
      if (speakReply) {
        highlightSpokenReply(assistantMessage);
        await speak(reply);
      } else {
        setPhase("idle", "Layout updated", reply);
        showLayoutToast(reply);
      }
      return;
    }
    const approval = approvalAnswer(cleanText);
    if (approval !== null) {
      const [latest] = [...pendingActions.keys()].slice(-1);
      setPhase("thinking", approval ? "Working" : "Cancelling", approval ? "Running the approved action." : "Cancelling the request.");
      const reply = await decideAction(latest, approval);
      if (speakReply && reply) await speak(reply);
      else setPhase("idle", "Ready", reply || "");
      return;
    }
    const voiceOption = cleanText.toLowerCase().match(/^(?:turn |switch )?(wake ?word|interrupt(?:ion)?s?|barge[ -]?in)\s+(on|off)$|^(?:turn |switch )?(on|off)\s+(?:the )?(wake ?word|interrupt(?:ion)?s?|barge[ -]?in)$/);
    if (voiceOption) {
      const name = voiceOption[1] || voiceOption[4];
      const enabled = (voiceOption[2] || voiceOption[3]) === "on";
      if (/wake/.test(name)) { wakeWordEnabled = enabled; setVoiceOption("atulya.voice.wake", enabled); }
      else { bargeInEnabled = enabled; setVoiceOption("atulya.voice.bargein", enabled); }
      const reply = /wake/.test(name)
        ? enabled ? "Wake word is on. Start with “Hey Atulya”." : "Wake word is off. I'll answer everything I hear."
        : enabled ? "Interrupting is on. Talk over me to stop me." : "Interrupting is off.";
      appendMessage("assistant", reply);
      conversation.push({ role: "assistant", content: reply });
      setPhase("idle", "Ready", reply);
      return;
    }
    const cameraEnabled = cameraCommand(cleanText);
    if (cameraEnabled !== null) {
      const enabled = cameraEnabled ? await enableCamera() : (stopCamera(), true);
      const reply = cameraEnabled
        ? enabled ? "Camera preview is on. Atulya is not analyzing the video yet." : "Camera preview could not start. Check camera permission or availability."
        : "Camera preview is off.";
      const assistantMessage = appendMessage("assistant", reply);
      conversation.push({ role: "assistant", content: reply });
      if (speakReply) {
        highlightSpokenReply(assistantMessage);
        await speak(reply);
      } else setPhase("idle", enabled ? "Camera preview on" : "Camera preview off", reply);
      return;
    }
    setPhase("thinking", "Thinking", "Working on your message.");
    let serviceUnavailable = false;
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream, application/json" },
        body: JSON.stringify({ messages: conversation, image: includeVision ? captureCameraFrame() : null, conversation_id: conversationId, stream: true }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        serviceUnavailable = [404, 405, 503].includes(response.status);
        const message = [404, 405].includes(response.status)
          ? "Atulya needs to restart to update chat. Restart the app, then try again."
          : response.status === 503
            ? "Chat is unavailable right now. You can still use the scene and camera preview."
            : "Atulya couldn't complete that message. Please try again.";
        throw new Error(message);
      }
      let reply = "";
      let assistantMessage = null;
      let speechStream = null;
      let speechBuffer = "";
      if (response.headers.get("content-type")?.includes("text/event-stream")) {
        if (!response.body) throw new Error("Atulya's reply stream was unavailable.");
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let pending = "";
        let streamError = "";
        const processEvent = (raw) => {
          const dataLine = raw.split(/\r?\n/).find((line) => line.startsWith("data:"));
          if (!dataLine) return;
          const event = JSON.parse(dataLine.slice(5).trim());
          if (event.error) streamError = String(event.error);
          if (event.confirm) showActionRequest(event.confirm);
          if (typeof event.text === "string" && event.text) {
            reply += event.text;
            if (speakReply && localTtsReady) {
              if (!speechStream) speechStream = createSpeechStream();
              const [sentences, rest] = takeSentences(speechBuffer + event.text);
              speechBuffer = rest;
              sentences.forEach((sentence) => speechStream.push(sentence));
            }
            if (!assistantMessage) assistantMessage = appendMessage("assistant", "", null, false);
            assistantMessage.textContent = reply;
            messagesNode.scrollTop = messagesNode.scrollHeight;
          }
        };
        while (true) {
          const { value, done } = await reader.read();
          pending += decoder.decode(value || new Uint8Array(), { stream: !done });
          let boundary;
          while ((boundary = pending.indexOf("\n\n")) >= 0) {
            processEvent(pending.slice(0, boundary).replace(/\r$/, ""));
            pending = pending.slice(boundary + 2);
          }
          if (done) break;
        }
        if (pending.trim()) processEvent(pending);
        if (streamError) throw new Error(streamError);
        if (assistantMessage) saveMessage(assistantMessage);
      } else {
        const body = await response.json().catch(() => ({}));
        reply = String(body.text || "").trim();
        assistantMessage = reply ? appendMessage("assistant", reply) : null;
        (body.confirm || []).forEach(showActionRequest);
      }
      reply = reply.trim();
      if (!reply) throw new Error("Atulya returned an empty response.");
      conversation.push({ role: "assistant", content: reply });
      if (speakReply && speechStream) {
        highlightSpokenReply(assistantMessage);
        takeSentences(speechBuffer, true)[0].forEach((sentence) => speechStream.push(sentence));
        await speechStream.finish();
      } else if (speakReply) {
        highlightSpokenReply(assistantMessage);
        await speak(reply);
      }
      else setPhase("idle", "Ready", "Atulya replied in chat.");
    } catch (error) {
      const message = error.message || "Atulya could not complete that reply.";
      if (speakReply && serviceUnavailable) voiceSessionActive = false;
      setPhase("idle", serviceUnavailable ? "Chat unavailable" : "Reply unavailable", message);
      appendMessage("notice", message);
      if (speakReply) {
        if (!serviceUnavailable) resumeLiveVoice();
      }
    }
  }

  async function releaseMicrophone() {
    if (microphoneStream) microphoneStream.getTracks().forEach((track) => track.stop());
    microphoneStream = undefined;
    if (microphoneContext) await microphoneContext.close().catch(() => {});
    microphoneContext = undefined;
    microphoneAnalyser = undefined;
    recorder = undefined;
    refreshWave();
  }

  function stopRecorder() {
    const activeRecorder = recorder;
    if (!activeRecorder || activeRecorder.state === "inactive") return Promise.resolve(new Blob(recorderChunks, { type: recordingMime }));
    return new Promise((resolve) => {
      activeRecorder.addEventListener("stop", () => resolve(new Blob(recorderChunks, { type: recordingMime })), { once: true });
      try { activeRecorder.stop(); } catch { resolve(new Blob(recorderChunks, { type: recordingMime })); }
    });
  }

  async function finishListening() {
    if (!listening || !recorder) return;
    const activeRequest = voiceRequest;
    listening = false;
    const audio = await stopRecorder();
    await releaseMicrophone();
    if (activeRequest !== voiceRequest) return;
    if (!audio.size) {
      setPhase("idle", "No voice heard", "Try speaking again or type below.");
      resumeLiveVoice();
      return;
    }
    setPhase("thinking", "Understanding", "Turning your speech into text.");
    try {
      const formData = new FormData();
      formData.append("audio", audio, recordingMime.includes("webm") ? "message.webm" : "message.audio");
      // Let Whisper detect the spoken language, including mixed Hindi and English.
      const response = await fetch("/api/voice/transcribe", { method: "POST", body: formData });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        const backendDetail = typeof body.detail === "string" ? body.detail.trim() : "";
        const message = [404, 405].includes(response.status)
          ? "Atulya needs to restart to update voice support. Restart the app, then try again."
          : response.status === 503
            ? backendDetail || "Local speech recognition is unavailable. Finish voice setup, then restart Atulya."
            : "Speech recognition failed. Try again or type below.";
        throw new Error(message);
      }
      const heard = String(body.text || "").trim();
      const transcript = heard ? applyWakeWord(heard) : "";
      if (transcript === null || (!heard && wakeWordEnabled)) {
        // Not addressed to Atulya: keep waiting quietly for the wake word.
        setPhase("idle", "Say “Hey Atulya”", "Waiting for the wake word. Everything stays on this device.");
        resumeLiveVoice();
        return;
      }
      if (!heard) throw new Error("No speech was recognized. Try again or type below.");
      if (!transcript) {
        setPhase("listening", "Yes?", "I'm listening.");
        resumeLiveVoice();
        return;
      }
      await sendMessage(transcript, true);
    } catch (error) {
      setPhase("idle", "I missed that", error.message || "Speech recognition failed. You can type below.");
      appendMessage("notice", error.message || "Local speech recognition failed.");
      if (voiceReady) resumeLiveVoice();
      else voiceSessionActive = false;
    }
  }

  async function cancelListening(message = "Voice capture stopped.") {
    voiceRequest += 1;
    voiceSessionActive = false;
    listening = false;
    if (recorder && recorder.state !== "inactive") {
      recorder.ondataavailable = null;
      try { recorder.stop(); } catch {}
    }
    recorderChunks = [];
    await releaseMicrophone();
    window.speechSynthesis?.cancel?.();
    releaseSpeech();
    restoreIdlePhase(message);
  }

  async function startListening(resume = false) {
    if (!resume) voiceSessionActive = true;
    if (!voiceReady) {
      voiceSessionActive = false;
      setPhase("idle", "Voice unavailable", "Local speech input is not ready. Restart Atulya after voice setup completes.");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      voiceSessionActive = false;
      voiceBrowserBlocked = true;
      setPhase("idle", "Voice unavailable", "This browser can't record microphone audio. You can type below.");
      return;
    }
    const AudioContextType = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextType) {
      voiceSessionActive = false;
      voiceBrowserBlocked = true;
      setPhase("idle", "Voice unavailable", "This browser can't measure microphone input. You can type below.");
      return;
    }
    const requestId = ++voiceRequest;
    listening = true;
    speechDetected = false;
    lastSpeechAt = 0;
    noiseFloor = 0.003;
    recorderChunks = [];
    setPhase("listening", "Allow microphone", "Grant microphone access once. Speech sends automatically after each pause.");
    try {
      microphoneStream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      if (requestId !== voiceRequest) {
        microphoneStream.getTracks().forEach((track) => track.stop());
        microphoneStream = undefined;
        return;
      }
      voiceBrowserBlocked = false;
      microphoneContext = new AudioContextType();
      microphoneAnalyser = microphoneContext.createAnalyser();
      microphoneAnalyser.fftSize = 512;
      microphoneContext.createMediaStreamSource(microphoneStream).connect(microphoneAnalyser);
      const mimeCandidates = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/webm"];
      recordingMime = mimeCandidates.find((mime) => MediaRecorder.isTypeSupported?.(mime)) || "";
      recorder = recordingMime ? new MediaRecorder(microphoneStream, { mimeType: recordingMime }) : new MediaRecorder(microphoneStream);
      recordingMime = recorder.mimeType || recordingMime || "audio/webm";
      recorder.ondataavailable = (event) => { if (event.data?.size) recorderChunks.push(event.data); };
      recorder.onerror = () => {
        cancelListening().then(() => {
          const message = "The browser stopped recording. Check microphone access or type below.";
          setPhase("idle", "Microphone error", message);
          appendMessage("notice", message);
        });
      };
      recorder.start(200);
      const waiting = wakeWordEnabled && Date.now() >= awakeUntil;
      setPhase("listening", waiting ? "Say “Hey Atulya”" : "Listening",
        waiting ? "Live voice is on. Start with “Hey Atulya”; talk over me to interrupt."
          : "Speak naturally. Each turn sends after a pause; Atulya then listens again.");
      refreshWave();
    } catch (error) {
      if (requestId !== voiceRequest) return;
      await releaseMicrophone();
      listening = false;
      voiceSessionActive = false;
      voiceBrowserBlocked = true;
      const errors = {
        NotAllowedError: "Microphone permission was denied. Allow microphone access in browser settings, or type below.",
        PermissionDeniedError: "Microphone permission was denied. Allow microphone access in browser settings, or type below.",
        NotFoundError: "No microphone was found. Connect a microphone or type below.",
        NotReadableError: "The microphone is busy or unavailable. Close other apps using it, or type below.",
        SecurityError: "Microphone capture requires localhost or a secure HTTPS page.",
      };
      setPhase("idle", "Microphone unavailable", errors[error.name] || error.message || "Allow microphone access or type below.");
    }
  }

  function toggleListening() {
    if (!voiceSessionActive) {
      startListening();
      return;
    }
    const shouldSendFinalSpeech = listening && speechDetected && recorder;
    voiceSessionActive = false;
    if (shouldSendFinalSpeech) finishListening();
    else cancelListening("Live voice stopped.");
  }

  waveform.addEventListener("click", toggleListening);
  cameraToggle?.addEventListener("click", toggleCamera);
  cameraDevice?.addEventListener("click", (event) => event.stopPropagation());
  cameraDevice?.addEventListener("change", async () => {
    selectedCameraDeviceId = cameraDevice.value;
    try { localStorage.setItem("atulya.camera.deviceId", selectedCameraDeviceId); } catch { /* Ignore unavailable storage. */ }
    stopCamera();
    await startCamera();
  });
  waveform.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      toggleListening();
    }
  });
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && (document.body.classList.contains("camera-focus") || document.body.classList.contains("status-focus"))) {
      exitFocusedLayout();
      return;
    }
    if (event.altKey && event.key.toLowerCase() === "m") {
      event.preventDefault();
      toggleListening();
    }
    if (event.key === "Escape" && voiceSessionActive) cancelListening("Live voice stopped.");
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (listening) {
      const typedText = prompt.value.trim();
      if (typedText) {
        cancelListening();
        sendMessage(typedText);
      }
    } else sendMessage(prompt.value);
  });
  window.addEventListener("resize", () => { resizeWave(); refreshWave(); });
  window.addEventListener("pagehide", () => { stopCamera(); cameraBus?.close(); }, { once: true });
  resizeWave();
  refreshWave();

  window.addEventListener("atulya:scene-ready", () => {
    sceneReady = true;
    greet();
  }, { once: true });
  if (window.__HUM_SCENE_READY) {
    sceneReady = true;
    queueMicrotask(greet);
  }

  function decodeBase64Url(value) {
    const binary = atob(String(value).replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(value.length / 4) * 4, "="));
    return Uint8Array.from(binary, (character) => character.charCodeAt(0));
  }

  function encodeBase64Url(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    for (const byte of bytes) binary += String.fromCharCode(byte);
    return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
  }

  function decodePublicKey(options) {
    const publicKey = { ...options };
    publicKey.challenge = decodeBase64Url(options.challenge);
    if (options.user?.id) publicKey.user = { ...options.user, id: decodeBase64Url(options.user.id) };
    for (const key of ["excludeCredentials", "allowCredentials"]) {
      if (Array.isArray(options[key])) publicKey[key] = options[key].map((item) => ({ ...item, id: decodeBase64Url(item.id) }));
    }
    return publicKey;
  }

  function serializeCredential(credential) {
    const response = credential.response;
    const serialized = {
      id: credential.id,
      rawId: encodeBase64Url(credential.rawId),
      type: credential.type,
      authenticatorAttachment: credential.authenticatorAttachment,
      clientExtensionResults: credential.getClientExtensionResults?.() || {},
      response: { clientDataJSON: encodeBase64Url(response.clientDataJSON) },
    };
    if (response.attestationObject) serialized.response.attestationObject = encodeBase64Url(response.attestationObject);
    if (response.authenticatorData) serialized.response.authenticatorData = encodeBase64Url(response.authenticatorData);
    if (response.signature) serialized.response.signature = encodeBase64Url(response.signature);
    if (response.userHandle) serialized.response.userHandle = encodeBase64Url(response.userHandle);
    if (response.getTransports) serialized.response.transports = response.getTransports();
    return serialized;
  }

  async function startAuthorizedApplication() {
    if (applicationStarted) return;
    applicationStarted = true;
    fetch("/api/health", { headers: { Accept: "application/json" }, cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((health) => {
        voiceReady = Boolean(health.voice_ready && navigator.mediaDevices?.getUserMedia && window.MediaRecorder);
        localTtsReady = Boolean(health.speech_ready);
        brainReady = Boolean(health.brain_configured);
        visionReady = Boolean(health.vision_ready);
        const name = health.assistant_name || "Atulya";
        healthLoaded = true;
        if (connectionDot) connectionDot.setAttribute("aria-label", "Atulya service online");
        if (!brainReady) {
          setPhase("idle", "Chat unavailable", "Text chat is offline right now. The scene remains available.");
        } else if (!voiceReady) {
          setPhase("idle", "Voice unavailable", "Text chat is ready. Voice input and speech are currently offline.");
        } else {
          setPhase("idle", "Ready", `Connected to ${name}. Type or allow microphone access to start voice automatically.`);
        }
        prompt.disabled = !brainReady;
        prompt.placeholder = brainReady ? "Type a message…" : "Chat is starting or unavailable";
        if (visionChannel) setChannelState(visionChannel, "off");
        void startCamera();
        return restoreConversation().then(greet);
      })
      .catch(() => {
        if (connectionDot) connectionDot.classList.add("offline");
        setPhase("idle", "Service unavailable", "Atulya could not be reached. Restart the app and try again.");
      });
    refreshSystemStatus();
    window.setInterval(() => {
      if (document.visibilityState === "visible") refreshSystemStatus();
    }, 3000); // live CPU/RAM/network meters
  }

  async function refreshAuthState() {
    try {
      const response = await fetch("/api/auth/status", { headers: { Accept: "application/json" }, cache: "no-store" });
      if (!response.ok) throw new Error("Atulya could not check the local session.");
      const auth = await response.json();
      authSetupRequired = Boolean(auth.setup_required);
      if (authSetupTokenWrap) authSetupTokenWrap.hidden = !auth.setup_token_required || !auth.setup_token_configured;
      if (auth.authenticated) {
        if (authDialog.open) authDialog.close();
        document.body.classList.remove("auth-required");
        if (addPasskeyButton) addPasskeyButton.hidden = false;
        if (document.getElementById("add-voice-unlock")) document.getElementById("add-voice-unlock").hidden = false;
        if (manageUsersButton) manageUsersButton.hidden = !auth.is_admin;
        if (signOutButton) signOutButton.hidden = false;
        startAuthorizedApplication();
        return;
      }
      if (cameraStream) stopCamera();
      document.body.classList.add("auth-required");
      if (addPasskeyButton) addPasskeyButton.hidden = true;
      if (manageUsersButton) manageUsersButton.hidden = true;
      if (signOutButton) signOutButton.hidden = true;
      if (authMessage) authMessage.textContent = auth.setup_token_required && !auth.setup_token_configured
        ? "Remote first-time setup is locked. Configure ATULYA_ADMIN_SETUP_TOKEN on the server, then reload this page."
        : authSetupRequired
        ? "Create the first administrator passkey to protect Atulya on this device."
        : "Unlock this local session with your device passkey.";
      if (authActivate) authActivate.textContent = authSetupRequired ? "CREATE ADMIN PASSKEY" : deviceLinkToken ? "ADD PASSKEY FOR THIS DEVICE" : "SIGN IN WITH PASSKEY";
      const voiceButton = document.getElementById("auth-voice-unlock");
      if (voiceButton) {
        let hasKey = false;
        try { hasKey = Boolean(localStorage.getItem("atulya.voiceUnlock")); } catch { /* storage blocked */ }
        voiceButton.hidden = !hasKey;
      }
      const passwordForm = document.getElementById("auth-password-form");
      if (passwordForm) passwordForm.hidden = !auth.password_login;
      if (authInviteWrap) authInviteWrap.hidden = authSetupRequired;
      if (authJoin) authJoin.hidden = authSetupRequired;
      if (!authDialog.open) authDialog.showModal();
    } catch (error) {
      document.body.classList.add("auth-required");
      if (authMessage) authMessage.textContent = error.message || "Atulya could not check sign-in status.";
      if (!authDialog.open) authDialog.showModal();
    }
  }

  // "#link=<token>" (from LINK A DEVICE) adds a passkey for an existing account on this device/address.
  let deviceLinkToken = "";
  {
    const match = location.hash.match(/(?:^#|&)link=([A-Za-z0-9_-]{16,128})/);
    if (match) {
      deviceLinkToken = match[1];
      history.replaceState(null, "", location.pathname + location.search);
    }
  }

  async function runPasskeyCeremony(kind) {
    if (!window.PublicKeyCredential || !navigator.credentials) {
      throw new Error("This browser does not support device passkeys. Update the browser or use a passkey-capable browser.");
    }
    const isRegistration = kind === "register" || kind === "invite";
    const setupToken = authSetupToken?.value.trim() || "";
    const inviteToken = kind === "invite" ? authInviteToken?.value.trim() || "" : "";
    const authHeaders = { Accept: "application/json" };
    if (isRegistration && setupToken) authHeaders["X-Atulya-Setup-Token"] = setupToken;
    if (inviteToken) authHeaders["X-Atulya-Invite-Token"] = inviteToken;
    if (isRegistration && deviceLinkToken) authHeaders["X-Atulya-Device-Token"] = deviceLinkToken;
    const optionsResponse = await fetch(`/api/auth/${isRegistration ? "register" : "login"}/options`, {
      method: "POST", headers: authHeaders, cache: "no-store",
    });
    const optionsBody = await optionsResponse.json().catch(() => ({}));
    if (!optionsResponse.ok) throw new Error(optionsBody.detail || "Passkey setup could not start.");
    const credential = isRegistration
      ? await navigator.credentials.create({ publicKey: decodePublicKey(optionsBody.options) })
      : await navigator.credentials.get({ publicKey: decodePublicKey(optionsBody.options) });
    if (!credential) throw new Error("The passkey operation was cancelled.");
    const verifyResponse = await fetch(`/api/auth/${isRegistration ? "register" : "login"}/verify`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json", Accept: "application/json",
        ...(isRegistration && setupToken ? { "X-Atulya-Setup-Token": setupToken } : {}),
        ...(inviteToken ? { "X-Atulya-Invite-Token": inviteToken } : {}),
        ...(isRegistration && deviceLinkToken ? { "X-Atulya-Device-Token": deviceLinkToken } : {}),
      },
      body: JSON.stringify({ flow_id: optionsBody.flow_id, credential: serializeCredential(credential) }),
      cache: "no-store",
    });
    const verifyBody = await verifyResponse.json().catch(() => ({}));
    if (!verifyResponse.ok) throw new Error(verifyBody.detail || "Passkey verification failed.");
    return verifyBody;
  }


  // ---- Sign in with a code (Telegram / email / approval on a signed-in device) ----
  let loginRequestId = "";
  let loginPoll = 0;
  const codeBox = document.getElementById("auth-code");
  const codeStatus = document.getElementById("auth-code-status");
  const codeInput = document.getElementById("auth-code-input");

  async function finishCodeLogin(response) {
    const body = await response.json().catch(() => ({}));
    if (body.authenticated) {
      window.clearInterval(loginPoll);
      loginRequestId = "";
      authDialog.close();
      document.body.classList.remove("auth-required");
      await refreshAuthState();
      return true;
    }
    if (body.state === "denied" || body.state === "expired") {
      window.clearInterval(loginPoll);
      codeStatus.textContent = body.state === "denied" ? "Sign-in was denied or locked. Start again." : "The code expired. Start again.";
    }
    return false;
  }

  document.getElementById("auth-code-start")?.addEventListener("click", async () => {
    codeBox.hidden = false;
    codeStatus.textContent = "Sending a code…";
    try {
      const response = await fetch("/api/auth/login-requests", {
        method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ username: document.getElementById("auth-username")?.value || "atulya" }), cache: "no-store",
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || "Could not start sign-in.");
      loginRequestId = body.id;
      codeStatus.textContent = `Code sent to ${body.channels.join(", ")}. Type or say it, or approve on a signed-in device. Expires in 5 minutes.`;
      codeInput.focus();
      window.clearInterval(loginPoll);
      loginPoll = window.setInterval(async () => {
        if (!loginRequestId) return;
        await finishCodeLogin(await fetch(`/api/auth/login-requests/${encodeURIComponent(loginRequestId)}`, { cache: "no-store" }));
      }, 2000);
    } catch (error) {
      codeStatus.textContent = error.message;
    }
  });

  document.getElementById("auth-code-submit")?.addEventListener("click", async () => {
    if (!loginRequestId) return;
    const ok = await finishCodeLogin(await fetch(`/api/auth/login-requests/${encodeURIComponent(loginRequestId)}/code`, {
      method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ code: codeInput.value }), cache: "no-store",
    }));
    if (!ok) codeStatus.textContent = "That code didn't match. Check it and try again.";
  });
  codeInput?.addEventListener("keydown", (event) => { if (event.key === "Enter") document.getElementById("auth-code-submit").click(); });

  document.getElementById("auth-code-say")?.addEventListener("click", async () => {
    if (!loginRequestId || !navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) return;
    const button = document.getElementById("auth-code-say");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      const chunks = [];
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (event) => { if (event.data?.size) chunks.push(event.data); };
      button.disabled = true;
      button.textContent = "LISTENING… 5s";
      recorder.start();
      await new Promise((resolve) => setTimeout(resolve, 5000));
      await new Promise((resolve) => { recorder.onstop = resolve; recorder.stop(); });
      stream.getTracks().forEach((track) => track.stop());
      const form = new FormData();
      form.append("audio", new Blob(chunks, { type: recorder.mimeType || "audio/webm" }), "code.webm");
      codeStatus.textContent = "Checking what you said…";
      const ok = await finishCodeLogin(await fetch(`/api/auth/login-requests/${encodeURIComponent(loginRequestId)}/voice`, { method: "POST", body: form }));
      if (!ok) codeStatus.textContent = "I couldn't match that. Say the six digits clearly, or type them.";
    } catch {
      codeStatus.textContent = "Microphone unavailable here. Type the code instead.";
    } finally {
      button.disabled = false;
      button.textContent = "SAY CODE";
    }
  });

  // Signed-in devices: show and announce sign-in requests from other devices.
  const shownLoginRequests = new Set();
  async function checkPendingLogins() {
    if (document.body.classList.contains("auth-required")) return;
    try {
      const response = await fetch("/api/auth/pending-logins", { headers: { Accept: "application/json" }, cache: "no-store" });
      if (!response.ok) return;
      for (const item of (await response.json()).requests || []) {
        if (shownLoginRequests.has(item.id)) continue;
        shownLoginRequests.add(item.id);
        const card = document.createElement("div");
        card.className = "chat-message action-card";
        card.innerHTML = "<strong>SIGN-IN REQUEST</strong><span></span><div><button class=\"approve\" type=\"button\">APPROVE</button><button type=\"button\">DENY</button></div>";
        card.querySelector("span").textContent = `Someone wants to sign in from ${item.label}.`;
        const [approve, deny] = card.querySelectorAll("button");
        const decide = async (yes) => {
          approve.disabled = deny.disabled = true;
          card.dataset.state = yes ? "approved" : "denied";
          await fetch(`/api/auth/pending-logins/${encodeURIComponent(item.id)}`, {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ approve: yes }),
          }).catch(() => {});
        };
        approve.addEventListener("click", () => decide(true));
        deny.addEventListener("click", () => decide(false));
        messagesNode.append(card);
        messagesNode.scrollTop = messagesNode.scrollHeight;
        if (!speaking) speak(`Someone is asking to sign in from ${item.label}. Approve only if it's you.`);
      }
    } catch { /* offline; try again next tick */ }
  }
  window.setInterval(checkPendingLogins, 3000);


  // ---- Voice unlock (trusted device + spoken phrase) -------------------------------
  const VOICE_KEY = "atulya.voiceUnlock";
  const readVoiceKey = () => { try { return JSON.parse(localStorage.getItem(VOICE_KEY) || "null"); } catch { return null; } };
  const voiceUnlockButton = document.getElementById("auth-voice-unlock");
  const addVoiceUnlockButton = document.getElementById("add-voice-unlock");

  async function recordSeconds(seconds) {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    const chunks = [];
    const recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (event) => { if (event.data?.size) chunks.push(event.data); };
    recorder.start();
    await new Promise((resolve) => setTimeout(resolve, seconds * 1000));
    await new Promise((resolve) => { recorder.onstop = resolve; recorder.stop(); });
    stream.getTracks().forEach((track) => track.stop());
    return new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
  }

  addVoiceUnlockButton?.addEventListener("click", async () => {
    const phrase = window.prompt("Choose a private unlock phrase (3+ words) you'll say to unlock THIS device, e.g. 'saffron rocket at midnight'. Don't use your password.");
    if (!phrase) return;
    const response = await fetch("/api/auth/voice-unlock/enroll", {
      method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ phrase }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) { appendMessage("notice", body.detail || "Voice unlock could not be set up."); return; }
    try { localStorage.setItem(VOICE_KEY, JSON.stringify({ id: body.id, secret: body.device_secret })); } catch { /* storage blocked */ }
    appendMessage("assistant", "Voice unlock is set up on this device. Next time, tap UNLOCK WITH VOICE and say your phrase.");
  });

  voiceUnlockButton?.addEventListener("click", async () => {
    const key = readVoiceKey();
    if (!key) return;
    voiceUnlockButton.disabled = true;
    voiceUnlockButton.textContent = "LISTENING… SAY YOUR PHRASE";
    try {
      const form = new FormData();
      form.append("unlock_id", key.id);
      form.append("device_secret", key.secret);
      form.append("audio", await recordSeconds(4), "phrase.webm");
      voiceUnlockButton.textContent = "CHECKING…";
      const response = await fetch("/api/auth/voice-unlock", { method: "POST", body: form });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || "That didn't unlock.");
      authDialog.close();
      document.body.classList.remove("auth-required");
      await refreshAuthState();
    } catch (error) {
      if (authMessage) authMessage.textContent = error.message || "Microphone unavailable here.";
    } finally {
      voiceUnlockButton.disabled = false;
      voiceUnlockButton.textContent = "UNLOCK WITH VOICE";
    }
  });

  document.getElementById("auth-password-toggle")?.addEventListener("click", (event) => {
    const field = document.getElementById("auth-password");
    const show = field.type === "password";
    field.type = show ? "text" : "password";
    event.currentTarget.setAttribute("aria-pressed", String(show));
    event.currentTarget.setAttribute("aria-label", show ? "Hide password" : "Show password");
    event.currentTarget.textContent = show ? "🙈" : "👁";
    field.focus();
  });

  document.getElementById("auth-password-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const password = document.getElementById("auth-password");
    try {
      const response = await fetch("/api/auth/password", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ username: document.getElementById("auth-username").value, password: password.value }),
        cache: "no-store",
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || "Sign-in failed.");
      password.value = "";
      authDialog.close();
      document.body.classList.remove("auth-required");
      await refreshAuthState();
    } catch (error) {
      if (authMessage) authMessage.textContent = error.message;
    }
  });

  authActivate?.addEventListener("click", async () => {
    authActivate.disabled = true;
    try {
      if (authMessage) authMessage.textContent = authSetupRequired ? "Follow your device prompt to create the admin passkey." : "Confirm with your device passkey.";
      await runPasskeyCeremony(authSetupRequired || deviceLinkToken ? "register" : "login");
      deviceLinkToken = "";
      if (authSetupToken) authSetupToken.value = "";
      await refreshAuthState();
    } catch (error) {
      if (authMessage) authMessage.textContent = error.message || "Passkey sign-in failed. Try again.";
    } finally {
      authActivate.disabled = false;
    }
  });

  authJoin?.addEventListener("click", async () => {
    authJoin.disabled = true;
    try {
      if (authMessage) authMessage.textContent = "Follow your device prompt to create your private passkey.";
      await runPasskeyCeremony("invite");
      if (authInviteToken) authInviteToken.value = "";
      await refreshAuthState();
    } catch (error) {
      if (authMessage) authMessage.textContent = error.message || "Invitation enrollment failed. Check the code and try again.";
    } finally {
      authJoin.disabled = false;
    }
  });

  addPasskeyButton?.addEventListener("click", async () => {
    addPasskeyButton.disabled = true;
    try {
      await runPasskeyCeremony("register");
      setPhase("idle", "Backup passkey added", "This device can now use another passkey to unlock Atulya.");
    } catch (error) {
      setPhase("idle", "Passkey not added", error.message || "Try again or use a different passkey device.");
    } finally {
      addPasskeyButton.disabled = false;
    }
  });

  signOutButton?.addEventListener("click", async () => {
    await fetch("/api/auth/logout", { method: "POST", headers: { Accept: "application/json" } }).catch(() => {});
    window.location.reload();
  });

  function appendUserAction(parent, label, action, danger = false) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    if (danger) button.dataset.danger = "true";
    button.addEventListener("click", action);
    parent.append(button);
  }

  async function refreshUsers() {
    if (!usersList) return;
    usersList.replaceChildren();
    try {
      const response = await fetch("/api/auth/users", { headers: { Accept: "application/json" }, cache: "no-store" });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || "Could not load local accounts.");
      const credentialsByUser = new Map();
      for (const item of body.credentials || []) {
        const list = credentialsByUser.get(item.user_id) || [];
        list.push(item);
        credentialsByUser.set(item.user_id, list);
      }
      for (const user of body.users || []) {
        const card = document.createElement("section");
        card.className = "user-entry";
        const title = document.createElement("strong");
        title.textContent = `${user.display_name} · ${user.role === "admin" ? "ADMIN" : "USER"}`;
        const detail = document.createElement("small");
        detail.textContent = user.credential_count ? `${user.credential_count} passkey(s)` : "Invitation pending";
        card.append(title, detail);
        for (const credential of credentialsByUser.get(user.id) || []) {
          const row = document.createElement("div");
          row.className = "credential-entry";
          const label = document.createElement("small");
          label.textContent = `Passkey · ${new Date(credential.created_at * 1000).toLocaleDateString()}`;
          row.append(label);
          appendUserAction(row, "REVOKE", async () => {
            const result = await fetch(`/api/auth/credentials/${encodeURIComponent(credential.credential_id)}`, { method: "DELETE" });
            if (!result.ok) {
              const data = await result.json().catch(() => ({}));
              setPhase("idle", "Passkey retained", data.detail || "Keep another passkey enrolled first.");
            } else if (credential.user_id === "admin") {
              window.location.reload();
              return;
            }
            await refreshUsers();
          }, true);
          card.append(row);
        }
        if (user.role !== "admin") {
          appendUserAction(card, "DISABLE USER", async () => {
            if (!window.confirm(`Disable ${user.display_name}? Their passkeys and sessions will be revoked. Saved records will remain on this device.`)) return;
            const result = await fetch(`/api/auth/users/${encodeURIComponent(user.id)}`, { method: "DELETE" });
            if (!result.ok) {
              const data = await result.json().catch(() => ({}));
              setPhase("idle", "User not disabled", data.detail || "Try again.");
            }
            await refreshUsers();
          }, true);
        }
        usersList.append(card);
      }
    } catch (error) {
      const message = document.createElement("p");
      message.textContent = error.message || "Local accounts are unavailable.";
      usersList.append(message);
    }
  }

  manageUsersButton?.addEventListener("click", () => {
    if (!usersDialog?.open) usersDialog?.showModal();
    void refreshUsers();
  });
  $("#close-users")?.addEventListener("click", () => usersDialog?.close());
  document.getElementById("link-device")?.addEventListener("click", async () => {
    try {
      const response = await fetch("/api/auth/device-link", { method: "POST", headers: { Accept: "application/json" } });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || "Could not create a device link.");
      inviteResult.hidden = false;
      inviteResult.replaceChildren();
      const label = document.createElement("span");
      label.textContent = `Open this on your phone or other computer within ${body.expires_minutes} minutes to add a passkey for your account:`;
      const code = document.createElement("code");
      code.textContent = body.url;
      const copy = document.createElement("button");
      copy.type = "button";
      copy.textContent = "COPY LINK";
      copy.addEventListener("click", async () => {
        try { await navigator.clipboard.writeText(body.url); copy.textContent = "COPIED"; }
        catch { copy.textContent = "SELECT LINK TO COPY"; }
      });
      inviteResult.append(label, code, copy);
    } catch (error) {
      setPhase("idle", "Device link not created", error.message || "Try again.");
    }
  });

  inviteUserForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = inviteUserForm.querySelector("button[type=submit]");
    button.disabled = true;
    try {
      const response = await fetch("/api/auth/users", {
        method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ display_name: inviteDisplayName.value }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || "Could not create an invitation.");
      inviteResult.hidden = false;
      inviteResult.replaceChildren();
      const label = document.createElement("span");
      label.textContent = `Share this one-time code with ${body.display_name} (expires in 24 hours):`;
      const code = document.createElement("code");
      code.textContent = body.invitation_token;
      const copy = document.createElement("button");
      copy.type = "button";
      copy.textContent = "COPY CODE";
      copy.addEventListener("click", async () => {
        try { await navigator.clipboard.writeText(body.invitation_token); copy.textContent = "COPIED"; }
        catch { copy.textContent = "SELECT CODE TO COPY"; }
      });
      inviteResult.append(label, code, copy);
      inviteDisplayName.value = "";
      await refreshUsers();
    } catch (error) {
      setPhase("idle", "Invitation not created", error.message || "Try again.");
    } finally {
      button.disabled = false;
    }
  });

  void refreshAuthState();
})();
