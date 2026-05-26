#!/usr/bin/env python3
"""colab_worker.py — Runs on Colab via SSH. Single chunk training.

Usage (via SSH on Colab):
    python colab_worker.py \\
        --chunk conversation_chunk_001.jsonl \\
        --checkpoint-dir /content/drive/MyDrive/npdna_training/base_checkpoint \\
        --output-dir /content/drive/MyDrive/npdna_training/workers/worker_001

This script:
    1. Copies dataset chunk from Drive to local
    2. Loads checkpoint from Drive
    3. Trains with train_npdna
    4. Saves final checkpoint back to Drive output dir
    5. Writes DONE marker
"""
import argparse
import json
import os
import shutil
import sys
import time

DRIVE_BASE = "/content/drive/MyDrive/npdna_training"
DATASET_DIR = f"{DRIVE_BASE}/chunks"
CHECKPOINT_SRC = f"{DRIVE_BASE}/base_checkpoint"
TRAIN_SCRIPT = "/content/colab_worker.py"  # self-reference
LOCAL_DATA = "/content/data"
LOCAL_CHECKPOINT = "/content/checkpoint"
LOCAL_OUTPUT = "/content/output"
STEPS = 5000
BATCH_SIZE = 4
SEQ_LIMIT = 256


def setup():
    """Install deps on first run."""
    import subprocess
    subprocess.run(["pip", "install", "-q", "torch", "numpy"], capture_output=True)
    # Copy source from Drive
    if not os.path.exists("/content/tantra"):
        shutil.copytree(f"{DRIVE_BASE}/source/tantra", "/content/tantra")
        shutil.copytree(f"{DRIVE_BASE}/source/atulya", "/content/atulya")
    for name in ("requirements.txt", "pyproject.toml"):
        src = os.path.join(DRIVE_BASE, "source", name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join("/content", name))
    if "/content" not in sys.path:
        sys.path.insert(0, "/content")
    if os.path.exists("/content/requirements.txt"):
        subprocess.run(["pip", "install", "-q", "-r", "/content/requirements.txt"], capture_output=True)
    print("Setup complete")


def load_and_train(chunk_name: str, output_dir: str, resume: bool = False, steps: int = STEPS):
    """Load dataset chunk + checkpoint → train → save."""
    chunk_path = os.path.join(DATASET_DIR, chunk_name)
    if not os.path.exists(chunk_path):
        print(f"Missing dataset chunk: {chunk_path}")
        return False
    os.makedirs(LOCAL_DATA, exist_ok=True)
    data_path = os.path.join(LOCAL_DATA, chunk_name)
    if not os.path.exists(data_path):
        shutil.copy2(chunk_path, data_path)

    # Load checkpoint
    ckpt_dir = output_dir if resume else LOCAL_CHECKPOINT
    if not os.path.exists(ckpt_dir) or not os.listdir(ckpt_dir):
        # Copy from Drive base
        if os.path.exists(CHECKPOINT_SRC):
            os.makedirs(ckpt_dir, exist_ok=True)
            for fname in os.listdir(CHECKPOINT_SRC):
                src = os.path.join(CHECKPOINT_SRC, fname)
                dst = os.path.join(ckpt_dir, fname)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
        else:
            print(f"No checkpoint at {CHECKPOINT_SRC} or {ckpt_dir}")
            return False

    import torch
    from tantra.training.npdna_train import train_npdna

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")

    # Train
    print(f"Dataset: {chunk_name} ({os.path.getsize(data_path)/1e6:.1f}MB)")
    print(f"Training for {steps} steps...")
    train_start = time.time()

    _, losses = train_npdna(
        config_name="atulya_seed",
        max_steps=steps,
        lr=2e-3,
        batch_size=BATCH_SIZE,
        seq_limit=SEQ_LIMIT,
        data_path=data_path,
        log_every=50,
        checkpoint_every=0,
        output_dir=output_dir,
        resume_from=ckpt_dir,
        device=device,
    )

    elapsed = time.time() - train_start
    final_loss = float(losses[-1]) if losses else None
    loss_text = f"{final_loss:.4f}" if final_loss is not None else "N/A"
    print(f"Training complete: {elapsed/60:.1f} min, final loss: {loss_text}")

    # Write DONE marker
    os.makedirs(output_dir, exist_ok=True)
    done_payload = {
        "chunk": chunk_name,
        "steps": steps,
        "final_loss": final_loss,
        "train_seconds": elapsed,
        "completed_at": time.ctime(),
        "output_dir": output_dir,
    }
    with open(os.path.join(output_dir, "DONE"), "w") as f:
        json.dump(done_payload, f)
    print("DONE marker written")
    return True


def main():
    parser = argparse.ArgumentParser(description="NP-DNA Colab Worker")
    parser.add_argument("--chunk", required=True, help="Dataset chunk name (e.g. conversation_chunk_001.jsonl)")
    parser.add_argument("--output-dir", default=None, help="Output dir on Drive (default: DRIVE_BASE/workers/<chunk_name>)")
    parser.add_argument("--resume", action="store_true", help="Resume from output dir checkpoint")
    parser.add_argument("--steps", type=int, default=STEPS, help="Training steps")
    parser.add_argument("--setup-only", action="store_true", help="Only run setup, don't train")
    args = parser.parse_args()

    output_dir = args.output_dir or f"{DRIVE_BASE}/workers/worker_{args.chunk.replace('.jsonl', '').replace('.txt', '')}"

    setup()
    if args.setup_only:
        print("Setup complete (setup-only mode)")
        return

    success = load_and_train(args.chunk, output_dir, resume=args.resume, steps=args.steps)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
