# Atulya Tantra

Atulya Tantra is a local-first AI assistant platform: the Drishti web UI, provider routing, memory, tools, automation, and dashboard APIs live in one repo. The free-first brain chain runs Ollama or the built-in Tantra local model, with free/cloud fallbacks (Groq, OpenRouter, Gemini, NVIDIA NIM) and an offline persona fallback.

Custom LLM/model training and checkpoints live in a separate model repository. This repo connects models to the product through routers and provider adapters.

## Architecture

Four product pillars, plus shared support directories:

| Area | Folder | Purpose |
|---|---|---|
| Atulya | `atulya/` | Assistant brain: personality, identity, memory, provider routing, local model glue, heartbeat, CLI |
| Tantra | `tantra/` | Support layer: task classification, security, context, encryption, and legacy NP-DNA compatibility |
| Yantra | `yantra/` | Automation and tools: capabilities, harness, MCP, channels, plugins, dispatch, notifications |
| Drishti | `drishti/` | Web UI: React frontend, FastAPI dashboard backend, chat/voice APIs, automation routes |

Shared support directories:

- `config/` — cross-package static configuration (browser, devices, agent config, MCP servers)
- `assets/` — runtime-local app state: generated audio, uploads, scheduler state
- `outputs/` — generated reports, invoices, benchmark artifacts
- `docs/` — deployment, API reference, implementation plan, and MCP/Gmail OAuth guides
- `atulya/docs/` — architecture, security model, project map, contribution guide

The repo root intentionally has four product directories. New implementation goes into the owning package; see `atulya/docs/PROJECT_MAP.md` for the ownership map.

## Quick Start

Requires Python 3.10+.

```powershell
python -m pip install -e ".[dev,serve]"
```

Build the dashboard frontend:

```powershell
cd drishti
npm install
npm run build
cd ..
```

Start the dashboard:

```powershell
start.bat
```

Or run the backend directly:

```powershell
python -u -m drishti.app
```

Open:

```text
http://localhost:8501
```

First startup can take 30-60 seconds while FastAPI/Pydantic and native modules load.

## Free-First Provider Chain

Copy `.env.example` to `.env` and configure. Requests fail over in order:

1. **Ollama** — local/offline (`ATULYA_OLLAMA_MODEL`, `ATULYA_OLLAMA_HOST`)
2. **Tantra Local** — built-in local GGUF model (`tantra/`), no key required
3. **Groq** — free developer tier (`GROQ_API_KEY`)
4. **OpenRouter** — free models (`OPENROUTER_API_KEY`)
5. **Gemini** — free tier, rare fallback (`GEMINI_API_KEY`)
6. **OpenAI** — optional paid fallback (`OPENAI_API_KEY`)
7. **NVIDIA NIM** — optional (`NVIDIA_API_KEY`)
8. **OpenCode Zen** — offline persona-based response, no key required

Set `ATULYA_PREFER_TANTRA=1` to prefer the built-in local model for Telegram/local tests.

## Key Entry Points

- `atulya/llm.py` — `AtulyaLLM`, `get_default_llm()` (memory-enabled), tool-call pass-through, streaming
- `atulya/local_provider.py` — local GGUF chat/stream/tool-call normalization
- `atulya/intelligence.py` — `ProviderRouter`, provider wrappers
- `atulya/memory/vector_store.py` — dependency-free feature-hashed vector memory
- `yantra/capabilities/` — canonical tool registry (file, shell, web, todo, memory, browser, voice)
- `yantra/harness.py` — agent/skill/slash-command harness
- `drishti/dashboard/app.py` — FastAPI app, lifespan, static mount
- `drishti/dashboard/routes/` — dashboard, chat, automation, memory, upload routes

## Drishti Development

Run the Vite dev server (proxies `/api` and `/ws` to `127.0.0.1:8501`):

```powershell
cd drishti
npm run dev
```

Build production assets:

```powershell
cd drishti
npm run build
```

## Tests

```powershell
python -m pytest
```

Benchmarks run only with `--benchmark-enable` and otherwise skip.

## Dashboard APIs

Token-protected dashboard routes expect `X-Atulya-Token`.

```powershell
$token = $env:ATULYA_DASHBOARD_TOKEN
Invoke-RestMethod http://127.0.0.1:8501/api/system -Headers @{"X-Atulya-Token"=$token}
```

See `docs/API_REFERENCE.md` for the route list.

## More Docs

- `docs/DEPLOYMENT.md` — deployment, Docker, mobile/remote access
- `docs/API_REFERENCE.md` — dashboard and provider routes
- `atulya/docs/ARCHITECTURE.md` — deep technical architecture
- `atulya/docs/SECURITY_MODEL.md` — security model and threat boundaries
- `atulya/docs/PROJECT_MAP.md` — folder ownership and drift rules
- `CHANGELOG.md` — release history
