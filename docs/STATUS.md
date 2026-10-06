# Status: where we are

> **This is one half of a pair.** This file says what exists today and how well it is tested.
> **[ROADMAP.md](ROADMAP.md) says what is left and what comes next** — planned work, open fixes,
> and the ranked gap list. Deployment lives in [DEPLOYMENT.md](DEPLOYMENT.md).

**Legend:** **Done** = implemented and has unit tests. **Unverified** = implemented, but never run
on real hardware or accounts (a unit test with mocks does not count). **Planned** = not written yet.
Update this file in every PR.

**Last full test run:** 963 passed, 6 skipped, 0 warnings (local Windows run, 2026-10-06).

---

## Everyday actions (tools in `atulya/actions/` and friends)

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
| Control the PC | `pc_open_app`, `pc_type`, `pc_hotkey`, `pc_screenshot`, plus `files` (list, find, read, copy, move, delete to trash, write, edit, open, print), `clipboard`, `screen` (read by OCR, windows, click, scroll), `run_command`, `install_software`, `check_computer` (all in `computer.py`) | Tested against temp folders and fake permission levels; never run on a real PC, so unverified. Off until `ATULYA_PC_CONTROL=on`; risky actions ask first; files stay in the folders you allow (`ATULYA_ALLOWED_FOLDERS`) |
| Camera, pictures | `analyze_image`, `camera_status` | `camera_status` has no test |

---

## What is proven, and what is only proven in tests

The single most important thing to know about this project: **the test suite is strong and the
hardware coverage is weak.** Everything below is implemented and unit-tested; nothing in this
section has been exercised against a live service or a real device.

**Verified working end to end**

- **HTTPS option** (`ATULYA_HTTPS=on`) — checked against the real server: certificate verified by
  curl on `localhost`, plain http refused. Not tried from a real phone or over a real network
  address. The browser warns once about the certificate, by design.
- **Device fabric** — checked through the real server, spoken sentence → right key presses at a
  simulated Roku, with simulated devices speaking the real protocols over real sockets (Roku,
  Tasmota, WLED, Kodi, Shelly, Home Assistant, fake `adb`, real UDP Wake-on-LAN, SSDP). **Not tried
  with any real hardware.**
- **Money helper and bank alerts** — checked through the real server with real HTTP requests.
  **Not tried with a real bank statement, phone, bank SMS or mailbox.**
- **Dashboard, memory tree, speed panel, camera picker** — checked in a real browser, mostly with a
  fake camera and seeded numbers.
- **Core safety behaviours** — every fix below has a test that fails without the change: single-use
  approvals, hash-chained audit log, one-time device pairing codes, trigger-hijack refusal, SSRF
  protection, no `eval`, bounded inputs.

**Implemented, unverified, and honest about it**

- **Telegram, phone and cloud deployment** have never been checked against live services or real
  hardware. Unit tests use mocks.
- **Profile and identity**: account display names and saved preferences do reach chat answers,
  "who am I?" reads the saved profile, new pairings remember who approved them, an owner can link
  an allowlisted Telegram sender with a one-time code, and episodic recall is scoped per account.
  Legacy device records without an owner stay unlinked; old vector entries without a user scope are
  deliberately not recalled because their owner is unknown. Local accounts use usernames and
  display names — **verified email identity is not implemented.**
- **Async tests in this Windows sandbox** cannot run (asyncio hangs opening its local socket pair);
  the synchronous equivalents pass here, and CI/Linux still needs to confirm them.
- **LLM providers**: only the generic OpenAI-style class is exercised by tests — **no provider has
  been called live**, and default model names can go stale.
- **OpenCode Go** brain is implemented but never tested against the live service.

**Needs you, cannot be done from a container**

- A real hardware test pass: microphone, camera, TV, phone, PC control, Windows media keys.
- The Docker image build (see ROADMAP, fix F1).

Full list of what a real Jarvis has that Atulya does not: **[ROADMAP.md](ROADMAP.md)**.
