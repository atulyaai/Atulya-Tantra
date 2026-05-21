# Atulya Tantra

Atulya Tantra is an experimental open-source AI stack built around **NP-DNA
(NeuroPlastic DNA Network)**. The core idea is simple: keep a compact genome
that generates neural weights on demand, then combine it with sparse routing,
external memory, plasticity, multimodal encoders, and a web dashboard.

The repository is intentionally local-first. It can train and serve small
models on CPU, expose an OpenAI-compatible API, and provide dashboard controls
for training, model loading, memory exploration, and chat.

## Current Layout

```text
atulya/
  core/npdna/          NP-DNA model, tokenizer, cortex, generation, autonomy
  dashboard/           FastAPI backend and modular API routes
  dashboard_ui.html    Single-file dashboard frontend (HTML/CSS/JS)
  identity.py          Identity and role-aware prompt helpers
training/
  npdna_train.py       Training loop, resume support, optimizer recovery
  dataset/             Dataset builders and harvest utilities
data/                  Seed identity, tokenizer, and training data
tests/                 Unit and route regression tests
docs/images/           Architecture images used by the README
```

## What NP-DNA Does

Traditional neural models store large weight matrices directly. NP-DNA stores
compact seed parameters and uses a genome network to generate low-rank weight
factors at runtime.

```text
Input tokens
  -> tokenizer and embeddings
  -> sparse Neural Mesh
  -> DNA-generated Strands
  -> Memory Cortex retrieval
  -> language-model head
```

Core pieces:

| Component | Purpose |
| --- | --- |
| Genome | Generates per-strand weights from compact seeds |
| Strand | Causal gated state-space processing block |
| Neural Mesh | Routes each token to top-k strands |
| Memory Cortex | Vector memory for external facts |
| Plasticity Engine | Grows vocabulary and strands during training |
| Multimodal Encoders | Projects voice and image inputs into model space |
| Autonomy Layer | ReAct-style tool loop with restricted expression tools |

## Quickstart

```bash
pip install -e .
python -m pytest -q
python -m training.npdna_train --config seed --max-steps 10
python -m atulya.dashboard.app
```

The dashboard app provides chat, model management, training metrics, memory
inspection, system status, and OpenAI-compatible routes.

## Training

Small CPU runs are the default development path:

```bash
python -m training.npdna_train --config seed --max-steps 50 --device cpu
```

Training supports:

- checkpoint save and resume with automatic rotation
- stop-signal handling (graceful + hard termination)
- optimizer-state recovery after plasticity changes
- live metrics streaming via WebSocket to the dashboard
- dataset builders for identity and trilingual examples
- **RAG** (Retrieval-Augmented Generation) integration
- **LoRA adapters** for parameter-efficient fine-tuning
- **RLHF** (Reinforcement Learning from Human Feedback) phase support
- **Plasticity controls**: interval, overload/dead thresholds, grow cooldown
- **Auto-growing vocabulary** with no artificial limits (byte-fallback ensures any text can be encoded)
- **BPE tokenizer** with Hindi, Sanskrit, and English support
- **Sequence packing** for efficient training
- **bfloat16** support for GPU acceleration

## Dashboard Features

The NP-DNA Command Center (`dashboard_ui.html`) provides:

- **Metrics Tab**: Live loss trajectory, strand activity heatmap, architecture profile, benchmark radar
- **Knowledge Tab**: Interactive MoE expert visualization with neural cluster mapping
- **Training Tab**: Comprehensive training console with dataset management, hyperparameter controls, advanced training options (RAG, LoRA, RLHF, plasticity), resume/pause/stop controls, and real-time log streaming
- **Chat AI Tab**: Neural chat interface with multimodal support (audio/image), ReAct agent mode, translation modes, and telemetry tracing
- **Models Tab**: Model registry with checkpoint management, DNA compression stats, factory reset
- **Cortex Tab**: Memory vector management with semantic search, fact injection, sleep consolidation, and paginated registry
- **History Tab**: Run history with event tracking
- **Users Tab**: User management, API key generation, role permissions matrix
- **Domains Tab**: Linked domain management, DNS verification, webhook configuration, CORS settings
- **Settings Tab**: Organized into sub-tabs (Access, System, Notifications, Limits, Danger Zone)

## Security Posture

Implemented controls include bounded dashboard inputs, token-protected admin
routes, constant-time token comparison, restricted autonomy expression
evaluation, model path allowlisting, and regression tests for these paths.

Some security goals remain roadmap or partial until they are enforced across
all runtime entry points. See [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md)
for the explicit implemented/partial/planned split.

## Context Compression

The current repository does not include the older agent tree that previously
held a named context-compression helper. On `main`, context handling is focused
inside the NP-DNA tokenizer, generation path, dashboard routes, and training
pipeline. A standalone compressor should be added as a first-party module if
the product needs reusable cross-session compression.

## Verification

Use these checks before pushing changes:

```bash
python -m pytest -q
python -m atulya.cli info
rg -n -i "eval\\(|exec\\(|TODO|FIXME" atulya training tests README.md docs
```

## License

MIT.
