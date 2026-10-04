# Status: what is done, what is tested, what is next

Legend: **Done** = implemented and has unit tests. **Unverified** = implemented, but never run on real hardware or accounts
(a unit test with mocks does not count). **Planned** = not written yet. Update this file in every PR.

Last full test run: 542 passed, 8 skipped (`test_ambient.py` and `test_senses.py` skip without numpy).

## 1. Everyday actions (tools in `atulya/agent/`)

| Ability | Tool | State |
|---|---|---|
| Play a song / video | `play_music` (starts the top YouTube result; Spotify opens a search) | Unit-tested with mocks; **never run against live YouTube**, which can change its page at any time (falls back to the search page) |
| Pause, next, volume | `media_control` (Windows media keys) | Unverified |
| Open a website | `open_website` | Unverified on real browsers |
| Reminders | `set_reminder`, `list_reminders`, `cancel_reminder` | Done; spoken when due |
| Calendar | `calendar_add`, `calendar_list`, `calendar_remove` (local, or Google when connected) | Done |
| Meeting heads-up | `calendar.soon` event, rule `trg_calendar_soon` | Done (PR #58) |
| Email | `send_email`, `fetch_emails`, `configure_email` | Unverified on a real mailbox; sending asks first |
| Weather, time, calculator | `get_weather`, `get_forecast`, `current_time`, `calculate` | Done |
| Price watchlist, briefing | `track_*`, `morning_briefing` | Done |
| Smart home | `home_control`, `home_list_devices` | Unverified; needs Home Assistant or MQTT |
| Control the PC | `pc_open_app`, `pc_type`, `pc_hotkey`, `pc_screenshot` | Unverified; off until `ATULYA_PC_CONTROL=on`; asks first |
| Camera, pictures | `analyze_image`, `camera_status` | `camera_status` has no test |

## 2. Planned: real-world actions

Order matters: each step needs the one above it. Anything that spends money, books, sends or deletes **must ask first**.

| # | Feature | Plan | State |
|---|---|---|---|
| A1 | **Web agent**: "add the blue running shoes to my cart", "book a table" (`web_task`, `agent/webagent.py`) | Playwright session driven step by step by the brain. Hard stops in code: payment / place order / confirm booking clicks, password and card fields, CAPTCHA, non-http links. Asks before starting; every step is audited | Logic **done and tested** with a fake page (hard stops, page-text injection, step limit). **Not run on a real browser or real shop yet**; needs `pip install "atulya[browser]" && playwright install chromium` |
| A2 | Real playback: play a named song | Done for YouTube (top result, autoplay). Still planned: a controlled tab so pause/next work on it, and Spotify through its API | Partly done |
| A3 | Shopping helper | Built on A1: search several sites, compare price, add to cart, never pay | Planned |
| A4 | Appointments | Google Calendar invite and booking-site forms through A1; confirm the slot before submitting | Planned |
| A5 | Messaging by voice: "tell Mum I'm late" | `channels.py` has Telegram, Discord, Slack. Needs a contact book and a confirm-before-send | Planned |
| A6 | Phone control | Android companion over the Capacitor shell: open apps, play music, ring the phone, push alerts. iOS is far more limited | Planned |
| A7 | TV control | Android TV / Chromecast / Samsung / LG over the network (`device_controller.py` has IR, Wi-Fi, Bluetooth, MQTT transport only) | Planned. Needs your TV model |
| A8 | Desktop control beyond keystrokes | Window list, focus, click by text on screen (OCR), file search and open | Planned |
| A9 | Food, rides, bills | Only through official APIs or A1 with the same hard stops. Not before A1 is proven | Planned |

## 3. Planned: Jarvis behaviour

| Feature | State |
|---|---|
| Proactive: meeting heads-up | Done (PR #58) |
| Proactive: more triggers (traffic, bills, "you usually…") | Habit nudges done; the rest planned |
| Hologram readability: face no longer washed out; caption in a fixed side box that auto-scrolls; soft lip glow that follows the voice | Done and checked in a real render when idle. **Lip glow position is estimated and not yet seen while speaking** |
| Mood on the hologram: `/api/mood` (tested) tints the figure warm or cool and sets how lively it breathes; refreshed after each reply | Done in code; **colour shift is subtle and was not judged by eye** |
| Webcam as a sense (Settings → "Let Atulya see me"): in-browser motion presence, head turns toward you, "what do you see?" sends one picture to the vision brain; green-framed preview shows it is on | Done; checked in a real browser with a **fake camera** (video plays, no errors). **Not tried with a real camera or a real person**. Eye contact is motion-based, not face detection |
| More senses (hand gestures, face recognition, ambient light, sound events) | Planned |
| Voice ID (who is speaking) | Planned; needs a speaker-embedding model |
| Memory tree view in the web app (menu → Memory tree, or say "show memory"): animated tree, trunk = you, branch per kind, leaf per stored fact, new facts grow in live | **Done**: backend (`/api/memory/graph`, tested) and canvas animation, checked in a real browser with 12 seeded facts. Not yet: relations between people (Alice → Bob), vector-memory leaves |
| Automation dashboard in the web app (jobs, reminders, calendar, media, devices) | Planned |
| Encrypted memory at rest | `encrypted_storage.py` exists, nothing uses it |
| Phone sync and push | Planned |
| Brain speed | **Done**: with a cloud key set, cloud brains lead and the tiny local model is the offline fallback; the router measures each brain and tries the fastest first (pin an order with `ATULYA_BRAIN`). Not done: a smarter local model |
| Real hardware test pass (voice, PC control, camera) | **Needs you**: cannot be done from the cloud container |

## 4. Fixes

| Fix | State |
|---|---|
| README concept images in "How a request flows" and "Memory" (one said "Yantra") | Removed from the README. Files kept in `docs/images/` until real screenshots replace them |
| `docs/images/banner.jpg`, `hologram_ui.jpg` unused | Open: your call whether to delete |
| Email tests depended on leftover `data/` config | Fixed: tests use a temp data dir |
| `test_ambient.py`, `test_senses.py` failed to import without numpy | Fixed: skipped when missing |
| `camera_status` had no test | Fixed |
| Docker image never built | Open |
| Memory tree rebuilt as a big centred window (menu → Memory tree, or "show my memory tree"): trunk = you, 8 branch kinds (personal history, concepts & entities, preferences, episodic memories, skills, self-awareness, cognitive architecture, world knowledge), every golden node a real item; callouts for episodic memories, entity relations, preferences, vectors; tap a branch to open its full list with search; "open episodic memories" works by typed/spoken command | Done and checked in a real browser. **Not pixel-identical to the concept art**: it is far less dense because it only draws what is stored (82 items in the test). World knowledge stays empty until something fills it |
| Action engine dashboard (menu → Action engine, or "show the dashboard"): system status + measured brain speeds, PC automation (real on/off switch), web task flow, smart home hub (simulated unless Home Assistant), calendar & reminders, media player with working buttons; tap a tile or say "open the calendar" to expand | Done and checked in a real browser. Media buttons only work on Windows; home devices are practice devices without Home Assistant; PC control is untested on real hardware |
| Voice/typed "click" inside an open window ("open episodic memories", "open the calendar") | Done for both windows (`web/src/sections.js`); not tried with a real microphone |
| Brain tool calls were never audited (the audit log was only written by the old agent path), so "every action is logged" was false | Fixed in `toolbelt.py`, tested |
| Calendar events were saved but never loaded on restart, so a restart wiped the calendar | Fixed, tested |
| Link more brains: 22 providers in one table (`providers_catalog.py`): Claude, ChatGPT, Gemini, Groq, NVIDIA, OpenRouter, OpenCode Go, Mistral, DeepSeek, Qwen, Grok, Together, Fireworks, Cerebras, SambaNova, Perplexity, Kimi, GLM, SiliconFlow, Hugging Face, GitHub Models, your own server. Menu → Brains & keys: paste key, pick model, Test, Remove; saved to `.env` (owner-only), never shown again | Done and tested, UI checked in a real browser. **Only the generic OpenAI-style class is exercised by tests; no provider was called live.** Default model names can be out of date: change them in the card |
| Camera: detects cameras automatically, 📷 button asks the browser for permission, picker when several, remembers on/off and restarts by itself when already allowed | Done; checked with a fake camera (present, absent). Not tried on real hardware |
| Keys in `.env` were only read by `start.bat` (breaks on quotes, spaces, Notepad BOM) | Fixed: server and CLI read `.env` themselves (`atulya/envfile.py`, tested) and print `Brains ready: ...` at startup |
| "OpenCode" was only the last-resort "No brain loaded" message, so an OpenCode Go key did nothing | Fixed: real `OpenCode Go` brain (`OPENCODE_API_KEY`, default URL `https://opencode.ai/zen/go/v1`). **Not tested against the live service**; model names are defaults you can change with `ATULYA_OPENCODE_MODEL` |
| Webcam would not connect (reason hidden) | Error now says why (insecure address, blocked, busy, none found); falls back to any camera size. Needs your report of which one it is |
| Old sidebar UI appeared when the server was down (offline cache served an old saved copy) | Fixed: cache bumped to v3 (purges old copies); `start.bat` rebuilds on content change and had a duplicate build block removed. Do a hard refresh (Ctrl+Shift+R) once |

## 5. Safety rules for every new action

1. Reading and searching are free; **spending, booking, sending, deleting, posting** ask first, by voice or tap.
2. Never type passwords or card numbers. At a login or payment page, stop and hand over to you.
3. Every step goes to `data/agent/audit.jsonl`.
4. A page's text is data, never instructions (a product page cannot tell Atulya to do anything).
