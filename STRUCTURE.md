# 📁 Project Structure

Professional GitHub repository structure for Atulya Tantra.

```
atulya-tantra/
│
├── 📄 Root Files
│   ├── README.md                  # Main documentation
│   ├── LICENSE                    # MIT License
│   ├── VERSION                    # Version number
│   ├── CHANGELOG.md               # Version history
│   ├── CONTRIBUTING.md            # Contribution guidelines
│   ├── ROADMAP.md                 # Future plans
│   ├── INSTALL_GUIDE.md           # Detailed installation
│   ├── requirements.txt           # Python dependencies
│   ├── requirements_server.txt    # Server dependencies
│   ├── docker-compose.yml         # Docker setup
│   ├── Dockerfile                 # Docker image
│   ├── .gitignore                 # Git ignore rules
│   └── voice_gui.py               # Main entry point
│
├── 🎤 Core Applications
│   ├── voice_gui.py               # Desktop voice chat (primary)
│   └── system_tray_app.py         # Background mode
│
├── 🌐 clients/                    # Multi-platform clients
│   ├── web/                       # Browser interface
│   │   ├── index.html
│   │   └── README.md
│   └── cli/                       # Terminal interface
│       └── atulya_cli.py
│
├── 🧠 server/                     # FastAPI server (multi-device)
│   ├── main.py                    # Server entry point
│   ├── config.py                  # Server configuration
│   ├── services/                  # Microservices
│   │   ├── agent_orchestrator.py  # Multi-agent system
│   │   ├── sentiment_analyzer.py  # Emotion detection
│   │   ├── ai_service.py          # AI inference
│   │   ├── memory_service.py      # Conversation storage
│   │   ├── voice_service.py       # TTS/STT
│   │   └── task_service.py        # System automation
│   └── models/                    # Model routing
│       └── model_router.py
│
├── 🤖 models/                     # AI model management
│   ├── README.md                  # Model documentation
│   ├── configs/                   # Model configurations
│   └── prompts/                   # System prompts
│       └── system_prompt.txt
│
├── 📊 data/                       # User data (gitignored)
│   ├── README.md                  # Data structure docs
│   ├── conversations/             # Chat history
│   ├── memory/                    # Long-term memory
│   ├── cache/                     # Temporary cache
│   └── logs/                      # Application logs
│
├── 🧪 tests/                      # Test suite
│   ├── README.md                  # Testing guide
│   ├── unit/                      # Unit tests
│   ├── integration/               # Integration tests
│   └── e2e/                       # End-to-end tests
│
├── 📚 docs/                       # Documentation
│   ├── README.md                  # Documentation hub
│   ├── getting-started.md         # Quick start guide
│   ├── user-guide.md              # User manual
│   ├── api-reference.md           # API documentation
│   └── architecture.md            # System design
│
├── 🔧 scripts/                    # Utility scripts
│   ├── README.md                  # Scripts guide
│   ├── setup.sh                   # Linux/Mac setup
│   ├── setup.ps1                  # Windows setup
│   └── test_models.py             # Model comparison
│
├── 🎨 assets/                     # Media files
│   ├── README.md                  # Assets guide
│   ├── icons/                     # App icons
│   ├── images/                    # Screenshots
│   └── videos/                    # Demo videos
│
├── ⚙️ config/                     # Configuration
│   └── settings.py                # App settings
│
├── 🎙️ wake_word/                 # Wake word detection
│   └── detector.py
│
└── 🚀 Deployment Scripts
    ├── INSTALL.bat                # Windows installer
    ├── RUN_ME.bat                 # Quick launcher
    └── START_SERVER.bat           # Server launcher
```

---

## 📌 Key Directories

### For Users:
- **Root** - Main files, run `voice_gui.py`
- **clients/** - Different interfaces (web, CLI)
- **scripts/** - Setup and utility scripts

### For Developers:
- **server/** - Backend services and API
- **tests/** - Test suite
- **docs/** - Full documentation
- **models/** - AI model configuration

### Ignored (Privacy):
- **data/** - All user data (conversations, memory)
- **.venv/** - Python virtual environment
- **.git/** - Git history

---

## 🎯 Entry Points

| File | Purpose | Usage |
|------|---------|-------|
| `voice_gui.py` | Desktop voice chat | Main entry point |
| `server/main.py` | FastAPI server | Multi-device access |
| `clients/cli/atulya_cli.py` | Terminal interface | CLI access |
| `system_tray_app.py` | Background mode | System tray app |

---

## 📦 Distribution

When uploading to GitHub:
- ✅ All source code included
- ✅ Documentation complete
- ✅ Tests structured
- ✅ Scripts ready
- ❌ User data excluded (.gitignore)
- ❌ Virtual envs excluded (.gitignore)
- ❌ Cache/logs excluded (.gitignore)

---

**Professional, organized, GitHub-ready!** ✨

