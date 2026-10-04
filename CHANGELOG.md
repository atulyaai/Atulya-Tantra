# Changelog

All notable changes to **Atulya Tantra** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Changed
- **Hindi names (see README, Layout):** the Python packages are now `buddhi` (thinking), `yantra` (actions and tools), `upakaran` (devices), `indriya` (senses), `shruti` (hearing), `smriti` (memory), `vani` (speech), `sandesh` (messaging), `sevak` (server, `python -m atulya.sevak`), `raksha` (protection) and `bhava` (mood and persona). At the top level `web/` is now `drishti/` (the screen), `docs/` is `granth/` and `tests/` is `pariksha/`. `data/` keeps its name so existing memory and settings stay in place. Old import paths (`atulya.cognition`, `atulya.server` ...) no longer exist.
- Removed the unused `encrypted_storage` module (replaced by `atulya/raksha/vault.py`).

### Changed (earlier)
- **One English layout:** `yantra/` and `drishti/` are gone. All Python lives in `atulya/` (`capabilities/`, `senses/`, `mcp/`, `server/`, `channels.py` ...), the screen is `web/` (flat `src/`), and `assets/` + `config/` are one `data/` folder. `python -m atulya.server` starts the server; `atulya/core/` was flattened. Update imports (`yantra.x` -> `atulya.x`, `drishti.dashboard` -> `atulya.server`). The nginx container and the empty Docker volume were dropped; the Dockerfile now builds the web app.

### Added
- `start.bat` builds the web app only when its source changed and installs the web tools only when missing, so `drishti/node_modules` can be deleted (project: 260 files in 59 folders).
- All documentation now lives in `docs/` (was split with `atulya/docs/`).
- Admin-only details: brain/model info, health, telemetry, agent tools, devices, model list and model names in replies are hidden from normal users (403 on the server).
- One-screen UI: the orb is the whole app; pages became pop-ups (Esc closes), opened by voice ("show users") or the menu. Caption card, suggestion chips, volume up to 300%.
- `docs/FEATURES.md`: what Atulya has and what is missing.
- Hindi/Hinglish wake words and voice barge-in ("stop", "ruko", "चुप").
- Tools: `play_music`, `media_control`, price tracking (`track_*`), `morning_briefing`, and opt-in PC control (`pc_*`).
- Audit log of every tool call; `recommend_tier()` for picking a brain size by free RAM.
- GitHub Actions CI (ruff + pytest on Ubuntu and Windows).
- New architecture diagram (`atulya/docs/images/architecture.svg`).

- `ATULYA_BRAIN=auto`, local scene description through Ollama (`moondream`), `ATULYA_LOCKDOWN`, `/api/audit`.
- Daily spoken briefing (`ATULYA_BRIEFING_AT`), Piper offline voice, optional wake-word model gate; voice commands for music, media keys and the briefing.

### Removed
- Overlap: unused `atulya/observability/`, `tantra_local.py` (folded into `local_provider.py`; the provider is now named "Atulya Local"), a duplicate favicon, and four docs folded into others (PROJECT_MAP into CONTRIBUTING, WEBUI_RECOMMENDATIONS into FEATURES, google_mcp_oauth into DEPLOYMENT).
- The sidebar and Talk page, plus about 2,900 lines of CSS for them (stylesheet 3,702 -> 756 lines).
- Deep clean: unused imports (lint now enforces it), unused `SandboxManager`/`PromptInjectionGuard`/`EncryptionManager`/`SecurityManager`, the leftover NP-DNA cortex health check, empty old package folders; SECURITY_MODEL.md rewritten to match today.
- More dead code: `workflow_engine`, `yantra/capabilities/sandbox` (duplicate of core/security), `core/task_classifier`, `config/agent_config.json` and their tests.
- Unused modules: `yantra` harness/dispatch/orchestrator/agents/kgraph/plugins/selfimprovement/selfrepair/assistant/notify, `atulya.brain`, `atulya.soul`, `atulya.tokenjuice`, and their tests.
- NP-DNA research model, its pages, and its diagrams (they described a model that no longer lives here).

## [0.4.1] — 2026-05-25

Consolidated test files from 30 to 4 (one per package), deduplicating imports and renaming overlapping integration classes with `Integration` suffix. All 413 tests pass.

### Changed
- `tests/tantra/` (18 files → `test_tantra.py`), `tests/yantra/` (9 files → `test_yantra.py`), `tests/atulya/` (2 files → `test_atulya.py`), `tests/integration/` (1 file → `test_integration.py`)
- 11 overlapping integration test classes renamed with `Integration` suffix to avoid name collisions

## [0.4.0] — 2026-05-25

Deep bug bounty pass: 11 structural fixes across the memory subsystem, audit log, voice pipeline, and error handling.

### Fixed
- **C1 — Temp file leak** (`voice_pipeline.py`): `_save_temp_audio()` leaked a `.wav` file on every STT call. Now saves to a managed path and deletes after use.
- **C2 — Audit log OOM + hash chain race** (`audit_log.py`): `_load_last_hash()`, `verify()`, and `__len__()` read the entire file into memory. Rewritten to stream lines; hash state now persisted *after* flush+fsync to survive crashes; `encoding="utf-8"` added for Windows compat.
- **H1 — Session ID loads 100K rows** (`manager.py`): `store_session()` called `get_recent(limit=100000)` just to count entries. Now uses `stats()` with `SELECT COUNT(*)`.
- **H2 — DB reconnect overhead** (`session_search.py`, `subconscious.py`, `reflection.py`, `tree.py`): All four providers opened and closed SQLite connections on every operation, defeating WAL caching. Switched to persistent connections with a `close()` method for cleanup.
- **H3 — ReflectionProvider memory bloat** (`reflection.py`): Loaded every `.json` file into RAM at init and wrote each entry to a separate file. Rewritten to use SQLite with indexed queries.
- **H4 — Missing Windows encoding** (`npdna_train.py:894`, `audit_log.py:45`): Added `encoding="utf-8"` to file writes that defaulted to cp1252 on Windows.
- **H5 — Silent error swallowing** (`helpers.py`): Added `logger.debug()` calls to 3 `except Exception` blocks in `_tail_lines`, `_pid_running`, and `_read_status_file`.
- **M1/M2 — MemoryTree unbounded SELECT** (`tree.py`): `_update_l1` and `_update_l2` loaded all rows for a topic/summary. Added `LIMIT 1000` and `LIMIT 500` respectively.
- **M3 — `shell=True` in ExecTool** (`capabilities/__init__.py`): Replaced `subprocess.run(command, shell=True, ...)` with list-form `shlex.split()` call.
- **M4 — Dashboard cache race** (`helpers.py`): `DashboardState.MODEL_CACHE` mutation wrapped in `threading.Lock`.

## [0.3.1] — 2026-05-25

Audit and hardening pass: 11 runtime bugs fixed, file consolidation, channel hardening, and project-wide lint cleanup.

### Fixed
- **11 runtime bugs** across `plugins.py`, `voice_pipeline.py`, `external_client.py`, `orchestrator.py`, `prompt_cache.py`, `obsidian.py`, `tree.py`, `health.py`, `channels.py`, and `heartbeat.py`.
- **Circular import** in `health.py` (removed broken `from atulya.heartbeat import HeartbeatSystem`).
- **Telegram channel retries**: renamed `max_retries` → `max_retries_` to avoid parameter collision.
- **Context window guard**: already handled token estimation for `token_count ≤ 0`.

### Changed
- **`data/` → `assets/`**: Root app config directory renamed; updated all 17 module defaults, `atulya/config.py`, and `.env.example`.
- **Channel stubs → webhook implementations**: WhatsApp, Signal, Matrix, Teams, and IRC channels now inherit from `WebhookChannel` instead of `StubChannel`.
- **HeartbeatSystem**: `_provider_check()` now queries `ModelFailover.get_provider_status()` and reports open circuit breakers.
- **bridge.py merged into unified.py**: `ingest_agent_output()` method added to `UnifiedSelfImprovement`; hardcoded `D:/Hermes/cron/output` paths removed; original `bridge.py` deleted.
- **lint auto-fix**: Ruff fixed 107 issues (unused imports, unused variables); 24 cosmetic issues remain (E402/E702/E741).
- **`tantra/__init__.py`**: Added `__version__ = "0.3.0"`.
- **Compatibility wrappers preserved**: `cortex_autostore.py`, `plasticity_autoscale.py`, `yantra/tools/`, `atulya/smriti/` kept as clean re-exports.

### Added
- **ExecTool** (`yantra/capabilities/__init__.py`): `ApprovalSystem` gate with `RiskLevel.CRITICAL` for shell execution.
- **MemoryStoreTool/MemorySearchTool**: Default path changed from relative `"."` to `Path.home() / ".atulya" / "memory"`.
- **Unified `unified.py` (was bridge.py)**: `UnifiedSelfImprovement.ingest_agent_output()` ingests cron agent outputs and logs findings to the self-improvement tracker.

### Removed
- **`yantra/selfimprovement/bridge.py`**: Deleted after merge into `unified.py`.
- **`incoming/` directory**: Deleted; removed `health.py` reference.
- **`assets/prompt_cache/`**: Moved from `data/prompt_cache/` (automatic with directory rename).

## [0.3.0] — 2026-05-24

This release establishes the unified, multi-package autonomous framework, transforming Atulya Tantra from a standalone neural model into a production-grade, CPU-first agentic system.

### Added
- **Saarthi Agent System (`yantra/assistant/`)**: Implemented the complete Saarthi automation orchestrator featuring multi-channel communication (WebChat, webhook, RSS, git ingestion).
- **TaskBrain Controller (`yantra/assistant/task_brain.py`)**: A state-machine-based background automation manager tracking task progressions (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`).
- **Cron Scheduler (`yantra/assistant/cron.py`)**: Standard job scheduler driving periodic agent updates and data syncs.
- **Hierarchical Memory Trees (`memory/tree.py`)**: Structured tree memory summarizing agent logs and operational facts into multi-level categories (L1 localized topics, L2 global contexts).
- **Obsidian Vault Exporter (`memory/obsidian.py`)**: Seamless Markdown vault generation, enabling agent experiences and thoughts to be natively visualised in Obsidian.
- **Signed MCP Manifest Server (`yantra/mcp/`)**: Full Model Context Protocol (MCP) server supporting cryptographically signed manifests for secure tool definitions.
- **MCP External Client (`yantra/mcp/external_client.py`)**: JSON-RPC 2.0 client manager supporting stdio and HTTP transports for external MCP servers.
- **Trilingual Grammar & Fluency Engine (`tantra/core/grammar.py`)**: Modular evaluation system verifying grammatical coherence in English, Hindi, and Sanskrit.
- **Failover & Circuit-Breaker Reliability (`tantra/core/model_failover.py`)**: Automatic API fallback framework switching between cloud LLM providers and local models with closed/open/half-open circuit statuses.
- **Continuous Multimodal Adapters (`tantra/npdna/encoders.py`, `tantra/npdna/codecs.py`)**: VoiceEncoder (STFT + Conv1D) and VisionEncoder (Conv2D ViT patch projector) plus frozen codec layers for audio/image/video tokenization.
- **Audio Encoder (`tantra/npdna/encoder_audio.py`)**: CPU-optimized audio encoder using mel spectrogram + convolution projection.
- **Plugins System (`yantra/plugins/`)**: Plugin registry with trust levels (VERIFIED/COMMUNITY/UNTRUSTED), lifecycle hooks, and security scanning.
- **Self-Repair System (`yantra/selfrepair.py`)**: Automated repair engine for ModuleNotFoundError and FileNotFoundError with action execution.
- **Device Controller (`yantra/device_controller.py`)**: Centralized device management with CPU-first optimization, thread and memory control.
- **Event Bus (`yantra/events.py`)**: Lightweight async event bus for decoupled inter-system communication.
- **Channel System (`yantra/channels.py`)**: Unified multi-channel inbound/outbound communication replacing separate notify/saarthi modules.
- **Dispatch Layer (`yantra/dispatch.py`)**: Smart dispatch engine integrating TaskClassifier, ModelFailover, ToolRegistry, and PluginRegistry into a single agent entry point.
- **Dashboard API Routes (`drishti/backend/dashboard/`)**: Full FastAPI backend with 8 route modules — auth, system, model, train, chat, cortex, automation, openai — all wired to production frontend.
- **Production Dashboard UX**: Token persistence across restarts, background model warm-up, training subprocess watchdog, memory guard, streaming chat SSE.
- **Unified Config (`atulya/config.py`)**: Centralized `AtulyaConfig` dataclass loaded from `.env` + config.json, single source of truth for all data directories.

### Changed
- **Modular Packaging**: Consolidated directories into clear packages (`tantra`, `yantra`, `memory`, `atulya`, `drishti`), declared in `pyproject.toml`.
- **System Versioning**: Aligned package version to `0.3.0` across configurations.
- **Safety Approvals**: Integrated manual validation workflows requiring superuser checks for critical shell-execution commands.
- **Moved `tantra/core/npdna/` → `tantra/npdna/`**: The NP-DNA model is the system centrepiece, not an infrastructure utility.
- **Moved `atulya/smriti/` → shared top-level `memory/` with compatibility re-exports**: Memory is shared between atulya and yantra packages.

---

## [0.2.0] — 2026-02-15

Focused on system robustness, data security, context limits, and active vector database maintenance.

### Added
- **Security Guardrails (`tantra/core/security.py`)**: Added regex-based secrets redacting, password hashing/verification, and prompt injection detection filters.
- **SSRF Network Shield**: Restricts web tools from hitting local/private network targets (e.g., `127.0.0.1`, `192.168.0.0/16`).
- **Cryptographic Audit Logs (`tantra/core/audit_log.py`)**: Developed a tamper-evident action logger maintaining SHA-256 hash chains.
- **AES Storage Encryption (`tantra/core/encryption.py`)**: Encrypted sensitive operational vault variables at rest.
- **Context Compactor (`tantra/core/context.py`)**: Added a window guard utilizing blank-line compression and line-deduplication to preserve active attention space.
- **Subconscious Insights (`memory/subconscious.py`, `memory/reflection.py`)**: Logged agent choices and periodically extracted reflections or high-level behavioral rules.
- **Cortex Sleep Consolidation Cycles**: Automated Memory Cortex `sleep_cycle()` merging highly similar vector entries to prune database redundancy while conserving facts.

### Changed
- **Sparse Routing Balance**: Regularised routing collapse through a balanced loss metric, ensuring uniform usage of Gated SSM Strands.
- **Save/Load HF-style Layout**: Saved model indexes, metadata copies, tokenizer arrays, and cortex databases under unified HF-style directories.

---

## [0.1.0] — 2025-10-10

Initial release containing the proof-of-concept mathematical formulations of the NeuroPlastic DNA architecture.

### Added
- **DNA Genome Generator**: Compressed weights storage by learning low-rank matrix generating maps from seed vectors.
- **Gated SSM Strands**: Custom recurrent causal State-Space modules running in $O(T)$ time.
- **Sparse Router**: Implemented a routing module assigning each token to a top-$k$ subset of strands.
- **Active Memory Cortex**: Vector knowledge storage and retrieving database.
- **Plasticity Engine**: Architectural auto-growing controls monitoring loss plateaus and token coverage.
- **Atulya Tokenizer**: BPE tokenizer with automatic vocabulary expansion capability.
- **CLI & Dashboard**: Built initial web interfaces for prompt testing and live metrics tracking.
