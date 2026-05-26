#!/usr/bin/env python3
"""Full Colab distributed training manager.

Usage:
    python training_collab/monitor.py --setup
    python training_collab/monitor.py --setup --full-data
    python training_collab/monitor.py --sync
    python training_collab/monitor.py --watch
    python training_collab/monitor.py --merge
    python training_collab/monitor.py --status
    python training_collab/monitor.py --check-rclone
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from rclone_utils import find_rclone


LOCAL_CHECKPOINT = "F:/Atulya Tantra/tantra/outputs/npdna/"
LOCAL_DATA = "F:/Atulya Tantra/tantra/data/"
LOCAL_COLAB = "F:/Atulya Tantra/training_collab/"
LOCAL_TANTRA = "F:/Atulya Tantra/tantra/"
LOCAL_ATULYA = "F:/Atulya Tantra/atulya/"
LOCAL_PYPROJECT = "F:/Atulya Tantra/pyproject.toml"
LOCAL_REQUIREMENTS = "F:/Atulya Tantra/requirements.txt"
LOCAL_SYNC_DIR = "F:/Atulya Tantra/colab_sync/workers/"
LOCAL_CHUNKS = "F:/Atulya Tantra/data/chunks/"
LOCAL_INDEX = os.path.join(LOCAL_CHUNKS, "data_chunks.json")
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
        print("  powershell -ExecutionPolicy Bypass -File training_collab\\setup_rclone_drive.ps1")
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
    data_steps = []
    if "--full-data" in sys.argv or os.environ.get("ATULYA_UPLOAD_FULL_DATA") == "1":
        data_steps.append((LOCAL_DATA, f"{DRIVE_REMOTE}/dataset/"))
    else:
        seed_dataset = os.path.join(LOCAL_DATA, "seed_dataset.jsonl")
        if os.path.exists(seed_dataset):
            data_steps.append((seed_dataset, f"{DRIVE_REMOTE}/dataset/"))
        else:
            print("  Full dataset upload skipped. Use --full-data to upload all data.")

    steps = [
        (LOCAL_CHECKPOINT, f"{DRIVE_REMOTE}/base_checkpoint/"),
        *data_steps,
        (LOCAL_TANTRA, f"{DRIVE_REMOTE}/source/tantra/"),
        (LOCAL_ATULYA, f"{DRIVE_REMOTE}/source/atulya/"),
        (LOCAL_PYPROJECT, f"{DRIVE_REMOTE}/source/"),
        (LOCAL_REQUIREMENTS, f"{DRIVE_REMOTE}/source/"),
        (f"{LOCAL_COLAB}/train.ipynb", f"{DRIVE_REMOTE}/scripts/"),
        (f"{LOCAL_COLAB}/train.ipynb", f"{DRIVE_REMOTE}/"),
        (f"{LOCAL_COLAB}/colab_worker.py", f"{DRIVE_REMOTE}/"),
    ]
    common_args = [
        "--exclude",
        "data/**",
        "--exclude",
        "outputs/**",
        "--exclude",
        "__pycache__/**",
        "--exclude",
        ".pytest_cache/**",
        "--exclude",
        ".ruff_cache/**",
        "--exclude",
        ".git/**",
        "--exclude",
        "*.pyc",
        "--exclude",
        "*.egg-info/**",
        "--exclude",
        "*.bak.*",
        "--exclude",
        "live_metrics.jsonl",
        "--progress",
    ]
    for src, dst in steps:
        if os.path.exists(src):
            print(f"  Uploading {os.path.basename(src.rstrip('/'))}...")
            subprocess.run([RCLONE_CMD, "copy", src, dst, *common_args])
            print(f"  OK {os.path.basename(src.rstrip('/'))} -> Drive")
        else:
            print(f"  Missing, skipped: {src}")

    # Upload dataset chunks
    if os.path.isdir(LOCAL_CHUNKS):
        print("  Uploading dataset chunks...")
        subprocess.run([RCLONE_CMD, "copy", LOCAL_CHUNKS, f"{DRIVE_REMOTE}/chunks/", "--progress"])
        print("  OK chunks -> Drive")

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
    subprocess.run(
        [
            RCLONE_CMD,
            "copy",
            f"{DRIVE_REMOTE}/chunk_status/",
            "F:/Atulya Tantra/colab_sync/chunk_status/",
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
    model_path = os.path.join(worker_path, "model.pt")
    if os.path.exists(model_path) and os.path.getsize(model_path) > 100:
        return model_path

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

    output = "F:/Atulya Tantra/tantra/outputs/npdna/colab_merged.pt"
    torch.save(merged, output)
    total_params = sum(value.numel() for value in merged.values()) / 1e6
    print(f"Merged {count} workers -> {output} ({total_params:.0f}M params)")
    return output


def status() -> None:
    """Print local synced worker and chunk status."""
    completed = []
    active = []
    failed = []

    if os.path.exists(LOCAL_SYNC_DIR):
        for worker_dir in sorted(os.listdir(LOCAL_SYNC_DIR)):
            worker_path = os.path.join(LOCAL_SYNC_DIR, worker_dir)
            if not os.path.isdir(worker_path):
                continue
            done_path = os.path.join(worker_path, "DONE")
            heartbeat_path = os.path.join(worker_path, "HEARTBEAT.json")
            failed_path = os.path.join(worker_path, "FAILED")
            if os.path.exists(done_path):
                completed.append(worker_dir)
            elif os.path.exists(failed_path):
                failed.append(worker_dir)
            elif os.path.exists(heartbeat_path) or os.path.exists(os.path.join(worker_path, "STARTED.json")):
                active.append(worker_dir)

    print("Colab worker status")
    print(f"  completed: {len(completed)}")
    print(f"  active:    {len(active)}")
    print(f"  failed:    {len(failed)}")
    if active:
        print("Active workers:")
        for name in active[:20]:
            print(f"  - {name}")
    if completed:
        print("Completed workers:")
        for name in completed[:20]:
            print(f"  - {name}")

    # Chunk status
    if os.path.exists(LOCAL_INDEX):
        import json
        with open(LOCAL_INDEX) as f:
            idx = json.load(f)
        ck_state = Path("F:/Atulya Tantra/training_collab/.controller_state.json")
        processed = []
        if ck_state.exists():
            with open(ck_state) as f:
                st = json.load(f)
                processed = st.get("processed_chunks", [])
        print("\nChunk status:")
        print(f"  total:     {idx.get('total_chunks', '?')}")
        print(f"  processed: {len(processed)}")
        print(f"  total GB:  {idx.get('total_bytes', 0) / 1e9:.2f}")


def clean_workers(max_age_days: int = 3) -> list[str]:
    """List and optionally clean incomplete workers from Drive.

    Scans Drive workers/ directory for DONE markers and removes stale
    (no DONE after max_age_days) worker dirs from both Drive and local.
    Returns list of removed worker names.
    """
    if not check_remote():
        return []

    dry_run = "--dry-run" in sys.argv or "--dryrun" in sys.argv
    label = " (DRY-RUN)" if dry_run else ""
    print(f"Scanning Drive workers/{label}...")
    result = subprocess.run(
        [RCLONE_CMD, "lsjson", f"{DRIVE_REMOTE}/workers/"],
        capture_output=True, text=True,
    )
    try:
        workers = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        workers = []
    print(f"  Found {len(workers)} entries on Drive")

    if "--list-workers" in sys.argv:
        for w in workers:
            name = w.get("Name", w.get("Path", "?"))
            is_dir = w.get("IsDir", False)
            size = w.get("Size", 0)
            mod_time = w.get("ModTime", "?")[:19]
            print(f"  {'dir ' if is_dir else 'file'} {name:45s} {mod_time}  {size/1e6:.1f}MB")
        return []

    # Find workers that are complete (have DONE) vs stale
    removed = []
    for w in workers:
        name = w.get("Name", "")
        if not name or not w.get("IsDir"):
            continue
        # Check if this worker has DONE
        done_check = subprocess.run(
            [RCLONE_CMD, "lsf", f"{DRIVE_REMOTE}/workers/{name}/DONE"],
            capture_output=True, text=True,
        )
        has_done = done_check.returncode == 0 and done_check.stdout.strip() != ""

        # Remove stale (no DONE) workers from Drive and local
        if not has_done:
            print(f"  Stale (no DONE): {name}")
            if not dry_run:
                print(f"  -> Removing from Drive: {name}")
                subprocess.run([RCLONE_CMD, "purge", f"{DRIVE_REMOTE}/workers/{name}/"],
                               capture_output=True)
                local_path = os.path.join(LOCAL_SYNC_DIR, name)
                if os.path.exists(local_path):
                    shutil.rmtree(local_path)
                    print(f"  -> Removed local: {local_path}")
                removed.append(name)

    print(f"\n{'DRY-RUN: ' if dry_run else ''}Removed {len(removed)} stale workers")
    return removed


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
    elif "--status" in sys.argv:
        status()
    elif "--clean-workers" in sys.argv:
        clean_workers()
    elif "--list-workers" in sys.argv:
        clean_workers()  # uses --list-workers internally
    else:
        print(__doc__)
