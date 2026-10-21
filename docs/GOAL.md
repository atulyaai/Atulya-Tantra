# GOAL — Jarvis as the product, AGI only if the score moves

**Jarvis** is the product: hear, answer, act on your devices, remember, and speak first. A point counts only when a live check on this server passes.

**AGI is not a feature in this repository.** Storing a rule, editing a prompt, or writing this file does not create one. The AGI score stays at 0 until `data/novel_tasks.jsonl` records a passed task that was not hand-coded. No fine-tune has been run. Ask "where are you on the goal?" and the `goal_status` tool reads the live score.

| Score | Counts when |
|---|---|
| Jarvis | News source saved, a routine enabled, a learned rule, a device paired, that device polling, Telegram configured, and one outside action with a receipt |
| AGI | An unscripted task passes, model weights change from measured failures, or unapproved code edits start succeeding tests |

The older zero-cost Jarvis notes below are the build list. Where they disagree with the live score, the live score wins.


**Atulya should hear you, think, act on your devices, and talk back — running on hardware you already own, using only free and open-source pieces. No paid APIs or subscriptions are needed for any core feature.**

"Real" means each feature passes a live check on the actual device, with a receipt. Code that exists but hasn't been checked doesn't count (same rule as `docs/TODO.md`).

## The bar: what "Jarvis" means here

1. **Always listening, privately.** Say a wake word ("Atulya"). It hears you offline on the PC and the phone.
2. **Understands and answers fast.** Local model, voice reply starts in under 2 s on the PC.
3. **Does things, not just talks.** Opens apps, finds and reads files, sets reminders that really fire, plays music, controls the PC from the phone.
4. **Knows the world.** Weather, news, web search with sources, maps and routes.
5. **Remembers you.** Facts, preferences and past conversations, kept on your own disk.
6. **Speaks first when it matters.** Reminders, rain alerts and a morning briefing, pushed to the phone.
7. **Is honest.** It says "done" only after something actually happened. Otherwise it says what failed.
8. **Is safe.** Anything that changes files or sends something outside asks for approval first.

## The free stack (no paid services)

| Need | Free choice | Status in repo |
|---|---|---|
| Brain (LLM) | Local GGUF via llama.cpp (`models/chat/Qwen3.5-2B-Q4_K_M`); larger Qwen/Llama GGUF when the hardware allows | present |
| Speech → text | faster-whisper (PC), Vosk (small server), Android recognizer | present |
| Text → speech | Piper / sherpa-onnx voices | present |
| Wake word | openWakeWord (custom "Atulya" model) | **missing** |
| Web search | SearXNG self-hosted, or DuckDuckGo HTML | **missing** (RES-01) |
| Page reading | httpx + readability → local LLM summary | **missing** (RES-02) |
| Weather | Open-Meteo | done |
| Maps / routes | OpenStreetMap Nominatim + OSRM | location done, routes missing |
| Push to phone | Telegram bot (free) and/or self-hosted ntfy, instead of Firebase | Telegram done |
| Music | yt-dlp + local player | search only, no playback |
| Documents | pypdf, python-docx, openpyxl, python-pptx | **missing** |
| Vision / gestures | Local ONNX models in `models/vision`, `models/gesture` | assets present, unverified |
| Remote access | Tailscale free tier or Cloudflare Tunnel free | see `REMOTE_ACCESS.md` |
| Hosting | Your own PC / existing server | done |

Rule: if a feature needs a paid key, it's **optional**. It never blocks the core loop.

## Known bugs (fix these before new features)
Reported by the owner on 2026-10-21. Each is closed only after a live check on the real site or device.

- [ ] **B1 — Same device listed many times.** The Devices panel showed the same device as several separate rows instead of one block.
  - Also fixed: a device re-paired under an old name no longer shows the old device's jobs (they move to "<name> (revoked)").
  - Fixed in code: the panel now shows one expandable block per device, with abilities, last-seen time and that device's jobs inside (`webui/controls.js`). Pairing now refuses a name that differs from an existing device only by case, spaces, `-` or `_` (`tools/plugins/system/agents.py`, test `tests/plugins/test_device_dedupe.py`).
  - Still to do: deploy, then revoke the extra rows that already exist on the server, and confirm the panel shows each device once.
- [ ] **B2 — This desktop is not added as a device.** The owner's PC (i3-9100F, Brio 100 mic) isn't paired, so the server and phone can't send it jobs.
  - Owner step: Devices → type Laptop/PC → name it (e.g. "Desktop") → Create device credential, then run `python -m tools.device_companion --url https://atulvij.com` on this PC and paste the token.
  - Build step: the companion should start with Windows (M1-6 / M7) and the Test connection ping must return an executed receipt.
- [x] **B4 — An old device test no longer matches.** `tests/core/test_device_jobs.py::test_pairing_scopes_devices_jobs_and_revocation` fails because `AgentHub.authenticate` now also returns `abilities` (part of the voice-loop work). Update the test.
- [ ] **B5 — Android SMS/call approval dialog never built.** `MainActivity.kt` was changed (AUDIT C3), but the app hasn't been compiled or tried on the phone.
  - Compiled 2026-10-22: the debug APK builds (`android/app/build/outputs/apk/debug/app-debug.apk`, 7.6 MB) after fixing a missing `PendingIntent` import in `MainActivity.kt`, which also means the app source had never built in this form. Still to do: install it on the phone and try an SMS and a call.
- [ ] **B6 — Lock file untested on Linux.** `requirements.lock.txt` may fail on the server because `tflite-runtime` has no Python 3.12 wheels (AUDIT N2).
  - Checked 2026-10-21: all 66 non-Windows pins download as Python 3.12 Linux x86_64 wheels (`pip download --platform manylinux… --python-version 3.12`). `openwakeword`/`tflite-runtime` are Windows-only in the lock, so the server never installs them. Still to do: one real `pip install -r requirements.lock.txt` on the server during deploy.
- [ ] **B14 — Duplicate reminders/meetings.** There is no idempotency check, so a repeated tool call or a resend saves the same reminder twice, and both fire (`web_reminders.py:34`, `reminders.py:56`, `calendar.py:66`).
  - Fixed in code: the same text at the same time returns the existing reminder or meeting instead of adding one (web, Telegram, calendar). Tests: `tests/plugins/test_no_duplicate_reminders.py`. Duplicates already on the server still need a cleanup. Still to do: deploy and check live.
- [ ] **B15 — `/api/status` always shows speech "ready"/green**, even on the browser-voice fallback (`atulya/server.py:1786-1789`).
  - Fixed in code: speech shows "setup" on the browser-voice fallback. Still to do: deploy and check live.
- [x] **B17 — A device token with `voice_loop` can approve actions as its owner.** A device credential must never approve actions; that bypasses human approval (`tools/plugins/system/agents.py:21`).
- [ ] **B23 — The owner check only recognised the user id "admin".** Fixed in code 2026-10-21: role comes from the auth store (`PluginContext.is_admin`), so a second admin works and a user named "admin" without the role doesn't. Also added security headers (nosniff, no framing, same-origin referrer, a basic CSP) for M13. Still to do: deploy and check.
- [ ] **B27 — This PC has no default speaker set in Windows.** Only a Realtek WDM-KS output exists and the default output is -1, so playback "on the default device" fails. Fixed in code 2026-10-21: the voice-loop player falls back to the first output device (test in `tests/voice/test_voice_loop.py`). Hardware check: the Brio mic records real signal (3 s, RMS 0.003, peak 0.04), and Atulya's voice played on device 6 with no errors. Acoustic loopback test (play "Hey Jarvis, what is the weather tomorrow?" on the speakers and record it on the Brio mic): **failed**. The mic saturates at full scale only while the WDM-KS output plays (and returns NaN/zero samples with a quiet test tone), so playback through raw WDM-KS is unreliable and may sound like noise. No wake word was detected and no speech was transcribed from that recording. **Owner step:** in Windows Settings → System → Sound → Output, enable the Realtek speakers (they seem disabled, so Windows exposes no normal playback device), then re-run the loopback test.
- [ ] **B28 — Can't change the news briefing by asking.** Reported by the owner 2026-10-22: asking from the phone app to change the news feed sent on Telegram did nothing. Cause: the morning briefing is set only by server settings (`ATULYA_BRIEFING_TIME`, a default city) in `telegram.py:638-666`. There is no tool to change its time, city, topics or channel, so the assistant can't do it from any channel. Fix: a per-user `briefing_settings` tool (time, city, topics such as local/India/world/tech/sports, sources, channel telegram/app/both/off, on/off), stored in the profile and used by the sender, with tests.
- [ ] **B29 — Telegram settings can't be changed from the phone app.** Telegram options (briefing, which alerts go to Telegram, quiet hours) are server settings, not something the assistant can change. Fix: owner-only tools plus a "Telegram" section in the web UI (shared by the app) to view and change them; admin-only items stay admin-only (M12).
- [ ] **B30 — News and alerts arrive on Telegram but never as a phone-app notification.** Cause: the briefing is sent only through Telegram, and the Android app is a WebView, which can't receive web push. Firebase (FCM) isn't used, so the app has no way to be woken. Free fix: the app checks Atulya's notification inbox on a schedule (Android WorkManager, about every 15 minutes, plus right away when opened) and shows a local notification using the notification code it already has (`AlarmReceiver.kt`). Optional later: self-hosted ntfy for instant delivery. Each message goes to the channels the user chose in B28 (telegram/app/both).

- [x] **B3, B7–B13, B16, B18 — webui2 (`/v2`) faked data and actions.** Closed on 2026-10-21 by removing webui2: the owner chose to keep only webui v1. The `/v2` route is gone from `atulya/server.py`; the files are in `F:\Atulya-Tantra-cleanup-archive\webui2`.
- [ ] **B19 — Failed screen actions are silent.** `webui/assistant.js:1754` swallows errors from `screen_control` actions, so the chat says done while nothing changed.
  - Fixed in code: an unknown or failing screen action now posts a notice in chat (`webui/assistant.js`). Still to do: deploy and check live.
- [x] **B20 — Document reader can't read PDFs.** `tools/plugins/information/document.py:18` needs pymupdf, but the project installs pypdf. It is also not registered as a tool (AUDIT CL7).
  - Fixed 2026-10-21: the reader uses pypdf (plus DOCX/XLSX/PPTX/TXT) and is registered as `read_document`, limited to Desktop/Documents/Downloads; tests in `tests/plugins/test_documents.py`. Scanned PDFs have no OCR.
- [ ] **B21 — Any signed-in user can control and read the owner's PC.** The pc-control tools (`search_files`, `read_document`, `take_screenshot`, `open_app`, `open_url`, `media_control`) have no owner check (`tools/plugins/toolkit.py:339-352,1009-1012,1155-1160`). The user approves their own action, and `read_document` is low-risk, so under `ask_risky` there is no card at all.
  - Fixed in code 2026-10-21: pc-control tools (search_files, read_document, screenshot, open_app/url, media) are removed from the tool list for non-admin accounts and also refuse inside each handler. Tests: `tests/plugins/test_owner_only_tools.py`. Still to do: deploy and check with a second account.
- [ ] **B22 — Any signed-in user can switch the owner's smart-home devices.** `POST /api/smarthome/scene` and the `smart_home_control` tool have no admin check (`atulya/server.py:1954`).
  - Fixed in code 2026-10-21: `/api/smarthome/scene` returns 403 for non-admins, and `smart_home_control` is owner-only. Still to do: deploy and check.
- [ ] **B24 — Adding someone to the Telegram allowlist makes them the admin.** Every allowlisted id signs in as `admin`, shares the owner's memory and history, and can approve the owner's actions (`telegram.py:26`, `server.py:1528`). Keep the allowlist to the owner only, and bind approvals to the requesting Telegram id (AUDIT S3).
  - Partly fixed 2026-10-22 (Auditor verified): approvals are now bound to the Telegram id that asked. Still true: every allowlisted id is the owner account, so keep the allowlist to the owner only.
  - 2026-10-22: approvals are now bound to the requesting Telegram id (code + tests). Every allowlisted id is still the admin, so keep the allowlist to the owner only.
- [ ] **B25 — Data stores default to the admin user.** `memory.py` and `history.py` use `user_id="admin"` as the default, and `_is_admin` falls back to `user_id == "admin"`. A missed argument leaks the owner's data (AUDIT S1/S2).
  - Fixed in code 2026-10-22 (Auditor verified): user_id is required, and admin is never assumed.
  - 2026-10-22: fixed in code. `user_id` is now required and `is_admin` fails closed (347 tests pass).
- [ ] **B26 — The CSP doesn't block scripts.** It has no `default-src`/`script-src`, so XSS isn't mitigated (`atulya/server.py:2365`, AUDIT S4).
  - Fixed in code 2026-10-22 (Auditor verified on a local server): a full CSP with no console violations, and the page and 3D scene still load. Still to do: check on the live site after deploy.
  - 2026-10-22: fixed. The CSP now has `default-src`/`script-src`. Local live check: no CSP console errors, and the page works signed out. Production still to check.
- Add more here as they're found. Each bug gets a test before it's marked fixed.

## Design rule: update from the server, rebuild the app rarely
The Android app is a shell around the web UI, so every screen, feature and fix in `webui/` and on the server reaches the phone on the next app open, with no new APK. A new APK is needed only when the phone itself must do something new (a new Android permission, background work, SMS/calls, notification access). To keep that rare, build the native side once as a **generic bridge**: a notification inbox poller (B30), "run phone action X" with an approval dialog, and permission requests. After that, new features are added on the server only. The app also checks the server for a newer APK version and offers a one-tap update.

## Milestones (in order — each ends with a live check)

### M1 — The voice loop works end to end (the "Jarvis moment")
- [ ] openWakeWord listener on the PC → STT → local LLM → tools → Piper reply.
- [ ] You can interrupt it mid-sentence (barge-in).
- **Done when:** you say "Atulya, what's the weather tomorrow?" with no clicks and hear a correct answer in under 3 s, 10 times in a row.

### M2 — It controls the PC
- [ ] Open/close apps, volume, media keys, lock screen, screenshot.
- [ ] Find a file, read it (PDF/DOCX/XLSX/TXT), summarize it (FIL-01, FIL-02).
- [ ] Anything that changes files goes through the approval queue (PLT-04).
- **Done when:** "find my latest invoice PDF and tell me the total" works by voice.

### M3 — It knows the live world
- [ ] Web search with sources (SearXNG) and page summaries (RES-01, RES-02).
- [ ] Routes and travel time via OSRM (LOC-06).
- **Done when:** answers to current-events questions cite real links you can open.

### M4 — It reaches you, and it's reliable
- [ ] Reminders survive a restart and arrive with sound on the phone (Telegram/ntfy). Delivery receipts recorded.
- [ ] Morning briefing: weather, calendar, sourced news.
- [ ] Rain/severe-weather alerts (LOC-07).
- **Done when:** a reminder set yesterday fires today after a reboot, and the phone rings.

### M5 — Phone ↔ PC as one assistant
- [ ] Device agent: the server or phone can run approved actions on the paired laptop (FIL-06, H6).
- [ ] Music actually plays on the chosen device.
- **Done when:** from the phone, outside the home, "play my playlist on the laptop" plays audio there.

### M6 — Eyes (stretch)
- [ ] Camera: "what am I holding?" using a local vision model. Gestures verified on the real phone.

### M7 — Full device control
- [ ] PC: apps, windows, volume/brightness, power (sleep/lock/shutdown), clipboard, keyboard/mouse macros, Wi-Fi/Bluetooth toggles.
- [ ] Phone (Android app): open apps, alarms, flashlight, volume/DND, media, calls/SMS with an approval dialog.
- [ ] One `device_action` tool: picks the target device, asks approval for risky actions, records a receipt.
- **Done when:** by voice, "lock my laptop" and "set an alarm for 7 on my phone" both happen and leave receipts.

### M8 — Device usage awareness
- [ ] Track CPU/RAM/disk/battery/network and screen time per app on PC and phone, stored locally.
- [ ] Answer "what did I use most today?" and "why is my PC slow?" with real numbers.
- [ ] Warn when the disk is low, battery is bad, or a process is hogging the CPU.
- **Done when:** a daily usage summary matches Task Manager / Android Digital Wellbeing within 10%.

### M9 — Autonomous agent mode ("AGI mode", honestly scoped)
True AGI isn't achievable with any model, free or paid. This milestone is the closest real thing: an agent that plans, acts and checks its own work on multi-step goals.
- [ ] Plan → act → observe → retry loop using the existing tools, with step limits and a visible task timeline.
- [ ] Long goals survive restarts (durable jobs, PLT-09) and report progress.
- [ ] Every action that changes something or sends outside still goes through approval.
- **Done when:** "find the 3 largest files in Downloads, summarize them, and remind me about them tomorrow" completes unattended except for approvals, with receipts.

### M10 — Fully proactive
- [ ] Morning brief, rain alerts, calendar heads-ups, low-battery/disk warnings and follow-ups on unfinished tasks, all without being asked.
- [ ] Quiet hours, per-type on/off switches, and "why did you tell me this?" for each alert.
- **Done when:** a week of use has no missed reminder, no alert during quiet hours, and you keep at least 80% of alert types on.

### M11 — Self-evolving (safely)
- [ ] Learns preferences from corrections ("shorter", "don't tell me that") into memory/profile.
- [ ] Logs failed tool calls and proposes fixes (prompt, tool or code) as a reviewable diff, never auto-merged into core.
- [ ] Can write new skills (`tools/skills/<name>/SKILL.md`) from repeated requests; each needs owner approval and must pass tests before it's enabled.
- [ ] Every self-change is versioned and can be rolled back.
- **Done when:** in a week it proposes at least 3 improvements, you accept them, the tests stay green, and rolling one back works.

### M12 — Many users, one owner: profiles and strict separation
Today: `users` has `admin`/`user` roles (`atulya/auth.py`), but devices, tools and data aren't fully scoped by role.
- [ ] Each user has their own profile (name, language, voice, tone, city), memory, chats, reminders and devices. Nobody sees another user's data.
- [ ] **Devices belong to their owner.** Only the owner can see, pair, test, revoke or send jobs to their devices. The admin's devices are invisible to normal users, and a normal user's devices are private from other users.
- [ ] **Dangerous tools are admin-only:** PC control, device actions, shell/service restart, server status, maintenance, MCP, secrets, smart home. Normal users get safe tools (chat, weather, news, their own reminders and memory).
- [ ] Admin can invite, disable and remove users and set per-user tool limits. The admin can't read another user's private chats unless that user shares them.
- [ ] **Age-based content settings per profile.** Each profile is marked adult or child (the admin sets it; a child can't change their own).
  - Adult profiles can turn on "adult content allowed". Atulya then doesn't refuse or lecture about legal adult content (search, links, conversation). It's the adult's choice, and it's off by default until they turn it on.
  - Child profiles always have filtering on: safe search, no adult content, and the admin is notified of blocked attempts if they choose.
  - Never allowed for anyone: illegal content, including anything sexual involving minors and non-consensual material.
  - The setting is checked on the server for every request, not just in the UI. Note that a cloud model provider's own rules may still refuse some requests; the local model follows this setting.
- [ ] Every request is checked on the server (never just hidden in the UI), with tests that a normal user gets 403 on every admin route and device.
- **Done when:** a second test account can sign in, chat and set reminders, but gets 403 on every device, PC-control and admin route, and can't see the owner's devices, chats or memory. The tests cover every route.

### M13 — Security (cybersecurity and the web UI)
- [ ] Web UI hardening: strict Content-Security-Policy, CSRF protection on every state-changing route, secure/HttpOnly/SameSite cookies, no secrets in the page, `innerHTML` audit (no injection from model or user text).
- [ ] Rate limits and lockouts on sign-in, pairing and approvals; device tokens hashed, expiring and revocable (done in part).
- [ ] An audit log of who did what (PLT-07): sign-ins, approvals, device jobs, admin changes, viewable by the admin.
- [ ] Prompt-injection defence: web pages, documents, emails and messages are always marked untrusted and can't trigger actions without approval (partly done).
- [ ] Free security tooling in the test run: `pip-audit` (dependencies), `bandit` (Python), a secrets scan, and a checklist pass based on the OWASP Top 10.
  - Started 2026-10-21: `python -m tools.security_check` runs pip-audit and bandit and passes. It found and fixed certifi 2026.10.18 (PYSEC-2026-4320 → 2026.10.19); the other bandit hits were reviewed as false positives (fixed table names, parameterised values, a checksum-verified archive). A secrets pattern scan is included (passes). Still to add: the OWASP checklist.
- [ ] Encrypt secrets at rest on Linux too (AUDIT H3).
- **Done when:** all of these checks run clean on every change, and an audit pass by the Auditor finds no HIGH issues.

### M14 — Reach Atulya on any channel (free options only)
| Channel | Free option | Notes |
|---|---|---|
| Telegram | Bot API, free | Working today; keep as the main remote channel |
| Email | Gmail API (free quota) or any IMAP/SMTP mailbox | Read, summarize, draft; sending always needs approval |
| SMS | Your own Android phone sends and receives through the Atulya app (uses your SIM plan) | No paid SMS gateway |
| Phone calls | Android app places and answers calls; Atulya can speak the call script with TTS | Every call needs approval (B5) |
| WhatsApp | Official WhatsApp Cloud API: replies within 24 h of the user's message are free; starting a conversation costs money | Unofficial WhatsApp Web libraries break WhatsApp's terms and get numbers banned, so they're out |
| Push notifications | Self-hosted ntfy, or Telegram | Replaces Firebase |
- [ ] One inbox: messages from every channel arrive in the same conversation and identity (one account everywhere, PLT-05).
- [ ] Atulya picks the right channel to reach you (phone if it's urgent, Telegram otherwise, never during quiet hours).
- **Done when:** you can ask Atulya on Telegram to "text Rahul I'm late" and it drafts the SMS, asks approval, sends it from your phone, and confirms with a receipt.

### M15 — Any device, any OS, controlled from anywhere
- [ ] Companion for Windows, Linux and macOS that runs as a background service and starts with the system; Android phone and tablet app; Android TV app; headless Linux server agent.
- [ ] **Unattended install by the owner:** one command or installer plus a one-time pairing code installs, pairs and starts the companion with no further clicks. It always shows that it's installed, is listed in Devices, and can be removed with one click. **No hidden or covert installs, and never on a device the owner doesn't own.**
- [ ] Control from anywhere: phone → laptop, laptop → TV, Telegram → server, all through the same device jobs with receipts. No ports opened on the devices (outbound connection only).
- [ ] Per-device abilities and per-device approval rules (e.g. lock screen is fine without asking; a file delete always asks).
- **Done when:** from the phone, away from home, you can lock the desktop, play something on the TV, and check the server's disk, each with an executed receipt.

### M16 — Talks like a person, not a robot
- [ ] Natural replies: short by default, warm, uses your name sometimes, no "As an AI…" or bullet-point lists in speech; it matches your language (English/Hindi/Hinglish).
- [ ] Conversation memory: remembers what you said earlier today, follows up ("did the meeting go well?"), asks a short question when unsure instead of guessing.
- [ ] Turn-taking: you can interrupt it; it can say "one sec" while working; it never reads out long tool output.
- [ ] A persona the owner can tune (name, tone, humour level), per user.
- **Done when:** in a blind check of 20 conversations, you rate at least 16 as "sounds natural", with no robotic phrases.

### M17 — Senses work end to end, in real life
- [ ] Voice in: wake word → speech-to-text on PC and phone (M1).
- [ ] Voice out: natural TTS on PC, phone and TV.
- [ ] Camera: "what's this?" and "read this" with a local vision model (M6).
- [ ] Gestures: the set in the Guide works on the real phone and webcam (e.g. palm = stop, thumbs up = approve a low-risk action).
- [ ] Each has a recorded live check on the real device, not just a test.
- **Done when:** one session uses all five (wake word, voice question, spoken answer, camera question, gesture to stop), on the real devices, with no clicks.

### M18 — Cross-device control toolkit (tools, MCP and skills)
Today: the MCP server (`tools/mcp/server.py`) exposes only 5 safe tools (weather, news, time, calculate, what_can_you_do), and there are 2 skills (daily-briefing, self-repair). Device jobs support ping, say, open_url/app, list/read files, photos, media, SMS, call, display message and battery.
- [ ] **Files on any paired device:** list, search, view, read, copy, move, rename, edit (with a diff preview) and delete (to the recycle bin first, never a permanent delete without a separate confirm). Transfer files between devices (phone → PC, PC → TV).
- [ ] **Apps and system:** open, close and list apps; running processes; volume, brightness, media; lock, sleep, restart, shutdown; clipboard sync between devices; screenshots; notifications from the phone shown on the PC.
- [ ] **Network:** list devices on the home network (read-only scan), Wake-on-LAN, ping and speed check, router status where it has a free local API; per-device online/offline history.
- [ ] **Servers:** disk, CPU, services, logs (read-only for everyone except the admin); restart a service only with approval.
- [ ] **TV:** play, pause, volume, open app, cast a URL (Android TV app or ADB over the local network, paired by the owner).
- [ ] **One MCP server for outside AI apps** (Claude Desktop, VS Code, etc.) exposing the same tools, with the same per-user permissions and approvals. Admin-only tools are never exposed to normal users' MCP tokens.
- [ ] **Skills** (`tools/skills/<name>/SKILL.md`) for multi-step jobs: "back up my phone photos to the PC", "clean up Downloads", "find what's eating disk space on all devices", "move this movie to the TV and play it", "morning device health report".
- [ ] Safety rules for every tool: owner-only by default, read-only tools run directly, anything that changes or deletes asks approval and leaves a receipt, deletes go to the recycle bin, and every action is in the audit log (M13).
- **Done when:** from the phone you can find a file on the desktop, preview it, copy it to the phone, and delete the original (recycle bin, after approval), each with a receipt; and the same tools work from an outside MCP client signed in as the owner.

### M19 — Inbox assistant: sort, clean up and auto-reply across all your messages
Atulya looks at everything arriving on your phone and email, decides what matters, cleans up the rest, and answers people for you while you're away. All free, on your own devices.

**What it can see (how it works, free):**
| Source | How Atulya reads it | What it can do |
|---|---|---|
| Email (Gmail or any IMAP mailbox) | Gmail API / IMAP | Read, label, archive, delete (to Trash), draft and send replies |
| SMS | Atulya Android app | Read; delete needs Atulya set as the default SMS app (Android rule) |
| WhatsApp, Snapchat, Instagram, Telegram and other apps | Android notification access (`NotificationListenerService`): the same permission auto-reply apps use | Read incoming messages from their notifications, dismiss notifications, and reply where the app offers an inline "Reply" button (WhatsApp does) |

**Limits (so nothing is promised that can't work):** other apps don't allow outside programs to delete their chats or read old history. For WhatsApp, Snapchat and similar apps, Atulya works on new messages as they arrive, can reply through the notification, and can dismiss them, but can't delete messages inside those apps. No unofficial WhatsApp/Snapchat libraries (they break the apps' terms and get accounts banned).

- [ ] **Sort:** each new message is marked important, can wait, or junk (promotions, spam, OTPs older than 10 minutes, newsletters), using your rules first and the model second.
- [ ] **Clean up:** junk emails are archived or moved to Trash (recoverable for 30 days); junk notifications are dismissed. **If it isn't sure, it asks you** instead of guessing.
- [ ] **Your rules:** say it in plain words ("always delete Swiggy promos", "never touch messages from Mom", "OTPs: delete after 10 minutes") and Atulya saves it as a rule you can see, edit and switch off in the web UI. It applies the rules automatically from then on.
- [ ] **Away / sleeping auto-reply:** when you're marked away, asleep (quiet hours) or busy, Atulya sends a short holding reply to real people, once per conversation: "Hi, Arjun is away right now and will reply when he's back." Only to contacts or people you've chatted with before, never to unknown numbers or groups unless you say so.
- [ ] **When you're back:** a short summary of what came in, what it replied, and what it cleaned up, with an undo for any deletion.
- [ ] Safety: every send and delete is logged with an undo where possible; first-time rules ask for confirmation; nothing is sent from your accounts outside your rules.
- **Done when:** over one day, junk email and notifications are cleaned up per your rules, a WhatsApp message received while you're "asleep" gets the holding reply once, you get a "you're back" summary, and every action shows in the log with no wrong deletions.

### M20 — Access to anything, from anywhere
One rule: whatever you can reach at home, you can reach from anywhere, safely.
- [ ] **Every device** (PC, laptop, phone, tablet, TV, servers) reachable from any other, and from Telegram and the web, through outbound-only connections (no open ports at home), M15/M18.
- [ ] **Every kind of thing:** files, apps, screens (view-only screenshot, plus remote control with approval), cameras (owner only, with a visible indicator on the device), messages and email (M19), calendar, notes, smart home, network, server logs.
- [ ] **Every way in:** web UI, phone app, Telegram, voice (M21), MCP clients; same account, same permissions (M12) and the same approvals everywhere.
- [ ] **Works offline-first at home:** if the internet is down, devices on the same Wi-Fi still talk to the home PC directly.
- [ ] Safety stays the same everywhere: owner-only for your devices, approvals for changes, everything in the audit log (M13).
- **Done when:** from your phone on mobile data, you can open a file from the desktop, see the desktop's screen, check the server's disk, and turn off a light, each in under 10 seconds and with a receipt.

### M21 — Full voice control panel: voice can do everything
Anything you can do by tapping or typing, you can do by speaking.
- [ ] **Every web UI action has a voice command:** settings (voice, language, tone, briefing, quiet hours), Devices (pair, test, revoke), reminders, routines, approvals, connections, music, camera, history, users (admin).
- [ ] **Spoken approvals, done safely (M2-2):** Atulya reads the action, and you say "yes, do it" on your own signed-in device. Risky actions (delete, send, pay) also need a PIN, a fingerprint or a tap. A device token alone can never approve (B17).
- [ ] **Easy ways in:** wake word ("Atulya"); push-to-talk button; long-press the phone's power or assistant button to start listening; a "voice mode" that hides the screen and just talks; a home-screen widget and a quick-settings tile on Android.
- [ ] **No commands to memorise:** say it naturally ("make it quieter", "what's on my PC's screen", "send the news to the app from now on"); Atulya maps it to the right action and asks only if it's unsure.
- [ ] **"What can I say here?"** gives short, spoken examples for the current screen.
- [ ] A test that lists every UI button and checks it has a matching voice tool (no gaps).
- **Done when:** you can go a full day using Atulya by voice only, with no taps except for approval taps on risky actions.

### Why Atulya doesn't add features to itself yet (and how M11 will fix it)
The parts exist, but they aren't connected into a loop:
- `atulya/maintenance.py` can already **propose** a code change and **apply it with rollback**, but only for a small list of files, and only when the owner approves each one. Auth, secrets and deployment files are protected. This is deliberate: code that rewrites itself without checks can break itself, or open a security hole.
- Nothing yet **notices** what's missing (failed requests, "I can't do that" replies, repeated manual steps), **writes** the new skill or tool, and **tests** it before asking you.

**The self-evolving loop to build (M11):**
1. **Notice:** log every failed or refused request and every "I can't do that yet" reply.
2. **Propose:** once a week (or when something fails three times), pick the top gaps and draft a fix: a new skill (`tools/skills/`), a new tool, or a code change.
3. **Test in a sandbox:** run the full test suite plus `tools.security_check` on the draft, never on the live system.
4. **Ask once:** "I can now do X. Here's what changed. Enable it?" One tap (or "yes" by voice, with M21's safety rules) enables it.
5. **Watch and roll back:** if errors rise after enabling, it rolls back on its own and tells you.
- Things it may do **without asking:** learn your preferences, add new skills that only read (never change or send anything), and fix its own prompts. Anything that changes code, sends messages or controls devices **always asks first**.
- **Done when:** in one month, it ships at least 5 new abilities you didn't build by hand, every one passed tests before you saw it, and any you disliked rolled back in one tap.

### How the "AGI" goal fits
"AGI" here means M9 (plans and acts on its own), M10 (proactive), M11 (improves itself safely), M16 (behaves like a person) and M17 (senses), together. True AGI isn't something any model can deliver today, free or paid. This is the closest real system, and every part of it can be checked.

## Not doing (keeps it free and focused)
- No OpenAI/Anthropic/Google paid APIs in the core loop.
- No Firebase / paid push, and no paid TTS voices.
- No WhatsApp messages that Atulya starts (they cost money). Free replies through the official Cloud API are fine (M14). No unofficial WhatsApp libraries.
- No covert installs, spyware-style monitoring, or access to devices the owner doesn't own.
- No paid SMS or calling gateways; the owner's own phone does that.

## How we track progress
- Day-to-day work: `docs/TODO.md`. Capability map: `docs/CAPABILITIES.md`. This file only changes when the goal changes.
- A box gets ticked only with evidence: a test, a log line or a recording from the real device.
