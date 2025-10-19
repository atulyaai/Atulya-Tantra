# Atulya Tantra - Level 5 Autonomous AGI System

[![Version](https://img.shields.io/badge/version-2.5.0-blue.svg)](https://github.com/yourusername/atulya-tantra)
[![Status](https://img.shields.io/badge/status-production--ready-green.svg)](https://github.com/yourusername/atulya-tantra)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Atulya Tantra** is a Level 5 Autonomous AGI system designed to be the ultimate AI assistant, combining the conversational intelligence of ChatGPT with the advanced capabilities of Claude Anthropic, plus autonomous decision-making and system control capabilities.

## 🎯 **Current Status: v2.5.0 "Level 5 AGI Foundation"**

✅ **Phase 0 Complete**: Clean Architecture Refactoring  
✅ **Phase 1 Complete**: Core AI Intelligence  
✅ **Phase 2 Complete**: Modern UI  

🚀 **Next**: Phase 3 (Admin Panel), Phase 4 (Testing), Phase 5 (Autonomous AI), Phase 6 (Production)

## 🧠 **Core Features**

### **Intelligent AI Routing**
- **Task Classification**: Automatically detects coding, research, creative, simple, and general tasks
- **Sentiment Analysis**: Identifies frustrated, urgent, positive, negative, excited, neutral emotions
- **Smart Model Selection**: Routes to optimal models (Ollama, OpenAI, Anthropic) based on task type and complexity
- **Context-Aware Responses**: Uses conversation history for better responses

### **Advanced Memory System**
- **Semantic Search**: ChromaDB + SentenceTransformer for finding relevant conversation history
- **Knowledge Graph**: NetworkX-based relationship storage for topics and entities
- **Conversation Memory**: Intelligent context management with topic extraction
- **Persistent Storage**: All conversations saved with embeddings for future reference

### **Modern UI**
- **ChatGPT-Style Interface**: Clean, professional design inspired by ChatGPT
- **Claude Anthropic Color Theme**: Orange accent (#ff6b35) with professional grays
- **Responsive Design**: Perfect experience on desktop, tablet, and mobile
- **Dark Mode Support**: Automatic dark mode detection and styling
- **Advanced Features**: Auto-resize input, loading animations, keyboard shortcuts

### **Production-Ready Architecture**
- **Clean Modular Design**: Layered architecture with proper separation of concerns
- **Dependency Injection**: Loose coupling between components
- **Unified Configuration**: Single `config/config.yaml` source of truth
- **Error Handling**: Robust error handling throughout
- **Health Monitoring**: Comprehensive health checks and metrics

## 🏗️ **Architecture**

```
src/
├── api/           # FastAPI routes and dependencies
├── core/ai/       # AI intelligence (classifier, sentiment, router, context)
├── core/memory/   # Vector store and knowledge graph
├── services/      # Business logic (AI service, chat service)
└── config/        # Configuration and DI container

webui/
├── index.html     # Modern ChatGPT-style interface
└── src/           # Ready for React migration
```

## 🚀 **Quick Start**

### **Prerequisites**
- Python 3.11+
- Ollama (optional, for local models)
- OpenAI API key (optional)
- Anthropic API key (optional)

### **Installation**

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/atulya-tantra.git
   cd atulya-tantra
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   # Copy example environment file
   cp .env.example .env
   
   # Edit .env with your API keys
   OPENAI_API_KEY=your_openai_key
   ANTHROPIC_API_KEY=your_anthropic_key
   ```

4. **Start the server**
   ```bash
   python main.py
   ```

5. **Open your browser**
   ```
   http://localhost:8000
   ```

## 🧪 **Testing**

Run the comprehensive test suite:

```bash
# Test clean architecture
python test_architecture.py

# Test Phase 1 AI intelligence
python test_phase1.py

# Test Phase 2 UI
python test_phase2.py
```

## 📊 **Current Capabilities**

### **Level 2-3 AI Intelligence**
- ✅ Smart task classification and model routing
- ✅ Sentiment-aware responses with tone adjustment
- ✅ Semantic conversation memory with context relevance
- ✅ Professional ChatGPT-style UI
- ✅ Production-ready architecture

### **Supported AI Models**
- **Ollama**: `mistral:latest`, `gemma2:2b`, `qwen2.5-coder:7b`
- **OpenAI**: `gpt-4`, `gpt-3.5-turbo`
- **Anthropic**: `claude-3-sonnet-20240229`, `claude-3-haiku-20240307`

### **Task Types**
- **Coding**: Python, JavaScript, Java, C++, SQL, algorithms
- **Research**: Information gathering, analysis, explanations
- **Creative**: Writing, storytelling, content creation
- **Simple**: Greetings, basic questions, quick answers
- **General**: Complex reasoning, multi-step tasks

## 🎨 **UI Features**

- **Welcome Screen**: Professional landing with feature showcase
- **Chat Interface**: Message bubbles with avatars and metadata
- **Sidebar**: Clean conversation list with active states
- **Input Area**: Auto-resize textarea with action buttons
- **Responsive Design**: Perfect mobile experience with sidebar toggle
- **Keyboard Shortcuts**: Enter to send, Shift+Enter for new line
- **Loading States**: Smooth animations during AI generation

## 🔧 **Configuration**

All configuration is managed through `config/config.yaml`:

```yaml
app:
  name: "Atulya Tantra"
  version: "2.5.0"
  environment: development

ai:
  models:
    ollama:
      base_url: "http://localhost:11434"
      models:
        coding: "qwen2.5-coder:7b"
        simple: "gemma2:2b"
        complex: "mistral:latest"
    openai:
      api_key: ${OPENAI_API_KEY}
      models:
        default: "gpt-4"
    anthropic:
      api_key: ${ANTHROPIC_API_KEY}
      models:
        default: "claude-3-sonnet-20240229"

features:
  intelligent_routing: true
  sentiment_analysis: true
  autonomous_agents: true
  desktop_automation: true
  voice_interface: true
```

## 🛣️ **Roadmap**

### **Phase 3: Admin Panel** (Next)
- React-based admin dashboard
- Real-time analytics and monitoring
- WebSocket integration for live updates
- Advanced system management features

### **Phase 4: Testing Suite**
- Comprehensive unit, integration, and E2E tests
- Performance and security testing
- AI behavior validation
- Automated testing pipeline

### **Phase 5: Autonomous AI**
- Decision engine for autonomous operation
- Proactive monitoring and self-healing
- Self-learning capabilities
- Multi-agent orchestration

### **Phase 6: Production Deployment**
- Docker and Kubernetes deployment
- Security hardening and monitoring
- Scalability and performance optimization
- Enterprise features and compliance

## 🤝 **Contributing**

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 **Acknowledgments**

- **OpenAI** for GPT models
- **Anthropic** for Claude models
- **Ollama** for local model hosting
- **FastAPI** for the web framework
- **ChromaDB** for vector storage
- **NetworkX** for knowledge graphs

## 📞 **Support**

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/yourusername/atulya-tantra/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/atulya-tantra/discussions)

---

**Atulya Tantra** - Building the future of AI assistance, one conversation at a time. 🚀