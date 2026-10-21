(() => {
  const $ = (selector) => document.querySelector(selector);
  const dialog = $("#control-dialog"), content = $("#control-content");
  const camera = $("#quick-camera");
  const shown = new Set();
  let polling = false;
  const node = (tag, text, className) => {
    const item = document.createElement(tag);
    if (text !== undefined) item.textContent = text;
    if (className) item.className = className;
    return item;
  };
  const when = (value) => new Date(value).toLocaleString();
  async function api(path, options = {}) {
    const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json", ...options.headers } });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      const error = new Error(response.status === 401 ? "Sign in to see your saved information." :
        response.status === 403 ? "This information is available to the owner account only." :
          (typeof body.detail === "string" ? body.detail : "Request failed. Please try again."));
      error.status = response.status;
      throw error;
    }
    return response.json();
  }
  function syncCamera() {
    if (!camera || camera.disabled) return;
    const active = document.body.classList.contains("camera-on");
    camera.setAttribute("aria-pressed", String(active));
    camera.dataset.status = active ? "green" : "red";
    const pip = camera.querySelector(".status-pip");
    if (pip) pip.className = `status-pip ${active ? "green" : "red"}`;
    camera.title = active ? "Camera: Live · Click to turn off" : "Camera: Inactive · Click to turn on";
  }
  new MutationObserver(syncCamera).observe(document.body, { attributes: true, attributeFilter: ["class"] });
  syncCamera();
  const legendDialog = $("#legend-dialog");
  $("#quick-legend")?.addEventListener("click", () => {
    if (legendDialog && !legendDialog.open) legendDialog.showModal();
  });
  $("#close-legend")?.addEventListener("click", () => legendDialog?.close());
  function open(title) {
    $("#control-title").textContent = title;
    content.replaceChildren(node("p", "Loading…"));
    if (!dialog.open) dialog.showModal();
  }
  function errorMessage(error) { content.append(node("p", error.message, "control-error")); }
  $("#close-control").addEventListener("click", () => dialog.close());
  document.addEventListener("atulya-device-status", (event) => {
    const notice = node("article");
    notice.append(node("strong", "Gesture needs attention"), node("p", event.detail.gesture));
    const dismiss = node("button", "Dismiss"); dismiss.addEventListener("click", () => notice.remove());
    notice.append(dismiss); $("#reminder-notices").append(notice);
  });
  async function maintenancePanel() {
    open("Maintenance & proposed fixes");
    try {
      const data = await api("/api/maintenance");
      content.replaceChildren(node("p", "Checks run every five minutes, including Google connection and companion heartbeat status. Jarvis can inspect listed WebUI/backend files and propose fixes with rollback. You review the diff and tests before applying. Authentication, secrets and deployment configuration are protected."));
      const auto = node("button", data.proactive.enabled ? "Automatic AI proposals on · Turn off" : "Automatic AI proposals off · Turn on");
      auto.addEventListener("click", async () => {
        auto.disabled = true;
        try { await api("/api/maintenance/proactive", { method: "PUT", body: JSON.stringify({ enabled: !data.proactive.enabled }) }); await maintenancePanel(); }
        catch (error) { errorMessage(error); auto.disabled = false; }
      });
      content.append(auto, node("small", "Uses your configured AI and may consume provider credits. Runs only for changed faults, at most once per hour. Sends an attention alert through connected owner Telegram/push channels. Proposes changes for review; never applies them automatically."));
      if (data.proactive.last_run.result) content.append(node("p", data.proactive.last_run.result));
      const check = node("button", "Check now"); check.type = "button";
      check.addEventListener("click", async () => {
        check.disabled = true;
        try { await api("/api/maintenance/check", { method: "POST" }); await maintenancePanel(); }
        catch (error) { errorMessage(error); check.disabled = false; }
      }); content.append(check);
      content.append(node("h3", "Latest check"));
      const health = data.health;
      content.append(node("p", health.checked_at ? when(health.checked_at) : "First check pending"));
      for (const finding of health.findings || []) content.append(node("p", `${finding.area}: ${finding.message}${finding.next_step ? " · " + finding.next_step : ""}`, "control-error"));
      if (health.checked_at && !health.findings?.length) content.append(node("p", "Asset presence and WebUI syntax checks passed. Physical camera and gesture recognition still need a device check."));
      content.append(node("h3", "Editable files"), node("p", (health.editable_files || []).join(", ")));
      content.append(node("p", health.skill_policy || "New skills can be proposed for owner review."));
      content.append(node("h3", "Proposed fixes"));
      if (!data.proposals.length) content.append(node("p", "No proposed fixes. Ask Jarvis to run maintenance_check, inspect a permitted file, and propose a fix."));
      for (const proposal of data.proposals) {
        const row = node("div", undefined, "control-row");
        row.append(node("strong", `${proposal.path} · ${proposal.state}`), node("p", proposal.reason), node("small", proposal.check));
        const details = node("details"), summary = node("summary", "Review changed lines"), diff = node("pre", proposal.diff);
        details.append(summary, diff); row.append(details);
        if (["proposed", "applied"].includes(proposal.state)) {
          const action = proposal.state === "applied" ? "rollback" : "apply";
          const button = node("button", action === "apply" ? "Approve & apply this patch" : "Roll back this patch");
          button.addEventListener("click", async () => {
            button.disabled = true;
            try { await api(`/api/maintenance/proposals/${proposal.id}/${action}`, { method: "POST" }); await maintenancePanel(); }
            catch (error) { errorMessage(error); button.disabled = false; }
          }); row.append(button);
        }
        content.append(row);
      }
    } catch (error) { content.replaceChildren(); errorMessage(error); }
  }
  $("#quick-maintenance").addEventListener("click", maintenancePanel);
  async function reminders() {
    open("Reminders & meetings");
    try {
      const data = await api("/api/reminders");
      content.replaceChildren(node("p", "Reminders appear in this page while Atulya is open and signed in. If you close it, overdue reminders appear when you return. Background or Telegram delivery is not enabled for these reminders."));
      const form = node("form");
      const messageLabel = node("label", "Remind me to");
      const message = node("input"); message.required = true; message.maxLength = 1000; message.name = "message";
      messageLabel.append(message);
      const dateLabel = node("label", "When (your device’s local time)");
      const date = node("input"); date.type = "datetime-local"; date.required = true; date.name = "due_at";
      dateLabel.append(date);
      const save = node("button", "Save reminder"); save.type = "submit";
      let editingId = null;
      const test = node("button", "Test a reminder in 10 seconds"); test.type = "button";
      const feedback = node("p"); feedback.setAttribute("role", "status");
      form.append(messageLabel, dateLabel, save, test, feedback); content.append(form);
      async function create(text, due) {
        save.disabled = test.disabled = true;
        try {
          const result = await api(editingId ? `/api/reminders/${editingId}` : "/api/reminders", { method: editingId ? "PUT" : "POST", body: JSON.stringify({ message: text, due_at: due.toISOString() }) });
          const savedId = editingId || result.id;
          await reminders();
          content.prepend(node("p", `Saved reminder #${savedId} for ${when(due.toISOString())}.`, "control-success"));
        } catch (error) { feedback.textContent = error.message; }
        finally { save.disabled = test.disabled = false; }
      }
      form.addEventListener("submit", (event) => { event.preventDefault(); void create(message.value, new Date(date.value)); });
      test.addEventListener("click", () => { editingId = null; void create("Reminder delivery test", new Date(Date.now() + 10000)); });
      content.append(node("h3", "Saved reminders"));
      if (!data.reminders.length) content.append(node("p", "No web reminders have been saved."));
      for (const item of data.reminders) {
        const row = node("div", undefined, "control-row");
        const state = item.cancelled_at ? "Cancelled" : item.shown_at ? `Shown in page ${when(item.shown_at)}` : "Scheduled";
        row.append(node("strong", `#${item.id} · ${item.message}`), node("small", `${when(item.due_at)} · ${state}`));
        if (!item.cancelled_at && !item.shown_at) {
          const edit = node("button", "Edit reminder"); edit.type = "button";
          edit.addEventListener("click", () => {
            editingId = item.id; message.value = item.message;
            const local = new Date(item.due_at);
            date.value = new Date(local.getTime() - local.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
            save.textContent = `Save changes to #${item.id}`; form.scrollIntoView({ block: "nearest" }); message.focus();
          }); row.append(edit);
          const cancel = node("button", "Cancel reminder"); cancel.type = "button";
          cancel.addEventListener("click", async () => {
            cancel.disabled = true;
            try { await api(`/api/reminders/${item.id}`, { method: "DELETE" }); await reminders(); }
            catch (error) { errorMessage(error); cancel.disabled = false; }
          }); row.append(cancel);
        }
        content.append(row);
      }
      content.append(node("h3", "Upcoming meetings"));
      const meetings = await api("/api/calendar?conversation_id=controls");
      if (!meetings.events.length) content.append(node("p", "No upcoming meetings saved."));
      for (const item of meetings.events) {
        const row = node("div", undefined, "control-row");
        row.append(node("strong", `#${item.id} · ${item.title}`), node("small", when(item.starts_at)));
        const remove = node("button", "Remove meeting");
        remove.addEventListener("click", async () => {
          remove.disabled = true;
          try { await api(`/api/calendar/${item.id}?conversation_id=controls`, { method: "DELETE" }); await reminders(); }
          catch (error) { errorMessage(error); remove.disabled = false; }
        }); row.append(remove); content.append(row);
      }
      if (!document.body.classList.contains("non-admin")) {
        content.append(node("h3", "Telegram reminder history"));
        const telegram = await api("/api/reminders/telegram");
        content.append(node("small", telegram.delivery));
        if (!telegram.reminders.length) content.append(node("p", "No reminders saved in the Telegram delivery queue."));
        for (const item of telegram.reminders) {
          const state = item.cancelled_at ? "Cancelled" : item.failed_at ? "Failed" : item.delivered_at ? "Sent to Telegram · phone alert unverified" : "Scheduled";
          const row = node("div", undefined, "control-row");
          row.append(node("strong", `#${item.id} · ${item.message}`), node("small", `${when(item.due_at)} · ${state}`));
          content.append(row);
        }
      }
    } catch (error) { content.replaceChildren(); errorMessage(error); }
  }
  $("#quick-reminders").addEventListener("click", reminders);
  $("#quick-connections").addEventListener("click", async () => {
    open("Connections & access");
    try {
      const data = await api("/api/connections");
      content.replaceChildren(node("h3", "Built-in plugins"));
      for (const plugin of data.plugins) {
        const row = node("div", undefined, "control-row");
        row.append(node("strong", plugin.name), node("small", `Access: ${(plugin.permissions || []).join(", ") || "Basic tools"}`));
        const toggle = node("button", plugin.enabled ? "Enabled · Disable" : "Disabled · Enable");
        toggle.type = "button";
        toggle.addEventListener("click", async () => {
          toggle.disabled = true;
          try {
            const result = await api(`/api/plugins/${encodeURIComponent(plugin.id)}`, {
              method: "POST", body: JSON.stringify({ enabled: !plugin.enabled }) });
            plugin.enabled = result.plugin.enabled;
            await refreshCapabilities();
            toggle.textContent = plugin.enabled ? "Enabled · Disable" : "Disabled · Enable";
          } catch (error) { errorMessage(error); }
          finally { toggle.disabled = false; }
        });
        row.append(toggle); content.append(row);
      }
      const capabilityPanel = node("div");
      async function refreshCapabilities() {
        const result = await api("/api/capabilities");
        capabilityPanel.replaceChildren(node("h3", "Tool readiness"), node("p", "Readiness does not confirm execution or device verification."));
        for (const cap of result.capabilities) {
          const row = node("div", undefined, "control-row");
          row.append(node("strong", `${cap.name} · ${cap.status.replaceAll("_", " ")}`), node("small", cap.description), node("small", cap.next_step));
          capabilityPanel.append(row);
        }
      }
      content.append(capabilityPanel);
      await refreshCapabilities();
      const googleAccount = node("button", "Google, Gmail & Calendar accounts");
      googleAccount.addEventListener("click", connectionsPanel); content.prepend(googleAccount);
      content.append(node("h3", "Skills"), node("p", "Skills provide workflow instructions. Their actions require connected tools and the same approvals."));
      if (!data.skills.length) content.append(node("p", "No skills installed."));
      for (const skill of data.skills) {
        const row = node("div", undefined, "control-row");
        row.append(node("strong", skill.name), node("small", skill.description)); content.append(row);
      }
      content.append(node("h3", "MCP"), node("p", data.mcp.incoming), node("p", data.mcp.outgoing),
        node("p", `Exported tools depend on enabled plugins: ${data.mcp.tools.join(", ")}`),
        node("h3", "Maintenance access"), node("p", data.maintenance));
      const form = node("form");
      const nameLabel = node("label", "Connection name"), name = node("input"); name.required = true; name.maxLength = 60; nameLabel.append(name);
      const urlLabel = node("label", "HTTPS MCP endpoint"), url = node("input"); url.required = true; url.type = "url"; url.placeholder = "https://your-server.example/mcp"; urlLabel.append(url);
      const add = node("button", "Save MCP connection"); add.type = "submit";
      form.append(nameLabel, urlLabel, node("small", "Use an endpoint you trust. Initial support connects servers without authentication. Saving does not grant any tools."), add);
      form.addEventListener("submit", async (event) => {
        event.preventDefault(); add.disabled = true;
        try { await api("/api/mcp/connections", { method: "POST", body: JSON.stringify({ name: name.value, url: url.value }) }); $("#quick-connections").click(); }
        catch (error) { errorMessage(error); add.disabled = false; }
      }); content.append(node("h3", "External MCP servers"), form);
      for (const connection of data.external_mcp || []) {
        const row = node("div", undefined, "control-row");
        row.append(node("strong", connection.name), node("small", connection.url), node("p", connection.status));
        const test = node("button", "Test & discover tools");
        test.addEventListener("click", async () => {
          test.disabled = true;
          try { await api(`/api/mcp/connections/${connection.id}/test`, { method: "POST" }); $("#quick-connections").click(); }
          catch (error) { errorMessage(error); test.disabled = false; }
        }); row.append(test);
        const remove = node("button", "Disconnect");
        remove.addEventListener("click", async () => {
          remove.disabled = true;
          try { await api(`/api/mcp/connections/${connection.id}`, { method: "DELETE" }); $("#quick-connections").click(); }
          catch (error) { errorMessage(error); remove.disabled = false; }
        }); row.append(remove);
        for (const tool of connection.tools) {
          const grant = node("button", `${tool.granted ? "Revoke" : "Grant"} ${tool.name}`);
          grant.title = tool.description;
          grant.addEventListener("click", async () => {
            grant.disabled = true;
            try { await api(`/api/mcp/connections/${connection.id}/grant`, { method: "POST", body: JSON.stringify({ tool: tool.name, granted: !tool.granted }) }); $("#quick-connections").click(); }
            catch (error) { errorMessage(error); grant.disabled = false; }
          }); row.append(grant);
        }
        content.append(row);
      }
    } catch (error) { content.replaceChildren(); errorMessage(error); }
  });
  $("#quick-status").addEventListener("click", async () => {
    open("Dashboard");
    const cameraOn = document.body.classList.contains("camera-on");
    content.replaceChildren(node("p", `Camera on this device: ${cameraOn ? "on" : "off"}. ${cameraOn ? ($("#gesture-result")?.textContent || "") : "Gesture detection waits for the camera."}`));
    content.append(node("p", "Connections manages granted MCP tools. Maintenance can diagnose issues and propose edits to permitted WebUI and skill files. Recent tool runs below show what actually executed."));
    try {
      const data = await api("/api/status?conversation_id=controls");
      const grid = node("div", undefined, "dashboard-grid"); content.append(grid);
      for (const key of ["service", "model", "cpu", "memory", "network", "host", "voice", "speech", "vision", "gesture", "telegram", "issue"]) {
        const row = node("div", undefined, "control-row");
        row.dataset.state = data[key]?.state || "unknown";
        row.append(node("strong", key.toUpperCase()), node("span", data[key]?.label || "Unknown")); grid.append(row);
      }
      content.append(node("h3", "Recent tool runs"));
      const activity = await api("/api/activity?limit=30");
      if (!activity.entries.length) content.append(node("p", "No recorded tool runs. This does not confirm that an action was completed."));
      for (const item of activity.entries) {
        const row = node("div", undefined, "control-row");
        row.append(node("strong", `${item.tool} · ${item.outcome}`), node("small", `${when(item.at)} · ${item.channel}`)); content.append(row);
      }
    } catch (error) { errorMessage(error); }
  });
  function googleConnect(features) {
    const url = new URL("/api/auth/google/start", location.origin);
    url.searchParams.set("connect", "true"); url.searchParams.set("features", features);
    if (window.AtulyaNative) window.AtulyaNative.postMessage(JSON.stringify({cmd:"google_login", url:url.href}));
    else location.assign(url.href);
  }
  async function connectionsPanel() {
    open("Connections");
    try {
      const google = await api("/api/google/status");
      content.replaceChildren(node("h3", "Google · Gmail & Calendar"),
        node("p", "Signing in to Atulya and granting Google service access are separate. Choose the services you want to connect."),
        node("p", google.connected ? `Connected: ${google.email || "Google account"}` : "Not connected"));
      if (!google.configured) content.append(node("p", "Google OAuth is not configured on the server."));
      if (google.last_error) content.append(node("p", google.last_error, "control-error"));
      content.append(node("small", `Granted scopes: ${(google.scopes || []).join(", ") || "None"}`));
      for (const [label, features] of [["Connect Gmail", "gmail"], ["Connect Calendar", "calendar"], ["Connect both", "all"]]) {
        const button = node("button", label); button.disabled = !google.configured;
        button.addEventListener("click", () => googleConnect(features)); content.append(button);
      }
      const test = node("button", "Test Google access");
      test.addEventListener("click", async () => {
        test.disabled = true;
        try { const result = await api("/api/google/test", {method:"POST"}); content.append(node("p", result.message)); }
        catch (error) { errorMessage(error); } finally { test.disabled = false; }
      });
      const disconnect = node("button", "Disconnect Google services");
      disconnect.addEventListener("click", async () => {
        disconnect.disabled = true;
        try { await api("/api/google/connection", {method:"DELETE"}); await connectionsPanel(); }
        catch (error) { errorMessage(error); disconnect.disabled = false; }
      }); content.append(test, disconnect);
      content.append(node("h3", "Telegram"), node("p", "Chat, reminders and scheduled updates use the server. Use Schedules to control recurring messages. Phone notification sound is controlled by Android and Telegram."));
      const readiness = await api("/api/readiness");
      content.append(node("h3", "What needs attention"));
      if (!readiness.findings.length) content.append(node("p", "Configured connections and recent device heartbeats are ready. Run service/device tests to verify execution."));
      for (const finding of readiness.findings) content.append(node("p", `${finding.message} · ${finding.next_step}`, "control-error"));
      content.append(node("h3", "WhatsApp Business"), node("p", "Not connected. The new Atulya Business account needs a Meta account, phone number and approved server credentials."));
      const mcp = node("button", "Manage MCP connections");
      mcp.addEventListener("click", () => $("#quick-connections")?.click()); content.append(mcp);
    } catch (error) { errorMessage(error); }
  }
  async function devicesPanel() {
    open("Devices & execution receipts");
    try {
      const data = await api("/api/devices");
      content.replaceChildren(node("p", "Each device has its own revocable credential and allowed actions. A queued request is not execution."));
      const refresh = node("button", "Refresh devices & receipts");
      refresh.addEventListener("click", devicesPanel); content.append(refresh);
      for (const device of data.devices) {
        const row = node("details", undefined, "control-row device-block");
        const deviceJobs = data.jobs.filter(job => job.device === device.name);
        const seen = device.seen ? new Date(device.seen * 1000).toLocaleString() : "never";
        row.append(node("summary", `${device.name} · ${device.status} · last seen ${seen}`),
          node("small", `Abilities: ${device.abilities.join(", ")}`));
        const jobList = node("div");
        jobList.append(node("h4", `Jobs (${deviceJobs.length})`));
        for (const job of deviceJobs.slice(0, 10)) jobList.append(node("p", `${job.kind} · ${job.status} · ${job.output || "No execution receipt yet."}`));
        row.append(jobList);
        const test = node("button", "Test connection");
        test.disabled = !device.abilities.includes("ping");
        test.addEventListener("click", async () => {
          test.disabled = true;
          const feedback = node("p", "Sending a ping; waiting for this device's receipt…"); row.append(feedback);
          try {
            const result = await api(`/api/devices/${encodeURIComponent(device.name)}/test`, {method:"POST"});
            const deadline = Date.now() + 15000;
            let finished = false;
            while (Date.now() < deadline && dialog.open) {
              const snapshot = await api("/api/devices");
              const job = snapshot.jobs.find(item => item.id === result.job.id);
              if (job && ["executed", "failed", "cancelled", "unconfirmed"].includes(job.status)) {
                feedback.textContent = `${job.status === "executed" ? "Connection verified" : job.status}: ${job.output || "No execution receipt"}`;
                finished = true; break;
              }
              await new Promise(resolve => setTimeout(resolve, 1000));
            }
            if (!finished) feedback.textContent = "No receipt yet. Start the companion on this device, then refresh Devices to inspect the queued ping.";
          } catch(error) { feedback.textContent = error.message; }
          finally { test.disabled = false; }
        }); row.append(test);
        const revoke = node("button", "Revoke device");
        revoke.addEventListener("click", async () => {
          revoke.disabled = true;
          try { await api(`/api/devices/${encodeURIComponent(device.name)}`, {method:"DELETE"}); await devicesPanel(); }
          catch (error) { errorMessage(error); revoke.disabled = false; }
        }); row.append(revoke); content.append(row);
      }
      const form = node("form");
      const typeSelect = node("select");
      typeSelect.style.cssText = "width:100%;margin-bottom:8px;padding:8px;border-radius:6px;background:#102630;color:#fff;border:1px solid #437181;";
      typeSelect.innerHTML = `
        <option value="phone">📱 Mobile Phone (Android / iOS)</option>
        <option value="tv">📺 Smart TV (Android TV / Fire TV)</option>
        <option value="tablet">📟 Tablet (iPad / Android Tab)</option>
        <option value="laptop" selected>💻 Laptop / PC (Windows / Mac / Linux)</option>
      `;
      const labelType = node("label", "Device type");
      labelType.append(typeSelect);

      const label = node("label", "Device name (e.g. Living Room TV, Pixel 9, MacBook)");
      const name = node("input"); name.required = true; name.maxLength = 40; name.placeholder = "Living Room TV"; label.append(name);
      const choices = node("fieldset"); choices.append(node("legend", "Granted abilities"));
      const allAbilities = [
        "ping", "say", "open_url", "open_app",
        "list_files", "read_file",
        "take_photo", "list_photos",
        "media_control", "send_sms", "place_call",
        "display_message", "battery_status"
      ];
      const presets = {
        phone: ["ping", "say", "take_photo", "list_photos", "send_sms", "place_call", "open_app", "battery_status"],
        tv: ["ping", "say", "media_control", "open_app", "open_url", "display_message"],
        tablet: ["ping", "say", "take_photo", "list_photos", "open_app", "list_files", "read_file", "display_message"],
        laptop: ["ping", "battery_status", "open_app", "open_url", "media_control", "display_message"]
      };
      const checkMap = {};
      const grants = [];
      choices.style.cssText = "display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:6px;";
      for (const ability of allAbilities) {
        const item = node("label", ability); item.style.cssText = "display:flex;align-items:center;gap:6px;font-size:13px;";
        const check = node("input"); check.type = "checkbox"; check.value = ability;
        check.style.cssText = "width:auto;margin:0;";
        check.checked = presets.laptop.includes(ability);
        checkMap[ability] = check;
        item.prepend(check); choices.append(item); grants.push(check);
      }
      typeSelect.addEventListener("change", () => {
        const selectedPreset = presets[typeSelect.value] || [];
        for (const ability of allAbilities) {
          if (checkMap[ability]) {
            checkMap[ability].checked = selectedPreset.includes(ability);
          }
        }
      });

      const pair = node("button", "Create device credential"); pair.type = "submit";
      form.append(labelType, label, choices, pair); content.append(form);
      form.addEventListener("submit", async (event) => {
        event.preventDefault(); pair.disabled = true;
        try {
          const result = await api("/api/devices/pair", {method:"POST", body:JSON.stringify({name:name.value, abilities:grants.filter(c=>c.checked).map(c=>c.value), device_type:typeSelect.value})});
          const secret = node("textarea"); secret.readOnly = true; secret.value = result.token;
          secret.style.cssText = "width:100%;height:60px;margin-top:8px;background:#031018;color:#65e7f5;font-family:monospace;padding:8px;";
          content.append(node("p", "Keep this credential private. On your PC run the command below and paste it into the hidden token prompt. Keep the companion running, then use Test connection. The current Android APK does not consume this device queue; an installed companion is required."), secret,
            node("pre", `python -m tools.device_companion --url ${location.origin}`));
        } catch (error) { errorMessage(error); } finally { pair.disabled = false; }
      });
      const orphanJobs = data.jobs.filter(job => !data.devices.some(device => device.name === job.device));
      if (orphanJobs.length) content.append(node("h3", "Jobs for removed devices"));
      for (const job of orphanJobs) {
        const row = node("div", undefined, "control-row");
        row.append(node("strong", `${job.device} · ${job.kind} · ${job.status}`), node("small", job.id), node("p", job.output || "No execution receipt yet.")); content.append(row);
      }
    } catch (error) { errorMessage(error); }
  }

  async function smartHomePanel() {
    open("Smart Home & Ambient Scenes");
    try {
      content.replaceChildren(node("p", "Automate room lighting, smart devices, and trigger ambient scenes."));
      const grid = node("div", undefined, "dashboard-grid");
      const scenes = [
        { id: "movie_mode", title: "🎬 Movie Mode", desc: "Dim lights to 20%, pause background audio, ready TV" },
        { id: "work_mode", title: "💼 Work Mode", desc: "100% daylight white, productivity audio & alerts" },
        { id: "goodnight", title: "🌙 Goodnight", desc: "Turn off all lights, verify sensors, mute non-emergencies" },
        { id: "relax", title: "☕ Relax", desc: "Warm ambient lighting with calming volume" }
      ];
      for (const scene of scenes) {
        const card = node("div", undefined, "control-row");
        card.append(node("strong", scene.title), node("small", scene.desc));
        const trigger = node("button", "Activate");
        trigger.addEventListener("click", async () => {
          trigger.disabled = true;
          try {
            const res = await api("/api/smarthome/scene", { method: "POST", body: JSON.stringify({ scene: scene.id }) });
            card.append(node("p", res.result));
          } catch (err) { errorMessage(err); } finally { trigger.disabled = false; }
        });
        card.append(trigger); grid.append(card);
      }
      content.append(grid);

      content.append(node("h3", "Direct Device Action"));
      const devForm = node("form");
      const devLabel = node("label", "Device or Entity Name (e.g. Desk Lamp, Living Room TV)");
      const devInput = node("input"); devInput.required = true; devInput.placeholder = "Desk Lamp"; devLabel.append(devInput);
      const actLabel = node("label", "Action (turn_on, turn_off, toggle)");
      const actInput = node("input"); actInput.value = "turn_on"; actLabel.append(actInput);
      const brightLabel = node("label", "Brightness % (optional, 0-100)");
      const brightInput = node("input"); brightInput.type = "number"; brightInput.min = 0; brightInput.max = 100; brightInput.placeholder = "80"; brightLabel.append(brightInput);
      const sendBtn = node("button", "Execute Command"); sendBtn.type = "submit";
      devForm.append(devLabel, actLabel, brightLabel, sendBtn); content.append(devForm);
      devForm.addEventListener("submit", async (e) => {
        e.preventDefault(); sendBtn.disabled = true;
        try {
          const res = await api("/api/smarthome/scene", {
            method: "POST",
            body: JSON.stringify({ device: devInput.value, action: actInput.value, brightness: brightInput.value ? parseInt(brightInput.value) : null })
          });
          content.append(node("p", res.result));
        } catch (err) { errorMessage(err); } finally { sendBtn.disabled = false; }
      });
    } catch (err) { errorMessage(err); }
  }

  async function expensesPanel() {
    open("Expenses & Financial Intelligence");
    try {
      const data = await api("/api/expenses");
      const summary = data.summary || { total_spent: 0, total_transactions: 0, by_category: {} };
      const card = node("div", undefined, "control-row");
      card.append(
        node("strong", `Total Spending: ₹${Number(summary.total_spent).toLocaleString("en-IN", {minimumFractionDigits: 2})}`),
        node("small", `${summary.total_transactions} recorded transactions`)
      );
      content.replaceChildren(card);

      const addForm = node("form");
      addForm.append(node("h3", "Log Expense"));
      const amtLabel = node("label", "Amount (₹)");
      const amtInput = node("input"); amtInput.type = "number"; amtInput.step = "any"; amtInput.required = true; amtInput.placeholder = "450"; amtLabel.append(amtInput);
      const merchLabel = node("label", "Merchant / Payee");
      const merchInput = node("input"); merchInput.required = true; merchInput.placeholder = "Swiggy / Amazon / Metro"; merchLabel.append(merchInput);
      const catLabel = node("label", "Category");
      const catSelect = node("select");
      catSelect.style.cssText = "width:100%;margin-bottom:8px;padding:8px;border-radius:6px;background:#102630;color:#fff;border:1px solid #437181;";
      catSelect.innerHTML = "<option>Food & Dining</option><option>Travel & Commute</option><option>Shopping</option><option>Utilities</option><option>Healthcare</option><option>Personal</option>";
      catLabel.append(catSelect);
      const submitExpense = node("button", "Record Expense"); submitExpense.type = "submit";
      addForm.append(amtLabel, merchLabel, catLabel, submitExpense); content.append(addForm);
      addForm.addEventListener("submit", async (e) => {
        e.preventDefault(); submitExpense.disabled = true;
        try {
          await api("/api/expenses", { method: "POST", body: JSON.stringify({ amount: parseFloat(amtInput.value), merchant: merchInput.value, category: catSelect.value }) });
          await expensesPanel();
        } catch (err) { errorMessage(err); submitExpense.disabled = false; }
      });

      const smsForm = node("form");
      smsForm.append(node("h3", "Test Bank / UPI SMS Parsing"));
      const smsLabel = node("label", "Paste Bank / UPI SMS Text");
      const smsInput = node("input"); smsInput.required = true; smsInput.placeholder = "Rs 450 spent on card at SWIGGY"; smsLabel.append(smsInput);
      const smsBtn = node("button", "Parse & Auto-Log"); smsBtn.type = "submit";
      smsForm.append(smsLabel, smsBtn); content.append(smsForm);
      smsForm.addEventListener("submit", async (e) => {
        e.preventDefault(); smsBtn.disabled = true;
        try {
          const res = await api("/api/expenses/parse-sms", { method: "POST", body: JSON.stringify({ sms_text: smsInput.value }) });
          if (res.parsed) { await expensesPanel(); } else { errorMessage(res.message); smsBtn.disabled = false; }
        } catch (err) { errorMessage(err); smsBtn.disabled = false; }
      });

      content.append(node("h3", "Recent Transactions"));
      for (const item of data.recent || []) {
        const row = node("div", undefined, "control-row");
        row.append(
          node("strong", `₹${Number(item.amount).toLocaleString("en-IN", {minimumFractionDigits: 2})} · ${item.merchant}`),
          node("small", `${item.category} · ${item.date}`)
        );
        content.append(row);
      }
    } catch (err) { errorMessage(err); }
  }

  $("#open-connections")?.addEventListener("click", connectionsPanel);
  $("#quick-devices")?.addEventListener("click", devicesPanel);
  $("#quick-smarthome")?.addEventListener("click", smartHomePanel);
  $("#quick-expenses")?.addEventListener("click", expensesPanel);

  async function weatherPanel(city="", period="today") {
    open("Weather & outlook");
    const form = node("form"),label = node("label","City"),input = node("input"),submit=node("button","Show weather");
    input.value=city;input.maxLength=100;label.append(input);submit.type="submit";form.append(label,submit);
    content.replaceChildren(form);
    form.addEventListener("submit",event=>{event.preventDefault();weatherPanel(input.value,period);});
    try {
      const data=await api(`/api/weather?city=${encodeURIComponent(city)}&when=${period}`);
      const card=node("p",data.summary);card.style.whiteSpace="pre-line";content.append(card);
      for (const [name,value] of [["Today","today"],["Tomorrow","tomorrow"],["7 days","week"]]) {
        const button=node("button",name);button.setAttribute("aria-pressed",String(value===period));
        button.addEventListener("click",()=>weatherPanel(input.value,value));content.append(button);
      }
      const daily=data.daily,days=daily.time || [],highs=daily.temperature_2m_max || [],lows=daily.temperature_2m_min || [];
      const points=days.map((day,i)=>({day,hi:highs[i],lo:lows[i],rain:daily.precipitation_probability_max?.[i]})).filter(p=>Number.isFinite(p.hi)&&Number.isFinite(p.lo));
      if (points.length) {
        const ns="http://www.w3.org/2000/svg",svg=document.createElementNS(ns,"svg");svg.setAttribute("viewBox","0 0 560 180");svg.setAttribute("role","img");svg.setAttribute("aria-label","Daily low and high temperature forecast, degrees Celsius");
        const title=document.createElementNS(ns,"title");title.textContent="Daily low and high temperatures (°C)";svg.append(title);
        const min=Math.min(...points.map(p=>p.lo))-2,max=Math.max(...points.map(p=>p.hi))+2;
        for (const [index,point] of points.entries()) {
          const x=40+index*480/Math.max(1,points.length-1),y=v=>130-(v-min)/(max-min)*105;
          const line=document.createElementNS(ns,"line");line.setAttribute("x1",x);line.setAttribute("x2",x);line.setAttribute("y1",y(point.hi));line.setAttribute("y2",y(point.lo));line.setAttribute("stroke","#65e7f5");line.setAttribute("stroke-width","10");svg.append(line);
          const text=document.createElementNS(ns,"text");text.setAttribute("x",x);text.setAttribute("y","158");text.setAttribute("text-anchor","middle");text.setAttribute("fill","#eefaff");text.setAttribute("font-size","11");text.textContent=`${point.lo}–${point.hi}°`;svg.append(text);
        }
        content.append(svg,node("small","Forecast range by day · Open-Meteo"));
        for (const point of points) content.append(node("p",`${point.day}: ${point.lo}–${point.hi}°C · rain ${point.rain ?? "?"}%`));
      }
    } catch(error){errorMessage(error);}
  }
  $("#quick-weather")?.addEventListener("click",()=>weatherPanel());

  async function phonePanel() {
    open("Phone actions");
    try {
      const data = await api("/api/phone/actions");
      content.replaceChildren(node("p", "SMS drafts and dialer requests prepared on the server appear here. Tap a request in the Android app. You send the SMS or place the call in the phone's own app."));
      if (!window.AtulyaNative) content.append(node("p", "Open this screen in the updated Atulya Android app to execute phone actions."));
      for (const item of data.requests) {
        const row = node("div", undefined, "control-row");
        row.append(node("strong", `${item.kind === "dial" ? "Call" : "SMS draft"} · ${item.number}`));
        if (item.body) row.append(node("p", item.body));
        const run = node("button", item.kind === "dial" ? "Open phone dialer" : "Open SMS composer");
        run.disabled = !window.AtulyaNative;
        run.addEventListener("click", () => {
          run.disabled = true;
          window.AtulyaNative.postMessage(JSON.stringify({cmd:item.kind,id:item.id,number:item.number,body:item.body}));
          row.append(node("small", "Waiting for the phone app's receipt…"));
        });
        const cancel = node("button", "Cancel request");
        cancel.addEventListener("click", async () => {
          try {await api(`/api/phone/actions/${item.id}/receipt`,{method:"POST",body:JSON.stringify({state:"cancelled"})});await phonePanel();}
          catch(error){errorMessage(error);}
        }); row.append(run,cancel);content.append(row);
      }
      if (!data.requests.length) content.append(node("p", "No pending phone requests. Ask Atulya to prepare an SMS or call with the number."));
    } catch (error) { errorMessage(error); }
  }
  document.addEventListener("atulya-phone-receipt", async event => {
    const receipt = event.detail;
    try {
      await api(`/api/phone/actions/${encodeURIComponent(receipt.id)}/receipt`,{method:"POST",body:JSON.stringify({state:receipt.status})});
      if (dialog.open && $("#control-title").textContent === "Phone actions") {
        await phonePanel();content.prepend(node("p", `${receipt.status.replaceAll("_"," ")}. No SMS send or completed call is verified.`));
      }
    } catch(error){errorMessage(error);}
  });
  $("#quick-phone")?.addEventListener("click",phonePanel);

  async function schedulesPanel() {
    open("Scheduled updates & recurring reminders");
    try {
      const data = await api("/api/automations");
      content.replaceChildren(node("p", "One-time reminders and recurring schedules are separate. This list shows the recurring Telegram updates."));
      for (const item of data.routines) {
        const row = node("div", undefined, "control-row");
        row.append(node("strong", item.name), node("small", `${data.types[item.action] || item.action} · ${item.days} ${item.when} · ${item.enabled ? "On" : "Paused"}`));
        const toggle = node("button", item.enabled ? "Pause" : "Resume");
        toggle.addEventListener("click", async () => {
          toggle.disabled = true;
          try { await api(`/api/automations/${encodeURIComponent(item.id)}`, { method: "PUT", body: JSON.stringify({ enabled: !item.enabled }) }); await schedulesPanel(); }
          catch (error) { errorMessage(error); toggle.disabled = false; }
        });
        const remove = node("button", "Delete schedule");
        remove.addEventListener("click", async () => {
          remove.disabled = true;
          try { await api(`/api/automations/${encodeURIComponent(item.id)}`, { method: "DELETE" }); await schedulesPanel(); }
          catch (error) { errorMessage(error); remove.disabled = false; }
        });
        row.append(toggle, remove); content.append(row);
      }
      if (!data.routines.length) content.append(node("p", "No recurring schedules."));
      const stop = node("button", "Cancel all one-time & recurring reminders");
      stop.addEventListener("click", async () => {
        stop.disabled = true;
        try {
          const result = await api("/api/reminders/cancel-all", { method: "POST" });
          await schedulesPanel();
          content.prepend(node("p", `Cancelled ${result.web_cancelled} app reminders and ${result.telegram_cancelled} Telegram reminders; paused ${result.recurring_reminders_disabled} recurring reminders. ${result.note}`));
        } catch (error) { errorMessage(error); stop.disabled = false; }
      });
      content.append(stop, node("small", data.delivery));
      const history=await api("/api/notifications");
      content.append(node("h3","Recent scheduled messages"),node("small",history.note));
      for(const item of history.deliveries) {
        const row=node("div",undefined,"control-row");
        row.append(node("strong",`${item.source} · ${item.status}`),node("small",new Date(item.created*1000).toLocaleString()),node("p",item.text));
        content.append(row);
      }

    } catch (error) { errorMessage(error); }
  }
  $("#quick-schedules")?.addEventListener("click", schedulesPanel);

  async function pollReminders() {
    if (polling || document.hidden) return;
    polling = true;
    try {
      const data = await api("/api/reminders?due_only=true");
      for (const item of data.reminders) {
        if (!shown.has(item.id)) {
          const notice = node("article");
          notice.append(node("strong", `Reminder #${item.id}`), node("p", item.message), node("small", `Due ${when(item.due_at)}`));
          const dismiss = node("button", "Dismiss"); dismiss.type = "button";
          dismiss.addEventListener("click", () => notice.remove()); notice.append(dismiss);
          // Dialogs occupy the browser's top layer. Put notices in the open dialog so they are visible there too.
          (dialog.open ? content : $("#reminder-notices")).prepend(notice);
          shown.add(item.id);
        }
        await api(`/api/reminders/${item.id}/shown`, { method: "POST" });
      }
    } catch (error) {
      if (error.status === 401) { shown.clear(); $("#reminder-notices").replaceChildren(); }
    } finally { polling = false; }
  }
  window.setInterval(pollReminders, 3000);
  document.addEventListener("visibilitychange", () => { void pollReminders(); });
  async function implementationPanel() {
    open("Work log: completed, active and unfinished");
    try {
      const report = await api("/api/implementation");
      content.replaceChildren(node("p", `${report.scope} Updated ${report.updated}.`));
      for (const item of report.items) {
        const row = node("div", undefined, "control-row");
        row.append(node("strong", `${item.title} · ${item.status.replaceAll("_", " ")}`));
        row.append(node("p", item.evidence), node("p", `Next: ${item.next}`));
        content.append(row);
      }
    } catch (error) { errorMessage(error); }
  }
  async function operationsPanel() {
    open("Server operations & critical alerts");
    try {
      const report = await api("/api/operations");
      content.replaceChildren(node("p", `Worker: ${report.worker_connected ? "connected" : "not connected"}. ${report.limits}`));
      const refresh = node("button", "Refresh operations");
      refresh.addEventListener("click", operationsPanel); content.append(refresh);
      const toggle = node("button", report.alerts_enabled ? "Mute critical server alerts" : "Enable critical server alerts");
      toggle.addEventListener("click", async () => {
        try { await api(`/api/operations/alerts/${!report.alerts_enabled}`, {method:"PUT"}); await operationsPanel(); }
        catch (error) { errorMessage(error); }
      });
      content.append(toggle, node("p", "To restart, ask Atulya to restart its service, review the approval, then check the receipt here. Telegram acceptance does not prove phone sound or delivery."));
      for (const item of report.jobs) content.append(node("p", `${item.kind} ${item.target} · ${item.status} · ${item.result || "No execution receipt yet"}`));
      for (const alert of report.alerts) content.append(node("p", `${alert.message} · ${alert.status}`));
    } catch (error) { errorMessage(error); }
  }
  async function tasksPanel() {
    open("Persistent diagnostic tasks");
    try {
      const report = await api("/api/tasks");
      content.replaceChildren(node("p", report.limits));
      const refresh = node("button", "Refresh tasks");
      refresh.addEventListener("click", tasksPanel); content.append(refresh);
      const start = node("button", "Check my devices and Google connection");
      start.addEventListener("click", async () => {
        start.disabled = true;
        try { await api("/api/tasks", {method:"POST", body:JSON.stringify({checks:["devices","google_connection"]})}); await tasksPanel(); }
        catch (error) { errorMessage(error); start.disabled = false; }
      });
      content.append(start);
      for (const task of report.tasks) {
        const row = node("div", undefined, "control-row");
        row.append(node("strong", `${task.id} · ${task.status} · ${task.checkpoint}/${task.plan.length} checks`));
        for (const result of task.results) row.append(node("pre", JSON.stringify(result, null, 2)));
        if (["queued","running"].includes(task.status)) {
          const cancel = node("button", "Cancel task");
          cancel.addEventListener("click", async () => {
            try { await api(`/api/tasks/${encodeURIComponent(task.id)}`, {method:"DELETE"}); await tasksPanel(); }
            catch (error) { errorMessage(error); }
          });
          row.append(cancel);
        }
        content.append(row);
      }
    } catch (error) { errorMessage(error); }
  }

  async function smartHomePanel() {
    open("Smart Home & Ambient Scenes");
    try {
      content.replaceChildren(node("p", "Automate room lighting, smart devices, and trigger ambient scenes."));
      const grid = node("div", undefined, "dashboard-grid");
      const scenes = [
        { id: "movie_mode", title: "🎬 Movie Mode", desc: "Dim lights to 20%, pause background audio, ready TV" },
        { id: "work_mode", title: "💼 Work Mode", desc: "100% daylight white, productivity audio & alerts" },
        { id: "goodnight", title: "🌙 Goodnight", desc: "Turn off all lights, verify sensors, mute non-emergencies" },
        { id: "relax", title: "☕ Relax", desc: "Warm ambient lighting with calming volume" }
      ];
      for (const scene of scenes) {
        const card = node("div", undefined, "control-row");
        card.append(node("strong", scene.title), node("small", scene.desc));
        const trigger = node("button", "Activate");
        trigger.addEventListener("click", async () => {
          trigger.disabled = true;
          try {
            const res = await api("/api/smarthome/scene", { method: "POST", body: JSON.stringify({ scene: scene.id }) });
            card.append(node("p", res.result));
          } catch (err) { errorMessage(err); } finally { trigger.disabled = false; }
        });
        card.append(trigger); grid.append(card);
      }
      content.append(grid);

      content.append(node("h3", "Direct Device Action"));
      const devForm = node("form");
      const devLabel = node("label", "Device or Entity Name (e.g. Desk Lamp, Living Room TV)");
      const devInput = node("input"); devInput.required = true; devInput.placeholder = "Desk Lamp"; devLabel.append(devInput);
      const actLabel = node("label", "Action (turn_on, turn_off, toggle)");
      const actInput = node("input"); actInput.value = "turn_on"; actLabel.append(actInput);
      const brightLabel = node("label", "Brightness % (optional, 0-100)");
      const brightInput = node("input"); brightInput.type = "number"; brightInput.min = 0; brightInput.max = 100; brightInput.placeholder = "80"; brightLabel.append(brightInput);
      const sendBtn = node("button", "Execute Command"); sendBtn.type = "submit";
      devForm.append(devLabel, actLabel, brightLabel, sendBtn); content.append(devForm);
      devForm.addEventListener("submit", async (e) => {
        e.preventDefault(); sendBtn.disabled = true;
        try {
          const res = await api("/api/smarthome/scene", {
            method: "POST",
            body: JSON.stringify({ device: devInput.value, action: actInput.value, brightness: brightInput.value ? parseInt(brightInput.value) : null })
          });
          content.append(node("p", res.result));
        } catch (err) { errorMessage(err); } finally { sendBtn.disabled = false; }
      });
    } catch (err) { errorMessage(err); }
  }

  async function expensesPanel() {
    open("Expenses & Financial Intelligence");
    try {
      const data = await api("/api/expenses");
      const summary = data.summary || { total_spent: 0, total_transactions: 0, by_category: {} };
      const card = node("div", undefined, "control-row");
      card.append(
        node("strong", `Total Spending: ₹${Number(summary.total_spent).toLocaleString("en-IN", {minimumFractionDigits: 2})}`),
        node("small", `${summary.total_transactions} recorded transactions`)
      );
      content.replaceChildren(card);

      const addForm = node("form");
      addForm.append(node("h3", "Log Expense"));
      const amtLabel = node("label", "Amount (₹)");
      const amtInput = node("input"); amtInput.type = "number"; amtInput.step = "any"; amtInput.required = true; amtInput.placeholder = "450"; amtLabel.append(amtInput);
      const merchLabel = node("label", "Merchant / Payee");
      const merchInput = node("input"); merchInput.required = true; merchInput.placeholder = "Swiggy / Amazon / Metro"; merchLabel.append(merchInput);
      const catLabel = node("label", "Category");
      const catSelect = node("select");
      catSelect.style.cssText = "width:100%;margin-bottom:8px;padding:8px;border-radius:6px;background:#102630;color:#fff;border:1px solid #437181;";
      catSelect.innerHTML = "<option>Food & Dining</option><option>Travel & Commute</option><option>Shopping</option><option>Utilities</option><option>Healthcare</option><option>Personal</option>";
      catLabel.append(catSelect);
      const submitExpense = node("button", "Record Expense"); submitExpense.type = "submit";
      addForm.append(amtLabel, merchLabel, catLabel, submitExpense); content.append(addForm);
      addForm.addEventListener("submit", async (e) => {
        e.preventDefault(); submitExpense.disabled = true;
        try {
          await api("/api/expenses", { method: "POST", body: JSON.stringify({ amount: parseFloat(amtInput.value), merchant: merchInput.value, category: catSelect.value }) });
          await expensesPanel();
        } catch (err) { errorMessage(err); submitExpense.disabled = false; }
      });

      const smsForm = node("form");
      smsForm.append(node("h3", "Test Bank / UPI SMS Parsing"));
      const smsLabel = node("label", "Paste Bank / UPI SMS Text");
      const smsInput = node("input"); smsInput.required = true; smsInput.placeholder = "Rs 450 spent on card at SWIGGY"; smsLabel.append(smsInput);
      const smsBtn = node("button", "Parse & Auto-Log"); smsBtn.type = "submit";
      smsForm.append(smsLabel, smsBtn); content.append(smsForm);
      smsForm.addEventListener("submit", async (e) => {
        e.preventDefault(); smsBtn.disabled = true;
        try {
          const res = await api("/api/expenses/parse-sms", { method: "POST", body: JSON.stringify({ sms_text: smsInput.value }) });
          if (res.parsed) { await expensesPanel(); } else { errorMessage(res.message); smsBtn.disabled = false; }
        } catch (err) { errorMessage(err); smsBtn.disabled = false; }
      });

      content.append(node("h3", "Recent Transactions"));
      for (const item of data.recent || []) {
        const row = node("div", undefined, "control-row");
        row.append(
          node("strong", `₹${Number(item.amount).toLocaleString("en-IN", {minimumFractionDigits: 2})} · ${item.merchant}`),
          node("small", `${item.category} · ${item.date}`)
        );
        content.append(row);
      }
    } catch (err) { errorMessage(err); }
  }

  $("#open-device-connections")?.addEventListener("click", () => {
    const menu = document.querySelector(".account-menu");
    if (menu) menu.open = false;
    void devicesPanel();
  });
  $("#quick-implementation")?.addEventListener("click", implementationPanel);
  $("#quick-operations")?.addEventListener("click", operationsPanel);
  $("#quick-tasks")?.addEventListener("click", tasksPanel);
})();
