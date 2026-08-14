# Contributing to Atulya Tantra

> **This document is the single source of truth for anyone (human or AI agent) working on this project.**
> Read this FIRST before touching any code.

---

## Hard Rules (NON-NEGOTIABLE)

### DO
- Run `python -m pytest atulya/tests tantra/tests yantra/tests drishti/tests -v` before every commit
- ✅ Keep all code CPU-first — GPU is optional, never required
- ✅ Use type hints on every function signature
- ✅ Add docstrings to every public class and function
- ✅ Keep dependencies minimal (torch, numpy, psutil only for core)
- ✅ Preserve existing comments and docstrings when editing
- ✅ Use `logging` module — never `print()` in library code
- ✅ Test Hindi/Sanskrit whenever touching the tokenizer
- Update the owning module's tests when adding new features

### DON'T
- ❌ Never hardcode identity, personality, or prompts — use `tantra/training/datasets/identity.json`
- ❌ Never add GPU-only dependencies to `pyproject.toml`
- ❌ Never commit model weights to git (use GitHub Releases or HF Hub)
- Never commit `__pycache__/`, `.egg-info/`, or generated `tantra/outputs/` artifacts
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
�   +-- tokenjuice/                # token accounting helpers
�   +-- docs/                      # architecture, contribution, security, project map
�   +-- persona.py                 # unified identity + personality
�   +-- soul.py                    # SOULSystem compatibility wrapper
�   +-- llm.py                     # AtulyaLLM, memory-enabled default, tool-call pass-through, streaming
�   +-- local_provider.py          # local GGUF chat/stream/tool-call normalization
�   +-- tantra_local.py            # built-in Tantra local model glue
�   +-- intelligence.py            # ProviderRouter and provider wrappers
�   +-- heartbeat.py               # model/provider/Cortex/disk/memory health checks
�   +-- production_readiness.py    # readiness checks
�   +-- cli.py                     # CLI entry point
+-- config/                        # cross-package static configuration
+-- docs/                          # deployment, API reference, implementation plan
+-- drishti/                       # React dashboard + FastAPI backend
�   +-- frontend/src/              # editable React source
�   +-- dashboard/                 # FastAPI app, helpers, state, routes
�   +-- nginx/                     # reverse-proxy config for docker deployment
�   +-- dist/                      # built frontend assets (gitignored)
�   +-- app.py                     # backend entrypoint
�   +-- package.json
�   +-- vite.config.js
+-- tantra/                        # Support layer
�   +-- npdna/                     # legacy/reference NP-DNA compatibility code
�   +-- core/                      # security, context, encryption, model failover
�   +-- training/                  # legacy/reference dataset and training utilities
�   +-- scripts/                   # support and compatibility utilities
�   +-- outputs/                   # generated local artifacts (gitignored)
+-- tests/                         # root test suite
+-- yantra/                        # Automation and tools
�   +-- capabilities/              # canonical tools: exec, workflow, browser, voice, web search
�   +-- harness.py                 # agents, skills, slash commands, safety
�   +-- channels.py                # unified 14-channel communication system
�   +-- mcp/                       # MCP server, client, transport, manifests
�   +-- assistant/                 # task brain, cron scheduler, source ingestion
�   +-- kgraph/                    # knowledge-graph store
�   +-- orchestrator/              # agent orchestration
�   +-- selfimprovement/           # unified self-improvement (bridge merged)
�   +-- selfrepair.py              # automated error recovery
�   +-- dispatch.py                # classifier + failover + tools dispatch
�   +-- events.py                  # async event bus
�   +-- device_controller.py       # CPU-first device management
�   +-- notify/                    # notification facade
�   +-- plugins/                   # plugin SDK with trust levels
+-- pyproject.toml                 # package metadata, extras, tool config
+-- start.bat                      # Windows launcher
```

---

## Where Things Go

| Artifact | Location | Git? |
|---|---|---|
| Source code | `atulya/` | ✅ Yes |
| Training scripts | `training/` | ✅ Yes |
| Tests | `tests/` | ✅ Yes |
| Identity config | `tantra/training/datasets/identity.json` | ✅ Yes |
| Tokenizer vocab | `tantra/training/datasets/tokenizer.json` | ✅ Yes |
| README images | `atulya/docs/images/` | ✅ Yes |
| Model weights | `outputs/` → GitHub Releases | ❌ Never in git |
| Training data (large) | `assets/*.jsonl` | ❌ Generated locally |
| Checkpoints | `outputs/npdna/checkpoints/` | ❌ Never in git |

---

## How to Add a New Feature

### 1. New NP-DNA Component
```
1. Create file in tantra/npdna/your_component.py
2. Export it in tantra/npdna/__init__.py
3. Add config dataclass in config.py (with defaults)
4. Wire it into model.py
5. Add tests in tests/test_npdna.py
6. Run: python -m pytest tests/ -v
```

### 2. New Training Feature
```
1. Add to training/npdna_train.py (or new file in training/)
2. Add CLI flag in the argparse section
3. Test with: python training/npdna_train.py --config seed --steps 10
4. Verify loss decreases
```

### 3. New Modality (Voice/Vision)
```
1. Create tantra/npdna/encoder_audio.py (or encoder_vision.py)
2. Encoder must output: (batch, seq_len, hidden_size) tensor
3. Wire into NpDnaModel.forward() with modality flag
4. The rest of the pipeline (mesh, cortex, head) stays the same
5. Add tests
```

### 4. New Language Support
```
1. Add Unicode ranges in tokenizer.py _build_initial_vocab()
2. Add training samples in tantra/training/datasets/build_dataset.py
3. Test: python -c "from tantra.npdna import AtulyaTokenizer; t=AtulyaTokenizer(); print(t.encode('your text'))"
```

---

## Running Tests

```bash
# All tests (must pass before any commit)
python -m pytest atulya/tests tantra/tests yantra/tests drishti/tests -v

# Quick smoke test
python -m atulya.cli info

# Training smoke test (30 seconds)
python -m tantra.training.npdna_train --config atulya_seed --steps 30

# Benchmark
python -m tantra.training.benchmark --config atulya_seed
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

1. Run all tests: `python -m pytest atulya/tests tantra/tests yantra/tests drishti/tests -v`
2. Train and save model: `python -m tantra.training.npdna_train --config atulya_seed --steps 500`
3. Upload weights to GitHub Releases (not git!)
4. Tag release: `git tag v0.3.1 && git push --tags`
5. Update README with benchmark results
