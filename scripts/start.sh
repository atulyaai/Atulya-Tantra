#!/bin/bash

# Atulya Tantra - Startup Script
# Version: 2.5.0

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Python is installed
check_python() {
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed"
        exit 1
    fi
    
    python_version=$(python3 --version | cut -d' ' -f2)
    log_info "Python version: $python_version"
}

# Check if virtual environment exists
check_venv() {
    if [ ! -d "venv" ]; then
        log_warning "Virtual environment not found. Creating one..."
        python3 -m venv venv
        log_success "Virtual environment created"
    fi
}

# Activate virtual environment
activate_venv() {
    log_info "Activating virtual environment..."
    source venv/bin/activate
    log_success "Virtual environment activated"
}

# Install dependencies
install_dependencies() {
    log_info "Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    log_success "Dependencies installed"
}

# Check environment configuration
check_config() {
    if [ ! -f ".env" ]; then
        log_warning "Environment file not found. Creating from example..."
        cp env.example .env
        log_warning "Please edit .env file with your configuration"
    fi
}

# Create necessary directories
create_directories() {
    log_info "Creating necessary directories..."
    mkdir -p logs
    mkdir -p data
    mkdir -p data/cache
    mkdir -p data/uploads
    mkdir -p data/vectors
    log_success "Directories created"
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."
    alembic upgrade head
    log_success "Database migrations completed"
}

# Start the application
start_app() {
    log_info "Starting Atulya Tantra Level 5 AGI System..."
    
    # Set environment variables
    export PYTHONPATH="${PYTHONPATH}:$(pwd)"
    
    # Start the application
    python start.py
}

# Main function
main() {
    log_info "Starting Atulya Tantra Level 5 AGI System..."
    
    # Check prerequisites
    check_python
    check_venv
    activate_venv
    
    # Setup
    install_dependencies
    check_config
    create_directories
    run_migrations
    
    # Start application
    start_app
}

# Handle script arguments
case "${1:-start}" in
    "start")
        main
        ;;
    "install")
        check_python
        check_venv
        activate_venv
        install_dependencies
        create_directories
        log_success "Installation completed"
        ;;
    "migrate")
        check_venv
        activate_venv
        run_migrations
        ;;
    "help")
        echo "Usage: $0 [start|install|migrate|help]"
        echo "  start   - Start the application (default)"
        echo "  install - Install dependencies and setup"
        echo "  migrate - Run database migrations"
        echo "  help    - Show this help message"
        ;;
    *)
        echo "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac
