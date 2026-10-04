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
| A6 | Phone control | Android over ADB (keys, volume, open app by name, open link, battery, screenshot); anything else through Home Assistant. Ringing a phone and push alerts need a companion app. iPhone: very limited | **Built for Android** (see device fabric below); not tried on a real phone. iPhone not covered |
| A7 | TV control | Roku, Kodi, Android/Fire TV (ADB), Wake-on-LAN, and Samsung/LG/others via Home Assistant (see device fabric below) | **Built**; not tried on a real TV. Samsung/LG direct, Chromecast and AirPlay are not coveredr TV model |
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
| Ambient light: the webcam measures room brightness and the hologram eases its glow in a dark room | Done; checked that the camera still runs with it, **the glow change itself was not judged by eye** |
| Hand gestures, face recognition, sound events (claps, doorbell, glass) | **Not built.** Gestures and faces need a downloaded vision model (about 10 MB) and sound classes need an audio model; neither could be tested here, so I did not ship guesses |
| Voice ID (who is speaking) | **Not built**: needs a speaker-embedding model and real voices to test. Even when built it should only personalise, never unlock anything |
| Memory tree view in the web app (menu → Memory tree, or say "show memory"): animated tree, trunk = you, branch per kind, leaf per stored fact, new facts grow in live | **Done**: backend (`/api/memory/graph`, tested) and canvas animation, checked in a real browser with 12 seeded facts. Not yet: relations between people (Alice → Bob), vector-memory leaves |
| Automation dashboard in the web app (jobs, reminders, calendar, media, devices) | Planned |
| Encrypted memory at rest (`atulya/vault.py`): set `ATULYA_VAULT_PASSPHRASE` in `.env`; money, calendar, reminders, email settings, chat history and your profile are then stored encrypted (scrypt key, Fernet). Tamper is detected; a wrong passphrase locks the data and can never overwrite it; with no passphrase it says plainly that it is off. Status in the dashboard (System tile) | Done, 7 tests. **Lose the passphrase and the data is gone.** Not covered: the vector memory, the audit log, `.env` itself, and anyone who can read your running PC's memory. The old `encrypted_storage.py` is not used (it fell back to base64 and kept its key beside the data) |
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
| **Device fabric** (`atulya/devices/`, guide in `docs/DEVICES.md`): one layer for any controllable device. Four connection methods (JSON profiles over HTTP, ADB for Android/Fire TV, Wake-on-LAN, Home Assistant for thousands of brands); network discovery (port + profile probing, SSDP, ADB, Home Assistant); a hub that stores devices and understands speech from each device's own abilities, with no brand list in code; tools for the brain (`device_do`, `device_list`, `device_discover`, `device_add`, `device_learn` …); "learn this device" drafts a profile with the brain and you approve it; dashboard panel with Scan, Add and per-device buttons; confirm-first for risky actions; LAN-only and URL-encoding safety | Done, 52 tests including **simulated devices speaking the real protocols over real sockets** (Roku, Tasmota, WLED, Kodi, Shelly, Home Assistant, a fake `adb`, a real UDP Wake-on-LAN receiver, SSDP). Checked end to end through the real server: spoken sentence -> right key presses at a simulated Roku. **Not tried with any real hardware.** Built-in profiles come from public protocol descriptions and may need fixes on real devices |
| "If not sure, check with AI" for bank messages: rules read clear messages; a message that mentions money but does not parse is sent to your brain (account numbers, phones, emails, links removed first; never for OTPs, offers or due reminders). The AI's answer is only accepted if the amount really appears in the message; AI-read entries are marked and the reply says "please check". `ATULYA_MONEY_AI=off` turns it off | Done, 4 tests with a fake brain. **Not tried with a real brain.** Note: it sends redacted message text to whichever brain answers, which may be a cloud company |
| **Money helper** (`atulya/agent/money.py`): "I spent 500 on groceries", "how much did I spend this month / on food / last month", budgets with left/over notes, monthly bills with a heads-up 3 days before ("bill.due"), "I paid the electricity bill", bank-statement CSV import (debits only, duplicates skipped, "undo the import"), Money tile in the dashboard. Local file only (`data/agent/money.json`); never connects to a bank and never pays | Done, 14 tests, and checked through the real server with the phrases above. **Not tried with a real bank statement**: column names are matched for common Indian-bank exports (Date / Narration / Withdrawal / Deposit, or Date / Description / Amount) and may need adding for yours. Currency is ₹ (change with `ATULYA_CURRENCY`) |
| **Bank alerts from SMS and email**: `POST /api/money/sms` (a phone's SMS-forwarding app sends each bank SMS; its own key opens nothing else), "check my email for bank transactions" (Gmail or IMAP), paste-in tool, OTP/offer/due messages ignored, same transaction by SMS and email counted once, credits shown as money in. Setup card: Action engine → Money → Link my phone | Done, 19 tests, and exercised by posting real HTTP requests to the running server. **Not tried with a real phone, real bank SMS or a real mailbox.** The sample alert wordings in the tests are my own approximations of common Indian-bank messages; banks differ, so check totals in the first week. IMAP reading is untested live. Phone must reach the PC (same Wi-Fi with `ATULYA_HOST=0.0.0.0`, or Tailscale) |
| Any tool with a parameter named `name` crashed ("multiple values for argument 'name'") | Fixed in `ToolRegistry.execute`, tested |
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
