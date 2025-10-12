#!/bin/bash
# Setup script for Linux/Mac

echo "🚀 Setting up Atulya Tantra..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found! Please install Python 3.8+"
    exit 1
fi

# Check Ollama
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama not found! Installing..."
    curl https://ollama.ai/install.sh | sh
fi

# Install dependencies
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

# Download model
echo "🤖 Downloading AI model..."
ollama pull gemma2:2b

echo "✅ Setup complete!"
echo ""
echo "🎤 Run: python3 voice_gui.py"

