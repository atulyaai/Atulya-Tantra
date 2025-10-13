#!/bin/bash
# Atulya Tantra - Docker Entrypoint Script

set -e

echo "======================================"
echo "🤖 Atulya Tantra - Starting..."
echo "======================================"

# Start Ollama service in background
echo "📦 Starting Ollama service..."
ollama serve &
OLLAMA_PID=$!

# Wait for Ollama to be ready
echo "⏳ Waiting for Ollama to start..."
sleep 5

# Pull default model if not already present
echo "📥 Checking for AI model..."
if ! ollama list | grep -q "phi3:mini"; then
    echo "📥 Downloading phi3:mini model (lightweight, ~2.2GB)..."
    ollama pull phi3:mini
    echo "✅ Model downloaded successfully"
else
    echo "✅ Model already present"
fi

# Run any initialization commands
echo "🔧 Initializing system..."
python -c "from core.logger import get_logger; logger = get_logger('docker'); logger.info('System initialized')"

# Run the command passed to docker run
echo "🚀 Starting application..."
exec "$@"

