# Atulya-Tantra — working rules for AI assistants

## Goal
Make Atulya a Jarvis that works in daily use: short replies, voice-first, proactive, multi-channel, and safe.

## How to work
- Prefer measured improvements over new untested features.
- Verify on the live server before calling something done.
- Push back if a better approach exists.

## Where it runs
- Production: https://atulya.atulvij.com (ubuntu@137.23.42.211, `/home/ubuntu/Atulya-Tantra`, `atulya.service` on :8501).
- Secrets in `data/secrets.enc` and `.env`. Never commit them.
- Laptop is for development; GitHub Actions deploys after clean tests.

## Do not touch without asking
- `webui/renderer.js`, `webui/scene/**` — owner’s hologram scene. Add features around them.

## Safety
- Side-effecting tools use `confirm=True` and the approval queue.
- Logs are redacted.

## Current status (2026-10-13)
- 40 tools loaded. Voice, routines, Gmail/Calendar (after re-auth), free multimodal vision, gesture model present.
- Persona is short Jarvis style. Morning briefing ~40 words. Calendar reminder routine added.
- Telegram allowlist merges into admin account.

## Open
See `docs/TODO.md`. Highest: always-on wake word, laptop agent running, stronger cross-session memory, WebUI polish.
