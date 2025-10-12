# 📦 Installation Guide

Complete step-by-step guide to install Atulya Tantra on your system.

---

## Prerequisites

### 1. Python 3.8+
Download from: https://www.python.org/downloads/

**Windows:** Check "Add Python to PATH" during installation

**Verify:**
```powershell
python --version
```

### 2. Ollama
Download from: https://ollama.ai/

**Windows:** Run installer, it auto-starts

**Linux/Mac:**
```bash
curl https://ollama.ai/install.sh | sh
```

**Verify:**
```powershell
ollama --version
```

### 3. Git (Optional, for cloning)
Download from: https://git-scm.com/

---

## Quick Installation

### Option 1: Automatic (Windows)
```powershell
# Run the installer
.\INSTALL.bat
```

This will:
- Install Python dependencies
- Download recommended AI model (phi3:mini or gemma2:2b)
- Setup everything automatically

### Option 2: Manual

#### Step 1: Install Python Dependencies
```powershell
# Core dependencies
pip install -r requirements.txt

# Server dependencies (optional)
pip install -r requirements_server.txt
```

#### Step 2: Download AI Model
```powershell
# Fast model (recommended for voice)
ollama pull gemma2:2b

# OR balanced model
ollama pull phi3:mini

# OR powerful model
ollama pull mistral:7b-instruct-v0.3-q4_0
```

#### Step 3: Test Installation
```powershell
# Start Ollama (if not running)
ollama serve

# Test voice GUI
python voice_gui.py
```

---

## Model Comparison

| Model | Size | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| **gemma2:2b** | 1.6GB | ⚡⚡⚡⚡⚡ | ⭐⭐⭐⭐ | **Voice (Recommended)** |
| **phi3:mini** | 2.3GB | ⚡⚡⚡ | ⭐⭐⭐⭐⭐ | Balanced |
| **mistral:7b** | 4.1GB | ⚡⚡ | ⭐⭐⭐⭐⭐ | Complex tasks |
| **tinyllama:1.1b** | 637MB | ⚡⚡⚡⚡⚡ | ⭐⭐ | Ultra-fast |

**Recommendation:** Start with `gemma2:2b` for best voice experience!

---

## Advanced Installation

### Server Mode (Multi-Device)

#### 1. Install Server Dependencies
```powershell
pip install -r requirements_server.txt
```

#### 2. Start Server
```powershell
.\START_SERVER.bat
# OR
cd server
python main.py
```

#### 3. Access From Clients
- **Desktop:** `python voice_gui.py`
- **Web:** Open `clients/web/index.html` in browser
- **CLI:** `python clients/cli/atulya_cli.py`
- **Background:** `python system_tray_app.py`

### Docker Deployment

#### 1. Install Docker
Download from: https://www.docker.com/

#### 2. Deploy
```bash
docker-compose up -d
```

This starts:
- Atulya server on port 8000
- Ollama on port 11434

Access web interface: http://localhost:8000

---

## Troubleshooting

### Issue: "ollama command not found"
**Solution:** Install Ollama from https://ollama.ai/

### Issue: "No module named 'speech_recognition'"
**Solution:** 
```powershell
pip install -r requirements.txt
```

### Issue: Model download slow/stuck
**Solution:**
```powershell
# Cancel download
Ctrl+C

# Try smaller model
ollama pull gemma2:2b
```

### Issue: Voice not working
**Solution:**
- Check microphone permissions
- Install audio dependencies:
```powershell
pip install pyaudio speechrecognition edge-tts pygame
```

### Issue: Server won't start
**Solution:**
- Check port 8000 is free
- Install server dependencies:
```powershell
pip install -r requirements_server.txt
```

---

## Configuration

### Change AI Model
Edit `config/settings.py`:
```python
default_model = "gemma2:2b"  # Change to your preferred model
```

### Change Voice
Edit `voice_gui.py`:
```python
# Line ~530 - TTS voice
communicate = edge_tts.Communicate(text, 'en-US-AriaNeural')
# Options: en-US-GuyNeural, en-GB-SoniaNeural, etc.
```

### Adjust Response Length
Edit `voice_gui.py`:
```python
# Line ~420 - num_predict controls length
'num_predict': 10 if is_simple else 30  # Increase for longer responses
```

---

## Verify Installation

Run the test suite:
```powershell
python test_models.py
```

This will:
- Test all installed models
- Compare speed & quality
- Recommend best model for you

---

## Next Steps

1. **Start Voice Chat:** `python voice_gui.py`
2. **Read Documentation:** Check `README.md`
3. **Explore Features:** See `ROADMAP.md`
4. **Report Issues:** Open GitHub issue
5. **Contribute:** See `CONTRIBUTING.md`

---

## Getting Help

- **Documentation:** `README.md`, `ROADMAP.md`
- **Issues:** GitHub Issues
- **Community:** Coming soon!

---

**🎉 Congratulations! Atulya Tantra is ready to use!** 🚀

