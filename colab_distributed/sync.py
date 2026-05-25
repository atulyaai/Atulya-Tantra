#!/usr/bin/env python3
"""sync.py — Poll Google Drive for completed worker checkpoints, download to local.

Runs as a loop or background process.

Usage:
    python sync.py                          # run once (download all new)
    python sync.py --watch                  # poll every 60s
"""
import subprocess, time, sys, os

from rclone_utils import find_rclone

RCLONE_REMOTE = os.environ.get("ATULYA_RCLONE_REMOTE", "gdrive").rstrip(":")
DRIVE_ROOT = os.environ.get("ATULYA_DRIVE_ROOT", "npdna_training").strip("/")
DRIVE_REMOTE = f"{RCLONE_REMOTE}:{DRIVE_ROOT}/workers/"
LOCAL_SYNC_DIR = "F:/Atulya Tantra/colab_sync/workers/"
os.makedirs(LOCAL_SYNC_DIR, exist_ok=True)

def sync_once():
    rclone = find_rclone()
    if not rclone:
        print("rclone not found. Install it first, then run: rclone config")
        return None
    print(f"🔄 Syncing workers from Drive...")
    result = subprocess.run([
        rclone, "copy", DRIVE_REMOTE, LOCAL_SYNC_DIR,
        "--exclude", "*.jsonl",  # don't download raw data
        "--verbose"
    ], capture_output=True, text=True)
    print(result.stdout[-500:] if result.stdout else "  No changes")
    return result

if __name__ == "__main__":
    if "--watch" in sys.argv:
        print("👁️  Watching for new workers (poll every 60s)...")
        while True:
            sync_once()
            time.sleep(60)
    else:
        sync_once()
