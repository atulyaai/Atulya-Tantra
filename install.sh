#!/bin/bash

# Atulya Tantra - Complete Installation Script
# Installs dependencies, sets up environment, and optionally installs as system service

set -e

echo "========================================"
echo "🌟 Atulya Tantra Installation Script 🌟"
echo "========================================"
echo ""

# Check Python version
echo "📌 Checking Python version..."
python3 --version || {
    echo "❌ Python 3 not found. Please install Python 3.8+."
    exit 1
}

# Install system dependencies
echo ""
echo "📦 Installing system dependencies..."

if command -v apt-get &> /dev/null; then
    echo "Detected Debian/Ubuntu system"
    sudo apt-get update
    sudo apt-get install -y ffmpeg portaudio19-dev espeak python3-dev python3-venv
elif command -v brew &> /dev/null; then
    echo "Detected macOS system"
    brew install ffmpeg portaudio espeak
elif command -v yum &> /dev/null; then
    echo "Detected RHEL/CentOS system"
    sudo yum install -y ffmpeg portaudio-devel espeak python3-devel
else
    echo "⚠️  Unknown system. Please install manually:"
    echo "   - ffmpeg"
    echo "   - portaudio"
    echo "   - espeak"
    echo ""
    read -p "Press Enter to continue anyway..."
fi

# Create virtual environment
echo ""
echo "🐍 Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
echo ""
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
echo ""
echo "📚 Installing Python dependencies (this may take 10-30 minutes)..."
pip install -r requirements.txt

# Setup environment file
echo ""
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo "✓ .env created from .env.example"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your HUGGINGFACE_TOKEN"
else
    echo "✓ .env file already exists"
fi

# Create necessary directories
echo ""
echo "📁 Creating data directories..."
mkdir -p data/vectors models/cache logs
echo "✓ Directories created"

# Ask about service installation
echo ""
read -p "📋 Install as system service? (y/N): " install_service

if [[ $install_service =~ ^[Yy]$ ]]; then
    SERVICE_NAME="atulya-tantra.service"
    SERVICE_FILE="$(pwd)/$SERVICE_NAME"
    SYSTEMD_PATH="/etc/systemd/system/$SERVICE_NAME"
    
    if [ ! -f "$SERVICE_FILE" ]; then
        echo "❌ Error: Service file not found at $SERVICE_FILE"
    else
        echo ""
        echo "🔧 Installing systemd service..."
        sudo cp "$SERVICE_FILE" "$SYSTEMD_PATH"
        sudo systemctl daemon-reload
        sudo systemctl enable "$SERVICE_NAME"
        
        echo ""
        read -p "Start service now? (y/N): " start_now
        if [[ $start_now =~ ^[Yy]$ ]]; then
            sudo systemctl start "$SERVICE_NAME"
            echo ""
            echo "Service status:"
            sudo systemctl status "$SERVICE_NAME" --no-pager
        fi
        
        echo ""
        echo "✅ Service installed!"
        echo ""
        echo "Service commands:"
        echo "  Start:   sudo systemctl start $SERVICE_NAME"
        echo "  Stop:    sudo systemctl stop $SERVICE_NAME"
        echo "  Status:  sudo systemctl status $SERVICE_NAME"
        echo "  Logs:    sudo journalctl -u $SERVICE_NAME -f"
    fi
fi

# Summary
echo ""
echo "========================================"
echo "✅ Installation Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Activate virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "2. Edit .env file and add your HUGGINGFACE_TOKEN:"
echo "   nano .env"
echo ""
echo "3. Start Atulya Tantra:"
echo "   python main.py"
echo ""
echo "   Or use the web interface:"
echo "   ./start_web.sh"
echo ""
echo "🌟 Enjoy your AI assistant!"
echo ""
