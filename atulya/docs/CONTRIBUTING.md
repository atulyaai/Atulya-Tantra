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

## Project Structure

```
Atulya-Tantra/
+-- atulya/            # the brain: cognition, agent tools, ambient listener, memory, LLM routing
+-- yantra/            # hands: capabilities, channels, MCP, senses, device control
+-- drishti/           # face: React frontend + FastAPI dashboard
+-- config/ docs/ install/
+-- tests/             # run by CI on Linux and Windows
+-- pyproject.toml     # package metadata, extras, tool config
+-- start.bat          # Windows launcher
```
(See PROJECT_MAP.md for the full ownership map.)

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
