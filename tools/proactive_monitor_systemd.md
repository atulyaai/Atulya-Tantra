# Atulya Proactive Monitor - Systemd Service

## Install as systemd timer (runs every 5 minutes)

```bash
# Copy service files
sudo cp tools/proactive_monitor.service /etc/systemd/system/
sudo cp tools/proactive_monitor.timer /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable --now proactive_monitor.timer

# Check status
systemctl list-timers --all | grep proactive
journalctl -u proactive_monitor.service -f
```

## Service file: /etc/systemd/system/proactive_monitor.service

```
[Unit]
Description=Atulya Proactive Health Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/home/ubuntu/Atulya-Tantra
ExecStart=/home/ubuntu/Atulya-Tantra/.venv/bin/python tools/proactive_monitor.py
User=ubuntu
Group=ubuntu
# Limit resources
MemoryMax=500M
CPUQuota=50%
TimeoutSec=300
# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=atulya-proactive-monitor

[Install]
WantedBy=multi-user.target
```

## Timer file: /etc/systemd/system/proactive_monitor.timer

```
[Unit]
Description=Run Atulya Proactive Monitor every 5 minutes
Requires=proactive_monitor.service

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
RandomizedDelaySec=30s
Persistent=true

[Install]
WantedBy=timers.target
```

## Manual run

```bash
# Run once manually
/home/ubuntu/Atulya-Tantra/.venv/bin/python tools/proactive_monitor.py

# Run with verbose output
/home/ubuntu/Atulya-Tantra/.venv/bin/python tools/proactive_monitor.py 2>&1 | tee /tmp/health_check.log
```

## Health check results

Results are saved to: `data/logs/health_check_results.json`

Example output:
```json
{
  "timestamp": "2026-10-13T16:30:00Z",
  "checks": {
    "mediapipe_runtime": {"ok": true, "severity": "error"},
    "gesture_model": {"ok": true, "severity": "error"},
    "vision_model": {"ok": false, "error": "Vision model missing", "severity": "warning"},
    "webui_integrity": {"ok": true, "severity": "warning"},
    "python_env": {"ok": true, "severity": "warning"},
    "disk_space": {"ok": true, "free_gb": 15.2, "severity": "warning"},
    "service_health": {"ok": true, "severity": "info"},
    "config_validity": {"ok": true, "severity": "warning"},
    "core_protection": {"ok": true, "severity": "info"},
    "log_rotation": {"ok": true, "severity": "info"}
  },
  "summary": {"ok": 9, "warning": 1, "error": 0, "critical": 0, "fixed": 0}
}
```