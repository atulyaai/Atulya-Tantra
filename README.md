# Atulya Tantra AGI

> **The Future of AI Assistance** - Where JARVIS meets Skynet

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Status](https://img.shields.io/badge/status-active-success.svg)]()
[![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)](ROADMAP.md)

**Atulya Tantra** is a comprehensive AGI (Artificial General Intelligence) system that combines the conversational elegance of JARVIS with the autonomous capabilities of Skynet. It's designed to be your personal AI companion—intelligent, proactive, and capable of both thinking and acting.

---

## ✨ Key Features

### 🎭 JARVIS-like Personality
- **Natural Conversations**: Context-aware dialogue with emotional intelligence
- **Proactive Assistance**: Anticipates your needs and offers timely suggestions
- **Voice Interface**: "Hey JARVIS" wake word with continuous voice interaction
- **Multi-Modal Understanding**: Process text, voice, images, and documents
- **Sophisticated Personality**: Professional, witty, loyal, and eloquent

### 🛡️ Skynet-like Autonomy
- **Task Automation**: Schedule and execute tasks automatically
- **Self-Monitoring**: Continuous health checks and performance tracking
- **Auto-Healing**: Automatic error detection and recovery
- **System Control**: Manage your computer, applications, and workflows
- **Autonomous Decision Making**: Intelligent operations with safety guardrails

### 🤖 Multi-Agent Architecture
- **Code Agent**: Programming assistance, debugging, code review
- **Research Agent**: Web search, fact-checking, information gathering
- **Creative Agent**: Writing, brainstorming, content generation
- **Data Agent**: Data analysis, visualization, processing
- **System Agent**: File management, process control, automation

### 🧠 Advanced AI Capabilities
- **Multi-Provider Support**: Ollama (local), OpenAI (GPT-4), Anthropic (Claude)
- **Streaming Responses**: Real-time response generation
- **Vector Memory**: Semantic search and long-term memory
- **Knowledge Graphs**: Relationship mapping and reasoning
- **RAG System**: Retrieval Augmented Generation for enhanced accuracy

### 🌐 Modern Web Interface
- **ChatGPT-style UI**: Clean, intuitive chat interface
- **Real-time Streaming**: See responses as they're generated
- **File Upload**: Drag-and-drop documents and images
- **Voice Input**: Click-to-speak functionality
- **Dark/Light Themes**: Customizable appearance
- **Mobile Responsive**: Works on desktop, tablet, and mobile

### 🔒 Enterprise-Grade Security
- **JWT Authentication**: Secure token-based authentication
- **Role-Based Access Control**: Admin, user, and agent roles
- **Rate Limiting**: Protect against abuse
- **Encryption**: Data encrypted at rest and in transit
- **Audit Logging**: Track all security events

### 📊 Monitoring & Observability
- **Prometheus Metrics**: Comprehensive performance metrics
- **Structured Logging**: JSON-formatted, searchable logs
- **Health Checks**: Continuous system monitoring
- **Grafana Dashboards**: Real-time visualization
- **Cost Tracking**: Monitor API usage and costs

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Ollama** (for local AI) - [Download](https://ollama.ai)
- **Git**

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/atulyaai/Atulya-Tantra.git
   cd Atulya-Tantra
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Pull the AI model** (for local use)
   ```bash
   ollama pull gemma2:2b
   ```

4. **Configure environment**
   ```bash
   # Copy the environment template
   cp env.example .env
   
   # Edit .env and add your API keys (optional)
   # For local-only use, no API keys needed!
   ```

5. **Start the application**
   
   **Option A: Legacy Desktop Version** (Current)
   ```bash
   # Windows
   python tantra.py
   
   # Linux/Mac
   ./start.sh
   ```
   
   **Option B: Production Web Version** (Coming Soon)
   ```bash
   # Start the FastAPI server
   python Core/main.py
   
   # Or use Docker
   docker-compose up
   ```

6. **Access the interface**
   - **Desktop GUI**: Opens automatically
   - **Web UI**: Visit http://localhost:8000

---

## 📖 Usage Guide

### Voice Commands

Wake up JARVIS:
```
"Hey JARVIS"
```

Natural conversation:
```
"What's the weather like today?"
"Tell me about quantum computing"
"Write a Python function to sort a list"
"Open Chrome and search for AI news"
```

System control:
```
"Close this window"
"Take a screenshot"
"Lock my screen"
"Open Calculator"
"Minimize all windows"
```

### Web Interface

1. **Send Messages**: Type in the input box or click the microphone for voice
2. **Upload Files**: Drag and drop images or documents for analysis
3. **View History**: Access past conversations from the sidebar
4. **Settings**: Customize AI provider, personality, and preferences
5. **Agents**: Select specialized agents for specific tasks

### API Usage

```python
import requests

# Send a message
response = requests.post(
    "http://localhost:8000/api/chat/send",
    json={
        "message": "Hello JARVIS!",
        "conversation_id": "optional-id",
        "user_id": "user123"
    },
    headers={"Authorization": "Bearer YOUR_JWT_TOKEN"}
)

# Stream responses
import sseclient

messages = sseclient.SSEClient(
    "http://localhost:8000/api/chat/stream",
    json={"message": "Tell me a story"}
)

for msg in messages:
    print(msg.data)
```

---

## 🏗️ Architecture

```
Atulya-Tantra/
├── Core/                      # Main application code
│   ├── main.py               # FastAPI entry point
│   ├── config/               # Configuration management
│   │   ├── settings.py       # App settings
│   │   └── logging.py        # Logging config
│   ├── agents/               # Multi-agent system
│   │   ├── base_agent.py     # Base agent class
│   │   ├── orchestrator.py   # Agent coordination
│   │   ├── code_agent.py     # Code assistance
│   │   ├── research_agent.py # Web search
│   │   ├── creative_agent.py # Content creation
│   │   ├── data_agent.py     # Data analysis
│   │   └── system_agent.py   # System control
│   ├── api/                  # REST API endpoints
│   │   ├── chat.py          # Chat endpoints
│   │   ├── auth.py          # Authentication
│   │   ├── agents.py        # Agent management
│   │   └── admin.py         # Admin endpoints
│   ├── brain/               # AI/LLM integrations
│   │   ├── llm_provider.py  # Provider abstraction
│   │   ├── ollama_client.py # Ollama integration
│   │   ├── openai_client.py # OpenAI integration
│   │   └── anthropic_client.py # Anthropic integration
│   ├── memory/              # Memory systems
│   │   ├── vector_store.py  # ChromaDB integration
│   │   ├── knowledge_graph.py # NetworkX graphs
│   │   └── conversation_memory.py # Chat history
│   ├── jarvis/              # JARVIS features
│   │   ├── personality.py   # Personality engine
│   │   ├── proactive.py     # Proactive assistance
│   │   └── multimodal.py    # Vision/files
│   ├── skynet/              # Skynet features
│   │   ├── scheduler.py     # Task scheduling
│   │   ├── monitor.py       # System monitoring
│   │   └── healer.py        # Auto-healing
│   ├── tools/               # Utilities
│   └── models/              # Data models
├── Webui/                   # Web interface
│   ├── index.html          # Main page
│   ├── app.js              # Frontend logic
│   └── styles.css          # Styling
├── Scripts/                 # Deployment scripts
├── Data/                    # Data storage
├── Test/                    # Tests
└── Legacy/                  # Old code

```

### Technology Stack

**Backend**:
- FastAPI - Modern Python web framework
- SQLAlchemy - Database ORM
- Pydantic - Data validation
- Redis - Caching and sessions
- ChromaDB - Vector database
- NetworkX - Knowledge graphs

**AI/ML**:
- Ollama - Local AI models
- OpenAI - GPT-4/GPT-4-turbo
- Anthropic - Claude 3.5 Sonnet
- Sentence Transformers - Embeddings

**Frontend**:
- HTML5/CSS3/JavaScript
- Server-Sent Events - Streaming
- WebSocket - Real-time updates

**DevOps**:
- Docker - Containerization
- GitHub Actions - CI/CD
- Prometheus - Metrics
- Grafana - Dashboards

---

## 📚 Documentation

- **[Roadmap](ROADMAP.md)** - Detailed development plan
- **[API Documentation](http://localhost:8000/docs)** - Interactive API docs (when running)
- **[Contributing](CONTRIBUTING.md)** - Contribution guidelines
- **[Architecture](ARCHITECTURE.md)** - System architecture
- **[Deployment](DEPLOYMENT.md)** - Deployment guide

---

## 🔧 Configuration

### Environment Variables

Key configuration options in `.env`:

```bash
# AI Provider (ollama, openai, anthropic)
PRIMARY_AI_PROVIDER=ollama

# Ollama Settings
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma2:2b

# OpenAI Settings (optional)
OPENAI_API_KEY=your-key-here
OPENAI_MODEL=gpt-4-turbo

# Anthropic Settings (optional)
ANTHROPIC_API_KEY=your-key-here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# Database
DATABASE_TYPE=sqlite  # or postgresql, json
SQLITE_PATH=data/tantra.db

# Security
SECRET_KEY=change-me-in-production
JWT_SECRET=change-me-in-production

# Features (enable/disable)
VOICE_ENABLED=true
AUTONOMOUS_OPERATIONS=false  # Safety: off by default
```

### Feature Flags

Control which features are enabled:

- **streaming** - Real-time response streaming
- **voice_interface** - Voice input/output
- **vision** - Image understanding
- **file_attachments** - File upload support
- **personality_engine** - JARVIS personality
- **proactive_assistance** - Proactive suggestions
- **task_scheduling** - Automated tasks
- **self_monitoring** - System health monitoring
- **autonomous_operations** - Autonomous actions (requires explicit enable)

---

## 🧪 Testing

Run the test suite:

```bash
# Unit tests
pytest Test/test_capabilities.py
pytest Test/test_context.py

# Full test suite (coming soon)
pytest --cov=Core --cov-report=html

# Integration tests
pytest Test/integration/

# Performance tests
pytest Test/performance/
```

---

## 🚀 Deployment

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# Or build manually
docker build -t atulya-tantra .
docker run -p 8000:8000 atulya-tantra
```

### Production Deployment

```bash
# Using uvicorn with multiple workers
uvicorn Core.main:app --host 0.0.0.0 --port 8000 --workers 4

# Or use gunicorn
gunicorn Core.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment guides.

---

## 🎯 Roadmap

See our detailed [ROADMAP.md](ROADMAP.md) for the complete development plan.

### Current Status: v3.0.0 Development (5% Complete)

**Recently Completed**:
- ✅ Repository restructure
- ✅ Core configuration system
- ✅ Environment management

**In Progress**:
- 🔄 Multi-database architecture
- 🔄 Vector memory system
- 🔄 Multi-agent framework

**Coming Soon**:
- ⏳ Multi-provider AI support
- ⏳ JARVIS personality engine
- ⏳ Web API and modern UI
- ⏳ Autonomous operations
- ⏳ Advanced monitoring

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Quick Start for Contributors

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Code Style

- **Python**: Black formatting, flake8 linting, type hints with mypy
- **JavaScript**: ES6+, Prettier formatting
- **Commits**: Conventional commits format

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Ollama** - For making local AI accessible
- **OpenAI** - For GPT models
- **Anthropic** - For Claude models
- **FastAPI** - For the excellent web framework
- **All Contributors** - Thank you for your contributions!

---

## 🆘 Support

- **GitHub Issues**: [Report bugs](https://github.com/atulyaai/Atulya-Tantra/issues)
- **GitHub Discussions**: [Ask questions](https://github.com/atulyaai/Atulya-Tantra/discussions)
- **Documentation**: [Read the docs](ROADMAP.md)

---

## 🌟 Star History

If you find this project useful, please consider giving it a star ⭐

---

## 📊 Project Stats

![GitHub stars](https://img.shields.io/github/stars/atulyaai/Atulya-Tantra?style=social)
![GitHub forks](https://img.shields.io/github/forks/atulyaai/Atulya-Tantra?style=social)
![GitHub watchers](https://img.shields.io/github/watchers/atulyaai/Atulya-Tantra?style=social)

---

**Atulya Tantra** - Your Personal AGI Assistant 🚀

*"The future of AI assistance is here."*
