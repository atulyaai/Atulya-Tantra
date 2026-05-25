#!/usr/bin/env python3
"""merge.py — FedAvg merge all completed worker checkpoints.

Collects checkpoints from colab_sync/workers/*/ that have a DONE marker,
and averages their parameters.

Usage:
    python merge.py
    python merge.py --output F:/Atulya Tantra/outputs/npdna/merged_model.pt
"""
import torch, os, sys, json, glob

WORKERS_DIR = "F:/Atulya Tantra/colab_sync/workers/"
OUTPUT = "F:/Atulya Tantra/outputs/npdna/merged_model.pt"

def find_completed_workers():
    """Find worker dirs with DONE marker and final checkpoint."""
    completed = []
    for worker_dir in os.listdir(WORKERS_DIR):
        wd = os.path.join(WORKERS_DIR, worker_dir)
        if not os.path.isdir(wd):
            continue
        if not os.path.exists(os.path.join(wd, "DONE")):
            print(f"  ⏳ {worker_dir}: not complete (no DONE marker), skipping")
            continue
        # Find final checkpoint
        ckpt = os.path.join(wd, "final.pt")
        if not os.path.exists(ckpt):
            # Maybe checkpoints subdir
            ckpt_dir = os.path.join(wd, "checkpoints")
            if os.path.exists(ckpt_dir):
                finals = sorted([f for f in os.listdir(ckpt_dir) if f.endswith('.pt')])
                if finals:
                    ckpt = os.path.join(ckpt_dir, finals[-1])
        if os.path.exists(ckpt) and os.path.getsize(ckpt) > 100:
            completed.append((worker_dir, ckpt))
            print(f"  ✅ {worker_dir}: {ckpt}")
        else:
            print(f"  ⚠️  {worker_dir}: no valid checkpoint, skipping")
    return completed

def fedavg_merge(completed):
    """Parameter averaging."""
    if not completed:
        print("❌ No completed workers to merge!")
        return None
    
    merged = None
    count = 0
    for name, path in completed:
        print(f"  Loading {name}...")
        state = torch.load(path, map_location='cpu')
        if merged is None:
            merged = {k: v.clone() for k, v in state.items()}
        else:
            for k in merged:
                merged[k] += state[k]
        count += 1
    
    for k in merged:
        merged[k] /= count
    
    print(f"✅ FedAvg merged {count} workers")
    return merged

if __name__ == "__main__":
    print(f"🔍 Scanning {WORKERS_DIR} for completed workers...")
    completed = find_completed_workers()
    merged = fedavg_merge(completed)
    
    if merged:
        output = sys.argv[sys.argv.index("--output") + 1] if "--output" in sys.argv else OUTPUT
        os.makedirs(os.path.dirname(output), exist_ok=True)
        torch.save(merged, output)
        print(f"📦 Saved → {output} ({sum(v.numel() for v in merged.values())/1e6:.0f}M params)")
