# Roadmap: what is left and what is next

This is the forward-looking half of the status pair. **[STATUS.md](STATUS.md) says where we are**
(capabilities and how well they are tested); **this file says what is left and what comes next.**

Legend: **Done** = implemented and has unit tests. **Unverified** = implemented, but never run on
real hardware or accounts (a unit test with mocks does not count). **Planned** = not written yet.

Order matters throughout: each step needs the one above it, and anything that spends money, books,
sends or deletes **must ask first**.

---

## Next

Ranked by what unblocks the most. Items 1-3 are the difference between a demo and a product.

| # | What | Why it is next | State |
|---|---|---|---|
| 1 | **Prove everything on real hardware** (microphone, camera, TV, phone, PC control, Windows media keys) | Almost every "Unverified" row in STATUS is waiting on this. It cannot be done from a container — it needs you to report what breaks | Needs you |
| 2 | **Verify Docker and the packaged build** | The production path in [DEPLOYMENT.md](DEPLOYMENT.md) has never actually been built (see Fix backlog F1). Shipping an untested deploy path is the single largest operational risk | Open |
| 3 | **Fast answers by default** | Local CPU brains take 14-90 s for a sentence, which is unusable for a voice assistant. A cloud key or a Colab GPU is the fast route today (`examples/`); a smaller, quicker local path is not built | Partially open |
| 4 | **Finish the web agent on a real browser** (A1) | Unblocks A3 shopping, A4 appointments and A9 food/rides — the whole real-world-action chain sits behind it | Logic done, never run live |
| 5 | **Hindi voice quality and a trained wake word** (gaps 10, 11) | The product is pitched as Hindi-first, and Hindi speech in and out is untested | Unverified |
| 6 | **Identity that works** — voice ID wired into permissions and personalisation, face recognition (gap 3) | Determines whether memory, permissions and replies can differ per person instead of per account | Not integrated |

---

## Planned: real-world actions

| # | Feature | Plan | State |
|---|---|---|---|
| A1 | **Web agent**: "add the blue running shoes to my cart", "book a table" (`web_task`, `atulya/jaal.py`) | Playwright session driven step by step by the brain. Hard stops in code: payment / place order / confirm booking clicks, password and card fields, CAPTCHA, non-http links. Asks before starting; every step is audited | Logic **done and tested** with a fake page (hard stops, page-text injection, step limit). **Not run on a real browser or real shop yet**; needs `pip install "atulya[browser]" && playwright install chromium` |
| A2 | Real playback: play a named song | Done for YouTube (top result, autoplay). Still planned: a controlled tab so pause/next work on it, and Spotify through its API | Partly done |
| A3 | Shopping helper | Built on A1: search several sites, compare price, add to cart, never pay | Planned |
| A4 | Appointments | Google Calendar invite and booking-site forms through A1; confirm the slot before submitting | Planned |
| A5 | Messaging by voice: "tell Mum I'm late" | Contact book, confirm-first messaging, Twilio outbound calls/SMS and signature-validated inbound callbacks | Implemented; Twilio account and real phone behaviour still need live verification. Other channels need their own setup |
| A6 | Phone control | Android over ADB (keys, volume, open app by name, open link, battery, screenshot); anything else through Home Assistant. Ringing a phone and push alerts need a companion app. iPhone: very limited | **Built for Android** (see device fabric below); not tried on a real phone. iPhone not covered |
| A7 | TV control | Roku, Kodi, Android/Fire TV (ADB), Wake-on-LAN, and Samsung/LG/others via Home Assistant (see device fabric below) | **Built**; not tried on a real TV. Samsung/LG direct, Chromecast and AirPlay are not covered for every TV model |
| A8 | Desktop control beyond keystrokes | Window list, focus, OCR label click, screen read, file search and open | Built with confirmation gating and mocked OCR tests; needs verification on a real desktop |
| A9 | Food, rides, bills | Only through official APIs or A1 with the same hard stops. Not before A1 is proven | Planned |

---

## Planned: Jarvis behaviour

| Feature | State |
|---|---|
| Proactive: meeting heads-up | Done (PR #58) |
| Proactive: more triggers (traffic, bills, "you usually…") | Habit nudges and user-authored event triggers exist; live traffic/leave-now provider is not built |
| Hologram readability: face no longer washed out; caption in a fixed side box that auto-scrolls; soft lip glow that follows the voice | Done and checked in a real render when idle. **Lip glow position is estimated and not yet seen while speaking** |
| Mood on the hologram: `/api/mood` (tested) tints the figure warm or cool and sets how lively it breathes; refreshed after each reply | Done in code; **colour shift is subtle and was not judged by eye** |
| Webcam as a sense (Settings → "Let Atulya see me"): in-browser motion presence, head turns toward you, "what do you see?" sends one picture to the vision brain; green-framed preview shows it is on | Done; checked in a real browser with a **fake camera** (video plays, no errors). **Not tried with a real camera or a real person**. Eye contact is motion-based, not face detection |
| Ambient light: the webcam measures room brightness and the hologram eases its glow in a dark room | Done; checked that the camera still runs with it, **the glow change itself was not judged by eye** |
| Hand gestures, face recognition, sound events (claps, doorbell, glass) | **Not built.** These need explicit opt-in, local models and real data before they can be trusted |
| Voice ID (who is speaking) | Optional enroll/identify/list provider and tools are implemented | Not connected to permissions or personalization; optional model and real-voice behaviour need direct tests. Do not use as an unlock mechanism |
| Memory tree view in the web app (menu → Memory tree, or say "show memory"): animated tree, trunk = you, branch per kind, leaf per stored fact, new facts grow in live | **Done**: backend (`/api/memory/graph`, tested) and canvas animation, checked in a real browser with 12 seeded facts. Not yet: relations between people (Alice → Bob), vector-memory leaves |
| Automation dashboard in the web app (jobs, reminders, calendar, media, devices) | **Done** (menu → Action engine); media buttons Windows only |
| Encrypted memory at rest (`atulya/raksha.py`): set `ATULYA_VAULT_PASSPHRASE` in `.env`; money, calendar, reminders, email settings, chat history and your profile are then stored encrypted (scrypt key, Fernet). Tamper is detected; a wrong passphrase locks the data and can never overwrite it; with no passphrase it says plainly that it is off. Status in the dashboard (System tile) | Done, 7 tests. **Lose the passphrase and the data is gone.** Not covered: the vector memory, the audit log, `.env` itself, and anyone who can read your running PC's memory. The old `encrypted_storage.py` is not used (it fell back to base64 and kept its key beside the data) |
| Phone sync and push | Paired-phone inbox API, Termux sync and optional VAPID delivery are implemented | Local code/tests exist; real Android permissions, native push setup and hardware behaviour remain unverified |
| Brain speed | **Done**: with a cloud key set, cloud brains lead and the tiny local model is the offline fallback; the router measures each brain and tries the fastest first (pin an order with `ATULYA_BRAIN`). Not done: a smarter local model |
| Real hardware test pass (voice, PC control, camera) | **Needs you**: cannot be done from the cloud container |

---

## Known gaps: what a real Jarvis has that Atulya does not (yet)

Honest list, most valuable first. "Built" means written and tested here; nothing below is proven on
your own devices.

| # | Gap | Why it matters | State |
|---|---|---|---|
| 1 | **Everything proven on real hardware** (microphone, camera, TV, phone, PC control, Windows media keys) | Every "Unverified" row in STATUS. A Jarvis that fails on the real TV is not Jarvis | Needs you: report what breaks; I fix |
| 2 | **Fast answers by default** | Local CPU brains take 14-90 s for a sentence; a cloud key or a Colab GPU is the fast route (`examples/`) | Cloud keys and the GPU route exist; a smaller, quicker local path is not built |
| 3 | **Knows who is there**: voice ID, face recognition, hand gestures, sound events (doorbell, clap, glass) | Voice identity tools exist, but identity-based personalization and permissions are not integrated | Voice ID needs direct feature tests and real-voice checks. Face recognition, gestures and sound-event detection are not built |
| 4 | **Sees the screen**: read it, click a button by its text, find a file | OCR label click now has unique-match and confirmation checks | Built in code with mocked OCR tests; unverified on a real second computer |
| 5 | **Acts on the web safely**: shopping, booking, bills, food, rides | `web_task` exists with hard stops (never pays); the shopping and booking flows on top (A3, A4, A9) are not built | Partly built |
| 6 | **Messages and calls by voice**: "tell Mum I'm late" | Contact book, confirm-first messaging, Twilio outbound SMS/calls and signed inbound callbacks | Code and local safety tests exist; real Twilio account and phone behaviour remain unverified |
| 7 | **Phone companion**: push alerts, ring my phone, location, read notifications, sync | Paired inbox, opt-in Termux SMS/notification sync, phone commands, admin pairing and optional VAPID delivery | Shruti phone listener now reuses shared audio/API components; no trained Atulya Hindi wake model is shipped. Native Android inbound-call support and real Android testing remain |
| 8 | **Works while you are away**: long jobs in the background that report back ("watch this price, research that, tell me tonight") | Shared cron runner now persists run status/progress, supports cancellation, enforces a five-minute run bound, expires run metadata after seven days, and marks uncertain in-flight work interrupted after restart without replay. Reflexes includes job controls and latest results | Local tests pass; job execution is limited by the existing assistant/kernel capabilities. Open-ended research workflows and sub-agents are not built |
| 9 | **Gets better from feedback**: thumbs up/down, "that was wrong", learning your style | Feedback is recorded and recent corrections guide later replies; profile facts/preferences are account-scoped | Automatic model fine-tuning and safe self-authored tools are not built |
| 10 | **Hindi voice quality**: speech recognition and speaking in Hindi, mixed Hindi-English | Hindi wake words exist; quality of Hindi speech in and out is untested | Unverified |
| 11 | **Trained "Atulya" wake word** | Optional local model gate; Termux and desktop use the shared gate | No trained Atulya/Hindi model is shipped; provide a compatible model and test phone microphone behaviour |
| 12 | **Smart-home scenes by voice** ("movie mode": lights, TV, volume) | Named routines and event-trigger rules exist and can call device tools | End-to-end, cross-provider scenes still need hardware verification and simpler setup; the routine/trigger engine itself is implemented |
| 13 | **Safer by construction**: OS sandbox, audit log, per-user rate limits and trusted family devices | Audit chain, pairing scopes, path rules, confirmations and bounded paired-agent queues exist | OS-level sandbox, per-route throttling, family/guest role onboarding and second-device security validation remain |
| 14 | **Easy to install and keep**: installer, updates, backups and CI | Guided `install.py`, `start.bat`, CI workflow and tagged releases exist | Guided setup is implemented; GitHub CI is not verified here. Packaged installer, staged updater/rollback and backup/restore remain |
| 15 | **Mood and eye contact on the hologram** | Mood detection exists; the figure's colour change is subtle and the eyes do not follow you yet | Partly built |

Smaller known gaps: face/gesture/sound perception; a shipped trained wake model; shopping and
booking workflows; traffic-aware departure suggestions; automatic model improvement; CI execution,
installer/updater and backup/restore; real device and service verification. Vector memory and the
audit log are not encrypted. Private files use encryption only when `ATULYA_VAULT_PASSPHRASE` is
configured.

---

## Fix backlog

Open items first — everything after the divider has already landed and is kept only as a record of
what was wrong and how it was verified.

| # | Fix | State |
|---|---|---|
| F1 | **Docker image never built** | **Open.** The documented production path in [DEPLOYMENT.md](DEPLOYMENT.md) has not been proven to build. Until F1 closes, treat Docker as unverified and prefer the native service path |
| F2 | Phone (Capacitor) files moved to their flat location, and the Docker build, were never re-checked after the folder restructure | **Open** |
| F3 | Webcam failure reason: the error now says *why* (insecure address, blocked, busy, none found) and falls back to any camera size | **Open on the diagnosis side** — it needs your report of which case it is |
| F4 | `OpenCode Go` brain (`OPENCODE_API_KEY`) is implemented but **never tested against the live service**; model names are defaults overridable with `ATULYA_OPENCODE_MODEL` | **Unverified** |
| F5 | Voice/typed "click" inside an open window works for both windows (`frontend/src/sections.js`) but was **not tried with a real microphone** | **Unverified** |
| F6 | Real hardware test pass (voice, PC control, camera) | **Needs you** — cannot be done from a container |

### Landed

| Fix | State |
|---|---|
| README concept images in "How a request flows" and "Memory" (one said "Yantra") | Removed from the README; files kept in `docs/` until real screenshots replace them |
| Email tests depended on leftover `kosh//` config | Fixed: tests use a temp data dir |
| `test_ambient.py`, `test_senses.py` failed to import without numpy | Fixed: skipped when missing |
| `camera_status` had no test | Fixed |
| **HTTPS option** (`ATULYA_HTTPS=on`): serves https with a self-signed certificate covering `localhost`, this computer's name and its network addresses (renewed when the address changes or 30 days before expiry); key file owner-only; `start.bat` prints the right address. Makes phone camera/mic work over Wi-Fi | Done, 4 tests, checked with the real server (certificate verified by curl on `localhost`, plain http refused). **Not tried from a real phone or over a real network address**. The browser warns once about the certificate, by design |
| **Device fabric** (`atulya/upakaran.py`, guide in [DEVICES.md](DEVICES.md)): one layer for any controllable device. Four connection methods (JSON profiles over HTTP, ADB for Android/Fire TV, Wake-on-LAN, Home Assistant for thousands of brands); network discovery; a hub that stores devices and understands speech from each device's own abilities, with no brand list in code; tools for the brain (`device_do`, `device_list`, `device_discover`, `device_add`, `device_learn` …); "learn this device" drafts a profile with the brain and you approve it; dashboard panel with Scan, Add and per-device buttons; confirm-first for risky actions | Done, 52 tests including **simulated devices speaking the real protocols over real sockets** (Roku, Tasmota, WLED, Kodi, Shelly, Home Assistant, a fake `adb`, a real UDP Wake-on-LAN receiver, SSDP). Checked end to end through the real server. **Not tried with any real hardware.** Built-in profiles come from public protocol descriptions and may need fixes on real devices |
| "If not sure, check with AI" for bank messages: rules read clear messages; a message that mentions money but does not parse is sent to your brain (account numbers, phones, emails, links removed first; never for OTPs, offers or due reminders). The AI's answer is only accepted if the amount really appears in the message; AI-read entries are marked and the reply says "please check". `ATULYA_MONEY_AI=off` turns it off | Done, 4 tests with a fake brain. **Not tried with a real brain.** It sends redacted message text to whichever brain answers, which may be a cloud company |
| **Money helper** (`atulya/kriya/`): "I spent 500 on groceries", "how much did I spend this month / on food / last month", budgets with left/over notes, monthly bills with a heads-up 3 days before, "I paid the electricity bill", bank-statement CSV import, Money tile in the dashboard. Local file only (`kosh/agent/money.json`); never connects to a bank and never pays | Done, 14 tests, checked through the real server with the phrases above. **Not tried with a real bank statement**: column names are matched for common Indian-bank exports and may need adding for yours. Currency is ₹ (change with `ATULYA_CURRENCY`) |
| **Bank alerts from SMS and email**: `POST /api/money/sms`, "check my email for bank transactions", paste-in tool, OTP/offer/due messages ignored, same transaction by SMS and email counted once | Done, 19 tests, exercised by posting real HTTP requests to the running server. **Not tried with a real phone, real bank SMS or a real mailbox.** Sample alert wordings are approximations of common Indian-bank messages; banks differ, so check totals in the first week |
| **Samsung Smart TV driver** (`atulya/upakaran.py`): remote keys over the TV's own websocket, pairing token stored, discovery by port 8001, speech works ("volume up on the samsung tv") | Done, 9 tests against a simulated TV. **Not tried on a real TV.** A TV that is fully off needs Wake-on-LAN; old plasma without Smart Hub cannot be controlled over the network |
| **Local brain speed**: plain questions no longer send the tool list (about 2,100 → 350 prompt tokens; Qwen3-4B on 4 CPU cores: 77 s → 14 s per answer) | Done and measured in the sandbox; your PC will differ. Bigger models are still slow on CPU: use a cloud key or the Colab route in `examples/` |
| Bug: after one slow answer the router preferred the "No brain loaded" reply over the real brain | Fixed, tested |
| Dead code removed: 5 unused memory modules, 10 unreferenced functions, the stale `requirements.txt` and an earlier `ROADMAP.md`, 4 unused images, the read-only Users menu | Done: 704 tests pass |
| Pretend smart-home devices removed from real use; memory tree redrawn closer to the concept art; camera preview and HUD overlap fixed | Done, 714 tests pass; checked in a real browser with a fake camera. **Not pixel-identical to the concept art**: its canopy has hundreds of nodes, ours draws only what is stored |
| `data/` → `kosh/`, `demo/` → `examples/`; old `data/` moved automatically on first start; old `/api/devices` controller removed | Done, tested (3 migration tests). **Not tried on Windows with a running server holding files open**: if the move fails it copies instead and keeps the old folder |
| **Speed panel** (menu → Brains & keys): measured seconds per brain, advice with 3 steps when only a slow local model answers, fast free providers first | Done, 2 tests, checked in a real browser with seeded numbers. **The promise "a few seconds" for Groq is general knowledge, not measured here**; use Test on your key to see your own number |
| Server startup: local model loads in a background thread (page open 5.0 s → 1.1 s with the 4B model, measured) | Done, test fails without the change. On your PC the gain depends on disk and model size |
| Memory tree shows all 8 branches (empty ones faded, "0 items") and denser boughs | Done, checked in a real browser. Still sparser than the concept art: it draws only what is stored |
| Any tool with a parameter named `name` crashed ("multiple values for argument 'name'") | Fixed in `ToolRegistry.execute`, tested |
| Memory tree rebuilt as a big centred window (menu → Memory tree): trunk = you, 8 branch kinds, every golden node a real item; callouts for episodic memories, entity relations, preferences, vectors; tap a branch to open its full list with search | Done and checked in a real browser. **Not pixel-identical to the concept art**: far less dense because it only draws what is stored. World knowledge stays empty until something fills it |
| Action engine dashboard (menu → Action engine): system status + measured brain speeds, PC automation (real on/off switch), web task flow, smart home hub, calendar & reminders, media player with working buttons | Done and checked in a real browser. Media buttons only work on Windows; home devices are practice devices without Home Assistant; PC control is untested on real hardware |
| Brain tool calls were never audited (the audit log was only written by the old agent path), so "every action is logged" was false | Fixed in `atulya/mastishk/aujar.py`, tested |
| Calendar events were saved but never loaded on restart, so a restart wiped the calendar | Fixed, tested |
| Link more brains: 22 providers in one table (`providers_catalog.py`); Menu → Brains & keys: paste key, pick model, Test, Remove; saved to `.env` (owner-only), never shown again | Done and tested, UI checked in a real browser. **Only the generic OpenAI-style class is exercised by tests; no provider was called live.** Default model names can be out of date: change them in the card |
| Camera: detects cameras automatically, 📷 button asks the browser for permission, picker when several, remembers on/off and restarts by itself when already allowed | Done; checked with a fake camera (present, absent). Not tried on real hardware |
| Keys in `.env` were only read by `start.bat` (breaks on quotes, spaces, Notepad BOM) | Fixed: server and CLI read `.env` themselves (`atulya/adhar.py`, tested) and print `Brains ready: ...` at startup |
| "OpenCode" was only the last-resort "No brain loaded" message, so an OpenCode Go key did nothing | Fixed: real `OpenCode Go` brain. See F4 above for what is still unverified |
| Old sidebar UI appeared when the server was down (offline cache served an old saved copy) | Fixed: cache bumped to v3 (purges old copies); `start.bat` rebuilds on content change. Do a hard refresh (Ctrl+Shift+R) once |
| Top-level folders renamed to English names (`docs/`, `tests/`, `atulya/indriya`) | Done and pushed. Note: this reverts an earlier rename to Hindi folder names — **the old `granth/`, `pariksha/`, `drishti/` and `web/` paths no longer exist** |
| Module count in the docs drifted from reality | Fixed: README and CONTRIBUTING now agree with the tree |
