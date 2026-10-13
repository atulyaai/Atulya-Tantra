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
    if (camera.disabled) return;
    const active = document.body.classList.contains("camera-on");
    camera.textContent = active ? "Camera on · Turn off" : "Camera off · Turn on";
    camera.setAttribute("aria-pressed", String(active));
  }
  new MutationObserver(syncCamera).observe(document.body, { attributes: true, attributeFilter: ["class"] });
  syncCamera();
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
      content.replaceChildren(node("p", "Automatic checks run every five minutes. Jarvis can inspect the permitted WebUI files and propose fixes. You review the diff before applying. Setup, authentication, secrets, deployment configuration, and scene files are protected."));
      const auto = node("button", data.proactive.enabled ? "Automatic AI proposals on · Turn off" : "Automatic AI proposals off · Turn on");
      auto.addEventListener("click", async () => {
        auto.disabled = true;
        try { await api("/api/maintenance/proactive", { method: "PUT", body: JSON.stringify({ enabled: !data.proactive.enabled }) }); await maintenancePanel(); }
        catch (error) { errorMessage(error); auto.disabled = false; }
      });
      content.append(auto, node("small", "Uses your configured AI and may consume provider credits. Runs only for changed faults, at most once per hour. Proposes changes for review; never applies them automatically."));
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
      for (const finding of health.findings || []) content.append(node("p", `${finding.area}: ${finding.message}`, "control-error"));
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
            toggle.textContent = plugin.enabled ? "Enabled · Disable" : "Disabled · Enable";
          } catch (error) { errorMessage(error); }
          finally { toggle.disabled = false; }
        });
        row.append(toggle); content.append(row);
      }
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
    content.replaceChildren(node("p", `Camera on this device: ${document.body.classList.contains("camera-on") ? "on" : "off"}. ${$("#gesture-result")?.textContent || ""}`));
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
})();
