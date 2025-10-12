# 🤖 AI Models

This directory contains model configurations and management.

## 📁 Structure

```
models/
├── README.md              # This file
├── configs/               # Model configuration files
├── prompts/               # System prompts for different models
└── cache/                 # Model cache (gitignored)
```

## 🎯 Supported Models

### Recommended for Voice
- **gemma2:2b** - Fastest, best for voice (2-3s response)
- **phi3:mini** - Balanced speed/quality

### Specialized Models
- **mistral:7b** - Complex reasoning
- **codellama:7b** - Code generation
- **llava:7b** - Vision (images/screenshots)

## 📥 Download Models

```bash
# Fast voice model
ollama pull gemma2:2b

# Balanced model
ollama pull phi3:mini

# Powerful model
ollama pull mistral:7b-instruct-v0.3-q4_0

# Code model
ollama pull codellama:7b

# Vision model (coming soon)
ollama pull llava:7b
```

## ⚙️ Model Configuration

Models are configured in `server/models/model_router.py` and `config/settings.py`.

## 🔮 Coming Soon

- Fine-tuned models for Atulya personality
- Custom wake word models
- Voice cloning models
- Multi-language models

