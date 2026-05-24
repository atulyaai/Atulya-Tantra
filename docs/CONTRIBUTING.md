# Contributing to Atulya Tantra

> **This document is the single source of truth for anyone (human or AI agent) working on this project.**
> Read this FIRST before touching any code.

---

## Hard Rules (NON-NEGOTIABLE)

### DO
- âœ… Run `python -m pytest tests/ -v` before every commit
- âœ… Keep all code CPU-first â€” GPU is optional, never required
- âœ… Use type hints on every function signature
- âœ… Add docstrings to every public class and function
- âœ… Keep dependencies minimal (torch, numpy, psutil only for core)
- âœ… Preserve existing comments and docstrings when editing
- âœ… Use `logging` module â€” never `print()` in library code
- âœ… Test Hindi/Sanskrit whenever touching the tokenizer
- âœ… Update `tests/test_npdna.py` when adding new features

### DON'T
- âŒ Never hardcode identity, personality, or prompts â€” use `tantra/training/datasets/identity.json`
- âŒ Never add GPU-only dependencies to `requirements.txt`
- âŒ Never commit model weights to git (use GitHub Releases or HF Hub)
- âŒ Never commit `__pycache__/`, `.egg-info/`, or `outputs/`
- âŒ Never break the flat `atulya/` package layout â€” no `src/` directory
- âŒ Never add `data/seed_dataset.jsonl` to git â€” it's auto-generated
- âŒ Never import from `_archive/` â€” those are dead legacy repos

---

## Project Structure

```
Atulya-Tantra/
├── assets/                        # app config cache (prompt_cache)
├── atulya/                        # Application AI: persona, heartbeat, observability, CLI
│   ├── memory/                    # compatibility imports for memory/
│   ├── persona.py                 # unified identity + personality
│   ├── identity.py                # compatibility wrapper
│   ├── config.py                  # AtulyaConfig dataclass (single source of truth)
│   ├── heartbeat.py               # model/provider/Cortex/disk/memory health checks
│   ├── observability/             # usage, metrics, traces, errors
│   ├── soul.py                    # SOULSystem compatibility wrapper
│   └── cli.py                     # CLI entry point
├── memory/                        # shared memory providers
│   ├── orchestrator.py            # provider registry, context assembly
│   ├── tree.py                    # hierarchical memory summaries
│   ├── obsidian.py                # markdown vault export
│   ├── prompt_cache.py            # prompt/result cache
│   ├── reflection.py              # insights and reflective notes
│   ├── subconscious.py            # decision/event log
│   ├── session_search.py          # session text search
│   └── manager.py                 # combined storage + search entry point
├── tantra/                        # NP-DNA model package
│   ├── npdna/                     # genome, mesh, strand, tokenizer, cortex, checkpointing
│   ├── core/                      # security, context, encryption, model failover
│   ├── training/                  # trainer, benchmark, dataset builders, RAG
│   │   └── datasets/              # identity.json and identity config files
│   ├── data/                      # training data examples and health scans
│   └── outputs/                   # generated model outputs and checkpoints
├── webui/                         # React dashboard + FastAPI backend
│   ├── frontend/src/              # editable React source
│   ├── backend/dashboard/         # FastAPI app, helpers, state, routes
│   ├── api/                       # route wrappers
│   ├── dist/                      # built frontend assets
│   ├── package.json
│   └── vite.config.js
├── yantra/                        # Automation and tools
│   ├── capabilities/              # canonical tools: exec, workflow, browser, voice, web search
│   ├── tools/                     # compatibility re-exports from capabilities/
│   ├── channels.py                # unified 14-channel communication system
│   ├── mcp/                       # MCP server, client, transport, manifests
│   ├── assistant/                 # task brain, cron scheduler, source ingestion
│   ├── selfimprovement/           # unified self-improvement (bridge merged)
│   ├── selfrepair.py              # automated error recovery
│   ├── dispatch.py                # classifier + failover + tools dispatch
│   ├── events.py                  # async event bus
│   ├── device_controller.py       # CPU-first device management
│   ├── notify/                    # notification facade
│   └── plugins/                   # plugin SDK with trust levels
├── docs/                          # architecture, contribution, security, project map
│   └── images/                    # diagrams and visuals for README
├── tests/                         # test suites
│   ├── tantra/
│   ├── yantra/
│   ├── atulya/
│   └── integration/
├── start_dashboard.bat
├── pyproject.toml
└── requirements.txt
```

---

## Where Things Go

| Artifact | Location | Git? |
|---|---|---|
| Source code | `atulya/` | âœ… Yes |
| Training scripts | `training/` | âœ… Yes |
| Tests | `tests/` | âœ… Yes |
| Identity config | `tantra/training/datasets/identity.json` | âœ… Yes |
| Tokenizer vocab | `tantra/training/datasets/tokenizer.json` | âœ… Yes |
| README images | `docs/images/` | âœ… Yes |
| Model weights | `outputs/` â†’ GitHub Releases | âŒ Never in git |
| Training data (large) | `assets/*.jsonl` | âŒ Generated locally |
| Checkpoints | `outputs/npdna/checkpoints/` | âŒ Never in git |

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
python -m pytest tests/ -v

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

1. Run all tests: `python -m pytest tests/ -v`
2. Train and save model: `python -m tantra.training.npdna_train --config atulya_seed --steps 500`
3. Upload weights to GitHub Releases (not git!)
4. Tag release: `git tag v0.3.1 && git push --tags`
5. Update README with benchmark results
