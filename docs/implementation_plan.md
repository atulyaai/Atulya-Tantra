# Atulya — Architecture, Access & Status Guide

> For developers and contributors to understand the system structure, how to run it, and what's done vs. pending.

---

## Architecture

```
Atulya Tantra/
├── atulya/          Brain: identity, persona, memory, intelligence/provider routing
├── tantra/          LLM Engine: NP-DNA models, training configs, datasets
├── yantra/          Automation: MCP tools, agents, capabilities, plugins
├── drishti/           User-Facing Interface
│   ├── dashboard/   FastAPI server (API routes + serves built frontend)
│   ├── public/      PWA assets (service worker, manifest, favicon)
│   └── dist/        Production build (auto-generated)
├── start.bat        Single entry point — runs everything
├── .env             Configuration (host, port, API keys, tokens)
└── requirements.txt Python dependencies
```

**Module Separation:**
- `atulya/` = Brain — who Atulya is, how it thinks, provider failover chain
- `tantra/` = LLM — training pipelines, NP-DNA research, model checkpoints
- `yantra/` = Automation — what Atulya can do (tools, agents, MCP, device control)
- `drishti/` = Interface — how users interact with Atulya

---

## How to Run

### Quick Start
```
Double-click start.bat
```

start.bat automatically:
1. Loads `.env` configuration
2. Checks Python environment
3. Installs Python deps if missing
4. Builds frontend if `drishti/dist/` is missing
5. Starts FastAPI backend (serves API + built frontend)
6. Opens browser to `http://localhost:8501`

### Developer Mode (Hot Reload)
```bash
# Terminal 1: Backend
python -m drishti.app

# Terminal 2: Frontend with hot reload
cd drishti
npm run dev
# Opens at http://localhost:5173 (proxies API to backend)
```

---

## How Users Access

### Desktop
1. Run `start.bat` → opens `http://localhost:8501`
2. Enter dashboard token (shown in terminal or set in `.env`)

### Mobile (Same Wi-Fi)
1. Set `ATULYA_HOST=0.0.0.0` in `.env`
2. Run `start.bat`
3. Open `http://<PC_IP>:8501` on phone browser
4. "Add to Home Screen" → launches as fullscreen app (no browser bars)

### Remote
- Tailscale (recommended) or ngrok for tunnel access

---

## UI Modes

| Mode | Who | How to Access |
|------|-----|---------------|
| **Holographic Mode** | End users | Default view — fullscreen orb, voice chat, camera |
| **Telemetry Cockpit** | Devs | Click "📊 TELEMETRY COCKPIT" in header |
| **Admin Drawer** | Devs | Click ⚙️ gear (bottom-right) → Training, Chat, Model tabs |

---

## Provider Failover Chain

Atulya tries providers in order until one responds:

1. **Local NP-DNA** (no key needed, uses local checkpoint)
2. **Ollama** (local, `ATULYA_OLLAMA_HOST`)
3. **Groq** (`GROQ_API_KEY`)
4. **OpenRouter** (`OPENROUTER_API_KEY`)
5. **Gemini** (`GEMINI_API_KEY`)
6. **OpenAI** (`OPENAI_API_KEY`)
7. **NVIDIA NIM** (`NVIDIA_API_KEY`)
8. **OpenCode Zen** (offline fallback, always works)

---

## Feature Status

### Working ✅
- FastAPI backend with all API routes (auth, chat, voice, training, model, system)
- Token-based authentication
- Provider routing with 7-level failover chain
- Fullscreen holographic UI with animated nervous system
- Voice input (browser SpeechRecognition API)
- Voice output (edge-tts neural + browser fallback)
- Continuous hands-free voice loop
- Camera vision (capture frame + analyze)
- Streaming chat (SSE)
- Training pipeline (start/stop/monitor/loss chart)
- Model inspector (NP-DNA checkpoint analysis)
- PWA (manifest + service worker + Add to Home Screen)
- Digital Nervous System with stimulated strand animations
- Memory Galaxy constellation visualization
- 413+ tests passing

### Missing / TODO 🚧

**High Priority:**
- Persistent chat history (messages lost on refresh)
- Text input in Holographic Mode (voice-only currently)
- Wake word "Hey Atulya" (UI shows it but not functional)
- Real intent classification (currently simulated)
- Vector memory persistence (galaxy is visual only, needs ChromaDB/FAISS)

**Medium Priority:**
- Yantra device control integration (IR/WiFi nodes visual only)
- Multi-user support (single token auth currently)
- Conversation context window (each message is standalone)
- File/image upload through UI
- Push notifications to Drishti

**Low Priority:**
- HTTPS/SSL for non-localhost PWA features
- Android APK wrapper (Capacitor/TWA)
- Light theme option
- Keyboard shortcuts
- WebSocket push for training status

---

## Tests

```bash
python -m pytest
# 413+ passed
```

---

## Configuration (.env)

```env
ATULYA_HOST=127.0.0.1       # Set 0.0.0.0 for mobile access
ATULYA_PORT=8501
ATULYA_DASHBOARD_TOKEN=      # Auth token (auto-generated if empty)

# Provider API Keys
OPENAI_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=
NVIDIA_API_KEY=

# Training
ATULYA_TRAIN_PYTHON=         # Python path for training subprocess
ATULYA_DASHBOARD_MAX_STEPS=50000
ATULYA_MAX_DATASET_UPLOAD_GB=5
```
