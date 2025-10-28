# 🧠 Atulya Tantra AGI

<div align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge&logo=github" alt="MIT License">
  <img src="https://img.shields.io/badge/Version-4.0.0-success?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/Status-Production-ready-success?style=for-the-badge" alt="Status">
</div>

<div align="center">
  <h3>✨ Advanced AGI system with real AI responses, intelligent automation, and multi-provider LLM support</h3>
  <p>Ollama | OpenAI | Anthropic | Intelligent System Commands | Voice Interface</p>
</div>

---

## 📌 Table of Contents

- [What is Atulya Tantra AGI?](#-what-is-atulya-tantra-agi)
- [Comparison: Jarvis vs Skynet vs Atulya Tantra](#-comparison-jarvis-vs-skynet-vs-atulya-tantra)
- [Quick Start](#-quick-start)
- [Architecture](#-architecture)
- [LLM Providers](#-llm-providers)
- [API Examples](#-api-examples)
- [Gallery](#-gallery)
- [Our Roadmap](#-our-roadmap)
- [Features](#-features)
- [Running Tests](#-running-tests)
- [Links](#-links)
- [Contributing](#-contributing)
- [License](#-license)

## 🎯 What is Atulya Tantra AGI?

Atulya Tantra AGI is an advanced artificial general intelligence system that integrates:

### 🤖 Core Capabilities
- **Real AI Responses**: No more hardcoded responses - uses actual LLM providers
- **Intelligent Automation**: Smart system commands with natural language understanding
- **Multi-Provider LLM Support**: Ollama (local), OpenAI, Anthropic with automatic fallback
- **Voice Interface**: Speech recognition and text-to-speech capabilities
- **System Control**: Window management, application launching, volume control
- **Live Data**: Weather, time, date, news, and web search integration
- **Memory System**: Conversation history and context awareness
- **AGI Reasoning**: Advanced decision-making and goal-oriented behavior

### 🔌 LLM Architecture
- **Primary**: Ollama with Gemma2:2b (local, private, fast)
- **Fallback**: OpenAI GPT-3.5-turbo (cloud, requires API key)
- **Alternative**: Anthropic Claude (cloud, requires API key)
- **Auto-Detection**: Automatically selects the best available provider
- **Intelligent Routing**: Context-aware response generation

### 🆕 Recent Improvements (v4.0.0)
- ✅ **Fixed Hardcoded Responses**: Now uses real AI instead of static text
- ✅ **Enhanced Automation**: Intelligent system command execution
- ✅ **Multi-LLM Support**: Seamless switching between providers
- ✅ **Better Error Handling**: Graceful fallbacks and user feedback
- ✅ **Improved Voice Interface**: Better speech recognition and TTS
- ✅ **Smart Commands**: Natural language understanding for system control
- **Provider Interface**: Clean abstraction for any LLM service

## 📊 Comparison: Jarvis vs Skynet vs Atulya Tantra

| Feature | Jarvis (Marvel) | Skynet (Terminator) | Atulya Tantra AGI |
|---------|----------------|---------------------|-------------------|
| **Purpose** | Personal assistant | Military AI | General AGI |
| **Intelligence** | Context-aware | Strategic planning | AGI reasoning |
| **Personality** | Emotional, helpful | Logical, ruthless | Adaptive, balanced |
| **Autonomy** | High (butler) | Extreme (leader) | Adaptive (orchestrator) |
| **AI Agents** | Single entity | Networked nodes | Multi-agent system |
| **Emotions** | Empathic | None | Emotional intelligence |
| **Learning** | Incremental | Exponential | Continuous evolution |
| **Ethics** | Human-aligned | Human-hostile | Ethics-aware |

### 🎯 Our Vision
We combine **Jarvis's helpful personality** with **Skynet's autonomous capabilities** while maintaining **human-aligned ethics**. Atulya Tantra is designed to be:
- As helpful as Jarvis
- As capable as Skynet
- As ethical as a human partner

## 📋 Quick Start

### Prerequisites
- Python 3.11+
- pip or conda

### Installation
```bash
# Clone the repository
git clone https://github.com/atulyaai/Atulya-Tantra.git
cd Atulya-Tantra

# Install dependencies
pip install -r requirements.txt
```

### Setup LLM Provider
```bash
# Option 1: Setup Ollama (Recommended - Local & Private)
python3 setup_llm_providers.py
# Follow instructions to install Ollama and pull Gemma2 model

# Option 2: Configure API keys
# Edit .env file with your OpenAI or Anthropic API keys
```

### Basic Usage
```bash
# Run the main application
python3 tantra.py

# Or test the AGI integration
python3 test_simple_agi.py
```

### Voice Commands Examples
- "What time is it?" - Get current time
- "What's the weather?" - Get weather information
- "Open Chrome" - Launch browser
- "Take a screenshot" - Capture screen
- "Search for Python tutorials" - Web search
- "Close window" - Close current window
- "What can you do?" - Get capabilities list

## 🏗️ Architecture

```
Atulya-Tantra/
├── Core/
│   ├── llm/           # LLM providers & router (TinyLlama, OpenAI, etc.)
│   ├── agents/         # 5 specialized AI agents
│   ├── conversation/   # Natural language processing
│   ├── memory/         # Knowledge graph & vector storage
│   ├── api/            # REST API endpoints
│   ├── dynamic/        # Self-evolution capabilities
│   └── monitoring/     # Health checks & metrics
├── Test/               # Comprehensive test suite
├── scripts/            # Developer utilities
├── .github/            # CI/CD workflows
└── requirements.txt    # Dependencies
```

## 🔌 LLM Providers

Default: **TinyLlama** (via HuggingFace Transformers)

```python
from Core.brain.llm_provider import generate_response

# Uses TinyLlama by default
response = generate_response("Hello!", provider="tinyllama")

# Easy to swap providers
response = generate_response("Hello!", provider="openai", config={"api_key": "..."})
```

## 📡 API Examples

<details>
<summary><strong>cURL: Chat message</strong></summary>

```bash
curl -X POST \
  http://localhost:8000/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{
        "user_id": "demo",
        "message": "Hello, what can you do?",
        "context": {}
      }'
```

</details>

<details>
<summary><strong>Python: Chat message</strong></summary>

```python
import requests

payload = {
    "user_id": "demo",
    "message": "Plan my day",
    "context": {}
}
r = requests.post("http://localhost:8000/api/chat/message", json=payload)
print(r.status_code, r.json())
```

</details>

<details>
<summary><strong>Python: Direct LLM call via provider shim</strong></summary>

```python
from Core.brain.llm_provider import generate_response

print(generate_response("Summarize benefits of AGI in 3 bullets."))
```

</details>

## 🖼️ Gallery

Place media in `assets/` and it will appear here.

<details open>
<summary><strong>Overview</strong></summary>

![Overview](assets/overview.png)

</details>

## 🎯 Our Roadmap

See [ROADMAP.md](ROADMAP.md) for detailed milestones:
- ✅ v3.0.x: Core AGI system with multi-agent architecture
- 🔄 v3.1.x: Advanced emotional intelligence and personality
- ⏳ v3.2.x: Enhanced autonomous operations
- 🔮 v4.0.x: Full general intelligence capabilities

## 📊 Features

- ✅ Multi-agent orchestration (5 specialized agents)
- ✅ Natural language conversation with context awareness
- ✅ Memory & knowledge graph storage
- ✅ RESTful API with FastAPI
- ✅ TinyLlama integration (CPU-friendly)
- ✅ Pluggable provider architecture
- ✅ Autonomous task scheduling
- ✅ Self-monitoring and health checks
- ✅ Emotional intelligence & sentiment analysis
- ✅ Dynamic code evolution

## 🧪 Running Tests

```bash
# Run all tests
pytest Test/

# Run specific test suite
pytest Test/test_agents.py

# With coverage
pytest --cov=Core Test/
```

## 🔗 Links

- 📖 [Documentation](https://github.com/atulyaai/Atulya-Tantra#readme)
- 🐛 [Issue Tracker](https://github.com/atulyaai/Atulya-Tantra/issues)
- 💡 [Discussions](https://github.com/atulyaai/Atulya-Tantra/discussions)
- 📋 [Roadmap](ROADMAP.md)
- 📝 [Changelog](CHANGELOG.md)

## 🤝 Contributing

Contributions welcome! Please read our contributing guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

<div align="center">
  <sub>Built with ❤️ by the Atulya Tantra team</sub>
  <br>
  <sub>Combining the best of Jarvis and Skynet with ethical AGI</sub>
</div>
