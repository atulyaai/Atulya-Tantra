#!/bin/bash

# Expose Grafana via Nginx on grafana.atulvij.com

set -e

echo "Setting up Grafana public access..."

# Create Nginx config for Grafana
sudo cat > /etc/nginx/sites-available/grafana.atulvij.com << 'EOF'
server {
    server_name grafana.atulvij.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    listen 80;
}
EOF

# Enable site
sudo ln -sf /etc/nginx/sites-available/grafana.atulvij.com /etc/nginx/sites-enabled/

# Test and reload Nginx
sudo nginx -t && sudo systemctl reload nginx

# Get SSL certificate
echo "Getting SSL certificate..."
sudo certbot --nginx -d grafana.atulvij.com --non-interactive --agree-tos --email admin@atulvij.com

echo "✅ Grafana is now accessible at https://grafana.atulvij.com"
