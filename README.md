# Atulya Tantra

Atulya Tantra is a local-first AI workspace for the Atulya assistant: Drishti WebUI, provider routing, memory, actions, security/context helpers, and dashboard APIs in one repo.

Custom model work lives in a separate model repository. This repo calls external and local models through the provider router; it does no model training.

## What This Is

| Area | Folder | Purpose |
|---|---|---|
| Atulya | `atulya/` | Personality, memory, identity, assistant brain, provider routing, local model glue, security/classification core (`atulya/core/`), docs |
| Yantra | `yantra/` | Actions, tools, automation, browser/device/camera/voice systems, action tests |
| Drishti | `drishti/` | Mobile/desktop experience: Live Mode, chat, dashboard, backend APIs, frontend build |

The goal is a local AI system that can remember, inspect itself, route work to the right model/provider, automate tasks, and expose controls through a dashboard.

## Current Layout

```text
Atulya Tantra/
|-- assets/                     # runtime-local app state: audio, temp files, scheduler state
|-- atulya/
|   |-- core/                   # security, task classification, safe expression eval
|   |-- docs/                   # architecture, security, contribution guide, project map
|   |-- memory/                 # memory providers, tree, reflection, Obsidian export
|   |-- observability/          # usage, metrics, tracing, error tracking
|   |-- cognition/              # kernel, safety, toolbelt, triggers, brain tiers (docs/COGNITIVE_ARCHITECTURE.md)
|   |-- agent/                  # agent loop, tools, intent router, proactive jobs
|   |-- llm.py                  # AtulyaLLM, memory-enabled default, tool-call pass-through, streaming
|   |-- local_provider.py       # local GGUF chat/stream/tool-call normalization
|   |-- tantra_local.py         # persona wrapper around the local GGUF model
|   |-- intelligence.py         # ProviderRouter and provider wrappers
|   |-- persona.py
|   |-- heartbeat.py
|   |-- production_readiness.py
|   `-- cli.py
|-- config/                     # cross-package static configuration
|-- docs/                       # deployment, API reference
|-- outputs/                    # generated reports, invoices, benchmark artifacts
|-- drishti/
|   |-- frontend/src/           # editable React frontend
|   |-- dashboard/              # FastAPI app, helpers, state, chat history, routes
|   |   `-- routes/             # auth, chat, users, cron, agent, files, voice, and more
|   |-- public/                 # static assets, favicon, manifest
|   |-- dist/                   # built frontend assets (auto-generated)
|   |-- app.py                  # backend entrypoint
|   |-- package.json
|   `-- vite.config.js
|-- yantra/
|   |-- capabilities/           # gated tools, workflow, browser, voice, web search (canonical)
|   |-- mcp/                    # MCP server/client/transport/manifest
|   |-- channels.py             # unified multi-channel communication (14 channels)
|   |-- events.py               # event bus
|   |-- device_controller.py    # CPU-first device management
|   `-- agents.py
|-- tests/                      # root test suite
|-- pyproject.toml
`-- start.bat
```

More ownership detail lives in [atulya/docs/PROJECT_MAP.md](atulya/docs/PROJECT_MAP.md).
Root folder drift is checked by `python -m yantra.assistant.structure_audit`.

## Quick Start

Use Python 3.10+.

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

First startup can take 30-60 seconds because FastAPI/Pydantic and Torch-related native modules load slowly.

## Environment & Pluggable Brains

Create a `.env` file in the root directory (based on `.env.example`). The dashboard reads these configurations on startup to configure path execution, binding configurations, and local/cloud intelligence fallback providers.

```text
# Host and port binding (Set host to 0.0.0.0 for mobile/local network access)
ATULYA_HOST=127.0.0.1
ATULYA_PORT=8501

# Free-first brain provider chain
ATULYA_OLLAMA_HOST=http://localhost:11434
ATULYA_OLLAMA_MODEL=llama3
GROQ_API_KEY=gsk_...      # free key from https://console.groq.com/keys
ATULYA_BRAIN=cloud        # Groq leads; local 0.6B model is the offline backup
ATULYA_GROQ_MODEL=llama-3.3-70b-versatile
OPENROUTER_API_KEY=sk-or-v1-...
GEMINI_API_KEY=AIzaSy...
OPENAI_API_KEY=sk-proj-...
NVIDIA_API_KEY=nvapi-...

# Dashboard API authentication
ATULYA_DASHBOARD_TOKEN=my_secure_session_token
```

### Fallback Failover Order
When you submit a request, the `ProviderRouter` scans the list of configured keys and automatically failovers in this order:
1. **Local GGUF**: Built-in Qwen3-0.6B model, no key required.
2. **Ollama**: Local LLMs (free/offline).
3. **Groq**: Free developer tier.
4. **OpenRouter**: Cloud-based aggregator free models.
5. **Gemini**: Free tier, rare fallback when configured.
6. **OpenAI**: Optional paid fallback.
7. **NVIDIA NIM**: Pluggable microservice containers.
8. **OpenCode Zen**: Offline rule-based persona fallback if all endpoints are offline or keys are missing.

Local custom models should be integrated through a provider endpoint or adapter. Keep their training and checkpoint lifecycle in the separate model repo.

---

## Mobile Access (Like Siri or Gemini)

Atulya Tantra is built mobile-first. You can access the voice cockpit, real-time cameras, memory, and planning modules on your smartphone or tablet with the feeling of a native OS assistant (like Siri or Gemini).

### Step 1: Bind Server to Local Network
Configure your `.env` file to expose the server to the local network:
```text
ATULYA_HOST=0.0.0.0
ATULYA_PORT=8501
```
Start the dashboard using `start.bat`.

### Step 2: Open on Mobile
1. Find your computer's local IP address (e.g., `192.168.1.15`).
2. Open Safari (iOS) or Chrome (Android) on your mobile device.
3. Navigate to: `http://192.168.1.15:8501`.
4. Enter your session token (`ATULYA_DASHBOARD_TOKEN`) to authenticate.

### Step 3: Add to Home Screen (PWA Mode)
- **iOS (Safari)**: Tap the **Share** button at the bottom, scroll down, and select **Add to Home Screen**.
- **Android (Chrome)**: Tap the **three-dot menu** at the top right and select **Add to Home screen** or **Install App**.

This places a native launcher icon on your smartphone home screen. Opening it hides browser navigation controls and launches Atulya in full-screen immersion mode.

### Step 4: Engage Hands-Free Voice Cycle
1. Click **ENGAGE ORACLE** to grant microphone permission.
2. Check the **HANDS-FREE** checkbox.
3. The interface will open the microphone, listen for voice input, process thoughts across the digital nervous system, vocalize responses via edge-tts, and automatically re-open the mic for continuous conversation.

### Step 5: Remote Mobile Access (Anywhere in the World)
To talk to Atulya outside your home WiFi network:
- **Tailscale (Recommended)**: Install Tailscale on your host computer and your phone. You can access Atulya from anywhere using the private Tailscale IP (e.g., `http://100.x.y.z:8501`) securely, without opening public ports.
- **ngrok**: Expose local port 8501 securely to a public ngrok domain: `ngrok http 8501`.

---

## Model Repo Boundary

Do not add new custom LLM training flows to this repository. Model architecture work, tokenizer changes, training jobs, checkpoints, evaluations, and model release artifacts belong in the separate LLM/model repo.

Use this repo to connect models to the product:

- Add provider keys and endpoint URLs in `.env`.
- Route chat through `atulya/llm.py` and provider/router adapters.
- Surface status, links, and diagnostics in Drishti.

## Drishti Development

Run the Vite dev server:

```powershell
cd drishti
npm run dev
```

The dev server proxies `/api` and `/ws` to `http://127.0.0.1:8501`.

Build production assets:

```powershell
cd drishti
npm run build
```

Backend entrypoint:

```powershell
python -u -m drishti.app
```

## Dashboard And Automation

```mermaid
flowchart LR
    Browser["Browser / Drishti"] --> Backend["drishti.app"]
    Backend --> App["FastAPI dashboard"]
    App --> Chat["chat/provider APIs"]
    App --> Models["model status/adapters"]
    App --> Yantra["Yantra MCP + tools"]
    Models --> External["external or local model repo endpoint"]
```

Important Yantra locations:

- `yantra/capabilities/`: file read/write/edit, gated shell execution, web search/fetch, todo, memory, browser, voice, and workflow capabilities (canonical)
- `yantra/channels.py`: unified 14-channel system (Discord, Telegram, Slack, Email, Webhook, WhatsApp, Signal, Matrix, Teams, IRC, WebChat, Console, Log, Twitter)
- `yantra/mcp/`: MCP server, transport, manifest signing, external client, dashboard bridge


- Agents define who should handle work: planner, coder, researcher, memory manager, safety checker, self-improvement, and automation operator.
- Skills define reusable abilities and point to one canonical tool name.
- Duplicate cleanup is handled by canonical registration: aliases map to one command or skill, and `YantraHarness.report_duplicates()` shows duplicate tool registration attempts.

## Memory And Identity

Atulya application memory lives in `atulya/memory/`. Memory is part of the assistant brain, not a fifth top-level product folder.

| Module | Purpose |
|---|---|
| `orchestrator.py` | provider registry and context assembly |
| `session_search.py` | session text search |
| `prompt_cache.py` | prompt/result cache |
| `subconscious.py` | decision/event log |
| `reflection.py` | insights and reflective notes |
| `tree.py` | hierarchical memory summaries |
| `obsidian.py` | markdown vault export |
| `vector_store.py` | dependency-free feature-hashed vector memory |

Identity and prompt behavior are controlled by `atulya/persona.py` and the Atulya memory modules. An optional identity override can be placed at `data/identity.json` (or pointed to with `ATULYA_IDENTITY_PATH`).

## API Example

Token-protected dashboard routes expect `X-Atulya-Token`.

```powershell
$token = $env:ATULYA_DASHBOARD_TOKEN
Invoke-RestMethod http://127.0.0.1:8501/api/system -Headers @{"X-Atulya-Token"=$token}
```

Routes implemented by the current backend:

| Route | Method | Real source |
|---|---|---|
| `/api/dashboard/bootstrap` | GET | current user, providers, and (for admins) system stats |
| `/api/system` | GET | `psutil` CPU/RAM/disk plus Python version |
| `/api/health` | GET | health check |
| `/api/chat` | POST | blocking chat routed through provider/model adapters |
| `/api/chat/stream` | POST | Server-Sent Events token stream |
| `/api/chat/history` | GET/DELETE | persisted conversation history |
| `/api/agent/status`, `/api/agent/process`, `/api/agent/tools` | GET/POST | agent tools and process control |
| `/api/auth/login` | POST | validates the dashboard token |
| `/api/users` | GET/POST/DELETE | user management |
| `/api/cron/jobs` | GET/POST/DELETE | automation job scheduler |
| `/api/upload`, `/api/files` | POST/GET/DELETE | file upload and serving |
| `/api/voice/voices`, `/api/voice/tts`, `/api/voice/stt`, `/api/voice/chat` | GET/POST | voice pipeline |
| `/api/notifications/subscribe` | POST | notification subscriptions |
| `/v1/models` | GET | OpenAI-compatible model list |

## Verification

```powershell
python -m pytest -q  # current suite: 623 passing tests
python -m atulya.cli doctor
```

## Notes

- Do not commit `.env`; it can contain secrets.
- Do not commit generated outputs, `__pycache__`, or large local datasets unless intentionally publishing data elsewhere.
- `drishti/node_modules` can exist locally for development, but should not be treated as source.
- `drishti/dist` is built by `start.bat` or CI; do not commit generated build output.
- `assets/` holds runtime-local app state; runtime artifacts such as scheduler state, memory databases, and email config are gitignored.
- Active LLM training data, checkpoints, and tokenizer artifacts belong in the separate model repo.
