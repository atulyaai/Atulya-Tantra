#!/bin/bash
"""
Atulya Tantra - Production Deployment Script
Version: 2.2.0 (WebMaster FINAL)
"""

set -e

echo "🚀 Atulya Tantra v2.2.0 - Production Deployment"
echo "=================================================="

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "❌ This script should not be run as root for security reasons"
   exit 1
fi

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.8+ is required. Found: $python_version"
    exit 1
fi

echo "✅ Python version check passed: $python_version"

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Install production dependencies
echo "🏭 Installing production dependencies..."
pip install gunicorn[gthread] supervisor

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data/{logs,uploads,cache,security,analytics}
mkdir -p webui/static
mkdir -p models/{audio,vision,text}

# Set permissions
echo "🔐 Setting permissions..."
chmod 755 scripts/*.sh
chmod 644 *.py
chmod 644 webui/*.html

# Run verification
echo "🧪 Running system verification..."
python scripts/verify_installation.py

if [ $? -eq 0 ]; then
    echo "✅ System verification passed!"
else
    echo "❌ System verification failed!"
    exit 1
fi

# Create systemd service file
echo "⚙️ Creating systemd service..."
sudo tee /etc/systemd/system/atulya-tantra.service > /dev/null <<EOF
[Unit]
Description=Atulya Tantra AGI System
After=network.target

[Service]
Type=exec
User=$USER
Group=$USER
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/.venv/bin
ExecStart=$(pwd)/.venv/bin/gunicorn server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
echo "🔄 Enabling service..."
sudo systemctl daemon-reload
sudo systemctl enable atulya-tantra.service

# Create nginx configuration (optional)
echo "🌐 Creating nginx configuration..."
sudo tee /etc/nginx/sites-available/atulya-tantra > /dev/null <<EOF
server {
    listen 80;
    server_name localhost;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        alias $(pwd)/webui/static/;
    }
}
EOF

# Enable nginx site (if nginx is installed)
if command -v nginx &> /dev/null; then
    sudo ln -sf /etc/nginx/sites-available/atulya-tantra /etc/nginx/sites-enabled/
    sudo nginx -t && sudo systemctl reload nginx
    echo "✅ Nginx configuration created"
else
    echo "⚠️ Nginx not found, skipping nginx configuration"
fi

# Create environment file template
echo "📝 Creating environment template..."
cp .env.example .env
echo "⚠️ Please edit .env file with your API keys"

# Start the service
echo "🚀 Starting Atulya Tantra service..."
sudo systemctl start atulya-tantra.service

# Wait for service to start
sleep 5

# Check service status
if sudo systemctl is-active --quiet atulya-tantra.service; then
    echo "✅ Service started successfully!"
    echo ""
    echo "🌐 Access URLs:"
    echo "   Main Interface: http://localhost:8000/webui"
    echo "   Admin Panel:    http://localhost:8000/admin"
    echo "   API Docs:       http://localhost:8000/docs"
    echo "   Health Check:   http://localhost:8000/health"
    echo ""
    echo "🔧 Service Management:"
    echo "   Start:   sudo systemctl start atulya-tantra"
    echo "   Stop:    sudo systemctl stop atulya-tantra"
    echo "   Restart: sudo systemctl restart atulya-tantra"
    echo "   Status:  sudo systemctl status atulya-tantra"
    echo "   Logs:    sudo journalctl -u atulya-tantra -f"
    echo ""
    echo "🎉 Atulya Tantra v2.2.0 is now running in production mode!"
else
    echo "❌ Service failed to start. Check logs:"
    sudo journalctl -u atulya-tantra --no-pager -l
    exit 1
fi
