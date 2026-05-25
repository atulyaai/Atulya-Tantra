#!/usr/bin/env python3
"""deploy.py — Upload current NP-DNA checkpoint + dataset + scripts to Google Drive.

Run once after setting up rclone or gdown.

Usage:
    python deploy.py               # interactive
    python deploy.py --rclone      # use rclone (default)
    python deploy.py --gdown       # use gdown
"""
import subprocess, sys, os

from rclone_utils import find_rclone

LOCAL_CHECKPOINT = "F:/Atulya Tantra/outputs/npdna/"
LOCAL_DATA = "F:/Atulya Tantra/data/"
LOCAL_SCRIPTS = "F:/Atulya Tantra/scripts/"
LOCAL_COLAB = "F:/Atulya Tantra/colab_distributed"
LOCAL_TANTRA = "F:/Atulya Tantra/tantra/"
LOCAL_ATULYA = "F:/Atulya Tantra/atulya/"

RCLONE_REMOTE = os.environ.get("ATULYA_RCLONE_REMOTE", "gdrive").rstrip(":")
DRIVE_ROOT = os.environ.get("ATULYA_DRIVE_ROOT", "npdna_training").strip("/")
DRIVE_REMOTE = f"{RCLONE_REMOTE}:{DRIVE_ROOT}/"

def upload_rclone():
    rclone = find_rclone()
    if not rclone:
        print("rclone not found. Install it first, then run: rclone config")
        return
    print("📤 Uploading via rclone...")
    subprocess.run([rclone, "copy", LOCAL_CHECKPOINT, DRIVE_REMOTE + "base_checkpoint/"])
    subprocess.run([rclone, "copy", LOCAL_DATA, DRIVE_REMOTE + "dataset/"])
    subprocess.run([rclone, "copy", LOCAL_TANTRA, DRIVE_REMOTE + "source/tantra/"])
    subprocess.run([rclone, "copy", LOCAL_ATULYA, DRIVE_REMOTE + "source/atulya/"])
    subprocess.run([rclone, "copy", "F:/Atulya Tantra/pyproject.toml", DRIVE_REMOTE + "source/"])
    subprocess.run([rclone, "copy", "F:/Atulya Tantra/requirements.txt", DRIVE_REMOTE + "source/"])
    subprocess.run([rclone, "copy", LOCAL_SCRIPTS, DRIVE_REMOTE + "scripts/"])
    subprocess.run([rclone, "copy", LOCAL_COLAB + "/train.ipynb", DRIVE_REMOTE + "scripts/"])
    print("✅ Upload complete!")

def upload_gdown():
    """Alternative using gdown (needs Drive API setup)."""
    print("⚠️  gdown upload not yet implemented — use rclone or manual upload.")
    print("    Upload these folders to npdna_training/ in your Drive:")
    print(f"      {LOCAL_CHECKPOINT} → base_checkpoint/")
    print(f"      {LOCAL_DATA} → dataset/")
    print(f"      {LOCAL_COLAB}/train.ipynb → scripts/")

if __name__ == "__main__":
    method = sys.argv[1] if len(sys.argv) > 1 else "rclone"
    if "rclone" in method:
        upload_rclone()
    else:
        upload_gdown()
