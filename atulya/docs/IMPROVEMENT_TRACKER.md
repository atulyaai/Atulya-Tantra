# Atulya Tantra Improvement Tracker

## Merge Tracker

| Item | Change | Need | Status |
|---|---|---|---|
| NP-DNA package | `tantra/core/npdna` -> `tantra/npdna` | Make the model a first-class brain package, not a nested core utility | Done |
| Persona | `atulya/identity.py` + `atulya/soul.py` -> `atulya/persona.py` | One source for identity, personality, prompts, and privacy rules | Done with compatibility wrappers |
| Channels | `yantra/notify` + assistant channel adapters -> `yantra/channels.py` | One inbound/outbound channel registry | Done with compatibility wrappers |
| Health scan | `tantra/data/scan_health.py` + `full_health_scan.py` -> `tantra/data/health.py` | Remove duplicated health scanners | Done with compatibility wrappers |
| Self-improvement | `bridge.py` + `unified.py` | Fold bridge logic into the unified self-improvement system | Done; bridge.py merged and deleted |
| Memory manager | `orchestrator.py` + `session_search.py` -> `manager.py` | One memory entry point for storage and search | Done; top-level `memory.manager` added |
| Cortex | `cortex.py` + `cortex_autostore.py` | Make autostore an optional Cortex mode | Done with compatibility wrapper |
| Plasticity | `plasticity.py` + `plasticity_autoscale.py` | Make autoscaling part of PlasticityEngine | Done with compatibility wrapper |

## System Upgrade Tracker

| Item | Change | Need | Status |
|---|---|---|---|
| Telegram token | Revoke/regenerate leaked bot token | Prevent bot takeover | Local token blanked; BotFather revoke still user action |
| Secret hygiene | Keep `.env` untracked and use `.env.example` | Prevent future leaks | Done; dashboard token file removed |
| Cron parser | Use `croniter` | Real cron schedules instead of hourly fallback | Done |
| Config | Add `AtulyaConfig` | One source for data/model/log paths | Done |
| TaskBrain SQLite | Persistent connection + write lock | Better performance and fewer DB locks | Done |
| Context tokens | Estimate token count when missing | Prevent silent context overflow | Done |
| Self-repair | Real gated repair actions | Move from advice text to actionable repairs | Done with explicit install gate |
| Heartbeat | Add model/provider/Cortex checks | Monitor app health, not only memory/disk | Done; circuit breaker check added |
| RSS ingest | Seen-URL dedup | Prevent duplicate entries every run | Done |

## Architecture Tracker

| Item | Change | Need | Status |
|---|---|---|---|
| Dispatcher | Add `yantra/dispatch.py` | Single execution path using classifier, model failover, tools, plugins | Done base dispatcher; imports canonical capabilities |
| Events | Add `yantra/events.py` | Decouple dashboard, repair, training, heartbeat | Done |
| Top-level memory | Consider `atulya/memory` -> `memory` | Only if memory becomes cross-layer infrastructure | Done; `atulya.memory` is compatibility wrapper |
| Web UI boundary | Route business logic through dispatcher | Keep frontend/backend thin | Recommendations documented; auth secret storage fixed |
| Self-improvement data | Move `yantra/agents/selfimprovement_findings.json` | Keep self-improvement state in one location | Done |

## New Capability Tracker

| Item | Change | Need | Status |
|---|---|---|---|
| Cortex graph | Add topics, related IDs, importance eviction | Better persistent knowledge retrieval | Done base fields and importance pruning |
| Strand specialization | Track activation topics per Strand | Enable targeted fine-tuning | Done base routing-topic counters |
| Prompt cache wiring | Use prompt cache in generation path | Speed up repeated prompts | Done base prompt cache hook |
| Audio encoder | Add `tantra/npdna/encoder_audio.py` | Plug voice features into NP-DNA | Done feature projector |
| Real Telegram channel | Implement send + receive in unified channels | First real external chat channel | Done basic Bot API send/getUpdates; requires valid token |
| WhatsApp/Signal/Matrix/Teams/IRC stubs | Replace StubChannel with webhook implementations | Enable real external communication | Done; all use WebhookChannel base |
