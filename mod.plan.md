<!-- 337c66ee-b84f-4889-9908-c61d81a24728 3e131008-9aea-487c-8532-ef3090947bfc -->
# Modular Cleanup, TinyLlama Default, AGI L5 Gap Audit

## Goals

- Clean up redundant files and reorganize into clear modules/folders.
- Deep refactor Core/ internals for better separation of concerns.
- Default to a single local small-model (TinyLlama via Transformers) without Ollama; keep provider registry pluggable to add others by category later.
- Comprehensive AGI Level 5 capability gap audit across Jarvis and Skynet.

## High-Level Steps

1) Repository consolidation and structure

- Move demos → `demos/`; scripts → `scripts/`; docs → `docs/`; web UI → `webui/`; deployment → `deploy/` (docker, k8s); monitoring → `monitoring/`; examples/tests → `tests/` (keep existing `Test/` as canonical).
- Remove or merge duplicate scripts/docs and outdated entry points; keep one canonical per purpose.
- Introduce `core/` module boundary inside `Core/` by function:
- `Core/llm/` (providers, router, token utils)
- `Core/agents/` (agent implementations and orchestrator)
- `Core/conversation/` (NLP, dialog mgmt)
- `Core/memory/` (vector store, knowledge graph, conversation memory)
- `Core/monitoring/` (health, metrics, logging)
- `Core/middleware/` (rate limiter, security headers)
- `Core/api/` (FastAPI endpoints)
- `Core/dynamic/` (self_evolution, installer, discovery)

2) Default LLM path: TinyLlama (no Ollama)

- Add `Core/llm/providers/tinyllama_provider.py` using HuggingFace Transformers, CPU-friendly quantized weights (TinyLlama/TinyLlama-1.1B-Chat-v1.0 or similar), with small context and sensible defaults.
- Define a clean provider interface `Core/llm/base.py` with `generate`, `count_tokens`, `get_model_info`, `test_connection`.
- Implement `Core/llm/router.py` that selects a primary provider (TinyLlama) and supports category-based overrides (e.g., chat, code, vision placeholder) via config only.
- Keep stubs/adapters for OpenAI/Anthropic/Ollama under `Core/llm/providers/`, disabled by default until keys present.
- Config-first model selection in `Core/config/settings.py`:
- `LLM_PRIMARY=tinyllama`
- `LLM_CATEGORY_MAP={"chat": "tinyllama"}` (extensible)

3) API and internal refactor to provider interface

- Update existing usages in `Core/brain/llm_provider.py` and callsites to use `Core/llm/router.py` and the base interface.
- Minimize surface changes: create a compatibility shim exporting `get_llm_router`, `generate_response` unchanged semantics.

4) Cleanup and standardization

- Remove redundant root-level tests (done) and demos; keep `demos/simple_working_demo.py` and `demos/final_jarvis_demo.py`.
- Normalize import paths to new module layout; add deprecation shims where needed to avoid breakage.
- Update README and docs with new structure and default model instructions.

5) AGI Level 5 capability gap audit (Jarvis/Skynet)

- Audit matrix across areas:
- Autonomy: long-horizon planning, self-initiated goals, event-driven triggers
- Multi-agent orchestration: roles, negotiation, shared memory, task passing
- Learning: continual learning hooks, feedback loops, skill acquisition
- Safety/guardrails: policy, rate limiting, privilege separation, sandboxing
- Monitoring/Auto-heal: observability, SLOs, remediation playbooks
- Tool-use/action layer: OS/web/system actions with verification and rollback
- Evaluation: offline test harness, competency benchmarks, regression suites
- Produce a `docs/AGI_L5_GAP_REPORT.md` with prioritized backlog and ownership.

6) CI and runnable defaults

- Adjust `requirements.txt` to include transformers and safetensors; keep DB optional.
- Add a light `make demo`/PowerShell script to run `demos/simple_working_demo.py` using CPU.
- Keep tests runnable without DB; mark DB tests optional/skip if env not set.

## Key File Changes

- New: `Core/llm/base.py` (provider interface); `Core/llm/router.py`; `Core/llm/providers/tinyllama_provider.py`.
- Refactor: `Core/brain/llm_provider.py` to delegate to router; ensure compatibility exports.
- Moves: `*demo*.py` → `demos/`; `Scripts/` → `scripts/`; `Webui/` → `webui/`; `k8s/`+`Dockerfile` → `deploy/`.
- Docs: `docs/README.md` (updated), `docs/AGI_L5_GAP_REPORT.md`.

## Risks/Mitigations

- Transformers model size: use TinyLlama 1.1B with low RAM settings; lazy-load.
- Import breakage: provide shims and staged refactor.
- CI time: cache models or use tiny stub for CI (mock provider).

### To-dos

- [x] Reorganize repo directories; move demos/scripts/docs/webui/deploy
- [x] Create provider base interface and router under Core/llm
- [x] Implement TinyLlama provider via Transformers (CPU-friendly)
- [x] Refactor Core/brain LLM usage to new router with shims
- [x] Keep minimal and one full demo; remove others
- [x] Update README and add AGI_L5_GAP_REPORT.md
- [x] Adjust requirements and CI to run CPU demo/tests
- [x] Perform comprehensive AGI Level 5 capability gap audit


