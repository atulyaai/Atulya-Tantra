# Project Map

This is the current ownership map after the package cleanup.

## Tantra: Model Core

Model-owned files live under `tantra/`.

- `tantra/npdna/`: NP-DNA model, genome, mesh, strand blocks, tokenizer, frozen codec references, cortex, checkpointing, generation, plasticity, and safe evaluation.
- `tantra/core/`: model-adjacent runtime systems such as task classification, context control, security, encryption, audit logging, and model failover.
- `tantra/core/eval_checkpoints.py`: checkpoint evaluation utility.
- `tantra/training/`: training loop, benchmark runner, RAG knowledge map, dataset builders, harvesting, merging, and JSONL utilities.
- `tantra/training/datasets/`: model/tokenizer identity data and training datasets.
- `tantra/outputs/`: generated checkpoints, logs, metrics, and benchmark files. Secrets do not belong here.

## WebUI: User Interface Surface

WebUI-owned files live under `webui/`.

- `webui/frontend/src/`: editable React source and browser API client.
- `webui/backend/app.py`: dashboard launcher for `python -m webui.backend.app`.
- `webui/backend/dashboard/`: FastAPI dashboard app, helpers, state, and API route implementation.
- `webui/api/`: WebUI import wrappers around shared dashboard routes.
- `webui/package.json`, `webui/vite.config.js`, `webui/index.html`: frontend build and Vite setup.
- `start_dashboard.bat`: root-level convenience launcher for the WebUI.

## Yantra: Automation And Tools

Automation-owned files live under `yantra/`.

- `yantra/capabilities/`: tool registry, workflow engine, browser automation, voice pipeline, and web search.
- `yantra/tools/`: compatibility imports for older callers.
- `yantra/mcp/`: MCP server, client, transport, signed manifests, dashboard bridge, and agent runner.
- `yantra/mcp/external_client.py`: external MCP server connection manager.
- `yantra/assistant/`: assistant channels, task brain, cron scheduler, and source ingestion.
- `yantra/channels.py`: unified 14-channel system (Discord, Telegram, Slack, Email, Webhook, WhatsApp, Signal, Matrix, Teams, IRC, WebChat, Console, Log, Twitter).
- `yantra/plugins/`: plugin lifecycle and safety checks.
- `yantra/dispatch.py`: classifier-aware capability dispatch.
- `yantra/selfimprovement/`: unified self-improvement tracker (bridge.py merged into unified.py).

## Atulya: Application AI Layer

Application-owned AI files live under `atulya/`.

- `memory/`: memory orchestrator, session search, prompt cache, subconscious log, reflection, memory tree, and Obsidian export.
- `atulya/memory/`: compatibility imports for older callers.
- `atulya/identity.py`: identity and role-aware prompt helpers.
- `atulya/cli.py`: command-line entry point.

New implementation should go into the owning package above. Do not add duplicate compatibility packages unless a real external API requires it.

