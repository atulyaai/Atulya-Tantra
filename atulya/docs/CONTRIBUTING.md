# Contributing to Atulya Tantra

> **This document is the single source of truth for anyone (human or AI agent) working on this project.**
> Read this FIRST before touching any code.

---

## Hard Rules (NON-NEGOTIABLE)

### DO
- Run `python -m pytest -q` before every commit
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
- ❌ Never add `data/seed_dataset.jsonl` to git — it's auto-generated
- ❌ Never import from `_archive/` — those are dead legacy repos

---

## Project Structure

```
Atulya-Tantra/
+-- assets/                        # runtime-local app state (audio, temp files, scheduler state)
+-- atulya/                        # Application AI: persona, memory, routing, local model glue
�   +-- memory/                    # memory providers, tree, reflection, Obsidian export, vector store
�   +-- agent/                     # proactive assistant agent loop and scheduled jobs
�   +-- observability/             # usage, metrics, traces, errors
�   +-- docs/                      # architecture, contribution, security, project map
�   +-- persona.py                 # unified identity + personality
�   +-- llm.py                     # AtulyaLLM, memory-enabled default, tool-call pass-through, streaming
�   +-- local_provider.py          # local GGUF chat/stream/tool-call normalization
�   +-- tantra_local.py            # persona wrapper around the local GGUF model
�   +-- intelligence.py            # ProviderRouter and provider wrappers
�   +-- heartbeat.py               # model/provider/Cortex/disk/memory health checks
�   +-- production_readiness.py    # readiness checks
�   +-- cli.py                     # CLI entry point
+-- config/                        # cross-package static configuration
+-- docs/                          # deployment, API reference
+-- drishti/                       # React dashboard + FastAPI backend
�   +-- frontend/src/              # editable React source
�   +-- dashboard/                 # FastAPI app, helpers, state, routes
�   +-- nginx/                     # reverse-proxy config for docker deployment
�   +-- dist/                      # built frontend assets (gitignored)
�   +-- app.py                     # backend entrypoint
�   +-- package.json
�   +-- vite.config.js
+-- tests/                         # root test suite
+-- yantra/                        # Automation and tools
�   +-- capabilities/              # canonical tools: exec, workflow, browser, voice, web search
�   +-- channels.py                # unified 14-channel communication system
�   +-- mcp/                       # MCP server, client, transport, manifests
�   +-- events.py                  # async event bus
�   +-- device_controller.py       # CPU-first device management
+-- pyproject.toml                 # package metadata, extras, tool config
+-- start.bat                      # Windows launcher
```

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
1. Add it under yantra/capabilities/ and register it with the harness
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
