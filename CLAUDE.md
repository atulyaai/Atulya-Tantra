# Atulya-Tantra — working rules for AI assistants

## Goal
Make Atulya a Jarvis that **actually works in daily use**: automated, fast, low-resource, tested for real
(real server, real model calls, real audio files, real OS actions) — not only unit tests with fakes.
Move toward more autonomy (planning, multi-step tools, proactive briefings) without losing safety.

## How to work
- Push back. If a better/faster approach exists, say so and argue for it; do not just agree.
- Verify for real before calling something done; say plainly what was only unit-tested.
- Prefer measured improvements (latency, RAM/CPU, accuracy) over new untested features.

## Do not touch without asking
- `webui/renderer.js`, `webui/scene/**` — the owner's scene and animations. Never rebuild or replace them.
  Add features around them (`assistant.js`, `renderer.css`, `index.html`). Image upscales go next to
  the originals for comparison, never over them.

## Safety invariants
- Anything that changes the computer or sends outside goes through the approval queue (`confirm=True` in
  `tools/plugins/toolkit.py`).
- Secrets live only in `.env` / `data/`; logs are redacted (`atulya/logging_setup.py`). Never commit them.

## Checks
```
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m ruff check .
node --check webui/assistant.js
.venv/Scripts/python -m atulya.cli selftest   # real end-to-end checks against this machine
```

## Open goals (see docs/TODO.md for detail)
1. Real daily use: sign in, voice, approvals, Telegram — fix what breaks.
2. Wake word via a small always-on model (openWakeWord), Whisper fallback.
3. One-command public access at atulya.atulvij.com (Cloudflare Tunnel) with strong auth.
4. Lowest resource profile that still works; measured peak/idle.
5. Agentic automation: multi-step plans, scheduled routines, proactive notices.
