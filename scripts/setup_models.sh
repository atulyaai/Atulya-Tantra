#!/bin/bash
# Atulya Tantra - Model Setup Script
# Downloads recommended lightweight models for the system

echo "======================================"
echo "🤖 Atulya Tantra - Model Setup"
echo "======================================"
echo

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama not found!"
    echo "Please install Ollama first: https://ollama.com"
    exit 1
fi

echo "✅ Ollama found"
echo

# Start Ollama service if not running
echo "🔧 Ensuring Ollama service is running..."
ollama serve &> /dev/null &
sleep 2

echo "📥 Downloading recommended models..."
echo

# Model 1: phi3:mini (Recommended - Small & Fast)
echo "1️⃣  phi3:mini (Recommended)"
echo "   Size: ~2.2GB | Speed: Fast | Quality: Good"
if ollama list | grep -q "phi3:mini"; then
    echo "   ✅ Already installed"
else
    echo "   📥 Downloading..."
    ollama pull phi3:mini
    echo "   ✅ Installed successfully"
fi
echo

# Model 2: gemma:2b (Alternative - Even Smaller)
echo "2️⃣  gemma:2b (Alternative - Smaller)"
echo "   Size: ~1.4GB | Speed: Very Fast | Quality: Good"
read -p "   Install gemma:2b? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if ollama list | grep -q "gemma:2b"; then
        echo "   ✅ Already installed"
    else
        echo "   📥 Downloading..."
        ollama pull gemma:2b
        echo "   ✅ Installed successfully"
    fi
fi
echo

# Model 3: mistral (Optional - Better Quality)
echo "3️⃣  mistral (Optional - Better Quality)"
echo "   Size: ~4.1GB | Speed: Moderate | Quality: Excellent"
read -p "   Install mistral? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if ollama list | grep -q "mistral"; then
        echo "   ✅ Already installed"
    else
        echo "   📥 Downloading..."
        ollama pull mistral
        echo "   ✅ Installed successfully"
    fi
fi
echo

echo "======================================"
echo "✅ Model Setup Complete!"
echo "======================================"
echo
echo "Installed models:"
ollama list
echo
echo "To use a specific model, edit configuration/settings.py:"
echo "  default_model = 'phi3:mini'  # or 'gemma:2b' or 'mistral'"
echo

