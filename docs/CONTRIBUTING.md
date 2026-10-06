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
- ❌ Do not rename/move user data or break public imports without a migration plan

---

## Project Map

The repository uses purpose-first English names for source and support directories. Product code stays in `atulya/` and `frontend/`; tests, docs, and examples stay separate.

### Folders

The repository root has `atulya/`, `frontend/`, `docs/`, `tests/`, `examples/`, `.github/`, and runtime-only `kosh/` and `runtime/` directories.

- `kosh/`: everything Atulya stores on your machine (memory, accounts, sessions, chat history, audit log, tokens). Git-ignored. Override the agent part with `ATULYA_AGENT_DATA_DIR`.
- `docs/`: guides, architecture, security, feature status and diagrams.
- `frontend/`: React/Vite UI and Capacitor configuration. `dist/` is generated; `node_modules/` is disposable and restored by the build when needed.
- `tests/`: pytest suites, grouped by subsystem. Tests are intentionally not mixed with application code.
- `examples/`: optional experiments and the Termux companion.
- `runtime/`: downloaded models; never commit model binaries.
- `atulya/`: all the Python.

### Inside `atulya/`

`atulya/` currently has 27 flat modules. Many old module names are Sanskrit/Hindi transliterations; new modules and directories should use clear English names. Rename old modules only with all imports, entry points, docs and compatibility paths updated together. Rules of thumb:

- New assistant tool: a function with `@tool(...)` in the skill module of `atulya/kriya/` that it belongs to.
- New device brand: a JSON profile in `upakaran_profiles.json` (or learn it with the brain); a new connection method goes in `upakaran.py`.
- New API route: in `atulya/dwar/`, next to the routes of the same kind (`routes_auth.py`, `routes_chat.py`, …); shared state and helpers belong in `atulya/dwar/__init__.py`. Anything the tests patch through `atulya.dwar` (config paths, auth helpers) must be read as `_d.<name>` inside a route module, otherwise the patch lands on the package but the route still reads its own copy.
- A new brain provider: a row in the catalogue in `atulya/mastishk/suchi.py`.
- Do not combine unrelated responsibilities just to lower the file count. Split large modules by API, actions, channels, integrations, memory, voice and runtime responsibility.

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
1. Assistant tool: add a function with `@tool(...)` in the matching skill module of `atulya/kriya/` (every module is imported and star-exported by `__init__.py`, so nothing else needs wiring up); if it acts on the outside world, add it to `_CONFIRM_TOOLS` in `buddhi/safety.py`.
   Heavier capability: add it in `atulya/kaushal.py`.
2. Add tests under tests/
3. Run: python -m pytest -q
```

---

## Running Tests

```bash
# All tests (must pass before any commit)
python -m pytest -q

# Quick smoke test
python -m atulya.adesh doctor
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
2. Build the frontend: `cd frontend && npm run build`
3. Tag release: `git tag v0.3.1 && git push --tags`
