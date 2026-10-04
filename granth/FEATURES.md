# Features: what Atulya has, and what is missing

Status is from the code and unit tests. Anything marked "untested live" has not been tried on real audio, hardware or accounts.

## Have it

| Area | Feature | Where |
|---|---|---|
| Face | One animated screen: hologram head (lip sync, blink, breathing), caption card, suggestion chips. Chat history, About you, Routines, Senses, Reflexes and Users open as pop-ups, by voice or the menu | `drishti/src/` |
| Voice in | Always-on listener, wake words in English and Hindi, "stop" interrupts speech, optional wake-word model | `atulya/shruti.py` |
| Voice out | Edge neural voices (online), system voice (offline), Piper (offline, optional) | `atulya/shruti.py`, `atulya/vani.py` |
| Brain | Local Qwen3 0.6B / 1.7B / 4B, `ATULYA_BRAIN=auto`, cloud failover (Groq, OpenRouter, Gemini, OpenAI) | `atulya/mastishk.py`, `atulya/mastishk.py` |
| Memory | Memory tree, reflection, vectors, Obsidian export; recalled only when you ask about the past (tiny brain) | `atulya/smriti/` |
| Safety | Risky actions ask first; audit log of every tool call; lockdown profile | `atulya/mastishk.py`, `atulya/kriya.py`, `atulya/raksha.py` |
| Assistant tools | Reminders, calendar, email, weather, open websites, calculator, time | `atulya/kriya.py` |
| Media | Play music (YouTube/Spotify search), media keys and volume (Windows) | `atulya/kriya.py` |
| Tracking | Price watchlist for public web pages | `atulya/kriya.py` |
| Briefing | Morning briefing, spoken daily at `ATULYA_BRIEFING_AT` | `atulya/kriya.py`, `atulya/shruti.py` |
| PC control | Open apps, type, shortcuts, screenshot; off unless enabled, always asks | `atulya/kriya.py` |
| Senses | Camera motion and person detection, OCR, scene description via Ollama (moondream) | `atulya/indriya/`, `atulya/indriya.py` |
| Home | Home Assistant and MQTT bridges (untested live) | `atulya/upakaran.py` |
| Channels | Telegram, Discord, Slack, email, webhooks and more (untested live) | `atulya/sandesh.py` |
| Other | Google Workspace, browser automation, documents, MCP server and client | `atulya/kaushal.py`, `atulya/setu.py` |
| Local sign-in | No login on the computer Atulya runs on; other devices log in | `atulya/dwar.py` |

## Missing or incomplete

| Gap | Notes |
|---|---|
| Voice and PC control on real hardware | Only unit-tested; try `atulya listen` and `ATULYA_PC_CONTROL=on` and report what breaks |
| Microphone in the web app | Browsers block the mic until you click once and allow it; the Claude browser pane blocks it entirely, so use Chrome or Edge |
| Trained "Atulya" wake-word model | openWakeWord ships none; the text-matched wake word is the default |
| Encrypted memory at rest | Optional: set `ATULYA_VAULT_PASSPHRASE` (see `atulya/raksha.py`). Not covered: vector memory, the audit log and `.env` |
| Voice ID (who is speaking) | Not started |
| Mood colours and eye contact on the hologram | Not started; mood detection exists in `atulya/bhava.py` |
| Phone sync and push | PWA and a Capacitor shell exist; no cross-device sync |
| Scene description by default | Needs `ollama pull moondream` or a Gemini key |
| A smarter brain | The 0.6B model is weak at jokes and reasoning; use `balanced`, `power` or `cloud` |
| Real music playback control | Opens a search in the browser; no player integration beyond media keys |
| Docker | The Dockerfile was fixed but has not been built |

## Next for the interface

- Keep route handlers thin: put logic in `atulya/` (cognition kernel and agent tools), not in `atulya/dwar_*.py`.
- Stream event-bus updates from `atulya.adhar` to the frontend over WebSocket.
- Add a compact system-health strip backed by heartbeat model, provider (circuit-breaker-aware), disk, and memory checks (provider check is done, need disk/memory in the web app).
- Show the audit log (`kosh/agent/audit.jsonl`) and PC-control status in the UI.
- Offer a one-click "lockdown" profile (localhost only, no wildcard CORS).
