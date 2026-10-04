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
- `drishti/` (दृष्टि, sight): the animated screen, all files side by side (`Orb.jsx` the orb, `Hologram.js` the head, `Panel.jsx` the pop-up shell, `index.html`, `vite.config.js`). `build.py` builds only when the source changed. `dist/` is generated. `android_*` are Capacitor files to copy into `android/` after `npx cap add android`.
- `atulya/`: all the Python.

### Inside `atulya/`

`atulya/` is 18 flat files, each named in Sanskrit/Hindi (Latin letters). The full table (file, Devanagari, meaning, what it holds) is in the [README](../README.md#layout). Rules of thumb:

- New assistant tool: a function with `@tool(...)` in `kriya.py`.
- New device brand: a JSON profile in `upakaran_profiles.json` (or learn it with the brain); a new connection method goes in `upakaran.py`.
- New API route: in `dwar.py`, next to the routes of the same kind.
- A new brain provider: a row in the catalogue in `mastishk.py`.
- Keep the layout flat: no sub-folders. If a file grows past a few thousand lines, split it by theme and name the new file in Sanskrit/Hindi, then add it to the README table.

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
1. Assistant tool: add a function with `@tool(...)` in `atulya/kriya.py` (or a themed file) and import its module at the bottom of `atulya/kriya.py`; if it acts on the outside world, add it to `_CONFIRM_TOOLS` in `buddhi/safety.py`.
   Heavier capability: add it in `atulya/kaushal.py`.
2. Add tests under pariksha/
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
2. Build the frontend: `cd drishti && npm run build`
3. Tag release: `git tag v0.3.1 && git push --tags`
