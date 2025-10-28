# 🧠 Atulya Tantra AGI

<div align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge&logo=github" alt="MIT License">
  <img src="https://img.shields.io/badge/Version-3.0.3-success?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/Status-Production-ready-success?style=for-the-badge" alt="Status">
</div>

<div align="center">
  <h3>✨ Advanced AGI system with emotional intelligence, autonomous operations, and multi-agent architecture</h3>
  <p>TinyLlama default model | Extensible LLM providers | Clean architecture</p>
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
- **AGI Reasoning**: Advanced decision-making and goal-oriented behavior
- **Multi-Agent System**: 5 specialized AI agents working in orchestration
- **Emotional Intelligence**: Sentiment analysis and personality-driven responses
- **Conversation Engine**: Natural language processing and context awareness
- **Memory System**: Knowledge graphs and vector storage for long-term memory
- **Autonomous Operations**: Self-monitoring, task scheduling, and auto-healing
- **RESTful API**: FastAPI-based web interface for integration
- **Dynamic Evolution**: Self-improving code generation and installation

### 🔌 LLM Architecture
- **Default**: TinyLlama (CPU-friendly, 1.1B parameters)
- **Pluggable Providers**: Easy to add OpenAI, Anthropic, Ollama, or any LLM
- **Category-based routing**: Select optimal model for chat, code, vision, etc.
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

```bash
# Clone the repository
git clone https://github.com/atulyaai/Atulya-Tantra.git
cd Atulya-Tantra

# Install dependencies
pip install -r requirements.txt

# Run the API server
python Core/api/main.py
```

Access the API at `http://localhost:8000/docs`

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
