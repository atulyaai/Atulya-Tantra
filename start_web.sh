#!/bin/bash

# Start Web Interface (Manual / Debug)
# For production, use: systemctl start atulya-tantra

cd "$(dirname "$0")"

# Activate venv if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Set environment variables
export FLASK_APP=web/app.py
export FLASK_ENV=production

echo "Starting Atulya Tantra Web Interface (Manual Mode)..."
echo "Note: For production, use 'systemctl start atulya-tantra'"

# Optimized for 16 vCPU (Aggressive)
# 9 workers * 4 threads = 36 concurrent requests
gunicorn -w 9 --threads 4 -b 0.0.0.0:5000 --timeout 120 --worker-class gthread web.app:app
