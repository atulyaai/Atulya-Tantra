#!/bin/bash

# Atulya Tantra - Auto-Installation Script for Linux/macOS
# Version: 2.0.1
# This script automatically detects the system and installs Atulya Tantra from zero

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Banner
print_banner() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    Atulya Tantra AGI System                ║"
    echo "║                    Auto-Installation Script                ║"
    echo "║                        Version 2.0.1                       ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# System detection
detect_system() {
    log "Detecting system..."
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
        if command -v apt-get &> /dev/null; then
            PACKAGE_MANAGER="apt"
        elif command -v yum &> /dev/null; then
            PACKAGE_MANAGER="yum"
        elif command -v dnf &> /dev/null; then
            PACKAGE_MANAGER="dnf"
        elif command -v pacman &> /dev/null; then
            PACKAGE_MANAGER="pacman"
        elif command -v zypper &> /dev/null; then
            PACKAGE_MANAGER="zypper"
        else
            error "Unsupported Linux distribution"
            exit 1
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        PACKAGE_MANAGER="brew"
    else
        error "Unsupported operating system: $OSTYPE"
        exit 1
    fi
    
    log "Detected: $OS with $PACKAGE_MANAGER package manager"
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        warning "Running as root. This is not recommended for security reasons."
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Install system dependencies
install_system_deps() {
    log "Installing system dependencies..."
    
    case $PACKAGE_MANAGER in
        "apt")
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip python3-venv git curl wget build-essential
            ;;
        "yum"|"dnf")
            sudo $PACKAGE_MANAGER install -y python3 python3-pip git curl wget gcc gcc-c++ make
            ;;
        "pacman")
            sudo pacman -S --noconfirm python python-pip git curl wget base-devel
            ;;
        "zypper")
            sudo zypper install -y python3 python3-pip git curl wget gcc gcc-c++
            ;;
        "brew")
            if ! command -v brew &> /dev/null; then
                log "Installing Homebrew..."
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            fi
            brew install python3 git curl wget
            ;;
    esac
    
    log "System dependencies installed successfully"
}

# Install Python dependencies
install_python_deps() {
    log "Installing Python dependencies..."
    
    # Create virtual environment
    python3 -m venv .venv
    source .venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install requirements
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
    else
        error "requirements.txt not found!"
        exit 1
    fi
    
    log "Python dependencies installed successfully"
}

# Setup data directories
setup_directories() {
    log "Setting up data directories..."
    
    mkdir -p data/{logs,uploads,cache,security,analytics,database}
    mkdir -p data/models/{audio,vision,text}
    
    # Set proper permissions
    chmod 755 data
    chmod 755 data/*
    
    log "Data directories created successfully"
}

# Initialize configuration
init_config() {
    log "Initializing configuration..."
    
    if [[ ! -f ".env" ]]; then
        if [[ -f ".env.example" ]]; then
            cp .env.example .env
            warning "Created .env from .env.example. Please edit it with your API keys."
        else
            error ".env.example not found!"
            exit 1
        fi
    fi
    
    log "Configuration initialized"
}

# Install optional dependencies
install_optional_deps() {
    log "Installing optional dependencies..."
    
    # Install Ollama if not present
    if ! command -v ollama &> /dev/null; then
        info "Installing Ollama for local AI models..."
        curl -fsSL https://ollama.ai/install.sh | sh
    fi
    
    # Install FFmpeg for audio processing
    case $PACKAGE_MANAGER in
        "apt")
            sudo apt-get install -y ffmpeg
            ;;
        "yum"|"dnf")
            sudo $PACKAGE_MANAGER install -y ffmpeg
            ;;
        "pacman")
            sudo pacman -S --noconfirm ffmpeg
            ;;
        "zypper")
            sudo zypper install -y ffmpeg
            ;;
        "brew")
            brew install ffmpeg
            ;;
    esac
    
    log "Optional dependencies installed"
}

# Run system tests
run_tests() {
    log "Running system tests..."
    
    source .venv/bin/activate
    
    if [[ -d "testing" ]]; then
        python -m pytest testing/ -v
    else
        warning "No tests found, skipping..."
    fi
    
    log "Tests completed"
}

# Initialize database
init_database() {
    log "Initializing database..."
    
    source .venv/bin/activate
    
    if [[ -f "scripts/init_admin_db.py" ]]; then
        python scripts/init_admin_db.py
    else
        warning "Database initialization script not found, skipping..."
    fi
    
    log "Database initialized"
}

# Create systemd service (Linux only)
create_service() {
    if [[ "$OS" == "linux" ]]; then
        log "Creating systemd service..."
        
        SERVICE_FILE="/etc/systemd/system/atulya-tantra.service"
        
        sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Atulya Tantra AGI System
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/.venv/bin
ExecStart=$(pwd)/.venv/bin/python server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        
        sudo systemctl daemon-reload
        sudo systemctl enable atulya-tantra
        
        log "Systemd service created. Use 'sudo systemctl start atulya-tantra' to start"
    fi
}

# Main installation function
main() {
    print_banner
    
    log "Starting Atulya Tantra installation..."
    
    detect_system
    check_root
    install_system_deps
    install_python_deps
    setup_directories
    init_config
    install_optional_deps
    init_database
    run_tests
    create_service
    
    log "Installation completed successfully!"
    
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    Installation Complete!                  ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    echo -e "${BLUE}Next steps:${NC}"
    echo "1. Edit .env file with your API keys"
    echo "2. Start the server: source .venv/bin/activate && python server.py"
    echo "3. Access the web interface: http://localhost:8000"
    echo "4. Admin panel: http://localhost:8000/admin"
    
    if [[ "$OS" == "linux" ]]; then
        echo "5. Start as service: sudo systemctl start atulya-tantra"
    fi
}

# Run main function
main "$@"
