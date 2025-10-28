# 🧠 Atulya Tantra AGI

<div align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge&logo=github" alt="MIT License">
  <img src="https://img.shields.io/badge/Status-Maintained-success?style=for-the-badge" alt="Status">
</div>

<div align="center">
  <h3>✨ Minimal, modular AGI runtime for production use</h3>
  <p>Default model: TinyLlama | Extensible: Any LLM provider | Clean architecture</p>
</div>

---

## 🎯 What It Is

Atulya Tantra AGI is a clean, minimal artificial general intelligence runtime. It focuses on clarity, testability, and extensibility.

### Key Characteristics
- 🎯 **Minimal Core**: Only essential modules for production
- 🔌 **Pluggable LLM**: TinyLlama default, easy to swap providers
- 🧪 **Testable**: Clean interfaces with comprehensive test coverage
- 📦 **Modular**: Clear separation of concerns
- ⚡ **Performance**: Fast reasoning and response generation

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
│   ├── llm/           # LLM providers & router
│   ├── agents/        # Multi-agent framework
│   ├── conversation/  # Natural language processing
│   ├── memory/        # Conversation & knowledge storage
│   ├── api/           # REST API endpoints
│   └── dynamic/       # Self-evolution capabilities
├── Test/              # Canonical test suite
├── scripts/           # Developer utilities
└── requirements.txt   # Dependencies
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

## 🧪 Running Tests

```bash
# Run all tests
pytest Test/

# Run specific test suite
pytest Test/test_agents.py

# With coverage
pytest --cov=Core Test/
```

## 📊 Features

- ✅ Multi-agent orchestration
- ✅ Natural language conversation
- ✅ Memory & knowledge graph
- ✅ RESTful API with FastAPI
- ✅ TinyLlama integration (CPU-friendly)
- ✅ Pluggable provider architecture

## 🔗 Links

- 📖 [Documentation](#)
- 🐛 [Issue Tracker](https://github.com/atulyaai/Atulya-Tantra/issues)
- 💡 [Discussions](https://github.com/atulyaai/Atulya-Tantra/discussions)

## 🤝 Contributing

Contributions welcome. Please read our contributing guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

<div align="center">
  <sub>Built with ❤️ by the Atulya Tantra team</sub>
</div>
