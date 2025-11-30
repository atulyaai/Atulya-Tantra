# Atulya Tantra - Service Access Guide

## 🌐 Public Access (via atulvij.com)

All services are accessible through your domain:

### Main Application
- **URL:** https://atulvij.com
- **Description:** Main web interface for Atulya Tantra AI
- **Protocol:** HTTPS (SSL enabled)

### Monitoring & Metrics
- **Prometheus Metrics:** https://atulvij.com/metrics
- **Description:** Application metrics for monitoring

## 🔧 Server-Local Access (for administration)

These are accessible only from the server itself:

### Prometheus
- **URL:** http://localhost:9090
- **Description:** Metrics database and query interface
- **Access:** SSH tunnel or local only

### Grafana
- **URL:** http://localhost:3000
- **Default Login:** admin/admin
- **Description:** Dashboards and visualization
- **Access:** SSH tunnel or local only

### Node Exporter
- **URL:** http://localhost:9100/metrics
- **Description:** System metrics (CPU, RAM, disk)
- **Access:** Local only

## 🔐 Exposing Grafana via Domain (Optional)

To access Grafana at https://grafana.atulvij.com:

1. Add DNS record: `grafana.atulvij.com` → Server IP
2. Create Nginx config for Grafana
3. Get SSL certificate with Certbot

**Command to expose Grafana:**
```bash
sudo ./expose_grafana.sh
```

## 📊 Current Configuration

- **App:** Binds to `0.0.0.0:5000` → Proxied via Nginx to https://atulvij.com
- **Prometheus:** Binds to `localhost:9090` → Local only
- **Grafana:** Binds to `localhost:3000` → Local only
- **Node Exporter:** Binds to `localhost:9100` → Local only

This setup ensures:
- ✅ Public can access the AI app
- ✅ Monitoring tools are secure (local only)
- ✅ Can expose monitoring if needed
