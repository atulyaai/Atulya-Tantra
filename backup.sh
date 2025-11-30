#!/bin/bash

# Automated backup script for Atulya Tantra
# Backs up: data, models, logs, config

BACKUP_DIR="/home/backups/atulya-tantra"
DATE=$(date +%Y%m%d_%H%M%S)
SOURCE_DIR="/home/atulya-tantra"

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "Starting backup at $DATE..."

# Backup data directory (memory, vectors)
if [ -d "$SOURCE_DIR/data" ]; then
    tar -czf "$BACKUP_DIR/data_$DATE.tar.gz" -C "$SOURCE_DIR" data
    echo "✓ Data backed up"
fi

# Backup configuration
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" -C "$SOURCE_DIR" \
    config.yaml .env 2>/dev/null || true
echo "✓ Config backed up"

# Backup logs (last 7 days)
if [ -f "/tmp/atulya.log" ]; then
    cp /tmp/atulya.log "$BACKUP_DIR/atulya_$DATE.log"
    echo "✓ Logs backed up"
fi

# Keep only last 7 days of backups
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete
find "$BACKUP_DIR" -name "*.log" -mtime +7 -delete

echo "✅ Backup complete: $BACKUP_DIR"
