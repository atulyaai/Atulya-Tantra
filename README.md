# Atulya Tantra - Advanced Voice AI Assistant

<div align="center">

![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)
![Status](https://img.shields.io/badge/status-production--ready-success.svg)

**A powerful, fast, and intelligent voice-enabled AI assistant built with state-of-the-art language models.**

[Features](#-features) • [Installation](#-quick-start) • [Usage](#-usage) • [About Us](#-about-us) • [Roadmap](#-roadmap)

</div>

---

## 🌟 Features

### Core Capabilities
- 🎤 **Voice Interaction** - Natural speech-to-text and text-to-speech with wake word detection
- 🧠 **Intelligent Responses** - Powered by Qwen2-0.5B (ultra-fast) or Qwen2.5-1.5B models
- 💾 **Long-term Memory** - RAG-based memory system with ChromaDB to remember facts and preferences
- 🔧 **Tool Integration** - Real-time price checking, web search, and fact verification
- ⚡ **Optimized Performance** - 16 vCPU support, sub-second responses on standard hardware
- 🌐 **Web Interface** - Modern, responsive web UI for easy interaction

### Advanced Features
- **Dynamic Configuration** - Environment-based settings, no hardcoded values
- **Automatic Memory Extraction** - Learns user preferences and facts from conversation
- **Knowledge Caching** - Smart caching for faster repeated queries
- **MCP Integration** - Model Context Protocol for enhanced capabilities
- **Modular Architecture** - Clean, maintainable codebase designed for scalability

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

## 👥 About Us

**Atulya AI** is dedicated to creating accessible, high-performance AI solutions that respect user privacy and run locally.

**Atulya Tantra** represents our vision of a personal AI assistant that is:
- **Private:** Runs entirely on your hardware, your data stays with you.
- **Fast:** Optimized for speed without compromising intelligence.
- **Capable:** Integrated with real-world tools and long-term memory.

Our team is passionate about pushing the boundaries of local AI inference and creating tools that empower users.

---

## 🗺️ Roadmap

We are constantly improving Atulya Tantra. Here's what's coming next:

- [ ] **Multi-modal Support:** Re-integrating vision capabilities with optimized models
- [ ] **Home Automation:** Integration with Home Assistant and IoT devices
- [ ] **Voice Cloning:** Custom voice profiles for text-to-speech
- [ ] **Mobile App:** Companion app for Android and iOS
- [ ] **Plugin System:** Easy community-contributed extensions

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
│   ├── tools.py            # Search, Price, Routing
│   ├── voice_input.py      # Speech-to-text
│   └── voice_output.py     # Text-to-speech
├── web/                    # Web interface
├── config.yaml             # Main configuration
├── main.py                 # CLI entry point
└── install.sh              # Installation script
```

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

<div align="center">

**Made with ❤️ by Atulya**

⭐ Star this repo if you find it helpful!

</div>
