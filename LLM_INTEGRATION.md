# Hybrid LLM Integration Guide

> **JARVIS now has intelligent conversation with multiple LLM backends!**

---

## 🎯 Quick Start: 3 Conversation Modes

Atulya supports 3 conversation modes that automatically degrade gracefully:

### Mode 1: Template Mode (Fastest, Works Offline)
```python
from atulya.conversation import ConversationalAI

# Uses predefined JARVIS templates - instant responses
jarvis = ConversationalAI(mode="template")
response = jarvis.process_input("Hello")
# → "Good day, Sir. How may I assist you?"
```

### Mode 2: LLM Mode (Smartest, Requires API)
```python
# Tries cloud LLM (OpenAI/Anthropic) or local model
jarvis = ConversationalAI(mode="llm")
response = jarvis.process_input("What's 2+2?")
# → Smart response from GPT-4/Claude/Ollama
```

### Mode 3: Hybrid Mode (Best of Both, RECOMMENDED)
```python
# Default mode - tries LLM first, falls back to templates
jarvis = ConversationalAI(mode="hybrid")  # This is default!
response = jarvis.process_input("Hello world")
# → Uses LLM if available, falls back to template if not
```

---

## 🏗️ Architecture: Hybrid Fallback Chain

```
User Input
    ↓
[Hybrid Mode Active?]
    ├─ YES → Try LLM (in order):
    │          1. Cloud LLM (OpenAI/Anthropic)
    │          2. Ollama Local 
    │          3. Local Pattern Model
    │          └─ If all fail → Use Templates
    │
    └─ NO (Template mode) → Use templates directly
                  ↓
        [JARVIS Response to User]
```

---

## 📦 LLM Providers Available

### 1. **Local Pattern Model** (Always Available)
```python
from atulya.llm.conversation_model import LocalConversationModel

model = LocalConversationModel()
response = model.process_input("Tell me a joke")
```

**Features:**
- ✅ Always works (built-in knowledge base)
- ✅ No API cost
- ✅ Instant responses

---

### 2. **Ollama** (Local LLM, Recommended)
```bash
# Install: https://ollama.ai
ollama serve
ollama pull neural-chat
# JARVIS auto-detects!
```

**Best Models:**
- `neural-chat` (4.5GB) - Recommended
- `mistral` (26GB) - Faster
- `llama2` (3.5GB) - Good alternative

---

### 3. **OpenAI** (Cloud, Most Capable)
```bash
export OPENAI_API_KEY=sk-your-key
# JARVIS auto-detects GPT-4!
```

---

### 4. **Anthropic Claude** (Cloud)
```bash
export ANTHROPIC_API_KEY=sk-ant-your-key
# JARVIS auto-detects Claude!
```

---

## 🚀 Setup Instructions

### Enable Ollama (Recommended)
```bash
curl https://ollama.ai/install.sh | sh
ollama serve
# In another terminal:
ollama pull neural-chat
```

### Enable OpenAI
```bash
export OPENAI_API_KEY=sk-your-key
```

### Enable Anthropic
```bash
export ANTHROPIC_API_KEY=sk-ant-your-key
```

---

## 📊 Provider Priority

Hybrid engine selects providers in this order:
1. **Local Model** (always available)
2. **Ollama** (if running)
3. **OpenAI** (if API key set)
4. **Anthropic** (if API key set)

---

## 🎓 Usage Examples

```python
from atulya import Atulya

atulya = Atulya(name="JARVIS")

# Uses hybrid mode by default
response = atulya.conversation.process_input("What's the weather?")

# Force specific mode
response = atulya.conversation.process_input(
    "What can you do?",
    use_llm=False  # Template only
)

# Check available providers
from atulya.llm import HybridLLMEngine
hybrid = HybridLLMEngine()
print(hybrid.get_available_providers())
```

---

## ✨ Features

| Feature | Local | Ollama | OpenAI | Claude |
|---------|-------|--------|--------|--------|
| Always works | ✅ | - | - | - |
| No API cost | ✅ | ✅ | - | - |
| Runs offline | ✅ | ✅ | - | - |
| High quality | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

**Your JARVIS now has intelligent conversation! 🤖✨**