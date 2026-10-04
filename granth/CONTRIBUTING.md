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
- ❌ Never hardcode identity, personality, or prompts — use `atulya/bhava/persona.py` (optional override: `kosh/identity.json`)
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

The repo root has `atulya/` (all the Python), `drishti/` (the screen, दृष्टि), `granth/` (guides, ग्रंथ), `pariksha/` (tests, परीक्षा) and one local-data folder, `kosh/`, which keeps its English name so existing installs keep their data.

- `kosh/`: everything Atulya stores on your machine (memory, accounts, sessions, chat history, audit log, tokens). Git-ignored. Override the agent part with `ATULYA_AGENT_DATA_DIR`.
- `granth/` (ग्रंथ, text): guides, architecture, security, features and images (the one place for documentation).
- `drishti/` (दृष्टि, sight): the animated screen. `src/` is the React source (`pages/Orb.jsx` the orb, `pages/Hologram.js` the head, `Panel.jsx` the pop-up shell), `public/` holds static files, `android/` the phone shell. `build.py` builds only when the source changed. `dist/` is generated.
- `atulya/`: all the Python.

### Inside `atulya/`

Each folder has a Sanskrit/Hindi name that says what it does:

- `buddhi/` (बुद्धि, intellect): the single pipeline every request goes through: `kernel` (perceive, understand, decide, act, remember, react), `safety` (what needs confirmation), `planner`, `triggers` (event-driven proactivity), `brain` (`ATULYA_BRAIN` tiers), plus `llm`, `intelligence` (the provider failover router), `local_provider` and `providers_catalog`. See [COGNITIVE_ARCHITECTURE.md](COGNITIVE_ARCHITECTURE.md).
- `yantra/` (यंत्र, machine): everything Atulya can do. `agent/`: assistant tools (reminders, email, calendar, weather, media, money, tracking, briefing, web tasks, PC control), the intent router and the audit log. `capabilities/`: browser automation, documents, Google Workspace, Home Assistant, web search and the creation tools. `mcp/`: MCP server, client, signed manifests and `servers.json` (all integrations ship disabled).
- `upakaran/` (उपकरण, devices): the device layer (profiles, ADB, Wake-on-LAN, Home Assistant, discovery, the hub). See [DEVICES.md](DEVICES.md).
- `indriya/` (इन्द्रिय, the senses): camera and home-sensor adapters, and `eyes` (reading pictures).
- `shruti/` (श्रुति, hearing): the always-on listener: microphone, wake words (English and Hindi), barge-in, tray icon, autostart.
- `smriti/` (स्मृति, memory): memory providers, session search, reflection, vectors, summary tree, Obsidian export.
- `vani/` (वाणी, speech): the voice pipeline.
- `sandesh/` (संदेश, message): Discord, Telegram, Slack, email, webhooks, WhatsApp, Signal, Matrix, Teams, IRC and more.
- `sevak/` (सेवक, servant): the FastAPI server (`python -m atulya.sevak`): API routes, accounts, sessions, chat history.
- `raksha/` (रक्षा, protection): `vault` (encryption at rest), `security`, `lockdown`.
- `bhava/` (भाव, feeling): `emotion`, `persona`, `identity`.
- Shared at the top: `cli`, `config`, `envfile`, `events`, `heartbeat`, `production_readiness`, `safe_eval`, `textutil`.

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
1. Assistant tool: add a function with `@tool(...)` under `atulya/yantra/agent/` and import its module at the bottom of `yantra/agent/tools.py`; if it acts on the outside world, add it to `_CONFIRM_TOOLS` in `buddhi/safety.py`.
   Heavier capability: add it under `atulya/yantra/capabilities/`.
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
