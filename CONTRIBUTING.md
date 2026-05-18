# Contributing to Atulya Tantra

> **This document is the single source of truth for anyone (human or AI agent) working on this project.**
> Read this FIRST before touching any code.

---

## Hard Rules (NON-NEGOTIABLE)

### DO
- ✅ Run `python -m pytest tests/ -v` before every commit
- ✅ Keep all code CPU-first — GPU is optional, never required
- ✅ Use type hints on every function signature
- ✅ Add docstrings to every public class and function
- ✅ Keep dependencies minimal (torch, numpy, psutil only for core)
- ✅ Preserve existing comments and docstrings when editing
- ✅ Use `logging` module — never `print()` in library code
- ✅ Test Hindi/Sanskrit whenever touching the tokenizer
- ✅ Update `tests/test_npdna.py` when adding new features

### DON'T
- ❌ Never hardcode identity, personality, or prompts — use `data/identity.json`
- ❌ Never add GPU-only dependencies to `requirements.txt`
- ❌ Never commit model weights to git (use GitHub Releases or HF Hub)
- ❌ Never commit `__pycache__/`, `.egg-info/`, or `outputs/`
- ❌ Never break the flat `atulya/` package layout — no `src/` directory
- ❌ Never add `data/seed_dataset.jsonl` to git — it's auto-generated
- ❌ Never import from `_archive/` — those are dead legacy repos

---

## Project Structure

```
Atulya-Tantra/
├── atulya/                        # Core Python package
│   ├── core/npdna/                # NP-DNA architecture (THE BRAIN)
│   │   ├── config.py              # Scaling configs (seed/nano/micro/small/medium)
│   │   ├── genome.py              # 🧬 DNA weight generator (low-rank compression)
│   │   ├── strand.py              # SSM processing unit (causal gated recurrence)
│   │   ├── mesh.py                # 🕸️ Sparse top-k routing fabric
│   │   ├── cortex.py              # 🗃️ External vector memory store
│   │   ├── model.py               # Full model wrapper (NpDnaModel + NpDnaCore)
│   │   ├── plasticity.py          # ⚡ Self-monitoring architecture adaptation
│   │   └── tokenizer.py           # Auto-scaling BPE (EN/HI/SA + byte-fallback)
│   ├── identity.py                # 🔒 Privacy-aware personality system
│   ├── dashboard.py               # 📊 Training dashboard generator
│   └── cli.py                     # CLI: atulya info / train / generate
├── training/                      # Training pipeline
│   ├── dataset/
│   │   ├── build_dataset.py       # Seed dataset builder
│   │   └── harvest_data.py        # Wikipedia/Hindi/Sanskrit data harvester
│   ├── npdna_train.py             # Main training loop
│   └── benchmark.py               # Perplexity, compression, strand benchmarks
├── data/
│   ├── identity.json              # Personality config (EDIT THIS to customize)
│   └── tokenizer.json             # Trained tokenizer vocabulary
├── tests/
│   └── test_npdna.py              # Unit tests (must ALL pass before commit)
├── docs/images/                   # Architecture diagrams for README
├── ARCHITECTURE.md                # Deep technical guide (you're here)
├── CONTRIBUTING.md                # This file
├── README.md                      # Public-facing docs
├── pyproject.toml                 # Package config
└── requirements.txt               # Dependencies
```

---

## Where Things Go

| Artifact | Location | Git? |
|---|---|---|
| Source code | `atulya/` | ✅ Yes |
| Training scripts | `training/` | ✅ Yes |
| Tests | `tests/` | ✅ Yes |
| Identity config | `data/identity.json` | ✅ Yes |
| Tokenizer vocab | `data/tokenizer.json` | ✅ Yes |
| README images | `docs/images/` | ✅ Yes |
| Model weights | `outputs/` → GitHub Releases | ❌ Never in git |
| Training data (large) | `data/*.jsonl` | ❌ Generated locally |
| Checkpoints | `outputs/npdna/checkpoints/` | ❌ Never in git |

---

## How to Add a New Feature

### 1. New NP-DNA Component
```
1. Create file in atulya/core/npdna/your_component.py
2. Export it in atulya/core/npdna/__init__.py
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
1. Create atulya/core/npdna/encoder_audio.py (or encoder_vision.py)
2. Encoder must output: (batch, seq_len, hidden_size) tensor
3. Wire into NpDnaModel.forward() with modality flag
4. The rest of the pipeline (mesh, cortex, head) stays the same
5. Add tests
```

### 4. New Language Support
```
1. Add Unicode ranges in tokenizer.py _build_initial_vocab()
2. Add training samples in training/dataset/build_dataset.py
3. Test: python -c "from atulya.core.npdna import AtulyaTokenizer; t=AtulyaTokenizer(); print(t.encode('your text'))"
```

---

## Running Tests

```bash
# All tests (must pass before any commit)
python -m pytest tests/ -v

# Quick smoke test
python -m atulya.cli info

# Training smoke test (30 seconds)
python training/npdna_train.py --config seed --steps 30

# Benchmark
python training/benchmark.py --config seed
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
2. Train and save model: `python training/npdna_train.py --config nano --steps 500`
3. Upload weights to GitHub Releases (not git!)
4. Tag release: `git tag v0.2.0 && git push --tags`
5. Update README with benchmark results
