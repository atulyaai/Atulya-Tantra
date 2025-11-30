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

gunicorn -w 2 -b 0.0.0.0:5000 --timeout 120 web.app:app
