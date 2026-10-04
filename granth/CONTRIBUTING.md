# Contributing to Atulya Tantra

> **This document is the single source of truth for anyone (human or AI agent) working on this project.**
> Read this FIRST before touching any code.

---

## Hard Rules (NON-NEGOTIABLE)

### DO
- ✅ Run `python -m pytest -q` and `ruff check .` before every commit
- ✅ Keep all code CPU-first — GPU is optional, never required
- ✅ Use type hints on every function signature
- ✅ Add docstrings to every public class and function
- ✅ Keep dependencies minimal; heavy features go behind optional extras
- ✅ Preserve existing comments and docstrings when editing
- ✅ Use `logging` module — never `print()` in library code
- Update the owning module's tests when adding new features

### DON'T
- ❌ Never hardcode identity, personality, or prompts — use `atulya/bhava.py` (optional override: `kosh/identity.json`)
- ❌ Never add GPU-only dependencies to `pyproject.toml`
- ❌ Never commit model weights to git (use GitHub Releases or HF Hub)
- Never commit `__pycache__/`, `.egg-info/`, or generated `outputs/` artifacts
- ❌ Never break the flat `atulya/` package layout — no `src/` directory

---

## Project Map

This is the current ownership map after the package cleanup.

The repo root intentionally has two product directories: `atulya/` (the Python) and `drishti/` (the screen). Shared support files live inside the product folder
that owns them.

Allowed root support directories:

- `kosh/`: runtime-local app state such as generated voice audio, temp uploads, and scheduler state.
- `granth/` (ग्रंथ, text): guides, architecture, security, features and images (the one place for documentation).

Do not add new root directories unless they are documented here. New implementation should go into the owning product package.

### Folders

The repo root has `atulya/` (all the Python), `drishti/` (the screen, दृष्टि), `granth/` (guides, ग्रंथ), `pariksha/` (tests, परीक्षा) `prayog/` (experiments) and one local-data folder, `kosh/` (an old `data/` folder is moved there automatically).

- `kosh/`: everything Atulya stores on your machine (memory, accounts, sessions, chat history, audit log, tokens). Git-ignored. Override the agent part with `ATULYA_AGENT_DATA_DIR`.
- `granth/` (ग्रंथ, text): guides, architecture, security, features and images (the one place for documentation).
- `drishti/` (दृष्टि, sight): the animated screen. `src/` is the React source (`Orb.jsx` the orb, `Hologram.js` the head, `Panel.jsx` the pop-up shell), `public/` holds static files, `android/` the phone shell. `build.py` builds only when the source changed. `dist/` is generated.
- `atulya/`: all the Python.

### Inside `atulya/`

Flat on purpose: one file per part where it fits, and a folder only where Python needs one to run it (`python -m atulya.sevak`, `python -m atulya.shruti`) or where a part is large. Every name is Sanskrit/Hindi:

- `buddhi/` (बुद्धि, intellect), a folder of flat files: the single pipeline every request goes through: `kernel` (perceive, understand, decide, act, remember, react), `safety` (what needs confirmation), `planner`, `triggers` (event-driven proactivity), `brain` (`ATULYA_BRAIN` tiers), plus `llm`, `intelligence` (the provider failover router), `local_provider` and `providers_catalog`. See [COGNITIVE_ARCHITECTURE.md](COGNITIVE_ARCHITECTURE.md).
- `yantra/` (यंत्र, machine), a folder of flat files: everything Atulya can do. Assistant tools in `tools.py` (plus `media`, `money`, `tracking`, `briefing`, `pc_control`, `webagent`, `devices_tools`, `calendar_watch`), the intent router and `audit`; heavier capabilities in `capabilities.py`, `browser_automation`, `document_engine`, `google_workspace`, `home_assistant`, `web_search` and friends; `mcp.py` (MCP server, client, signed manifests) with `mcp_servers.json` (all integrations ship disabled).
- `sevak/` (सेवक, servant), a folder: the FastAPI server (`python -m atulya.sevak`). The API is four files, `api_account.py` (sign-in, users, brains and keys, vault, system), `api_chat.py` (chat, voice, websocket, OpenAI-style endpoint), `api_agent.py` (automation, routines, triggers, uploads, creations) and `api_home.py` (dashboard, devices, senses, money, memory, mood, Google, notifications), plus `app.py`, `users.py`, `state.py`, `chat_history.py`.
- `shruti/` (श्रुति, hearing), a folder: the always-on listener: microphone, wake words (English and Hindi), barge-in, tray icon, autostart.
- Single files: `upakaran.py` (devices: base, ADB, Wake-on-LAN, Samsung, Home Assistant, profiles) with `upakaran_hub.py` (hub, discovery, learn-a-device) and `upakaran_profiles.json` (built-in device profiles; see [DEVICES.md](DEVICES.md)); `indriya.py` (senses: camera, home sensors, reading pictures); `smriti.py` (memory); `vani.py` (voice pipeline); `sandesh.py` (Discord, Telegram, Slack, email, webhooks and more); `raksha.py` (protection: vault, security, lockdown, https certificates); `bhava.py` (emotion, persona, identity).
- Shared at the top: `cli`, `config`, `envfile`, `events`, `heartbeat`, `kosh`, `production_readiness`, `safe_eval`, `textutil`.

The NP-DNA research model was removed. Custom model work belongs in a separate repository.

New code goes into the folder above that owns it. Do not add duplicate compatibility packages.

---

## Where Things Go

| Artifact | Location | Git? |
|---|---|---|
| Source code | `atulya/` | ✅ Yes |
| Tests | `pariksha/` | ✅ Yes |
| Model weights | separate model repo / HF Hub | ❌ Never in git |

---

## How to Add a New Feature

### 1. New Tool or Capability
```
1. Assistant tool: add a function with `@tool(...)` under `atulya/yantra/` and import its module at the bottom of `yantra/tools.py`; if it acts on the outside world, add it to `_CONFIRM_TOOLS` in `buddhi/safety.py`.
   Heavier capability: add it in `atulya/yantra/capabilities.py`.
2. Add tests under pariksha/
3. Run: python -m pytest -q
```

---

## Running Tests

```bash
# All tests (must pass before any commit)
python -m pytest -q

# Quick smoke test
python -m atulya.cli doctor
```

---

## Commit Message Format

```
type: brief description

- Detail 1
- Detail 2
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`

---

## Release Process

1. Run all tests: `python -m pytest -q`
2. Build the frontend: `cd drishti && npm run build`
3. Tag release: `git tag v0.3.1 && git push --tags`
