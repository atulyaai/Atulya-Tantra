# Atulya Tantra - Advanced Voice AI Assistant

<div align="center">

![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)

**A powerful, fast, and intelligent voice-enabled AI assistant built with state-of-the-art language models**

[Features](#features) • [Installation](#installation) • [Usage](#usage) • [Configuration](#configuration) • [Architecture](#architecture)

</div>

---

## 🌟 Features

### Core Capabilities
- 🎤 **Voice Interaction** - Natural speech-to-text and text-to-speech
- 🧠 **Intelligent Responses** - Powered by Qwen2-0.5B (ultra-fast) or Qwen2.5-1.5B models
- 💾 **Long-term Memory** - RAG-based memory system with ChromaDB
- 🔧 **Tool Integration** - Price checking, web search, fact verification
- ⚡ **Optimized Performance** - 16 vCPU support, sub-second responses
- 🌐 **Web Interface** - Modern web UI for easy interaction

### Advanced Features
- **Dynamic Configuration** - Environment-based settings, no hardcoded values
- **Automatic Memory Extraction** - Learns user preferences and facts
- **Knowledge Caching** - Smart caching for faster repeated queries
- **MCP Integration** - Model Context Protocol for enhanced capabilities
- **Modular Architecture** - Clean, maintainable codebase

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- 16GB+ RAM recommended (4GB minimum)
- HuggingFace account and token
- Linux, macOS, or Windows WSL

### Installation

```bash
# Clone the repository
git clone https://github.com/atulyaai/Atulya-Tantra.git
cd Atulya-Tantra

# Run installation script
chmod +x install.sh
./install.sh

# Edit .env file with your HuggingFace token
nano .env
```

The installation script will:
- ✅ Install system dependencies (ffmpeg, portaudio, espeak)
- ✅ Create Python virtual environment
- ✅ Install Python packages
- ✅ Set up configuration files
- ✅ Optionally install as system service

---

## 💻 Usage

### Command Line
```bash
# Activate virtual environment
source venv/bin/activate

# Start the assistant
python main.py
```

### Web Interface
```bash
# Start web server
./start_web.sh

# Open browser to http://localhost:5000
```

### As System Service
```bash
# If installed as service during setup
sudo systemctl start atulya-tantra
sudo systemctl status atulya-tantra
sudo journalctl -u atulya-tantra -f  # View logs
```

---

## ⚙️ Configuration

### Environment Variables
Create a `.env` file (copied from `.env.example`):

```env
# Required
HUGGINGFACE_TOKEN=your_token_here

# Optional
MODEL_NAME=Qwen/Qwen2-0.5B-Instruct
DEVICE=cpu
TANTRA_ENV=production
LOG_LEVEL=INFO
```

### Configuration File
Edit `config.yaml` for advanced settings:

```yaml
model:
  name: "Qwen/Qwen2-0.5B-Instruct"  # Ultra-fast model
  device: "cpu"
  max_memory: "60GB"

generation:
  temperature: 0.6
  max_tokens: 256
  top_p: 0.85
```

### Model Options
- **Qwen2-0.5B-Instruct** - Ultra-fast, ~0.5-1s response time (default)
- **Qwen2.5-1.5B-Instruct** - Balanced speed and quality
- **Custom models** - Any HuggingFace compatible model

---

## 🏗️ Architecture

### Project Structure
```
Atulya-Tantra/
├── atulya_tantra/          # Core package
│   ├── core.py             # Main engine
│   ├── text_ai.py          # Language model
│   ├── memory.py           # RAG memory system
│   ├── config_loader.py    # Dynamic configuration
│   ├── constants.py        # System constants
│   ├── utils.py            # Utilities
│   ├── base_model.py       # Base AI model class
│   ├── conversation_manager.py
│   ├── memory_extractor.py
│   ├── mcp_client.py       # MCP integration
│   ├── price_checker.py    # Price tools
│   ├── knowledge_cache.py  # Smart caching
│   ├── intelligent_router.py
│   ├── voice_input.py      # Speech-to-text
│   └── voice_output.py     # Text-to-speech
├── web/                    # Web interface
├── mcp_servers/            # MCP server configs
├── config.yaml             # Main configuration
├── main.py                 # CLI entry point
├── install.sh              # Installation script
└── requirements.txt        # Python dependencies
```

### Key Components

**TantraEngine** - Central orchestrator
- Intent detection
- Tool execution (price, search, facts)
- Memory retrieval (RAG)
- Response generation
- Memory storage

**Memory System** - ChromaDB + Sentence Transformers
- Conversation history
- User preferences
- Facts and knowledge
- Automatic extraction

**Configuration System** - Dynamic and flexible
- Environment-based configs
- No hardcoded values
- Easy customization

---

## 🛠️ Development

### Adding New Features
```python
from atulya_tantra import TantraEngine, get_config

# Initialize with custom config
engine = TantraEngine(config_path="custom_config.yaml")

# Process messages
response = engine.process_message("Hello!")
```

### Using Configuration
```python
from atulya_tantra import get_config
from atulya_tantra.constants import DEFAULT_MODELS

config = get_config()
model_name = config.get_model_name()
max_tokens = config.get_max_tokens()
```

---

## 📊 Performance

### Benchmarks (16 vCPU, 64GB RAM)
- **Response Time**: 0.5-1.0s (Qwen2-0.5B)
- **Throughput**: ~7-10 tokens/second
- **Memory Usage**: ~3-4GB (0.5B model)
- **Startup Time**: ~5-10 seconds

### Optimization
- 16 CPU threads utilized
- Smart caching for repeated queries
- Efficient memory management
- Optimized model loading

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Author

**Atulya (Atul Vij)**
- GitHub: [@atulyaai](https://github.com/atulyaai)

---

## 🙏 Acknowledgments

- Qwen team for excellent language models
- HuggingFace for model hosting
- ChromaDB for vector database
- All open-source contributors

---

## 📞 Support

For issues, questions, or suggestions:
- Open an [Issue](https://github.com/atulyaai/Atulya-Tantra/issues)
- Check [Documentation](https://github.com/atulyaai/Atulya-Tantra/wiki)

---

<div align="center">

**Made with ❤️ by Atulya**

⭐ Star this repo if you find it helpful!

</div>
