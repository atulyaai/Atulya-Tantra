#!/bin/bash
# AI Assistant - Universal Launcher (Linux/Windows)
# Version: 1.0.0

echo "🤖 Starting AI Assistant..."

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Detect OS and Python
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    OS="windows"
    PYTHON_CMD="python"
else
    OS="linux"
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    else
        PYTHON_CMD="python"
    fi
fi

echo "✅ OS: $OS, Python: $PYTHON_CMD"

# Check if Python is installed
$PYTHON_CMD --version >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Python is not installed. Please install Python 3.8+ first."
    read -p "Press Enter to exit..."
    exit 1
fi

# Check if main file exists
if [ ! -f "tantra.py" ]; then
    echo "❌ tantra.py not found in current directory"
    read -p "Press Enter to exit..."
    exit 1
fi

echo "✅ Tantra AI Assistant file found"

# Install dependencies
echo "🔍 Installing dependencies..."
if [ "$OS" = "windows" ]; then
    pip install SpeechRecognition pyttsx3 pyaudio tkinter pillow requests pywin32
else
    pip3 install SpeechRecognition pyttsx3 pyaudio tkinter pillow requests
fi

echo ""
echo "🚀 Launching AI Assistant..."
echo "   - Native GUI with voice features"
echo "   - Continuous conversation mode"
echo "   - Background/foreground operation"
echo ""

# Start the application
$PYTHON_CMD tantra.py

echo ""
echo "👋 AI Assistant has been closed."
read -p "Press Enter to exit..."
