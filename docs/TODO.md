# Atulya — working list

One list, in order. Each item: **status** · what · how it is verified. Work top to bottom; update this file in the
same commit as the fix. History of finished work: `git log` and `docs/archive/`.

Status: ✅ done (verified for real) · 🔧 in progress · ⬜ to do · ⛔ blocked on the owner (reason given)

## H. Capability platform — THE MAIN TRACK (owner, 2026-10-13: less APK polish, more real abilities)

Build every ability **once on the server**; web, app, Telegram and MCP all use it. Full map with status:
`docs/CAPABILITIES.md`. Rule: no channel-specific copies, nothing "can't do" without saying what's missing and how
to enable it. In this order (each step unlocks the next):

| # | Status | What | Done when |
|---|---|---|---|
| H1 | 🔧 | **Forecast + location** (2026-10-13 round 2: AQI/PM2.5/PM10, rain/snow mm, wind words + gusts, visibility, hot/cold verdict + change vs today, any colony/sector/full Indian address, saved places home/office, battery-safe location) — `get_weather(place?, when=now/next_hours/today/tomorrow/week)` with rain %, wind, UV, sunrise; `where_am_i`; device location by consent (web/app geolocation, Telegram 📍 button), stored with time stamp (stale ignored), home city fallback, asks once then re-answers automatically | ✅ real model, local: "rain tomorrow where I am" asks → location → "0 % rain"; "where am I" → Connaught Place; tests. ⏳ owner: phone + Telegram |
| H2 | ⬜ | **Capability catalogue + honest status:** one registry the AI reads ("what can you do here / what's missing"), status per tool (available / needs location / needs connection / needs approval / unsupported) with the next step; MCP serves the same registry (remove its duplicate tools); ask "short or detailed?" when unclear | "What can you do on Telegram?" gives a true list; MCP weather = new forecast |
| H3 | ⬜ | **Audit log:** every tool run recorded (user, channel, tool, args summary, result, time); viewable in ⋮ → ACTIVITY | Entry for each run; secrets never stored |
| H4 | ⬜ | **Web + maps:** web search with sources, read a page, places near me, route + travel time (OpenStreetMap/OSRM, free) | "Pharmacies near me", "how long to the airport", "search X" work on all channels |
| H5 | ⬜ | **Device registry + server ops:** list devices (server, laptop, phone) with status and granted abilities; server logs explained (approved paths, read-only), service restart with approval | "Check the server logs and explain the error" |
| H6 | ⬜ | **Files:** read/summarize PDF, DOCX, XLSX, CSV, code; upload in chat on all channels; **laptop agent** (outbound connection, approved folders, read-only first); phone files via Android picker | From Telegram: "find my latest budget sheet on my laptop and summarize it" |
| H7 | ⬜ | **Safe file edits + documents:** preview diff, save as new copy, approval, undo; create Word/Excel/PDF/PowerPoint | Edit shows diff, original kept |
| H8 | ⬜ | **Routines + watchers:** recurring tasks, rain/disk/site-down alerts, multi-step jobs that survive restarts | "Every weekday 8am: weather + calendar + server health on Telegram" |
| H9 | ⛔/⬜ | **Accounts:** Gmail + Google Calendar (needs D1 OAuth), GitHub (token) — read/draft free, send/change only with approval | "Summarize today's important emails and draft replies" |

Later (after H): browser actions on websites, outside MCP servers as tools, project memory, smart home (Home
Assistant), learning from outcomes. Not before H1–H8 work for real.

## A. Broken basics reported from real use (fix first)

| # | Status | Problem → fix | Verified by |
|---|---|---|---|
| A1 | 🔧 | Typed messages get no spoken reply → every reply spoken by default; 🔊/🔇 button; say "mute"/"unmute" | Built; needs your by-ear check |
| A2 | 🔧 | App/Mini App keeps demanding "Hey Atulya" → wake word now **off by default** (say "wake word on" for always-on) | Built; needs your by-ear check |
| A3 | 🔧 | Microphone permission asked repeatedly → one mic stream per session; the interrupt monitor reuses it (it used to open a second mic = second prompt); Telegram Mini App starts the mic on tap | Built; needs check in Telegram |
| A4 | ✅ | Status panel/tools for non-admins → hidden in UI **and** `/api/status` refuses non-admins (403) | Server test + UI |
| A5 | 🔧 | Overlap on phone/small windows → header on one line + account menu (⋮); phone = hologram top, chat bottom sheet; camera box only when camera is on | Screenshots desktop + 375 px phone ✅; Mini App/APK on a real phone pending |
| A6 | 🔧 | Hologram on phone/Mini App → live 3D kept when it runs; still hologram artwork when WebGL is missing or the scene never starts | Desktop + 375 px phone ✅; real phone pending |
| A7 | ✅ | "Update/reload page" prompt → an old cached page now reloads itself once; expired sessions show sign-in instead of an error | Code + UI |
| A8 | ✅ | Password sign-in with `atulya` → works on the public site in a real browser (the failed attempt was a mistyped password) | Public site, real browser |
| A9 | ✅ | Google-style sign-in: Continue with passkey → or username/email → Send approval to my devices / code / Use password; invitation + create account as links | Public site |
| A10 | ✅ | "Say code" removed; Resend added (30 s cooldown) | Public site |
| A11 | ✅ | Add passkey: account menu (⋮ → ADD PASSKEY) + offered after password/code sign-in | Public site |
| A12 | ✅ | Sign-up with an existing email jumps to sign-in for that account | UI flow |
| A13 | ✅ | App icon = the Atulya hologram face (web, PWA, Android launcher + round icon) | APK 0.2.1 |
| A14 | ✅ | APK download: https://atulya.atulvij.com/download (always the newest signed APK) + README | Public URL |
| A17 | 🔧 | APK: R8 code + resource shrinking, en/hi only, adaptive launcher icon (fits round/squircle/any mask, sharper head crop, webp); every android/ change on main auto-publishes the latest release so the in-app updater offers it | CI build size + phone install pending |
| A18 | 🔧 | Voice fixes: pause keeps the mic granted (muted, released after 10 idle min) so Telegram does not ask again; reply sentences are synthesized one at a time so speech starts with the first sentence instead of after typing; gesture model now installed on the server (was red/yellow) | Owner check in Telegram/APK |
| A15 | ✅ | Camera turned itself on at load → on demand only (button / "turn on camera"), remembered per device | Public site |
| A16 | ✅ | Greeting shown twice after reload → one greeting; "Welcome back" by voice | Public site |

## B. Server-first architecture (owner's server, always on)

| # | Status | What | Notes |
|---|---|---|---|
| B1 | ✅ | Atulya runs on the atulvij.com server (systemd `atulya.service`, ~60-340 MB RAM) and atulya.atulvij.com is served from it through the Cloudflare tunnel; old version stopped (kept as a backup folder); laptop host disabled | Server self-test 10/12 → 12/12 after clips fix |
| B2 | ⬜ | Laptop/desktop = **Atulya agents** that connect out to the server: PC control, local Whisper/TTS/LLM when available | Replaces the tunnel as the main path; tunnel kept for laptop-only setups |
| B3 | ⬜ | Server is the source of truth; clients cache locally and fetch only changes (delta sync); Telegram reads from server | — |
| B4 | ✅ | Encrypted daily backups (AES-256-GCM, keep 14) + off-site copy to the server; `atulya.cli backup`, `--restore`, `--show-key` | Real backup created, copied to server, decrypted and checked |
| B5 | 🔧 | Server voice = open source, CPU-only: **Vosk** recognition (~2.7 s) + **Piper** voices (~1.9 s/sentence), male + female, English + Hindi; loads on demand, unloads when idle. Whisper was 10-19 s on this server; Gemini is free-tier cloud (kept off) | Server benchmark; by-ear check pending |

| B6 | ✅ | Workflow: laptop = development → push to GitHub → clean-machine tests → server deploys itself (server-side health check + automatic rollback); deploy key can only run the deploy script | First automatic deploy 3c39eea, server self-test 12/12 |

## C. Same Atulya on every channel

| # | Status | What |
|---|---|---|
| C1 | ✅ | One account across web, app and Telegram (owner's Telegram = main account), live sync ~10-13 ms |
| C2 | ✅ | Telegram voice note → reply also as a voice note (local voice → OGG/Opus, plays inline) | Real TTS→Opus→Whisper round trip |
| C3 | ⬜ | Mini App looks and behaves like the web app (signed in automatically, voice, hologram) |
| C7 | ✅ | Male/female voice per person ("use a female voice"), used on web, app and Telegram voice notes | Code + server voices |
| C4 | ✅ | Per-user nickname for the assistant ("call yourself Tony") — answers to it and wakes on it on that user's devices; system stays Atulya | Code + wake test |
| C5 | ⛔ | WhatsApp — needs a Meta Business account + WhatsApp Cloud API number (owner) |
| C6 | ⛔ | Push notifications inside the APK — needs a Firebase project (owner); web/PWA push already works |

## D. Sign-in providers

| # | Status | What |
|---|---|---|
| D1 | 🔧 | Google sign-in — server code ready (verified email only; new emails become sign-ups for owner approval). Needs: owner creates the OAuth client (Web, redirect https://atulya.atulvij.com/api/auth/google/callback) → GOOGLE_CLIENT_ID/SECRET in server .env. **APK gap:** Google blocks sign-in inside WebViews → open in a Chrome Custom Tab and return a one-time code via App Link |
| D2 | ⛔ | Email verification / codes by email — needs a mailbox to send from (Gmail app password or hosting SMTP); none found on this PC |

## E. Voice and assistant quality

| # | Status | What |
|---|---|---|
| E1 | ⬜ | openWakeWord "Hey Atulya" model for always-on listening (Whisper fallback stays) |
| E2 | ✅ | Camera on demand: "turn on the camera" fixed; vision questions ("what do you see", "read this", "यह क्या है") switch it on; **only those send a frame to the AI** (privacy) | Pattern tests |
| E3 | ✅ | First words: instant spoken acknowledgement from the request itself (29 ms laptop, 9-78 ms server) | Self-test |

## G. Owner feedback 2026-10-12 (real phone use) — in order

| # | Status | What | Proof / next |
|---|---|---|---|
| G1 | 🔧 | Speech starts on the opening clause (comma or ~8 words) instead of the whole first sentence; sentences synthesized one at a time | Target first audio ≈1 s; measure on server |
| G2 | 🔧 | Passkeys: accept the Android app's own origin (apk-key-hash), exclude only this account's passkeys, clear error per failure reason, server logs the real cause | Owner retry on phone + web |
| G3 | 🔧 | Misheard speech ("we look up" → VLOOKUP) corrected by the brain from context; memory checked before asking; lasting facts saved | Prompt rule; real phrase test pending |
| G13 | ✅ | Phone chat panel grew with every message (old flex rule overrode its height) and covered the hologram; now fixed at 40 % and the messages scroll; status chips/footnote hidden on phones | Reproduced with 40 messages: 2297 px → 325 px, scrolls |
| G14 | ✅ | Requests the page didn't understand ("hide chat options") now work: many more phrases + Hindi instantly, and a `screen_control` AI tool for any wording (hide/show chat, conversation mode, new chat, history, settings, camera, mute, reload) | Real model: "make the messages go away so I only see you" → hide_chat, "start a fresh chat" → new_chat |
| G15 | ✅ | Phone hologram framing: ⋮ → VIEW: CLOSE-UP (fills the area) / WIDE (whole scene like the website); remembered per device | Local phone-size check |
| G16 | 🔧 | Phone chat panel 30 % (owner: 20-30 %), compact rows | Owner check |
| G17 | ✅ | Always the newest version on reopen: HTML no-cache (304 when unchanged), versioned assets cached 1 year (full cache wipe would re-download the scene each open) | Headers |
| G18 | 🔧 | Chrome/Edge use the browser's own speech recognizer (Google, free, accurate) like the APK; Telegram keeps the server recognizer; falls back to the server after 3 errors | Owner check in Chrome |
| G19 | 🔧 | Live server speed measured on every deploy: selftest timings in the deploy log (names/timings only — public repo) | Next deploy log |
| G20 | 🔧 | APK UI test on a CI emulator against a private Atulya on the runner (no Cloudflare): sign in, layout, hide chat → CHAT, ⋮ menu, rotation, reopen, crash, memory; failure blocks the release | Next APK build |
| G21 | ✅ | Phone sign-in box jumped when the keyboard closed → taps on CONTINUE missed; now anchored near the top | Emulator UI test passes with keyboard open |
| G22 | 🔧 | Android Back closed the whole app (e.g. with the ⋮ menu open) → now closes menu/dialog/conversation mode first; unlock grace survives the screen being recreated | Emulator UI test |
| G23 | ✅ | Phone landscape: chat panel ran past the bottom (message box cut), chips overlapped the title, system panel took ⅓ width → fits the screen | Local 915×412 check + emulator |
| G24 | ✅ | Passkeys proven end to end with a software authenticator: website over HTTPS + inside the Android app (app signing-key origin); phishing site / other app rejected. Test fails if the app-origin fix is removed | `tests/core/test_passkey_flows.py` |
| G25 | 🔧 | ⋮ menu shows which recognizer is used (PHONE / BROWSER / SERVER); emulator test checks the app uses the phone's whenever it has one, and photographs the real launcher icon | Next APK run |
| G4 | 🔧 | Conversation mode: TALK button / "hide chat" → full-screen hologram, keeps listening, chat still recorded; CHAT button returns; phone chat sheet 48→40 % height | Owner check on phone |
| G5 | 🔧 | App versions: automatic builds bump only the last number (0.5.1, 0.5.2…); middle number only for milestones | Next APK |
| G6 | ⬜ | **Speech recognition quality** (biggest issue): Android app → native Android recognizer (free, on-device, Hindi); Chrome → browser recognizer; Telegram/others → better server STT (decision: Groq free Whisper-large vs. local) | Owner decision |
| G7 | ⬜ | Noise: real voice-activity detection (Silero VAD in the browser) so clicks, nail clipping, "shh" and background talk don't trigger; ignore when nobody speaks; no "no speech" message for silence | |
| G8 | ⬜ | Chat management: clear, archive, delete; history and settings reachable from conversation mode | |
| G9 | ⬜ | Login: Telegram code auto-fill/magic link reliability; email magic link needs a mailbox (D2) | |
| G10 | 🔧 | Professional look: launcher icon v2 (whole head inside the safe zone, glow background; was cropped by round masks); app theme still to redo (owner to pick references) | Preview circle/squircle, light/dark |
| G11 | ⬜ | Phone access in the Android app (notifications, contacts, calls/SMS with approval) | |
| G12 | ⬜ | Hologram speaking animation matches speech in full-screen mode (renderer is owner's — needs owner OK) | |

## I. Full backlog — every feature the owner listed (2026-10-13) + Claude's additions

Priority: **P0** foundation · **P1** useful now · **P2** real agency · **P3** later/research. Status as in the rest
of this file. Work happens in section H order; this is the complete list so nothing is lost. Status per item is
also kept in `docs/CAPABILITIES.md`.

### I-A. Platform, access, safety (P0 unless noted)
- ⬜ PLT-01/02 Capability registry: schemas, versions, which channel/device/permission each needs; AI and UI read it (H2)
- ⬜ PLT-03 Same execution path for web, Telegram, Android, desktop, MCP (✅ web+Telegram; MCP has copies → H2)
- 🔧 PLT-04 Structured tool results + errors (location statuses done; general contract H2)
- ✅ PLT-05 Identity: passkeys, password, Telegram, codes · ⬜ PLT-06 per-user/device/resource/action permissions (H5)
- ✅ PLT-07 Approval before changes/sends · ⬜ PLT-08 status model: available / needs location / needs connection /
  needs clarification / needs approval / unsupported / temporarily down — each with a next step (H2)
- ⬜ PLT-09 Progress, cancel, timeouts for long work (H8) · ⬜ PLT-10 Audit trail + provenance (H3)
- ⬜ PLT-11 (P1) Integration health checks · ✅ PLT-12 Secrets encrypted, redacted logs · ⬜ PLT-13 (P1) quotas, budgets
- ⬜ PLT-14 (P1) Version compatibility · ⬜ PLT-15 Shared error taxonomy + retry policy

### I-B. Cognition (P0–P2)
- ⬜ COG-01 Intent classification · ⬜ COG-02 Goal decomposition + plans · ⬜ COG-03 (P1) prioritise by value/urgency/risk
- ⬜ COG-04 (P1) Multi-step execution with dependencies · ⬜ COG-05 (P1) alternatives + trade-offs
- ⬜ COG-06 (P1) Confidence/uncertainty · ⬜ COG-07 (P1) contradictions + assumptions · ⬜ COG-08 Verify results (no fake "done")
- ⬜ COG-09 (P1) Change strategy after failure · 🔧 COG-10 (P1) Model routing (race NVIDIA/Gemini/OpenRouter; measured)
- ⬜ COG-11 (P2) Parallel tasks · ⬜ COG-12 Escalate to the user when unsure · ⬜ COG-13 (P1) Persistent goals
- ⬜ COG-14 (P1) Event interrupts · ⬜ COG-15 (P2) What-if analysis · ⬜ COG-16 (P2) Loop/stuck detection

### I-C. Memory (P0–P2)
- ✅ MEM-01 Conversation memory · ✅ MEM-02 Preferences (name, tone, language, short/detailed, voice) + saved places
- ⬜ MEM-03 (P1) Episodic memory of actions/outcomes · 🔧 MEM-04 (P1) Semantic search (keyword now)
- 🔧 MEM-05 (P1) Procedures = skills (1 skill) · ⬜ MEM-06 (P2) Knowledge graph (people, projects, files, decisions)
- ⬜ MEM-07 (P1) Time-aware facts · ⬜ MEM-08 (P1) Source/confidence/freshness on facts · ⬜ MEM-09 (P2) Consolidation
- ⬜ MEM-10 (P1) Correct contradictions · ✅ MEM-11 Search past chats · ⬜ MEM-12 (P1) Project memory (status, blockers, next)
- ⬜ MEM-13 Export / delete / review memory · ✅ MEM-14 Separate users' memory · ⬜ MEM-15 (P1) Memory recall benchmarks

### I-D. Research and live information (P1)
- ⬜ RES-01 Web search with sources (H4) · ⬜ RES-02 Multi-source research with citations · ⬜ RES-03 Source/date checks
- ⬜ RES-04 Read websites, extract data · ⬜ RES-05 Compare products/services · ⬜ RES-06 (P2) Watch pages for changes
- ⬜ RES-07 Extract tables/entities/timelines · ⬜ RES-08 Research dossier · ⬜ RES-09/10 (P2) Knowledge bases, gap questions
- ✅ News headlines

### I-E. Weather, location, maps (P1)
- ✅ LOC-01/02/03 Current, hourly, today/tomorrow/7-day; rain/snow amounts + chance; wind in words, gusts, direction;
  humidity, visibility, UV, sunrise/sunset; hot/cold verdict and change vs today; week's hottest/coolest/wettest day
- ✅ LOC-04 (part) Air quality now + tomorrow: AQI (US scale), PM2.5, PM10, NO2, ozone · ⬜ pollen, India CPCB AQI scale
- ✅ LOC-05 Device location by consent (web/app/Telegram button), low-power, only when needed, stale after 6 h
- ✅ LOC-06 Saved places (home, office, gym…) + home city fallback · ✅ any colony/sector/landmark/full Indian address
- ✅ LOC-07 Where am I (address + map link) · ⬜ LOC-08 (P2) Routes, travel time, alternatives (OSRM) (H4)
- ⬜ LOC-09 (P2) Nearby hospitals/pharmacies/fuel/shops/restaurants + opening hours (H4)
- ✅ LOC-10 Local time · ⬜ time-zone conversion · ⬜ LOC-11 (P2) Location reminders ("when I reach office") — needs
  OS geofencing, not live tracking · ⬜ LOC-12 (P2) Travel weather / city comparison · ⬜ severe-weather push alerts (H8)

### I-F. Files and office work (P1–P2)
- 🔧 FIL-01 Find files (local only) → any paired device (H6) · ⬜ FIL-02 Read/summarise PDF, TXT, MD, DOCX, code (H6)
- ⬜ FIL-03 (P2) OCR scans/photos · ⬜ FIL-04 Create/edit/convert DOCX, PDF, TXT, MD, RTF (H7)
- ⬜ FIL-05 Excel/CSV read, create, edit, formulas, pivots, charts · ⬜ FIL-06 (P2) PowerPoint create/edit, speaker notes
- ⬜ FIL-07 Compare versions · ⬜ FIL-08 (P2) Extract invoices/forms/statements → Excel · ⬜ FIL-09 (P2) Batch organise/dedupe
- ⬜ FIL-10 Templates · ⬜ FIL-11 Validate spreadsheets/totals · ⬜ FIL-12 (P2) Archives, metadata, integrity
- ⬜ FIL-13 (P0) Preview before save + backup · ⬜ FIL-14 Cross-device search/transfer · ⬜ FIL-15 Safe batch edits + rollback
- ⬜ PDF tools: merge, split, rotate, extract pages, redact · ⬜ Upload a file in chat on every channel (H6)

### I-G. Devices: laptop, phone, server (P0–P2)
- ⬜ DEV-01 (P0) Pair/register/revoke a desktop or phone agent · ⬜ DEV-02 (P0) List devices + resources + status (H5)
- ⬜ DEV-03/04 Laptop files read/edit in approved folders (H6/H7) · 🔧 DEV-05 (P2) Screenshot (local) → explain screen
- ⬜ DEV-06 (P2) Clipboard, windows · 🔧 DEV-07 (P2) Open apps (local) → remote via agent · ⬜ DEV-08 Approved commands, sandboxed
- 🔧 DEV-09 CPU/RAM/disk/battery/network (server ✅, laptop via agent) · ⬜ DEV-10 Android share-to-Atulya + document picker
- ✅ DEV-11 Phone mic/camera/voice (permission) · ⬜ DEV-12 (P2) Notifications (Firebase ⛔), deep links, open apps
- ⬜ DEV-13 (P2) Offline queue + sync · ⬜ DEV-14 (P0) Heartbeat/health · ⬜ DEV-15 Secure outbound remote access for agents
- ⬜ Multi-computer (home, office, dev) · ⬜ Process monitor, installed software, troubleshooting · ⬜ Lost-device help (official tools)

### I-H. Email, calendar, communication (P2; needs Google OAuth D1)
- ⬜ COM-01 Search/summarise email · ⬜ COM-02 Draft replies (any tone/language) · ⬜ COM-03 Send only with approval
- ⬜ COM-04 Attachments → summarise/save · ⬜ COM-05 Calendar search/create/update, free slots, conflicts (local calendar ✅)
- ⬜ COM-06 Meeting prep + notes → actions · ⬜ COM-07 Follow-up tracking · ⬜ COM-08 Contacts (with permission)
- ✅ COM-09 Same account/history across channels · ⬜ COM-10 (P1) Delivery status, no duplicate messages
- ✅ Telegram · ⛔ WhatsApp (Meta Business, C5) · ⬜ Inbox organisation (labels, priority, archive suggestions)

### I-I. Websites and browser automation (P2)
- ⬜ WEB-01 Browse/interact with approved sites · ⬜ WEB-02 Fill forms, stop before submit · ⬜ WEB-03 Download/file documents
- ⬜ WEB-04 Secure website sessions · ⬜ WEB-05 Account status, invoices (official API first) · ⬜ WEB-06 (P3) Change detection
- ⬜ WEB-07 (P0) Explicit OK for purchases/payments/submissions · ⬜ WEB-08 (P0) Prompt-injection defence for page/email text
- ⬜ Bookmarks/reading list · ⬜ Price/availability checks · ⬜ Website troubleshooting

### I-J. Server, DevOps, coding (P1–P2)
- ✅ OPS-01 Server health (read-only) · ⬜ OPS-02 Diagnose app errors · ⬜ OPS-03 Inspect config safely (H5)
- ✅ OPS-04 Encrypted backups (restore drill ⬜) · ✅ OPS-05 Deploy + verify + rollback · ⬜ OPS-06 Vulnerabilities, TLS expiry
- ⬜ OPS-07 Understand repos · ⬜ OPS-08 Code changes + diffs · ⬜ OPS-09 Run tests/lint · ⬜ OPS-10 Stack traces
- ⬜ OPS-11 (P2) GitHub branches/issues/PRs/CI (H9) · ⬜ OPS-12 (P2) Databases · ⬜ OPS-13 (P3) Multi-server
- ✅ OPS-14 Post-deploy self-test (12 live checks each deploy) · ⬜ Disk cleanup preview · ⬜ Service restart with approval

### I-K. Automation (P0–P3)
- ✅ AUT-01 One-time reminders, morning briefing · ⬜ recurring routines · ⬜ AUT-02 (P1) Event/condition triggers
- ⬜ AUT-03 (P1) Multi-step workflows · ⬜ AUT-04/05/06/07 (P0) Retries, checkpoints, pause/cancel, no duplicates, history
- ⬜ AUT-08 (P0) Approval gates in workflows · ⬜ AUT-09/10 (P2) Parallel agents + checking their work
- ⬜ AUT-11 (P1) Workflow templates (skills) · ⬜ AUT-12 (P3) Visual builder · ⬜ AUT-13 (P1) Failure/deadline notices
- ⬜ AUT-14 (P0) Budgets, runaway-loop stop

### I-L. Smart home (P2–P3, via Home Assistant first)
- ⬜ IOT-01..05 Register devices; lights/fans/plugs/scenes; sensors; time/occupancy rules; health + manual override
- ⬜ IOT-06 (P3) Energy analysis · ⬜ IOT-07 (P0 when used) Safety interlocks for heaters/locks

### I-M. Data and decisions (P1–P3)
- ⬜ DAT-01 CSV/Excel analysis · ⬜ DAT-02 Cleaning/validation · ⬜ DAT-03 (P2) Charts/dashboards/reports · ⬜ DAT-04 (P2) Statistics
- ⬜ DAT-05 (P2) Trends/anomalies · ⬜ DAT-06 (P2) SQL · ⬜ DAT-07 (P3) Forecasting · ⬜ DAT-08 Reproducible calculations
- ⬜ DAT-09 (P2) Budget/scenario comparisons · ✅ exact arithmetic (calculate tool)

### I-N. Learning and evaluation (P1–P3)
- ⬜ LRN-01 Record outcomes + failure types · ⬜ LRN-02 (P2) Failure → regression test · ⬜ LRN-03 Tool-success/recall benchmarks
- 🔧 LRN-04 Model quality/latency comparison (provider benchmark done 2026-10-12) · ⬜ LRN-05 (P2) Suggest new skills
- ⬜ LRN-06..08 (P3) Experts, curated traces, LoRA with rollback · ⬜ LRN-09 (P2) Memory consolidation · ⬜ LRN-10 Progress dashboard

### I-O. Security, privacy, reliability (P0–P1)
- ⬜ SEC-01 Least privilege · ✅ SEC-02 Encrypted secrets · ⬜ SEC-03 Prompt-injection defences · ⬜ SEC-04 Sandboxed execution
- 🔧 SEC-05 Approval ✅ + audit ⬜ · ⬜ SEC-06 Retention/deletion controls · 🔧 SEC-07 Backups ✅, restore drills ⬜
- 🔧 SEC-08 Metrics (self-test timings ✅, tracing ⬜) · ⬜ SEC-09/10 Graceful degradation, partial-failure recovery
- ⬜ SEC-11 Adversarial tests · ✅ SEC-12 Separate users' data · ✅ IP bans, rate limits on sign-in

### I-P. Ecosystem (P1–P2)
- 🔧 ECO-01 MCP server (duplicate tools → shared registry, H2) · ⬜ ECO-02 (P2) Use outside MCP servers with approvals
- ⬜ ECO-03 Plugin manifests/versions · 🔧 ECO-04 Skill format (1 skill) · ⬜ ECO-05..10 SDK, webhooks, signed plugins, plugin tests

### I-Q. Voice and UX (P0–P2)
- ✅ UX-01 Streaming answers · 🔧 UX-02 Voice in/out, interruption (phone/Chrome recognizer ✅, VAD ⬜, wake word ⬜)
- ✅ UX-03 Hindi/English · 🔧 UX-04 Short/detailed (profile ✅; ask when unclear ⬜) · ✅ UX-05 Approval cards (diff previews ⬜)
- ⬜ UX-06 Unified task inbox · 🔧 UX-07 Searchable history (chats ✅, actions ⬜) · 🔧 UX-08 Accessibility (labels ✅)
- ⬜ UX-09 Device/connection/permission status screen · ⬜ UX-10 Clear limits + recovery steps (H2)

### I-R. Creativity and simulation (P1–P3)
- ⬜ CRE-01 (P2) Images/audio/video/presentations · ⬜ CRE-02 Iterative design with versions · ⬜ CRE-03/04 (P1) Several distinct
  options + critique against a rubric · ⬜ CRE-05..10 Style guides, simulations, experiments, synthetic tests, prior art, idea log

### I-S. Everyday life (P1–P3)
- ⬜ PER-01 Tasks/deadlines/commitments · ⬜ PER-02 Daily/weekly planning · ⬜ PER-03 Shopping comparison · ⬜ PER-04 Travel plans
- ⬜ PER-05 Warranty/subscription/renewal tracking · ⬜ PER-06 Personal documents · ⬜ PER-07 (P3) Home inventory/maintenance
- ⬜ PER-08 (P3) Expenses/budget · ⬜ PER-09 Forms/paperwork (stop before submit) · ⬜ PER-10 Routines + reminders

### I-T. Teams (P2, after personal use works)
- ⬜ ENT-01..10 Roles, shared knowledge with boundaries, team tasks, approval chains, federated search, reports,
  decision log, multi-tenant isolation, import/export, usage/cost reports

### I-U. Cognitive OS modules (research track, P2–P3; only once H works)
- ⬜ Manas event bus · Vivek attention/judgement · Chitta working memory · Smriti long-term memory · Aham identity/limits ·
  Nirikshak verification/failure analysis · Yantra typed actions · planner · sleep/consolidation — as shared services, not demos

### I-V. Claude's additions (not in the owner's lists)
- ⬜ **Activity log with "undo"** per action (H3) — the fastest way to trust autonomy
- ⬜ **"What can you do here?"** command per channel, generated from the registry (H2) — kills "I can't do that" surprises
- ⬜ **Real-request test set:** 50 of the owner's actual questions run after every deploy, scored (did it use the right tool,
  was the answer correct) — measures progress instead of counting features
- ⬜ **Telegram location reminders** using Telegram's *live location for a set time* (15 min/1 h/8 h), never 24×7
- ⬜ **India-specific:** CPCB AQI scale, IMD weather warnings, PIN-code lookup, Hindi place names
- ⬜ **Cost/latency meter** per reply (model, tools, ms) visible to the owner
- ⬜ **Offline-safe answers:** when a service is down, say so with the last known value and its time, never invent
- ⬜ **Privacy switch:** "forget my location" / "pause location" commands; location history never kept, only the latest
- ⬜ **Personal shortcuts:** user-defined phrases ("goodnight" → lights off, alarms, briefing tomorrow)

### What Claude would do better (process)
1. Fewer, deeper features: each step in H ships only when it works from **all three** channels with a real test.
2. Every tool reports what really happened (no "saved" unless saved) — the office bug of 2026-10-13 shows why.
3. Measure with the owner's real questions after each deploy, not unit tests alone.
4. Ask the owner for one 5-minute phone check per milestone instead of many small ones.

## I-W. Ideas backlog (2026-10-13, 302 items — not yet in the main track)

These are feature ideas from the owner, grouped by category. They do NOT repeat anything in sections A–V.
Most should never be built just because they are possible. The owner's top picks are marked with a star (⭐).

### Seeing, hearing, sensing
- ⬜ 90. Read any text in a photo (signboards, menus, documents) and translate it
- ⬜ 91. Identify plants, birds, insects and dog breeds from a photo
- ⬜ 92. Food photo → rough calories and nutrition (estimate, clearly marked)
- ⬜ 93. Read a medicine strip/label → name, dosage on the label, expiry (no medical advice)
- ⬜ 94. Scan a barcode or QR code → what it is, whether the link is safe
- ⬜ 95. Describe a scene for low-vision use ("what's in front of me?")
- ⬜ 96. Count objects in a photo (people in a queue, items on a shelf)
- ⬜ 97. Read meters (electricity, water) from a photo and log readings
- ⬜ 98. Handwriting → typed text (notes, whiteboards)
- ⬜ 99. Recognise songs playing nearby and save them to a playlist
- ⬜ 100. Sound alerts: doorbell, pressure cooker whistle, baby crying (on-device, opt-in)
- ⬜ 101. Room noise level and a "too loud for calls" warning
- ⬜ 102. Measure things from a photo with a reference object (approximate)
- ⬜ 103. Compare two photos for differences (before/after repair, document changes)
- ⬜ 104. Detect a damaged parcel from a delivery photo, for a claim

### Knowledge and answers
- ⬜ 105. Explain any topic at any level, with examples from your life
- ⭐ ⬜ 106. Fact-check a forwarded WhatsApp message, with sources
- ⬜ 107. Explain a legal notice, contract or agreement in simple words (not legal advice)
- ⬜ 108. Explain bills, insurance policies and terms-and-conditions clauses
- ⬜ 109. "Explain like I'm 10" / "explain like an expert" toggle
- ⬜ 110. Answers with confidence levels and "how I know this"
- ⬜ 111. Local knowledge: best time to visit places, crowd levels (where data exists)
- ⬜ 112. Unit conversions in Indian units (gaj, bigha, lakh/crore)
- ⬜ 113. Historical "on this day" for your interests
- ⬜ 114. Compare two things side by side (phones, cities, courses)
- ⬜ 115. Settle debates with evidence ("who's right?")

### Language
- ⬜ 116. Speak and understand 20+ Indian languages (as models allow)
- ⬜ 117. Live conversation interpreter (you speak Hindi, they hear English)
- ⬜ 118. Rewrite in any tone: formal, polite, firm, funny
- ⬜ 119. Grammar and spelling coach that explains the mistakes
- ⬜ 120. Write letters: complaint, leave application, RTI, landlord notice
- ⬜ 121. Transliteration (Hinglish ↔ Devanagari)
- ⬜ 122. Summaries of long text in your language
- ⬜ 123. Pronunciation help with audio
- ⬜ 124. Speech-writing for weddings, events and speeches

### Creative
- ⬜ 125. Poems, shayari and songs in your style
- ⬜ 126. Story writing with you, chapter by chapter
- ⬜ 127. Image generation for posters, invitations and logos
- ⬜ 128. Photo editing by voice ("remove background", "brighten")
- ⬜ 129. Short video from photos with music and captions
- ⬜ 130. Voice-over for videos in your chosen voice
- ⬜ 131. Presentation design from a topic
- ⬜ 132. Greeting cards for festivals, auto-personalised
- ⬜ 133. Song lyrics meaning and translation (discussion only)
- ⬜ 134. Comic strips and storyboards
- ⬜ 135. Interior-design ideas from a room photo
- ⬜ 136. Outfit suggestions from your wardrobe photos and the weather
- ⬜ 137. Name ideas (business, baby, pet, project) with domain checks
- ⬜ 138. Brainstorming partner that argues the other side

### Work and career
- ⬜ 139. Resume and LinkedIn improvement for a specific job
- ⬜ 140. Job search alerts matching your skills
- ⬜ 141. Mock interviews by voice, with feedback
- ⬜ 142. Salary research for a role and city
- ⬜ 143. Cover letters tailored per job
- ⬜ 144. Daily standup notes from your activity
- ⬜ 145. Email triage: urgent / later / ignore
- ⬜ 146. Delegation tracker ("what did I ask whom?")
- ⬜ 147. Meeting cost and time tracker
- ⬜ 148. Skill-gap plan for a target role
- ⬜ 149. Freelance proposal writer
- ⬜ 150. Workload balance warning ("too many deadlines this week")

### Business (for your companies)
- ⬜ 151. Business plan and pitch-deck drafts
- ⬜ 152. Market research summaries with sources
- ⬜ 153. Competitor monitoring (public pages)
- ⬜ 154. Customer-support reply drafts from your FAQ
- ⬜ 155. Inventory tracking from photos or spreadsheets
- ⬜ 156. GST return preparation help (draft only)
- ⬜ 157. Simple CRM: leads, follow-ups, deals
- ⬜ 158. Website chatbot powered by Atulya for atulvij.com visitors
- ⬜ 159. Marketing calendar and post drafts
- ⬜ 160. Price-change monitoring on suppliers' public pages
- ⬜ 161. Contract renewal and vendor reminders
- ⬜ 162. Daily business dashboard (sales, traffic, support) on Telegram

### Money (read-only and advice-free)
- ⬜ 163. Net-worth tracker from statements you upload
- ⬜ 164. Budget envelopes with alerts
- ⬜ 165. Insurance renewal and coverage summary
- ⬜ 166. Tax-saving checklist (80C and others, informational)
- ⬜ 167. Investment portfolio summary from statements (no buy/sell advice)
- ⬜ 168. "Can I afford this?" based on your budget rules
- ⬜ 169. Loan, credit-card and due-date tracking
- ⬜ 170. Detect unusual charges in statements
- ⬜ 171. Shared household expense ledger
- ⬜ 172. Gift budget per festival/person

### Health, fitness, wellbeing (information only)
- ⬜ 173. Workout plans by goal and equipment, with voice coaching
- ⬜ 174. Step/sleep data summaries (from connected fitness apps)
- ⬜ 175. Meal plans by diet preference (veg, Jain, diabetic-friendly; not medical advice)
- ⬜ 176. Yoga and breathing sessions guided by voice
- ⬜ 177. Period/cycle tracking (private, local)
- ⬜ 178. Mood check-ins and journalling prompts
- ⬜ 179. Mental-health resources and helplines when needed (never therapy)
- ⭐ ⬜ 180. Vaccination schedule reminders for family members
- ⬜ 181. Lab report organiser: trends over time (no diagnosis)
- ⬜ 182. Posture reminders while working

### Education (for you and family)
- ⬜ 183. Homework helper that teaches, not just answers
- ⬜ 184. Exam schedules and revision plans
- ⬜ 185. Practice questions from textbook photos
- ⬜ 186. Course recommendations for a goal
- ⬜ 187. Coding tutor with exercises
- ⬜ 188. Math step-by-step solver with explanations
- ⬜ 189. Reading-level stories for kids
- ⬜ 190. Quiz games for family learning

### Home
- ⬜ 191. Smart-home routines by time, weather or AQI (purifier on when AQI is bad)
- ⬜ 192. Energy-saving tips from electricity bills
- ⬜ 193. Plant watering reminders by weather
- ⬜ 194. Home maintenance calendar (cleaning, pest control, servicing)
- ⬜ 195. Water-tank and RO-filter schedules
- ⬜ 196. Security camera summaries ("anyone at the door today?"), your own cameras only
- ⬜ 197. Power-cut and water-supply schedule alerts (where published)
- ⬜ 198. Moving-house checklist and address-change list
- ⬜ 199. Rent agreement and payment reminders
- ⬜ 200. Furniture fit check with room measurements

### Family and relationships
- ⬜ 201. Shared family calendar
- ⬜ 202. Gift ideas from what people like
- ⬜ 203. Event planning: guest list, invites, RSVPs, menu, budget
- ⬜ 204. Kids' screen-time summaries (your own devices, with their knowledge)
- ⬜ 205. Family tree and stories archive
- ⬜ 206. Elder-care medicine and appointment coordination
- ⬜ 207. "Remember what X likes" (with their knowledge)

### Shopping
- ⬜ 208. Product comparison with reviews summarised
- ⬜ 209. Price-drop alerts (public prices)
- ⬜ 210. Warranty registration from invoices
- ⬜ 211. Return/refund deadline tracking
- ⬜ 212. "Buy again" reminders for consumables
- ⬜ 213. Size guide across brands
- ⬜ 214. Fake-review warning signs

### Travel and transport
- ⬜ 215. Cab fare estimate and route comparison
- ⬜ 216. Parking reminders ("where did I park?" photo + location)
- ⬜ 217. Vehicle service, insurance and PUC reminders
- ⬜ 218. Fuel log and mileage
- ⬜ 219. Traffic-aware "leave now" alerts for meetings
- ⬜ 220. Train/bus seat-availability alerts (official sources)
- ⬜ 221. Airport checklists and timings
- ⬜ 222. Lost-luggage claim helper
- ⬜ 223. Road-trip planner with stops, fuel and food

### Government and legal (help to understand and prepare, never to submit for you)
- ⬜ 224. RTI application drafts
- ⬜ 225. Consumer-complaint drafts (consumer forum, e-Daakhil)
- ⬜ 226. Document checklists per government service
- ⬜ 227. Scheme eligibility checker (government schemes)
- ⬜ 228. Property-document checklist
- ⬜ 229. Police complaint / FIR draft help (you submit)
- ⬜ 230. Explain court notices in simple words
- ⬜ 231. Voter ID and registration reminders

### Vehicles and machines
- ⬜ 232. Car fault codes explained (from an OBD reader app)
- ⬜ 233. Two-wheeler maintenance schedule
- ⬜ 234. EV charging-station finder
- ⬜ 235. Appliance error codes explained by model

### Developer and tech (beyond the current list)
- ⬜ 236. Write and run small scripts in a sandbox
- ⬜ 237. Explain any codebase by voice
- ⬜ 238. Generate APIs, databases and websites from a description
- ⬜ 239. Docker/server setup guides tailored to your server
- ⬜ 240. Log anomaly detection with explanations
- ⬜ 241. Load and performance testing for your sites
- ⬜ 242. Accessibility audit of your website
- ⬜ 243. Security headers / SSL / DNS audit
- ⬜ 244. Git commit-message and PR-description writer
- ⬜ 245. Natural language → SQL queries over your data
- ⬜ 246. Website change monitor for your own sites (visual diff)
- ⬜ 247. Generate test data and test cases
- ⬜ 248. Wake-on-LAN and remote PC status

### Security and privacy
- ⬜ 249. Privacy check of the app permissions on your phone (your own)
- ⬜ 250. Two-factor setup reminders per account
- ⬜ 251. "Is this email real?" header analysis
- ⬜ 252. Suspicious-link sandbox preview
- ⬜ 253. Personal data exposure check (your own data, public sources)
- ⬜ 254. Secure notes vault (encrypted)
- ⬜ 255. Emergency info card (blood group, contacts) on the lock screen

### Social and community
- ⬜ 256. Neighbourhood notices summary (RWA groups you're in)
- ⬜ 257. Volunteering opportunities nearby
- ⬜ 258. Event discovery by your interests (public listings)
- ⬜ 259. Social-media drafts in your voice (you post)
- ⬜ 260. Group-decision helper (polls, summarising opinions)

### Entertainment and fun
- ⬜ 261. Trivia and quiz games by voice
- ⬜ 262. Interactive stories and text adventures
- ⬜ 263. Chess/ludo-style games with the hologram
- ⬜ 264. Jokes and riddles in Hindi/English
- ⬜ 265. Movie and series tracker with release alerts
- ⬜ 266. Daily "fun fact" in your interests
- ⬜ 267. Karaoke mode with lyrics on screen (licensed sources)
- ⬜ 268. Hologram reactions and emotions during games

### Science, nature, environment
- ⬜ 269. Stargazing guide: what's visible tonight from your location
- ⬜ 270. Satellite pass times (ISS)
- ⬜ 271. Earthquake alerts and information
- ⬜ 272. Carbon-footprint estimate of trips and bills
- ⬜ 273. Gardening by season and climate
- ⬜ 274. Weather history ("was last October hotter?")

### Agriculture and rural (useful across India)
- ⬜ 275. Crop advice by soil, season and weather (informational)
- ⬜ 276. Mandi prices for crops
- ⬜ 277. Pest identification from leaf photos
- ⬜ 278. Irrigation timing by rain forecast

### Accessibility
- ⬜ 279. Full voice-only operation
- ⬜ 280. Large-text / high-contrast modes
- ⬜ 281. Screen-reader-friendly answers
- ⬜ 282. Sign-language learning resources
- ⬜ 283. Simplified mode for elderly users
- ⬜ 284. Dyslexia-friendly reading mode

### AI autonomy (later, always with approval and limits)
- ⬜ 285. Agents that work for hours on a goal and report progress
- ⬜ 286. Atulya calling businesses for you (where allowed), with a full transcript
- ⬜ 287. Negotiation drafts (price, rent), which you approve
- ⬜ 288. Self-improving skills from your corrections
- ⬜ 289. Multiple Atulya "personas" for work, family and fun
- ⬜ 290. Atulya-to-Atulya coordination between family members' assistants (opt-in)
- ⬜ 291. Simulations before big decisions (job change, move, purchase)
- ⬜ 292. Long-term goal coach (fitness, learning, savings) with weekly check-ins
- ⬜ 293. Predict what you'll need ("you usually order groceries on Sunday")
- ⬜ 294. Explainable decisions: "why did you suggest this?"
- ⬜ 295. Personal knowledge base built from everything you approve

### Hardware and physical world (future)
- ⬜ 296. Smart-glasses mode: what you see, described and translated
- ⬜ 297. Car mode: voice-only, driving-safe answers
- ⬜ 298. Smartwatch quick replies and alerts
- ⬜ 299. Robot vacuum and appliance control
- ⬜ 300. Drone/camera control for your own property (where legal)
- ⬜ 301. Wearable health alerts (falls, abnormal heart rate) from certified devices only
- ⬜ 302. Desk hologram display device for Atulya's face (your scene on dedicated hardware)

### Owner's top picks (build first when their category comes up)
1. ⭐ 69/252 — Scam and link checker (useful daily, easy to build)
2. ⭐ 27 — Telegram group summaries
3. ⭐ 106 — Fact-check forwarded messages
4. ⭐ 14/180 — Medicine and vaccination reminders
5. ⭐ 163–170 — Money summaries (read-only)
6. ⭐ 219 — "Leave now" traffic alerts
7. ⭐ 191 — Air-purifier-on-bad-AQI routine
8. ⭐ 3/4 — PNR and flight status

## F. Later (after A-E)

Smart home (Home Assistant) · Gmail/Calendar sync · music · file/PDF answers · routines & proactive notices ·
Google Play listing (owner account) · website traffic project (separate).

## Verified recently (real runs)

- Self-test 12/12 against the running server (chat+tools, memory, profiles, code sign-in, voice unlock, TTS→STT,
  briefing, PC approval, Telegram); clean installs pass on Windows/Ubuntu/macOS (GitHub Actions).
- Web servers: Cloudflare-only firewall on 80/443 (IPv4+IPv6), SSH keys only, fail2ban active — no change needed.
