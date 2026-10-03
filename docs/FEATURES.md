# Features: what Atulya has, and what is missing

Status is from the code and unit tests. Anything marked "untested live" has not been tried on real audio, hardware or accounts.

## Have it

| Area | Feature | Where |
|---|---|---|
| Face | Hologram head (lip sync, blink, breathing), orb home screen, Talk and Chat pages, knowledge map | `drishti/frontend/` |
| Voice in | Always-on listener, wake words in English and Hindi, "stop" interrupts speech, optional wake-word model | `atulya/ambient/` |
| Voice out | Edge neural voices (online), system voice (offline), Piper (offline, optional) | `atulya/ambient/audio.py`, `yantra/capabilities/voice_pipeline.py` |
| Brain | Local Qwen3 0.6B / 1.7B / 4B, `ATULYA_BRAIN=auto`, cloud failover (Groq, OpenRouter, Gemini, OpenAI) | `atulya/cognition/brain.py`, `atulya/intelligence.py` |
| Memory | Memory tree, reflection, vectors, Obsidian export; recalled only when you ask about the past (tiny brain) | `atulya/memory/` |
| Safety | Risky actions ask first; audit log of every tool call; lockdown profile | `atulya/cognition/safety.py`, `atulya/agent/audit.py`, `atulya/lockdown.py` |
| Assistant tools | Reminders, calendar, email, weather, open websites, calculator, time | `atulya/agent/tools.py` |
| Media | Play music (YouTube/Spotify search), media keys and volume (Windows) | `atulya/agent/media.py` |
| Tracking | Price watchlist for public web pages | `atulya/agent/tracking.py` |
| Briefing | Morning briefing, spoken daily at `ATULYA_BRIEFING_AT` | `atulya/agent/briefing.py`, `atulya/ambient/listener.py` |
| PC control | Open apps, type, shortcuts, screenshot; off unless enabled, always asks | `atulya/agent/pc_control.py` |
| Senses | Camera motion and person detection, OCR, scene description via Ollama (moondream) | `yantra/senses/`, `atulya/eyes.py` |
| Home | Home Assistant and MQTT bridges (untested live) | `yantra/capabilities/home_assistant.py` |
| Channels | Telegram, Discord, Slack, email, webhooks and more (untested live) | `yantra/channels.py` |
| Other | Google Workspace, browser automation, documents, MCP server and client | `yantra/capabilities/`, `yantra/mcp/` |
| Local sign-in | No login on the computer Atulya runs on; other devices log in | `drishti/dashboard/routes/auth.py` |

## Missing or incomplete

| Gap | Notes |
|---|---|
| Voice and PC control on real hardware | Only unit-tested; try `atulya listen` and `ATULYA_PC_CONTROL=on` and report what breaks |
| Microphone in the web app | Browsers block the mic until you click once and allow it; the Claude browser pane blocks it entirely, so use Chrome or Edge |
| Trained "Atulya" wake-word model | openWakeWord ships none; the text-matched wake word is the default |
| Encrypted memory at rest | `yantra/capabilities/encrypted_storage.py` exists but nothing uses it yet |
| Voice ID (who is speaking) | Not started |
| Mood colours and eye contact on the hologram | Not started; mood detection exists in `atulya/emotion.py` |
| Phone sync and push | PWA and a Capacitor shell exist; no cross-device sync |
| Scene description by default | Needs `ollama pull moondream` or a Gemini key |
| A smarter brain | The 0.6B model is weak at jokes and reasoning; use `balanced`, `power` or `cloud` |
| Real music playback control | Opens a search in the browser; no player integration beyond media keys |
| Docker | The Dockerfile was fixed but has not been built |
