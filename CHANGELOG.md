# Changelog

All notable changes to Atulya Tantra will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2025-10-12

### Added
- **Sentiment Analysis**: Rule-based emotion detection (happy, sad, angry, anxious, etc.)
- **Interrupt & Accumulate**: AI stops when user talks, combines multiple questions
- **Profile Memory**: Remembers user name across conversations
- **Speech Normalization**: Understands casual text ("h r u" → "how are you")
- **Smart Brevity**: 10 tokens for greetings, 30 for complex queries
- **GUI Enhancements**: Smaller input (2 lines), typing indicator (✍️)
- **Multi-Model Fallback**: gemma2:2b → phi3:mini auto-fallback
- **Professional GitHub**: LICENSE, .gitignore, CONTRIBUTING.md, CHANGELOG.md

### Changed
- Voice GUI input reduced from 3 to 2 lines for better UX
- Response time optimized: greetings now 2-3s (was 15s)
- Conversation history limited to last 6 messages for speed
- System prompt shortened for faster inference

### Fixed
- Interruption now properly stops AI and accumulates user input
- Emoji removal now comprehensive (regex-based)
- Microphone context manager properly used
- GUI window controls (minimize/maximize) enabled

## [1.0.0] - 2025-10-11

### Added (Initial Release)
- **Voice Conversation**: ChatGPT-style voice mode with TTS/STT
- **Server-Client Architecture**: FastAPI server with REST + WebSocket
- **Multi-Model Support**: Intelligent routing (phi3:mini, codellama, mistral)
- **Agent Orchestration**: 4 specialized agents (conversation, code, research, planning)
- **MCP Server**: Model Context Protocol with 5+ tools
- **Memory Service**: ChromaDB-based conversation persistence
- **Voice Service**: Edge-TTS + Google Speech Recognition
- **Task Service**: System info, file search, app launching
- **4 Client Types**: Desktop GUI, Web, CLI, System Tray
- **Wake Word Detection**: "Hey Atulya" activation
- **Emotional Intelligence**: JARVIS-like warm personality
- **Deployment**: Docker + Docker Compose support

### Clients
- Desktop Voice GUI (Tkinter)
- Web Client (HTML/CSS/JS)
- CLI Client (Python)
- System Tray App (with wake word)

### Services
- Agent Orchestrator
- MCP Server
- AI Service (multi-model routing)
- Memory Service (conversation storage)
- Voice Service (TTS/STT)
- Task Service (automation)

### Testing
- Deep testing suite (10 basic tests)
- Advanced features testing (5 tests)
- 87% overall pass rate

---

## Upcoming Features

### [1.1.0] - Planned
- LLaVA vision model (image/screen understanding)
- LangGraph workflow orchestration
- Advanced MCP tools (calendar, email, notes)
- Proactive AI (offers suggestions)
- Learning from interactions
- Custom wake word training

### [1.2.0] - Planned
- Mobile client (React Native)
- Multi-language support
- Voice cloning
- Plugin system
- Cloud sync
- Team collaboration features

---

**Legend:**
- `Added` - New features
- `Changed` - Changes in existing functionality
- `Deprecated` - Soon-to-be removed features
- `Removed` - Removed features
- `Fixed` - Bug fixes
- `Security` - Vulnerability fixes

