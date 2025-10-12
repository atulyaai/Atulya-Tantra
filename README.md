# 🤖 Atulya Tantra - Your Personal JARVIS

[![Version](https://img.shields.io/badge/version-1.0.1-blue.svg)](VERSION)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Ollama](https://img.shields.io/badge/ollama-required-orange.svg)](https://ollama.ai/)

**Voice-powered AI assistant with emotional intelligence, running 100% locally.**

> Like ChatGPT's voice mode, but private, offline, and extensible!

**🎉 NEW in v1.0.1:** Sentiment analysis • Interrupt & accumulate • Profile memory • 2-3s response times!

---

## ✨ Features

### Core Capabilities
- 🎤 **Voice Conversation** - Natural ChatGPT-style voice chat
- 🧠 **Emotional Intelligence** - Detects your mood and adapts responses
- 👤 **Profile Memory** - Remembers your name and preferences
- ⚡ **Interrupt & Accumulate** - Stop AI mid-sentence, combine questions
- 💬 **Speech Normalization** - Understands casual speech ("h r u" = "how are you")
- ⚙️ **Multi-Model Support** - Switches between models based on task
- 📝 **Dictation Mode** - Voice-to-text for writing
- 🌐 **Cross-Platform** - Windows, Linux, macOS

### Advanced Features
- 🤝 **Agent Orchestration** - 4 specialized AI agents (chat, code, research, planning)
- 🔧 **MCP Server** - Model Context Protocol for tool integration
- 🌍 **Server-Client Architecture** - Use from multiple devices
- 📊 **System Automation** - Control your computer with voice
- 💾 **Conversation Memory** - Persistent chat history
- 🎨 **Multiple Interfaces** - Desktop GUI, Web, CLI, System Tray

---

## 🚀 Quick Start

### Automatic Setup (Recommended)

**Windows:**
```powershell
.\scripts\setup.ps1
python clients\gui\voice_gui.py
```

**Linux/Mac:**
```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
python3 clients/gui/voice_gui.py
```

### Manual Setup

1. Install [Ollama](https://ollama.ai/)
2. Clone repo: `git clone https://github.com/YOUR_USERNAME/atulya-tantra.git`
3. Install: `pip install -r requirements.txt`
4. Download model: `ollama pull phi3:mini`
5. Run: `python clients/gui/voice_gui.py`

**See [Getting Started Guide](docs/getting-started.md) for detailed instructions.**

---

## 📖 Documentation

- **[Getting Started](docs/getting-started.md)** - Quick start guide
- **[API Reference](docs/README.md)** - Documentation hub
- **[Contributing](CONTRIBUTING.md)** - How to contribute
- **[Changelog](CHANGELOG.md)** - Version history
- **[Roadmap](ROADMAP.md)** - Future plans

---

## 🎯 Usage Examples

### Voice Conversation
```
You: "Hello"
Atulya: "Hey! How can I help?" (2-3s)

You: "My name is Alex"
Atulya: "Nice to meet you, Alex!"

[Later...]
You: "What's my name?"
Atulya: "Your name is Alex!"
```

### Sentiment Awareness
```
You: "I'm feeling frustrated"
Atulya: [Calm, patient tone] "I understand. What's troubling you?"

You: "I'm excited about this project!"
Atulya: [Enthusiastic tone] "That's awesome! Tell me more!"
```

### Interruption
```
Atulya: [Talking about Python...]
You: [Start speaking] "Wait, what about JavaScript?"
Atulya: [Stops immediately, responds to combined question]
```

---

## 🏗️ Architecture

```
atulya-tantra/
├── clients/              # User interfaces
│   ├── gui/             # Desktop applications
│   │   ├── voice_gui.py        # ChatGPT-style voice chat
│   │   └── system_tray_app.py  # Background mode with wake word
│   ├── cli/             # Command-line interface
│   └── web/             # Browser interface
├── server/              # FastAPI server (optional, for multi-device)
│   ├── main.py          # REST + WebSocket endpoints
│   ├── services/        # Core services
│   │   ├── ai_service.py       # Multi-model routing
│   │   ├── sentiment_analyzer.py
│   │   ├── memory_service.py
│   │   ├── voice_service.py
│   │   └── task_service.py
│   └── models/
│       └── model_router.py
├── agents/              # Multi-agent orchestration
│   └── agent_orchestrator.py
├── models/              # Model configurations
│   ├── audio/           # TTS, STT, wake word
│   ├── text/            # LLM prompts & configs
│   └── video/           # Vision models (future)
├── mcp/                 # Model Context Protocol (v1.1.0)
├── configuration/       # Settings and config
├── scripts/             # Setup and utility scripts
└── docs/                # Documentation
```

---

## 🤖 Supported Models

| Model | Size | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| **gemma2:2b** ⭐ | 1.6GB | ⚡⚡⚡⚡⚡ | ⭐⭐⭐⭐ | **Voice (Recommended)** |
| **phi3:mini** | 2.3GB | ⚡⚡⚡ | ⭐⭐⭐⭐⭐ | Balanced |
| **mistral:7b** | 4.1GB | ⚡⚡ | ⭐⭐⭐⭐⭐ | Complex tasks |
| **codellama:7b** | 3.8GB | ⚡⚡ | ⭐⭐⭐⭐⭐ | Code generation |
| **llava:7b** | 4.5GB | ⚡⚡ | ⭐⭐⭐⭐⭐ | Vision (images) |

**Download:**
```powershell
ollama pull <model-name>
```

---

## ⚙️ Configuration

### Change Default Model
Edit `configuration/settings.py`:
```python
default_model = "phi3:mini"  # Your preferred model
```

### Adjust Response Speed
Edit `clients/gui/voice_gui.py`:
```python
'num_predict': 10 if is_simple else 30  # Lower = faster
```

### Change Voice
Edit `clients/gui/voice_gui.py`:
```python
communicate = edge_tts.Communicate(text, 'en-US-AriaNeural')
# Try: en-US-GuyNeural, en-GB-SoniaNeural, etc.
```

---

## 🌐 Server Mode (Multi-Device)

Run server for access from multiple devices:

```powershell
# Start server
cd server
python main.py

# Access from:
# - Desktop: python clients/gui/voice_gui.py
# - Web: Open clients/web/index.html
# - CLI: python clients/cli/atulya_cli.py
# - API: http://localhost:8000/docs
```

---

## 🎤 Voice Features

### Smart Brevity
- **Simple queries** (e.g., "Hi") → 10 tokens (~2-3s)
- **Complex queries** (e.g., "Explain quantum physics") → 30 tokens (~5-8s)

### Speech Normalization
- "h r u" → "how are you"
- "u" → "you"
- "r" → "are"
- Understands casual texting language!

### Interruption Handling
- AI stops when you start talking
- Combines multiple questions
- Natural conversation flow

---

## 📊 Performance

### Response Times
- **Greetings:** 2-3 seconds (gemma2:2b)
- **Simple queries:** 4-6 seconds
- **Complex queries:** 8-12 seconds

### Resource Usage
- **RAM:** ~500MB (idle), ~2GB (active)
- **CPU:** 20-30% during inference
- **Disk:** ~2GB per model

---

## 🔮 Roadmap

### Coming Soon (v1.1.0)
- [ ] LLaVA vision model (image understanding)
- [ ] LangGraph workflow orchestration
- [ ] Advanced MCP tools (calendar, email)
- [ ] Proactive AI (offers suggestions)
- [ ] Learning from interactions

### Future (v1.2.0+)
- [ ] Mobile app (iOS/Android)
- [ ] Multi-language support
- [ ] Voice cloning
- [ ] Plugin system
- [ ] Cloud sync

See [ROADMAP.md](ROADMAP.md) for full details.

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Quick Contribution
1. Fork the repository
2. Create feature branch: `git checkout -b feature/your-feature`
3. Commit changes: `git commit -m "Add: your feature"`
4. Push: `git push origin feature/your-feature`
5. Open Pull Request

---

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.

**Free to use, modify, and distribute!**

---

## 🙏 Credits

Built with amazing open-source tools:
- **Ollama** - Local LLM infrastructure
- **FastAPI** - Modern web framework
- **Edge-TTS** - Microsoft Text-to-Speech
- **SpeechRecognition** - Google Speech API
- **ChromaDB** - Vector database for memory

Inspired by:
- **JARVIS** (Iron Man)
- **ChatGPT Voice Mode** (OpenAI)
- **Local-first AI movement**

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/YOUR_USERNAME/atulya-tantra/issues)
- **Discussions:** [GitHub Discussions](https://github.com/YOUR_USERNAME/atulya-tantra/discussions)
- **Email:** your-email@example.com

---

## ⭐ Star History

If you find Atulya Tantra useful, please give it a star! ⭐

---

**🎉 Ready to build your own JARVIS?** [Get Started →](docs/getting-started.md)

---

<div align="center">

**Made with ❤️ by the Open Source Community**

[Report Bug](https://github.com/YOUR_USERNAME/atulya-tantra/issues) • [Request Feature](https://github.com/YOUR_USERNAME/atulya-tantra/issues) • [Documentation](docs/README.md)

</div>
