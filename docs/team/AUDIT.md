# AUDIT

## S1-S5 verification (2026-10-22)

Tests: `pytest tests -q --ignore=tests/e2e`: **347 passed, 2 skipped in 293.3 s**.

| ID | Status | Evidence |
|---|---|---|
| S1 required user_id | **CLOSED** | `memory.py:49,59,75,85` and `history.py:139` now take `*, user_id: str` with no default. A missed argument is a TypeError, not an admin leak. |
| S2 explicit is_admin | **CLOSED** | `toolkit.py:291-294` returns `ctx.is_admin is True` and fails closed. `registry.py:32` defaults to None, which counts as not admin. |
| S3 Telegram allowlist binding | **PARTIAL** | Approvals are now bound to the requester: `ActionQueue.take(..., origin=f"tg:{id}")` (`toolkit.py:1202-1211`, `telegram.py:424,435,608`), so allowlist member B can't approve A's action from Telegram. Residual: every allowlisted id is still `OWNER_USER="admin"` (`telegram.py:26`) with shared memory and history and full admin tools. A web session (no origin) can still approve a Telegram-originated owner action, which is fine because it's the same account. Keep the allowlist to the owner only (document this in REMOTE_ACCESS/README). |
| S4 CSP | **CLOSED (local live check)** | `server.py:586-594`. Live on `atulya-check` :8599, signed out: the header is present (`default-src 'self'; script-src 'self' 'wasm-unsafe-eval' https://telegram.org https://www.youtube.com https://s.ytimg.com; …; frame-ancestors 'none'`) and `X-Frame-Options: DENY`. The console showed **no CSP violations**, only the expected 401s for signed-out `/api` calls and the Telegram WebView logs. The sign-in card renders, and the 3D scene loaded (`__HUM_SCENE_READY=true`, no fallback). `style-src 'unsafe-inline'` remains (low). The production site is not yet checked. |
| S5 device tools for users | **CLOSED** | `ask_device`/`device_action` were removed from `ADMIN_ONLY_TOOLS` (`toolkit.py:1159-1165`). They stay owner-scoped by `AgentHub`, which checks the device's owner. |

---

## M12-1/2/3 re-audit (2026-10-21)

Tests: `pytest tests -q --ignore=tests/e2e`: **337 passed, 2 skipped in 348.7 s**. Read-only; I tried to break it.

**Verified closed**
- **B21:** `pc-control` plugin and `smart_home_control` are marked `admin_only` (`toolkit.py:297-299,1159-1167`). They are stripped from non-admin toolboxes (`:1275-1278`) and refused again in `call` (`:1366`) and in `run_approved` (`:1438`). `TOOLS_BY_NAME` (`:1469`) is built after the `replace`, so the maintenance monitor gets the marked versions.
- **B22:** `POST /api/smarthome/scene` is admin in `route_access.py`. The middleware returns 403 before the handler runs (`server.py:251-254`).
- **B23:** `_owner_only` uses `_is_admin(ctx)` (`toolkit.py:291-303`). But see S2.
- **Route table:** every route is listed and `test_route_access.py` fails on an unlisted one. The admin entries match my earlier matrix, plus the new `/api/auth/users/{id}/content` and `/api/content-events`. Path params match `[^/]+`. A trailing slash is redirected by FastAPI and then re-checked.
- **Devices:** another account's device returns 404 (`device_api.py:39-43`). `voice_loop` pairing needs admin (`device_api.py:48`).
- **Per-user data:** `search_past_chats` → `history.search(..., ctx.user_id)` with `WHERE user_id=?` (`history.py:139-151`). Memory remember/forget/recall pass `user_id=ctx.user_id` (`toolkit.py:195-208`), and so do device listing (`:439`), reminders and expenses. No store call in `atulya/` or `tools/` omits `user_id` (grep).
- **MCP:** routes are admin, tools are admin_only and the context only gets `mcp_connections` for admins.
- **Security headers:** added (`server.py:2361-2366`). But see S4.

**New findings**
- **S1 (MEDIUM, fail-open default):** `memory.py:59,75,85` (`forget`/`list`/`relevant`) and `history.py:139` (`search`) default to `user_id="admin"`. Any future caller that forgets the argument silently reads or deletes the owner's data. Fix: make `user_id` a required keyword with no default. Tests then catch omissions.
- **S2 (MEDIUM, fail-open default):** `_is_admin` falls back to `ctx.user_id == "admin"` when `is_admin` is None (`toolkit.py:294`). Several contexts never set it (`telegram.py:539,566`, `server.py` maintenance monitor). Today they are all the owner, so nothing leaks, but admin rights still follow a magic id. Fix: default `False`, and set `is_admin=True` explicitly where the owner is known.
- **S3 (MEDIUM, design):** every Telegram allowlist id **is** the admin. They map to `OWNER_USER="admin"` (`telegram.py:26`, Mini App `server.py:1528-1529`), share one memory and history, and can approve any pending owner action (`telegram.py:418-421`, `take(action_id, OWNER_USER)`). If the owner adds a family member to `ATULYA_TELEGRAM_ALLOWLIST`, that person gets full admin, including PC control and MCP. Fix: document "allowlist = owner only". Members should use the approved-member path (`tg_<id>`), and the action owner should be bound to the specific Telegram id that triggered it.
- **S4 (MEDIUM, M13 partial):** the CSP is `object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'` (`server.py:2365`). It has no `default-src` or `script-src`, so it does nothing against XSS. Fix: add `default-src 'self'; script-src 'self'` (move the inline scripts out of `index.html` or hash them), and `connect-src 'self'`.
- **S5 (LOW, functional):** `ask_device` and `device_action` are admin_only (`toolkit.py:1160`). Normal users can pair their own devices (`route_access`: user) but cannot use them from chat. Either drop admin_only for these two (they are already owner-scoped by `AgentHub`), or hide pairing from non-admins.

---

## M12/M13 baseline (2026-10-21): multi-user isolation and web UI security

Read-only. I checked all 104 routes in `atulya/*.py`. "Scoped" means the handler passes `request.state.user_id` to its store. Session auth for every `/api/*` route is done by `SessionAuthMiddleware` (`server.py:~190-265`), except the public auth, app and push-key paths.

### Route matrix

| Routes | Admin-only? | Scoped by user? | Status |
|---|---|---|---|
| `/api/auth/users*`, `/api/auth/signups*`, `DELETE /api/auth/credentials/{id}` (`server.py:1481-1632`) | yes | n/a | OK |
| `/api/connections`, `POST /api/plugins/{id}`, `/api/reminders/telegram`, `/api/notifications` (`server.py:1657,1705,1832,1841`) | yes | n/a | OK |
| `/api/status`, `/api/activity` (`:1765,1849`) | partial (owner details gated at `:1781,:1853`) | n/a | OK |
| `/api/maintenance*`, `/api/mcp/*` (`workspace_api.py`, 10 handlers call `owner()`) | yes | n/a | OK |
| `/api/automations*`, `/api/reminders/cancel-all` (`automation_api.py`, `owner()` ×4) | yes | n/a | OK |
| `/api/memory`, `/api/calendar`, `/api/conversations*`, `/api/expenses*`, `/api/profile`, `/api/location`, `/api/reminders*`, `/api/music*`, `/api/phone/actions*`, `/api/devices*` | no (per-user data) | yes | OK |
| `/api/actions/{id}` (`:2209`) | no | yes (`take(id, user_id)`) | OK. **But see B21**: a user can approve PC actions for the host. |
| `/api/chat` (`:2024`) | no | yes | **B21**: the pc-control tools run on the owner's PC for any user. |
| `POST /api/smarthome/scene` (`:1954`) | **no** | n/a (home-wide) | **B22** |
| `/api/readiness` (`:681`) | no | yes | OK. Low: it reveals which integrations are configured. |
| `/api/plugins`, `/api/capabilities`, `/api/weather`, `/api/voice/*`, `/api/briefing`, `/api/music/search`, `/api/events` | no | yes / not needed | OK. Voice and briefing run on server CPU, rate-limited only for chat. |
| `/api/agents/*` (device bearer token) | device owner | yes | OK |

### What a normal `user` role can do today
Chat, memory, calendar, reminders, expenses, music queue, phone-action requests and device pairing for their own data. **They can also** do two things that belong to the owner:
- run `open_app`, `open_url`, `media_control`, `take_screenshot`, `search_files` and `read_document` **on the server/owner PC**. These tools need approval, but the user approves their own card.
- trigger home-wide smart-home actions.

### Findings
- **B21 (HIGH, M12):** `tools/plugins/toolkit.py:339-352` (`_pc`) and `:1009-1012` (`read_document`, low_risk) have no owner check. `Toolbox.__init__` (`:1155-1160`) strips pc-control only for the telegram/android channels or a headless host, never by role. A `user` account on the web can search the owner's Desktop, Documents and Downloads and read any document there (under `ask_risky` it is low-risk, so there is no card at all). They can also take screenshots of the owner's screen and open apps or URLs on it. Fix: drop the `pc-control` plugin tools in `Toolbox` unless `auth_store.is_admin(user_id)`. Return "owner only" from `_pc` as a second guard. Test: a user-role chat has no `search_files`/`read_document` schema, and calling the tool directly is refused.
- **B22 (HIGH, M12):** `server.py:1954-1959` `POST /api/smarthome/scene` has no admin check, and the `smart_home_control` tool (`toolkit.py`, confirm+low_risk) has no role check either. Any account can switch the owner's Home Assistant lights and switches once HASS is configured. Fix: owner-only, or a per-user grant list.
- **B23 (MEDIUM, M12):** `_owner_only` (`toolkit.py:289-290`) and `_cancel_all_reminders` (`:526`) compare `ctx.user_id == "admin"` literally, while routes use `auth_store.is_admin` (role). A second admin is denied, and the check depends on a magic id. Fix: pass `is_admin` into `PluginContext` once and use it everywhere.
- **M13-1 (MEDIUM):** there are no security headers at all. There is no `Content-Security-Policy`, `X-Frame-Options`/`frame-ancestors`, `X-Content-Type-Options` or `Referrer-Policy` (grep of `atulya/` and `webui/index.html`; only the Google callback sets Referrer-Policy at `google_auth.py:172`). The `SameSite=Strict` cookie stops a framed page from being signed in, which limits clickjacking. But with no CSP, any future XSS gets full access to the approval and passkey flows. Fix: a middleware adding `CSP: default-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'`, plus `nosniff` and `Referrer-Policy: same-origin`. Check that the inline scripts and styles in `index.html` still work.
- **M13-2 (OK):** CSRF is covered. Mutating methods with a foreign `Origin` or `Sec-Fetch-Site: cross-site` get 403 (`server.py:84-96`), and the session cookie is `HttpOnly; SameSite=Strict; Secure` on https (`:255-262`).
- **M13-3 (OK, watch):** `innerHTML` is used only with static strings (`assistant.js:835,929,986,2785,2932`, `controls.js:379,515`) and the gesture toast (`assistant.js:110`, values from the static `GESTURE_DEFINITIONS`). Model and user text go through `textContent`/`node()`, and links are limited to https with `noopener` (`assistant.js:1476-1482`). Add a lint rule that forbids `innerHTML` with template variables.
- **LOW:** any user can pair a device asking for the `voice_loop` ability. Use is refused later for non-admins (`server.py:208`), but pairing should refuse it up front.

---

## Deep-cleanup audit (2026-10-21): webui v1, atulya/, tools/

Read-only. A module counts as "unreferenced" when grep across atulya/, tools/, tests/, webui/ and the root scripts finds no import or launcher for it. Check CI and any external scripts before deleting.

**B17: CLOSED (code).** `atulya/server.py:185-209`: a voice_loop device token is accepted only on `/api/chat`, `/api/voice/transcribe` and `/api/voice/synthesize`, and only when the owner is an admin. `/api/actions/*` is explicitly excluded, so approving still needs a human session. Residual (LOW): through `/api/chat` the token runs every non-confirm tool as the admin (memory edits, maintenance read/propose, MCP list). Consider a voice-mode tool subset for device-token chats. Needs a test that `POST /api/actions/x` with a device bearer token returns 401.
**B15: fixed in code** (`server.py:1797-1800`: speech state comes from `speech_output.ready`). GOAL still shows it open with old line numbers. Tick it after a live check.

### Cleanup

| # | Action | Where | Why |
|---|---|---|---|
| CL1 | **remove** | `atulya-test-r36853fx/` (repo root, only `data/`) | Leftover temp dir from a test run. Also add `atulya-test-*` to .gitignore and make the test use `tmp_path`. |
| CL2 | **merge → remove** | `tools/laptop_agent.py` (13 lines, re-exports `device_companion`) | Duplicate entry point. Only `tests/core/test_device_jobs.py` imports it; point that test at `tools.device_companion`. |
| CL3 | **keep, document** | `tools/pc_companion_app.py` | The entry point for a packaged Windows exe (`dist/windows`?), not imported by code. If the exe build is gone, remove it. Otherwise note in the docstring which build script uses it. |
| CL4 | **remove or move to CI** | `tools/android_ui_test.py` (259 lines) | No workflow or script references it (no `.github/` in this checkout). Move it next to the release workflow that runs it, or delete it. |
| CL5 | **merge** | `tools/plugins/device.py` (`DeviceRegistry`, 165 lines) vs `tools/plugins/system/agents.py` (`AgentHub`) | Two device registries. Nothing imports `DeviceRegistry`/`init_device_registry`, and AgentHub is the live one. Remove `device.py` and keep the status vocabulary in `capabilities.py`. |
| CL6 | **merge** | `tools/plugins/routines.py` (377 lines: `RainTrigger`, `DiskFullTrigger`, `Workflow`, `RoutineScheduler`) vs `tools/plugins/productivity/routines.py` (live) | Two routine engines. The top-level one is used only by `tests/core/test_action_receipts.py`. Move the useful triggers (rain, LOC-07) into the live engine and remove the rest. |
| CL7 | **fix or remove** | `tools/plugins/information/document.py` (184 lines) | It is the FIL-02 document reader but nothing calls it: it is not a tool in `toolkit.TOOLS`. It also imports `fitz`/pymupdf (`:18`), while pyproject's `documents` extra installs **pypdf**, so PDF reading always falls back. Switch it to pypdf and register a `read_document` tool with folder limits, or remove it. |
| CL8 | **remove** | `webui/icons/favicon-48.png` | Not referenced by `index.html`, the manifest or JS. |
| CL9 | **document** | `webui/renderer.js` (1.1 MB minified Vite bundle) and `renderer.css` | A build output with no source in the repo (no `package.json` or `vite.config`). It can't be reviewed or rebuilt. Record where the source lives, or vendor it under `webui/vendor/` with a version note. The "dead" minified functions in it (`DE`, `MU`, …) are bundle internals, not cleanup targets. |
| CL10 | **fix docs** | `docs/CAPABILITIES.md:3,39,43,54,56,57,85` | Still "checked 2026-10-13". PLT-04 ✅ and PLT-08 ✅ are overstated: C3 is not built, and Linux secrets are plain base64. LOC-06, RES-01, RES-02 and DEV-02 are marked ⬜ though code exists (route_time, search_web/read_url, AgentHub). Firebase ⛔ (`:27`) is outdated, since the plan is now ntfy/Telegram. |
| CL11 | **fix docs** | `docs/GOAL.md` B15 line | The fix has landed (see above). Update its status and line reference. |

No new fake-success findings in webui v1 of the B7-B13 kind:
- **Reminder save:** the success text is shown only after the API call returns (`controls.js:122-125`).
- **Smart-home panel:** shows the server's honest `result`.
- **Status labels:** come from `/api/status` (`assistant.js:203`).
- **Swallowed `catch {}` blocks in `assistant.js`:** almost all are localStorage/sessionStorage guards. One exception is `assistant.js:1754`, where a failed screen action is silently ignored; see B19.

### New bugs (added to GOAL.md)
- **B19 (LOW)** `webui/assistant.js:1754`: `try { actions[action]?.(); } catch {}`. When `screen_control` fails, or the action name is unknown, nothing tells the user. The model has already said it was done. Fix: report failure back (a toast, plus a message in chat).
- **B20 (MEDIUM)** `tools/plugins/information/document.py:18`: the PDF reader depends on pymupdf, which is not installed (the lock has pypdf). FIL-02 cannot work even once it is wired up (see CL7).

---

## Bug hunt (2026-10-21): duplicates, fake status, success without a receipt

Code read directly; no code edited. Each item is also listed in GOAL.md "Known bugs" as B7 onward.

**Review of the B1 change (agents.py pairing dedupe, controls.js devices panel, test_device_dedupe.py):** correct for new pairings. The name key is normalised over case, spaces, `-` and `_`, and the tests cover the near-duplicate names, revoke-then-repair and other owners. Gaps:
- The dedupe does nothing for rows already on the server. B1 needs a one-off cleanup (revoke the extra rows), or a dry-run listing of near-duplicate groups.
- Jobs are keyed by device *name* (`controls.js:339`, `agents.py` jobs table). After a device is revoked and re-paired under the same name, the old device's jobs show up under the new device. Fix: key jobs by a device id, or filter by `created >= paired_at`.
- **Security (new, HIGH):** `ABILITIES = COMMANDS | {"voice_loop"}` (`agents.py:21`). The comment says a voice_loop device token can call the approve/deny routes as its owner. A device credential that can approve actions defeats the human approval step: a compromised companion, or the companion's own code, could queue and then approve `device_action`/`gmail_send`. Fix: device tokens must never reach `/api/actions/{id}`. Approval must come from a signed-in human session (or a native confirm on that device).

| ID | Sev | Where | Bug | Fix |
|---|---|---|---|---|
| B7 | HIGH | `webui2/app.js:1206-1222` | The Lights button flips to "ON" and toasts "Activated (80%)" before the request. It posts `{scene_id}`, but the server model needs `scene` (`server.py:394-395`), so every call returns 422, and the error is swallowed (`catch { /* Ignore */ }`). | Send `{scene}`, await the response, show `result` text only. On a non-2xx response, revert the toggle and show the error. |
| B8 | HIGH | `webui2/app.js:1225-1245`, `index.html:96-98` | The Security "ARMED/DISARMED" and Energy "ECO/BOOST" buttons only toggle local text and toasts. No backend call exists. | Remove them, or show "not connected" (disabled) until a real integration exists. |
| B9 | HIGH | `webui2/app.js:70-91` vs `server.py:1782+` | The CPU, RAM and disk gauges read `data.system.*`, but `/api/status` has no `system` key, so they always show the fallbacks 38% / 54% / 71%. The status always reads "OPTIMAL". On a network error the ping shows a fake "12 ms" (`:93`). | Read the real fields (`server.py:1738-1740` has `cpu`/`memory` levels), show "—" when missing, and show "offline" on errors. |
| B10 | HIGH | `webui2/index.html:178-191` | The weather card is hard-coded: "24°C Mostly Clear · Bangalore", humidity, AQI 38 and a 3-day forecast. | Load it from the weather API, or hide the card. |
| B11 | MEDIUM | `webui2/app.js:1252-1258` | Music Play toggles to ⏸ and toasts "Playing: Midnight Drive". There is no audio and no API call. | Wire it to `/api/music` or the player, or remove it. |
| B12 | MEDIUM | `webui2/app.js:715` | The boot toast always says "Optical Core: ASSEMBLED & ONLINE 🟢", regardless of server health. | Base it on the first `/api/status` result. |
| B13 | MEDIUM | `webui2/app.js:1115-1126` | The manual gesture "test" shows "Gesture Triggered … 95%" with a fixed confidence. Nothing is detected and no action runs. | Label it "demo", or route it through the real gesture handler. |
| B14 | MEDIUM | `tools/plugins/productivity/web_reminders.py:34-36`, `reminders.py:56`, `calendar.py:66-70` | Reminders and meetings have no idempotency. When the small model repeats a tool call (common), or the user resends, it creates identical rows: the same message or title and the same due time. This duplicates the reminders/calendar lists, and each copy fires. | Before inserting, check for an existing active row with the same user, message/title and due/start time (±60 s) and return it. Add a unique index or a test. |
| B15 | LOW | `server.py:1783`, `:1786-1789` | `/api/status` always reports `service: ready "Online"` and `speech: state "ready"` even when it falls back to the browser voice. The UI shows green when the local voice is missing. | Set `speech.state` from `speech_output.ready` (setup/ready). |
| B16 | LOW | `webui2/app.js:991` | "Voice bridge open — Listening..." is the browser's SpeechRecognition (`lang` hard-coded to en-US), not Atulya's local STT. That is misleading next to the "Whisper · local" status. | Say "Browser speech recognition", or use `/api/voice/transcribe`. |

Checked and OK: passkeys (`server.py:1150-1164` passes `exclude_credentials`, and credential_id is the primary key); push subscriptions (`push.py:31,60` key by endpoint with INSERT OR REPLACE, and 404/410 endpoints are pruned at `:121-131`); the webui Smart Home panel (`controls.js` smartHomePanel shows the server's `result` text, which is honest after H1); reminder notices are deduplicated by the `shown` set (`controls.js:676`).

---

## Re-audit 3 (2026-10-20): "Re-audit 2 fixes" + M1-1/M1-0

Re-run: `pytest tests -q --ignore=tests/e2e`: **179 passed, 1 skipped in 161.9 s**. Code read directly. No code edited.

| ID | Status | Evidence / gap |
|---|---|---|
| N1 honesty (cast/visual) | **CLOSED** | Results now say "Queued … not confirmed", and the test asserts that "Triggered" and "Casting to" are absent. |
| N2 lock file | **CLOSED on Windows / OPEN on Linux** | `requirements.lock.txt` exists (84 lines) and is tested. See N5. |
| N3 Silero VAD asset | **CLOSED** | `test_voice_deps.py::test_bundled_silero_vad_present` |
| C3 Android silent SMS/call | **PARTIAL (not compiled)** | `MainActivity.kt:410-430`: a native `AlertDialog` (`confirmNatively`, `:249-260`) is shown before send or call, and Cancel posts `cancelled`. That design is right. But it was never built or run (no JDK/SDK here), so it doesn't count as done. See N6. |
| H2 DNS-rebind residual, H3, H4, M1, M3, L1-L4 | **OPEN** | untouched |

**New findings**
- **N5 (HIGH, deploy):** the lock will likely fail on the Linux production server. `requirements.lock.txt:73` `tflite-runtime; sys_platform != "win32"` is unpinned, and tflite-runtime has no wheels for Python ≥3.12 (the lock header says it was built on 3.12). `openwakeword==0.6.0` pulls it in on Linux. The same marker also applies to macOS. Every other pin comes from the Windows venv and has not been checked against Linux wheels (onnxruntime, sherpa-onnx, ctranslate2, av). Fix:
  - give tflite-runtime the marker `python_version < "3.12"`, or exclude openwakeword from the server lock (wake word runs on the PC/phone, not the server) and use openWakeWord's `inference_framework="onnx"`;
  - have `make_lock.py` write `sys_platform == "linux"` instead of `!= "win32"`;
  - prove it with `pip install --dry-run --platform manylinux2014_x86_64 --python-version 3.12 --only-binary=:all: -r requirements.lock.txt`, or with a Linux CI job.
- **N6 (MEDIUM, C3 follow-up):** the SMS dialog shows `body.take(500)` (`MainActivity.kt:414`), but `sendDirectSms` sends up to 2000 chars. The user can approve text they never saw. Fix: show the full body (scrollable), or refuse bodies over 500 chars. Also add a "number not in contacts" warning. An on-device check (approve, cancel, back-press) is still needed.
- **N7 (LOW, correctness):** `local.py:17-27` `_wav_array` only catches `wave.Error`/`EOFError`. A truncated WAV with an odd byte count makes `np.frombuffer(..., "<i2")` raise `ValueError`, which surfaces as a 500 error instead of falling back to the temp-file path. Fix: catch `ValueError` as well, or trim to an even length. Add a test with a 16 kHz WAV truncated by one byte.
- **N8 (MEDIUM, evidence quality): `voice_bench.py` does not measure what M1 needs.**
  - The bench clip is the TTS-made 44.1 kHz WAV, so the new in-memory 16 kHz path from M1-1 is never exercised. The STT numbers are all from the temp-file path. Fix: resample the clip to 16 kHz mono or record a real 16 kHz clip.
  - `Toolbox(TOOLS, None)` (`voice_bench.py:62`) has no context, so tools with `needs_context`, reminders and location are dropped. "71 tool schemas" overstates the prompt. The "share your location" answer is an artefact of the bench, not of the product. Fix: build a `PluginContext` with a test user and a saved city, so the answer can be checked as correct.
  - The `_sentences` stop condition (`:33`) relies on `and`/`or` precedence and is hard to read. Add parentheses or a test.
  - `runtime.stop()` only kills a process it started (`local_llm.py:258-268`), so it does not kill an already-running owner server. OK.
- **N9 (INFO):** `ATULYA_STT_BEAM` (clamped 1-5) and `ATULYA_TTS_STEPS` (clamped 1-16) parse safely and fall back on bad input (`local.py:43-48`, `tts.py:64-68`). OK. The defaults are unchanged (base model, 8 steps), so production latency is the same as before. Steps 2/4 have had no listening check.

**M1 verdict:** the implementer's own numbers show the GOAL bar (<3 s, correct, 10/10) is **not met**. The real answer comes in 16-46 s with tools and 6.6-10.9 s without. The bottleneck is LLM prompt processing on a 4-core CPU. This is honest reporting and matches the code. Planner action needed: a voice-mode tool subset, prompt-cache reuse, `tiny.en`, or a GPU. There is still no microphone recording and no wake word or barge-in code.

---

## Re-audit 2 (2026-10-20): implementer Step 0 + Step V

Re-run: `pytest tests -q --ignore=tests/e2e`: **173 passed, 2 skipped in 113.6 s**. `test_approval_policy.py` and `test_voice_deps.py`: 22 passed. I verified this against the code, not only LOG.md.

| ID | Status | Evidence / remaining gap |
|---|---|---|
| C1 ask_device | **CLOSED (code + test)** | `toolkit.py:413-418` rejects non-read kinds and queues nothing. The new `device_action` (`:1023-1028`) is `confirm=True` and not low_risk, so it always asks. No other `AgentHub.enqueue` caller bypasses the Toolbox (grep of `atulya/`, `tools/`). Not live-checked in the WebUI. |
| C2 cast/visual | **CLOSED (code + test)** | `:1079` and `:1096`: confirm, not low_risk. |
| C3 Android silent SMS/call | **OPEN** | `MainActivity.kt:395-402` unchanged (deferred). |
| C4 calendar low_risk | **CLOSED** | `:1063-1068`: `low_risk` removed from update/delete. `calendar_create` stays low_risk (acceptable: creating an event is additive). |
| H1 smart-home honesty | **CLOSED (code + test)**, with a policy note | Now honest. It is `confirm + low_risk` (`:1073-1074`), so under `ask_risky` a configured HASS switches real devices with no card. Planner: decide whether that is intended. |
| H2 SSRF | **MOSTLY CLOSED** | `search.py:67-98`: https only, every resolved IP must be `is_global`, each redirect hop re-checked. Residual: DNS-rebinding TOCTOU (httpx re-resolves after the check), acknowledged in LOG. Fix: a transport that connects to the vetted IP with SNI/Host = hostname. |
| H3 secrets plaintext on Linux | **OPEN** | untouched |
| H4 in-memory queue | **OPEN** | untouched |
| M1 Telegram approvals | **OPEN** | untouched |
| M2 destructive memory/routine | **CLOSED** | `forget_fact` `:932-934`, `remove_routine` `:1042-1044`: confirm + low_risk |
| M3 CAPABILITIES stale | **OPEN** | not updated. PLT-04 ✅ is still overstated while C3 is open. |
| M4 untrusted web text | **CLOSED** | `wrap_untrusted` `:658-663`, plus the instruction text. Prompt-level only, so it reduces injection risk but does not eliminate it. |
| L1-L4 | **OPEN** | untouched |

**New findings**
- **N1 (MEDIUM, honesty):** queue-only tools still word their results as if the action happened. `visual_inspect` returns "Triggered visual inspection…" (`toolkit.py:531`). Nothing analyses the photo: the job is only `take_photo`, and no vision step reads the result. `cast_to_tv` returns "Casting to {tv}" (`:465`) when it has only queued a job. Fix: "Queued … not confirmed; see Devices for the receipt", as `_enqueue_device_job` already does.
- **N2 (HIGH, build):** `requirements.lock.txt` is missing at the repo root (confirmed: `Test-Path` returned False). `tools/bootstrap.py:299-301` raises `FileNotFoundError`, so a fresh `start.bat` install fails. The new voice, documents and pc extras are not locked anywhere. Fix: generate the lock from the current `.venv` (`pip freeze` filtered to the pyproject deps plus extras) and add a test that bootstrap's lock path exists.
- **N3 (LOW):** `pyproject.toml` relies on Silero VAD inside faster-whisper's assets (`:36`), an internal path of a third-party package. Pin faster-whisper tightly (already `<1.3`) and add a test that the asset file exists.
- **N4 (evidence):** the voice "live evidence" is a TTS→STT round trip in a scratch script, with no microphone. Warm STT is 1.37 s against a 0.8 s budget. M1 is still unproven, and the PLAN live checks in the WebUI (approval card, 127.0.0.1 blocked, lights without HASS) were **not run**. Per GOAL, C1/C2/H1/H2 count as closed in code and tests, but not as "done".

---

# Baseline (2026-10-20)

Auditor role: read-only review. No code was edited. `docs/team/LOG.md` and `PLAN.md` did not exist when this ran, so this is the **baseline audit** against `docs/GOAL.md` and `docs/CAPABILITIES.md`.

Test run: `.venv\Scripts\python.exe -m pytest tests -q -x --ignore=tests/e2e` — result: see "Test results" at the bottom.

Ranked by severity. Each finding: where it is, what is wrong, how to fix it.

---

## CRITICAL — breaks GOAL rule 8 ("anything that changes files or sends outside asks first")

### C1. `ask_device` sends SMS, places calls, reads files and takes photos with no approval
- `tools/plugins/toolkit.py:986-990` registers `ask_device` with `confirm=False` (the explicit `True, False` at :990). The enum includes `send_sms`, `place_call`, `read_file`, `take_photo`, `open_app`.
- `tools/plugins/toolkit.py:408-418` puts the job straight into `AgentHub.enqueue` (`tools/plugins/system/agents.py:63`), and the device executes it on its next poll. The only gate is "device was paired with that ability".
- Failure case: a prompt-injected web page read via `read_url`, or an injected email from `gmail_search`, tells the model "ask_device Phone send_sms …". It gets queued and run without the user ever seeing it.
- **Fix:** split it up. Read-only kinds (`ping`, `battery_status`, `list_files`, `list_photos`) can stay direct. Everything else (`send_sms`, `place_call`, `read_file`, `take_photo`, `open_url`, `open_app`, `say`, `display_message`, `media_control`) goes through `confirm=True` with a `describe` showing device, kind and detail. Add a test asserting `Toolbox.call("ask_device", {"command":"send_sms",...})` returns "Approval requested" and creates no job.

### C2. `cast_to_tv` and `visual_inspect` also skip approval
- `toolkit.py:1035-1039` (`cast_to_tv`, `True, False`) enqueues `open_url`/`media_control` on a device. `toolkit.py:1051-1055` (`visual_inspect`) enqueues `take_photo` (`toolkit.py:501-513`), which turns on a camera with no consent.
- **Fix:** `confirm=True` on both. The camera should never fire without a fresh approval.

### C3. Android bridge can send SMS and place calls silently
- `android/.../MainActivity.kt:395-402` (`send_sms_direct`, `call_direct`) → `sendDirectSms` at `:231` uses the SEND_SMS permission with no on-device confirmation. Any script running in the allowed origin's main frame (`:359`), for example after an XSS in the WebUI, can text or call any number. Right now no JS in the repo calls these commands, so this is latent attack surface with no feature behind it.
- **Fix:** remove both commands, or require a native confirmation dialog in Kotlin (number and body shown, user taps Send) before `SmsManager`/`ACTION_CALL`. Never trust the web layer for this.

### C4. Calendar delete/update/create run without approval when safety = `ask_risky`
- `toolkit.py:1231-1237`: for `confirm and low_risk` tools the approval step is skipped when the profile is `ask_risky`. `calendar_delete` (`:1027-1029`) is marked `low_risk=True`, and its description says "directly". Deleting an external Google event is a destructive outside change.
- **Fix:** drop `low_risk` from `calendar_delete` and `calendar_update`. Keep `low_risk` only for read-only or easily reversible actions.

## HIGH

### H1. Honesty violation: smart-home claims success when nothing happened
- `tools/plugins/system/smart_home.py:54-57`: any scene name returns "Triggered scene '…'" and never calls Home Assistant. `:81-83`: with no HASS configured it returns "Smart home action dispatched: … set to …". Both break GOAL rule 7 ("says done only after something actually happened").
- `toolkit.py:1030-1034`: it also has no `confirm`, and it does change physical devices.
- **Fix:** with no bridge, return "Not connected: set HASS_URL/HASS_TOKEN; nothing was changed." Run the scene actions for real, or report "unsupported". Add `confirm=True, low_risk=True`.

### H2. SSRF: `read_url` fetches any URL, including localhost and the LAN
- `toolkit.py:627-635` accepts `http://` and `tools/plugins/information/search.py:56-60` fetches with `follow_redirects=True` and no host check. The model, or an injected page, can read `http://127.0.0.1:<port>/api/...`, Home Assistant, the router admin page or cloud metadata (`169.254.169.254`) on the server, and the text comes back into chat.
- **Fix:** resolve the host and reject private, loopback, link-local and reserved IPs (`ipaddress.ip_address(...).is_global`). Re-check after every redirect (handle redirects manually, max 3). Allow https only by default.

### H3. "Secrets encrypted at rest" (PLT-08 ✅) is false on Linux, i.e. the production server
- `atulya/secrets_store.py:46-48`: off Windows the store is `PLAIN:` + base64, which is not encryption. `set_secret` (`:75-85`) also never `chmod 0600`s on non-Windows (only `protect` does, at `:106`).
- **Fix:** mark PLT-08 as 🔧 "Windows only". On Linux, use `keyring`/Secret Service or at minimum chmod 600 in `set_secret` as well. Add a test that the file mode is 0600 after `set_secret`.

### H4. Approval queue lives only in memory and is consumed before execution
- `toolkit.py:1077-1098`: `ActionQueue` is a process dict with a 180 s TTL. A restart drops pending approvals silently. `server.py:2112` pops the action and then runs it, so a crash or timeout during the run leaves no record that it was approved.
- Lower risk, but it matters for M5 ("approved actions on the paired laptop"). **Fix:** persist pending and approved actions (SQLite, like `AgentHub`) with a status. Show expired ones to the user as "expired, not run".

## MEDIUM

### M1. Telegram and Android channels cannot approve anything
- `toolkit.py:1240-1241`: with no `actions` view the tool returns "only available in the Atulya WebUI". CAPABILITIES says Telegram supports "approvals". Combined with C1/C2, the unsafe tools are exactly the ones that work everywhere and the safe ones are the ones that fail.
- **Fix:** Telegram inline-keyboard Approve/Deny that calls the same `ActionQueue.take`, bound to the Telegram user to account mapping.

### M2. Mutating memory, profile, routine and expense tools run directly
- `remember_fact`, `edit_fact`, `forget_fact` (`toolkit.py:897-902`), `update_profile` (`:941`), `add/edit/remove_routine` (`:993-1005`), `log_expense`, `parse_transaction_sms` (`:1040-1050`) change data on disk with no approval. `forget_fact` deletes by fuzzy query. This is defensible as a product choice (GOAL rule 8 is about "files"), but `forget_fact` and `remove_routine` are destructive and reachable through prompt injection.
- **Fix:** at least `forget_fact` and `remove_routine` should be `confirm=True, low_risk=True`. The planner should write the policy down explicitly.

### M3. `docs/CAPABILITIES.md` is stale and claims ✅ that the code contradicts
- PLT-04 ✅ "approval queue for anything that changes the computer or sends outside": contradicted by C1-C4 and H1.
- PLT-08 ✅: see H3.
- RES-01/RES-02 ⬜ and LOC-06 ⬜, but `search_web`, `read_url` and `route_time` exist (`toolkit.py:970-975`, `:1006`). DEV-02 ⬜, but `AgentHub` pairing exists (`agents.py:29`). None of these have live evidence listed.
- The file is mojibake (UTF-8 read as cp1252: "âœ…"). It was "checked 2026-10-13".
- **Fix:** re-encode as UTF-8 and re-mark every row with an evidence link (test name or log line). Anything with code but no live check is 🔧, not ✅.

### M4. `read_url`/`search_web` output goes straight into the prompt as instructions
- `toolkit.py:632-635` returns raw page text. Only `mcp_call_tool` is labelled "untrusted data, never instructions". This is the injection vector that feeds C1/C2.
- **Fix:** wrap fetched content in a clearly delimited "UNTRUSTED WEB CONTENT" block in the tool result and in the system instructions (`toolkit.py:1190`).

## LOW

- **L1.** `server_logs` (`toolkit.py:752-777`) reads `ATULYA_LOG_DIR` for any signed-in user (it has `needs_context` but no owner check), and log lines may contain user data from other accounts. Restrict it to admin, as `maintenance` is (`server.py:2119`).
- **L2.** Audit `_scrub_args` (`tools/plugins/audit.py:123-133`) redacts secret patterns but keeps phone numbers, email bodies and SMS text (first 100 chars). Consider omitting `body`/`detail` fields.
- **L3.** `device_companion.py:170-176` `list_photos` with no folder granted walks all of `~/Pictures` recursively, and `take_photo` (`:178-197`) saves outside the granted folder by default. This is inconsistent with the "granted folder only" policy used by `read_file`.
- **L4.** `open_app` on Windows (`device_companion.py:131`) passes model-supplied text to `os.startfile`, which will also open documents, `.lnk` and URLs. Map it through an allowlist of app names.

---

## Voice pipeline vs GOAL M1 (baseline)

| GOAL item | Code | Verdict |
|---|---|---|
| Wake word "Atulya" (openWakeWord) | No `openwakeword` or wake-word code anywhere under `tools/` | **missing** (matches GOAL) |
| STT | `tools/plugins/voice/local.py` (faster-whisper), `light.py:43` (Vosk); `/api/voice/transcribe` `server.py:2123` is upload-based (push-to-talk) | present, not always-on |
| TTS | `light.py:92` Piper, `tts.py` sherpa-onnx Supertonic | present |
| Barge-in | no code | **missing** |
| <2 s reply / <3 s end-to-end ×10 | no latency measurement or test found | **no evidence** |

M1 cannot be ticked. There is no continuous listening loop. The current flow is: record in the browser → upload → transcribe.

## PLAN.md vs GOAL.md
`docs/team/PLAN.md` does not exist yet. When it lands, check that it:
1. puts the safety fixes C1-C4 and H1 **before** M5 (the device agent), because M5 widens exactly those holes;
2. has an evidence step per milestone (GOAL "Done when" lines);
3. covers wake word and barge-in (M1), document reading (FIL-02, M2) and ntfy push (M4), which have no code today.

## Test results
2026-10-20: **156 passed, 2 skipped in 220.9 s** (`tests/`, excluding `tests/e2e`; e2e not run). The suite is green, but it does not catch C1-C4, H1 or H2. A green run is not evidence that the approval policy holds. Add regression tests for each finding as it is fixed.
