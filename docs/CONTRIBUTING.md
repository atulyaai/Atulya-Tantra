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
- ❌ Never hardcode identity, personality, or prompts — use `atulya/bhava/persona.py` (optional override: `data/identity.json`)
- ❌ Never add GPU-only dependencies to `pyproject.toml`
- ❌ Never commit model weights to git (use GitHub Releases or HF Hub)
- Never commit `__pycache__/`, `.egg-info/`, or generated `outputs/` artifacts
- ❌ Never break the flat `atulya/` package layout — no `src/` directory

---

## Project Map

This is the current ownership map after the package cleanup.

The repo root intentionally has three product directories: `atulya/`,
`atulya/`, and `web/`. Shared support files live inside the product folder
that owns them.

Allowed root support directories:

- `data/`: runtime-local app state such as generated voice audio, temp uploads, and scheduler state.
- `docs/`: guides, architecture, security, features and images (the one place for documentation).

Do not add new root directories unless they are documented here. New implementation should go into the owning product package.

### Folders

The repo root has three code-and-docs folders (`atulya/`, `web/`, `docs/`), plus `tests/` and one local-data folder.

- `data/`: everything Atulya stores on your machine (memory, accounts, sessions, chat history, audit log, tokens). Git-ignored. Override the agent part with `ATULYA_AGENT_DATA_DIR`.
- `docs/`: guides, architecture, security, features and images (the one place for documentation).
- `web/`: the animated screen. `src/` is the React source (`pages/Orb.jsx` the orb, `pages/Hologram.js` the head, `Panel.jsx` the pop-up shell), `public/` holds static files, `android/` the phone shell. `build.py` builds only when the source changed. `dist/` is generated.
- `atulya/`: all the Python.

### Inside `atulya/`

- `cognition/`: the single pipeline every request goes through: `kernel` (perceive, understand, decide, act, remember, react), `safety` (what needs confirmation), `planner`, `triggers` (event-driven proactivity), `brain` (`ATULYA_BRAIN` tiers). See [COGNITIVE_ARCHITECTURE.md](COGNITIVE_ARCHITECTURE.md).
- `agent/`: assistant tools (reminders, email, calendar, weather, media, tracking, briefing, PC control), the intent router and the audit log.
- `ambient/`: the always-on listener: microphone, wake words (English and Hindi), barge-in, tray icon, autostart.
- `memory/`: memory providers, session search, reflection, vectors, Obsidian export.
- `capabilities/`: browser automation, documents, voice pipeline, Google Workspace, Home Assistant, web search and the creation tools.
- `senses/`: camera and home-sensor adapters.
- `mcp/`: MCP server, client, signed manifests and `servers.json` (all integrations ship disabled).
- `server/`: the FastAPI server (`python -m atulya.sevak`): API routes, accounts, sessions, chat history.
- `channels.py`: Discord, Telegram, Slack, email, webhooks, WhatsApp, Signal, Matrix, Teams, IRC and more.
- `llm.py`, `intelligence.py`, `local_provider.py`: the brain and the provider failover chain.
- `persona.py`, `emotion.py`, `eyes.py`, `heartbeat.py`, `events.py`, `security.py`, `safe_eval.py`, `lockdown.py`, `textutil.py`, `cli.py`.

The NP-DNA research model was removed. Custom model work belongs in a separate repository.

New code goes into the folder above that owns it. Do not add duplicate compatibility packages.

---

## Where Things Go

| Artifact | Location | Git? |
|---|---|---|
| Source code | `atulya/` | ✅ Yes |
| Tests | `tests/` | ✅ Yes |
| Model weights | separate model repo / HF Hub | ❌ Never in git |

---

## How to Add a New Feature

### 1. New Tool or Capability
```
1. Assistant tool: add a function with `@tool(...)` under `atulya/yantra/agent/` and import its module at the bottom of `agent/tools.py`; if it acts on the outside world, add it to `_CONFIRM_TOOLS` in `cognition/safety.py`.
   Heavier capability: add it under `atulya/yantra/capabilities/`.
2. Add tests under tests/
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
2. Build the frontend: `cd web && npm run build`
3. Tag release: `git tag v0.3.1 && git push --tags`
