#!/bin/bash
# Test runner script for Atulya Tantra
# Run from WSL: wsl -d Ubuntu -- bash /mnt/f/Atulya\ Tantra/github_push/Atulya-Tantra/run_tests.sh

set -e

PROJECT_DIR="/mnt/f/Atulya Tantra/github_push/Atulya-Tantra"
VENV_DIR="/tmp/atulya-test-venv"

echo "=== Atulya Tantra Test Runner ==="
echo ""

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Install dependencies
echo "Installing test dependencies..."
pip install pytest pytest-asyncio pytest-cov -q 2>/dev/null

# Install project dependencies
echo "Installing project dependencies..."
pip install torch --index-url https://download.pytorch.org/whl/cpu -q 2>/dev/null || true
pip install numpy psutil cryptography croniter edge-tts -q 2>/dev/null || true
pip install fastapi uvicorn python-multipart -q 2>/dev/null || true

echo ""
echo "Running tests..."
echo ""

# Run tests
cd "$PROJECT_DIR"

echo "=== Test Suite 1: Vector Store ==="
python -m pytest tests/test_vector_store.py -v --tb=short 2>&1 || true
echo ""

echo "=== Test Suite 2: Chat History Integration ==="
python -m pytest tests/test_chat_history_integration.py -v --tb=short 2>&1 || true
echo ""

echo "=== Test Suite 3: Intent Classification ==="
python -m pytest tests/test_intent_classification.py -v --tb=short 2>&1 || true
echo ""

echo "=== Test Suite 4: Spirit Chat & Wake Word ==="
python -m pytest tests/test_spirit_chat.py -v --tb=short 2>&1 || true
echo ""

echo "=== Test Suite 5: Memory Manager Integration ==="
python -m pytest tests/test_memory_manager_integration.py -v --tb=short 2>&1 || true
echo ""

echo "=== All New Feature Tests Complete ==="
