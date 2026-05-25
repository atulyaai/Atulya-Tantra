---
title: "Google Colab Distributed Training for NP-DNA"
description: "Distribute NP-DNA training across 10 Google Colab accounts. Shards dataset, uploads via Google Drive, trains each shard on Colab GPU, syncs checkpoints back every 5GB, and merges models via parameter averaging."
category: "mlops"
---

# Colab Distributed Training for NP-DNA

## Overview

Distributes NP-DNA training across 10 free-tier Google Colab accounts. Each Colab:
1. Pulls its data shard + model from a shared Google Drive
2. Trains on GPU (T4/K80) — 50-100× faster than local CPU
3. Uploads checkpoints every 5GB to Google Drive
4. Local machine monitors Drive, merges checkpoints

## Architecture

```
Local Machine (i3-9100F)           Google Drive              Colab × 10
├── shard_dataset.py      ──→      ├── shard_0/              ├── Colab 0
├── deploy_to_colabs.py   ──→      ├── shard_1/              ├── Colab 1
├── monitor_drive.py      ──→      ├── ...                   ├── ...
├── merge_checkpoints.py  ←───     ├── checkpoints/          └── Colab 9
├── script.zip            ──→      └── training_script.py
```

## Prerequisites

- 10 Google accounts (free Colab works, 12h timeout/session limit)
- Google Drive API enabled for each (or 1 shared Drive with edit access for all)
- `gdown` installed locally (`pip install gdown`)
- `gspread` + `oauth2client` for Drive API

## Step 1: Dataset Sharding

```bash
python shard_dataset.py \
  --input /path/to/dataset \
  --num_shards 10 \
  --output F:/Atulya Tantra/data/sharded/
```

This splits the dataset into 10 shards (each ~2-5GB depending on total size).

## Step 2: Upload to Google Drive

For rclone setup, authorization, and multi-account remotes, see
[`RCLONE_AUTH.md`](RCLONE_AUTH.md).

```python
# upload_shards.py — uploads each shard to a folder per account
# Uses rclone or gdown to sync local → Drive
```

For each of 10 accounts:
- Create a folder `npdna_shard_{N}/`
- Upload `shard_{N}.jsonl` or `shard_{N}.bin`
- Upload the base model checkpoint + training script

## Step 3: Colab Notebook Template

Each Colab runs this notebook:

```python
# === Colab Notebook (run on each account) ===
# 1. Mount Google Drive
from google.colab import drive
drive.mount('/content/drive')

# 2. Copy shard data + training script locally
import shutil, os
shutil.copytree('/content/drive/MyDrive/npdna_shard_0/', '/content/npdna_data/')
os.chdir('/content/npdna_data')

# 3. Install dependencies
!pip install torch numpy datasets

# 4. Train — with periodic checkpoint uploads
import subprocess, time

CHECKPOINT_INTERVAL_GB = 5  # upload checkpoint every 5GB of processed data
total_data_gb = os.path.getsize('shard_0.jsonl') / 1e9
checkpoints_per_shard = max(1, total_data_gb / CHECKPOINT_INTERVAL_GB)
step_interval = total_steps // checkpoints_per_shard

for step in range(total_steps):
    train_step(...)
    if step % step_interval == 0 and step > 0:
        # Save checkpoint to Drive
        !cp -r /content/npdna_data/checkpoint.pt /content/drive/MyDrive/npdna_shard_0/checkpoints/step_{step}.pt
        print(f"Checkpoint uploaded: step {step}")

# 5. Final upload
!cp /content/npdna_data/final.pt /content/drive/MyDrive/npdna_shard_0/final_model.pt
print("Training complete for this shard!")
```

## Step 4: Monitor & Sync

```python
# monitor_drive.py — runs locally, polls Drive for completed checkpoints
# When a new checkpoint appears, downloads and stores it
# Tracks which shards are done, which are still running

import time, os
from watchdog.observers import PollingObserver

DRIVE_SYNC_DIR = "F:/Atulya Tantra/colab_sync/"
os.makedirs(DRIVE_SYNC_DIR, exist_ok=True)

# Use rclone to keep local copy in sync
subprocess.run(["rclone", "sync", "gdrive:npdna_training/", DRIVE_SYNC_DIR, 
                "--exclude", "shard_*/*.jsonl"])  # don't download raw data, just checkpoints
```

## Step 5: Merge Models (FedAvg)

```python
# merge_checkpoints.py
# Collect all final models from each shard
# Average parameters: theta_merged = 1/N * sum(theta_i)
# Based on Federated Averaging (FedAvg)

import torch

def fedavg_merge(checkpoint_paths, output_path):
    """Merge checkpoints via simple parameter averaging."""
    merged = None
    count = 0
    for path in checkpoint_paths:
        state = torch.load(path, map_location='cpu')
        if merged is None:
            merged = {k: v.clone() for k, v in state.items()}
        else:
            for k in merged:
                merged[k] += state[k]
        count += 1
    
    for k in merged:
        merged[k] /= count
    
    torch.save(merged, output_path)
    print(f"Merged {count} checkpoints → {output_path}")
```

## Limitations (Free Colab)

| Feature | Free Tier | Pro ($10/mo) |
|---------|-----------|--------------|
| Session | 60-90 min | 24h |
| GPU | T4/K80 | T4/V100/A100 |
| Cooldown | 12h/account | None |
| Background | No | Yes |
| Automation | Manual notebook start | Background + API |

**Workaround:** With 10 accounts, cycle through them: start colab notebooks in sequence so at any time 2-3 are training. Rotate accounts to avoid cooldown.

## File Structure

```
F:/Atulya Tantra/
├── colab_distributed/
│   ├── shard_dataset.py
│   ├── upload_shards.py
│   ├── colab_notebook_template.ipynb
│   ├── monitor_drive.py
│   ├── merge_checkpoints.py
│   └── start_all_colabs.sh        # Opens all 10 Colab links in browser
├── data/
│   └── sharded/                   # Output of shard_dataset.py
└── outputs/
    └── colab_merged/              # Merged checkpoints
```
