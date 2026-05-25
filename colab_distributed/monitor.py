#!/usr/bin/env python3
"""Full Colab distributed training manager.

Usage:
    python colab_distributed/monitor.py --setup
    python colab_distributed/monitor.py --sync
    python colab_distributed/monitor.py --watch
    python colab_distributed/monitor.py --merge
    python colab_distributed/monitor.py --check-rclone
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

from rclone_utils import find_rclone


LOCAL_CHECKPOINT = "F:/Atulya Tantra/outputs/npdna/"
LOCAL_DATA = "F:/Atulya Tantra/data/"
LOCAL_COLAB = "F:/Atulya Tantra/colab_distributed/"
LOCAL_TANTRA = "F:/Atulya Tantra/tantra/"
LOCAL_ATULYA = "F:/Atulya Tantra/atulya/"
LOCAL_PYPROJECT = "F:/Atulya Tantra/pyproject.toml"
LOCAL_REQUIREMENTS = "F:/Atulya Tantra/requirements.txt"
LOCAL_SYNC_DIR = "F:/Atulya Tantra/colab_sync/workers/"
os.makedirs(LOCAL_SYNC_DIR, exist_ok=True)

RCLONE_REMOTE = os.environ.get("ATULYA_RCLONE_REMOTE", "gdrive").rstrip(":")
DRIVE_ROOT = os.environ.get("ATULYA_DRIVE_ROOT", "npdna_training").strip("/")
DRIVE_REMOTE = f"{RCLONE_REMOTE}:{DRIVE_ROOT}"

RCLONE_CMD = find_rclone() or "rclone"
STATE_FILE = f"{LOCAL_COLAB}.monitor_state.json"
known_workers: set[str] = set()


def check_remote() -> bool:
    """Return True when rclone exists and the configured remote is authorized."""
    if not find_rclone():
        print("rclone not found. Run: winget install Rclone.Rclone")
        return False

    result = subprocess.run([RCLONE_CMD, "listremotes"], capture_output=True, text=True)
    remotes = {line.strip().rstrip(":") for line in result.stdout.splitlines()}
    if RCLONE_REMOTE not in remotes:
        print(f"rclone remote '{RCLONE_REMOTE}' is not configured.")
        print("Run this helper:")
        print("  powershell -ExecutionPolicy Bypass -File colab_distributed\\setup_rclone_drive.ps1")
        return False

    probe = subprocess.run([RCLONE_CMD, "lsd", f"{RCLONE_REMOTE}:"], capture_output=True, text=True)
    if probe.returncode != 0:
        print(f"rclone remote '{RCLONE_REMOTE}' exists but is not authorized.")
        print(f"Run: rclone config reconnect {RCLONE_REMOTE}:")
        return False
    return True


def load_state() -> float | None:
    global known_workers
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        known_workers.update(data.get("known_workers", []))
        return data.get("last_sync")
    return None


def save_state() -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"known_workers": sorted(known_workers), "last_sync": time.time()}, f)


def setup_drive() -> bool:
    """Deploy checkpoint, dataset, and notebook to Google Drive."""
    if not check_remote():
        return False

    print("Deploying to Drive...")
    steps = [
        (LOCAL_CHECKPOINT, f"{DRIVE_REMOTE}/base_checkpoint/"),
        (LOCAL_DATA, f"{DRIVE_REMOTE}/dataset/"),
        (LOCAL_TANTRA, f"{DRIVE_REMOTE}/source/tantra/"),
        (LOCAL_ATULYA, f"{DRIVE_REMOTE}/source/atulya/"),
        (LOCAL_PYPROJECT, f"{DRIVE_REMOTE}/source/"),
        (LOCAL_REQUIREMENTS, f"{DRIVE_REMOTE}/source/"),
        (f"{LOCAL_COLAB}/train.ipynb", f"{DRIVE_REMOTE}/scripts/"),
        (f"{LOCAL_COLAB}/train.ipynb", f"{DRIVE_REMOTE}/"),
    ]
    for src, dst in steps:
        if os.path.exists(src):
            subprocess.run([RCLONE_CMD, "copy", src, dst, "--verbose"], capture_output=True)
            print(f"  OK {os.path.basename(src.rstrip('/'))} -> Drive")
        else:
            print(f"  Missing, skipped: {src}")

    print_colab_link()
    print("Deploy complete.")
    return True


def print_colab_link() -> None:
    result = subprocess.run(
        [RCLONE_CMD, "lsjson", f"{DRIVE_REMOTE}/train.ipynb"],
        capture_output=True,
        text=True,
    )
    try:
        entries = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        entries = []

    if entries and entries[0].get("ID"):
        file_id = entries[0]["ID"]
        print("\nColab link:")
        print(f"  https://colab.research.google.com/drive/{file_id}")
        return

    print("\nCould not auto-read the notebook file ID.")
    print(f"Open Google Drive -> {DRIVE_ROOT} -> train.ipynb -> Open with -> Google Colab")


def sync_workers() -> list[tuple[str, str]]:
    """Download new worker checkpoints from Drive."""
    if not check_remote():
        return []

    subprocess.run(
        [
            RCLONE_CMD,
            "copy",
            f"{DRIVE_REMOTE}/workers/",
            LOCAL_SYNC_DIR,
            "--exclude",
            "*.jsonl",
            "--verbose",
        ],
        capture_output=True,
        text=True,
    )

    new_workers = []
    for worker_dir in os.listdir(LOCAL_SYNC_DIR):
        worker_path = os.path.join(LOCAL_SYNC_DIR, worker_dir)
        if not os.path.isdir(worker_path) or worker_dir in known_workers:
            continue
        if not os.path.exists(os.path.join(worker_path, "DONE")):
            continue

        ckpt_path = find_worker_checkpoint(worker_path)
        if ckpt_path:
            new_workers.append((worker_dir, ckpt_path))
            known_workers.add(worker_dir)

    save_state()
    return new_workers


def find_worker_checkpoint(worker_path: str) -> str | None:
    final_path = os.path.join(worker_path, "final.pt")
    if os.path.exists(final_path) and os.path.getsize(final_path) > 100:
        return final_path

    ckpt_dir = os.path.join(worker_path, "checkpoints")
    if not os.path.exists(ckpt_dir):
        return None

    checkpoints = sorted(f for f in os.listdir(ckpt_dir) if f.endswith(".pt"))
    if not checkpoints:
        return None

    ckpt_path = os.path.join(ckpt_dir, checkpoints[-1])
    if os.path.exists(ckpt_path) and os.path.getsize(ckpt_path) > 100:
        return ckpt_path
    return None


def merge_workers() -> str | None:
    """FedAvg merge all completed workers."""
    completed = []
    for worker_dir in os.listdir(LOCAL_SYNC_DIR):
        worker_path = os.path.join(LOCAL_SYNC_DIR, worker_dir)
        if not os.path.isdir(worker_path):
            continue
        if not os.path.exists(os.path.join(worker_path, "DONE")):
            continue
        ckpt_path = find_worker_checkpoint(worker_path)
        if ckpt_path:
            completed.append((worker_dir, ckpt_path))

    if not completed:
        print("No completed workers to merge.")
        return None

    import torch

    merged = None
    count = 0
    for name, path in completed:
        print(f"  + {name}")
        state = torch.load(path, map_location="cpu")
        if merged is None:
            merged = {key: value.clone() for key, value in state.items()}
        else:
            for key in merged:
                merged[key] += state[key]
        count += 1

    assert merged is not None
    for key in merged:
        merged[key] /= count

    output = "F:/Atulya Tantra/outputs/npdna/colab_merged.pt"
    torch.save(merged, output)
    total_params = sum(value.numel() for value in merged.values()) / 1e6
    print(f"Merged {count} workers -> {output} ({total_params:.0f}M params)")
    return output


def watch() -> None:
    """Continuously poll every 60 seconds."""
    print("Watching for Colab workers. Polling every 60 seconds.")
    while True:
        new = sync_workers()
        for name, ckpt in new:
            print(f"\nWorker {name} completed. Checkpoint: {ckpt}")
        time.sleep(60)


if __name__ == "__main__":
    load_state()

    if "--setup" in sys.argv:
        setup_drive()
    elif "--check-rclone" in sys.argv:
        if check_remote():
            print(f"rclone remote '{RCLONE_REMOTE}' is ready.")
    elif "--sync" in sys.argv:
        workers = sync_workers()
        if workers:
            print(f"{len(workers)} new worker(s):")
            for name, ckpt in workers:
                print(f"  OK {name}: {ckpt}")
            merge_workers()
        else:
            print("No new workers.")
    elif "--watch" in sys.argv:
        watch()
    elif "--merge" in sys.argv:
        merge_workers()
    else:
        print(__doc__)
