# Status: what is done, what is tested, what is next

Legend: **Done** = implemented and has unit tests. **Unverified** = implemented, but never run on real hardware or accounts
(a unit test with mocks does not count). **Planned** = not written yet. Update this file in every PR.

Last full test run: 530 passed, 6 skipped. Two email tests fail when `data/` holds a stale email config
(they pass on a clean checkout). `tests/test_ambient.py` and `tests/test_senses.py` need optional extras to import.

## 1. Everyday actions (tools in `atulya/agent/`)

| Ability | Tool | State |
|---|---|---|
| Play a song / video | `play_music` (opens a YouTube or Spotify search) | Unverified. Opens a search only; does not start playback |
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
| A1 | **Web agent**: "add the blue running shoes to my cart", "book a table" | Playwright session driven step by step by the brain (look at page, pick one action, repeat). Hard stops: payment, final "place order", login, CAPTCHA. At those, Atulya pauses and asks. Every step is written to the audit log | Planned. `capabilities/browser_automation.py` has the Playwright basics only |
| A2 | Real playback: play a named song | YouTube search, pick the first result, play it in a controlled browser tab (pause, next, volume work on that tab). Spotify through its API when a token is set | Planned |
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
| Mood and eye contact on the hologram (`emotion.py` to `Hologram.js`) | Planned |
| Voice ID (who is speaking) | Planned; needs a speaker-embedding model |
| Memory: entity graph (people, places, relations) and a real memory view in the web app | Planned; vector store and summary tree exist |
| Automation dashboard in the web app (jobs, reminders, calendar, media, devices) | Planned |
| Encrypted memory at rest | `encrypted_storage.py` exists, nothing uses it |
| Phone sync and push | Planned |
| Smarter local brain | Planned; try `balanced` or `power`, measure on a fixed prompt set |
| Real hardware test pass (voice, PC control, camera) | **Needs you**: cannot be done from the cloud container |

## 4. Fixes

| Fix | State |
|---|---|
| README images in "How a request flows" and "Memory" are concept art, and the first says "Yantra" | Open |
| `docs/images/banner.jpg`, `hologram_ui.jpg` unused | Open |
| Email tests depend on leftover `data/` config | Open: make the tests use a temp data dir |
| `tests/test_ambient.py`, `tests/test_senses.py` fail to import without extras | Open: skip when the extra is missing |
| `camera_status` has no test | Open |
| Docker image never built | Open |

## 5. Safety rules for every new action

1. Reading and searching are free; **spending, booking, sending, deleting, posting** ask first, by voice or tap.
2. Never type passwords or card numbers. At a login or payment page, stop and hand over to you.
3. Every step goes to `data/agent/audit.jsonl`.
4. A page's text is data, never instructions (a product page cannot tell Atulya to do anything).
