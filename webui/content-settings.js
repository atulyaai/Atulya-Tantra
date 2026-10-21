// Age & content settings (PLAN M12-6). Everything here is decided and enforced by the server;
// this page only shows the current state and sends the user's own choices.
(() => {
  const $ = (selector) => document.querySelector(selector);
  const dialog = $("#content-dialog");
  const state = $("#content-state");
  const dobForm = $("#birth-date-form");
  const dobInput = $("#birth-date");
  const adultRow = $("#adult-content-row");
  const adultBox = $("#adult-content");
  const LEVELS = { child: "Child-safe", adult: "Adult", adult_open: "Adult, adult topics allowed" };

  async function json(path, options = {}) {
    const response = await fetch(path, { headers: { "Content-Type": "application/json", Accept: "application/json" }, ...options });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Request failed.");
    return body;
  }

  async function refresh() {
    try {
      const settings = await json("/api/profile/content");
      state.textContent = `Current setting: ${LEVELS[settings.level] || settings.level}`
        + (settings.age_source === "admin" ? " (set by the administrator)" : "")
        + (settings.has_birth_date ? "" : ". Add your date of birth to change it.");
      dobForm.hidden = settings.has_birth_date || settings.age_source === "role";
      dobInput.max = new Date().toISOString().slice(0, 10);
      adultRow.hidden = settings.age_group !== "adult";
      adultBox.checked = Boolean(settings.adult_content);
    } catch (error) {
      state.textContent = error.message;
    }
  }

  $("#open-content-settings")?.addEventListener("click", () => {
    $(".account-menu")?.removeAttribute("open");
    if (!dialog.open) dialog.showModal();
    void refresh();
  });
  $("#close-content")?.addEventListener("click", () => dialog.close());

  dobForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!window.confirm(`Save ${dobInput.value} as your date of birth? You can't change it yourself afterwards.`)) return;
    try {
      await json("/api/profile/birth-date", { method: "PUT", body: JSON.stringify({ birth_date: dobInput.value }) });
    } catch (error) {
      state.textContent = error.message;
      return;
    }
    await refresh();
  });

  adultBox?.addEventListener("change", async () => {
    try {
      await json("/api/profile/adult-content", { method: "PUT", body: JSON.stringify({ enabled: adultBox.checked }) });
    } catch (error) {
      state.textContent = error.message;
    }
    await refresh();
  });

  // Admin: blocked requests from child accounts (category only, never the message).
  const events = $("#content-events");
  async function drawEvents() {
    if (!events) return;
    events.replaceChildren();
    try {
      const body = await json("/api/content-events");
      if (!body.events.length) return;
      const title = document.createElement("strong");
      title.textContent = "BLOCKED REQUESTS (child accounts)";
      events.append(title);
      for (const item of body.events.slice(0, 30)) {
        const row = document.createElement("small");
        row.textContent = `${new Date(item.at * 1000).toLocaleString()} · ${item.user_id} · ${item.category}${item.alerted ? " · alert sent" : ""}`;
        events.append(row);
      }
    } catch { /* not an administrator */ }
  }
  // Admin: the security log (PLAN M13-5): sign-ins, approvals, device jobs and admin changes.
  const securityLog = $("#security-log");
  async function drawSecurityLog() {
    if (!securityLog) return;
    securityLog.replaceChildren();
    try {
      const body = await json("/api/security-log?limit=40");
      const title = document.createElement("strong");
      title.textContent = `SECURITY LOG${body.intact ? "" : " · WARNING: the log was altered"}`;
      securityLog.append(title);
      for (const item of body.events) {
        const row = document.createElement("small");
        row.textContent = `${new Date(item.at * 1000).toLocaleString()} · ${item.kind} · ${item.actor} · ${item.action}`
          + `${item.target ? ` · ${item.target}` : ""} · ${item.outcome}${item.ip ? ` · ${item.ip}` : ""}`;
        securityLog.append(row);
      }
    } catch { /* not an administrator */ }
  }
  $("#manage-users")?.addEventListener("click", () => { void drawEvents(); void drawSecurityLog(); });
})();
