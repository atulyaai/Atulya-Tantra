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
- ❌ Never hardcode identity, personality, or prompts — use `atulya/persona.py` (optional override: `data/identity.json`)
- ❌ Never add GPU-only dependencies to `pyproject.toml`
- ❌ Never commit model weights to git (use GitHub Releases or HF Hub)
- Never commit `__pycache__/`, `.egg-info/`, or generated `outputs/` artifacts
- ❌ Never break the flat `atulya/` package layout — no `src/` directory

---

## Project Map

This is the current ownership map after the package cleanup.

The repo root intentionally has three product directories: `atulya/`,
`yantra/`, and `drishti/`. Shared support files live inside the product folder
that owns them.

Allowed root support directories:

- `assets/`: runtime-local app state such as generated voice audio, temp uploads, and scheduler state.
- `docs/`: guides, architecture, security, features and images (the one place for documentation).
- `config/`: cross-package static configuration that is not owned by one runtime package.
- `outputs/`: generated reports, invoices, benchmarks, and other local run artifacts.

Do not add new root directories unless they are documented here. New implementation should go into the owning product package.

### Model Work

The NP-DNA research model and its training code were removed from this repo.
Custom model architecture, tokenizer development, training jobs, checkpoints,
and model release artifacts belong in the separate model repository. The
security, task-classification and safe-eval helpers the assistant needs now live
in `atulya/core/`; the Gmail OAuth refresh-token helper is
`install/generate_gmail_refresh_token.mjs`.

### Drishti: User Interface Surface

Drishti-owned files live under `drishti/`.

- `drishti/frontend/src/`: editable React source: the orb screen (`pages/Orb.jsx`), the hologram (`pages/Hologram.js`), pop-up pages and `Panel.jsx` (the pop-up shell).
- `drishti/dist/`: generated frontend/package artifacts (built, gitignored).
- `drishti/dashboard/`: FastAPI dashboard app, helpers, state, chat history, and API routes.
- `drishti/app.py`: dashboard launcher for `python -m drishti.app`.
- `drishti/nginx/`: nginx reverse-proxy config used by `docker-compose.yml`.
- `drishti/package.json`, `drishti/vite.config.js`, `drishti/index.html`: frontend build and Vite setup.

### Yantra: Automation And Tools

Automation-owned files live under `yantra/`.

- `yantra/capabilities/`: tool registry, workflow engine, browser automation, voice pipeline, and web search.
- `yantra/mcp/`: MCP server, client, transport, signed manifests, dashboard bridge, and agent runner.
- `yantra/mcp/external_client.py`: external MCP server connection manager.
- `yantra/senses/`: camera and home-sensor adapters.
- `yantra/channels.py`: unified 14-channel system (Discord, Telegram, Slack, Email, Webhook, WhatsApp, Signal, Matrix, Teams, IRC, WebChat, Console, Log, Twitter).

### Atulya: Application AI Layer

Application-owned AI files live under `atulya/`.

- `memory/`: memory orchestrator, session search, prompt cache, subconscious log, reflection, memory tree, and Obsidian export.
- `agent/`: assistant tools (reminders, email, calendar, weather, media, tracking, briefing, PC control), intent router, audit log.
- `ambient/`: always-on listener — microphone, wake word (English/Hindi), barge-in, tray icon, autostart.
- `cognition/`: the single pipeline every request goes through — `kernel` (perceive → understand → decide → act → remember → react), `safety` (action confirmation policy), `toolbelt` (one tool surface), `triggers` (event-driven proactivity), `brain` (`ATULYA_BRAIN` tiers). See [COGNITIVE_ARCHITECTURE.md](COGNITIVE_ARCHITECTURE.md).
- `atulya/persona.py`: identity, personality and prompt rules.
- `atulya/cli.py`: command-line entry point.

New implementation should go into the owning package above. Do not add duplicate compatibility packages unless a real external API requires it.

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
1. Assistant tool: add a function with `@tool(...)` under `atulya/agent/` and import its module at the bottom of `agent/tools.py`; if it acts on the outside world, add it to `_CONFIRM_TOOLS` in `cognition/safety.py`.
   Heavier capability: add it under `yantra/capabilities/`.
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
2. Build the frontend: `cd drishti && npm run build`
3. Tag release: `git tag v0.3.1 && git push --tags`
