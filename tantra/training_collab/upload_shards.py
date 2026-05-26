#!/usr/bin/env python3
"""Upload per-account dataset shards to matching rclone remotes.

Example:
    python training_collab/upload_shards.py --accounts 10 --remote-prefix gdrive_acc
"""
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from rclone_utils import find_rclone


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shards-dir", default="training_collab/shards")
    parser.add_argument("--accounts", type=int, default=10)
    parser.add_argument("--remote-prefix", default="gdrive_acc")
    parser.add_argument("--drive-root", default="npdna_training")
    parser.add_argument("--transfers", type=int, default=4)
    parser.add_argument("--checkers", type=int, default=8)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rclone = find_rclone()
    if not rclone:
        raise SystemExit("rclone not found")

    for i in range(1, args.accounts + 1):
        remote = f"{args.remote_prefix}{i}"
        src = Path(args.shards_dir) / f"account_{i:02d}" / "dataset"
        if not src.exists():
            print(f"Skipping {remote}: no shard directory at {src}")
            continue

        dst = f"{remote}:{args.drive_root}/dataset/"
        print(f"Uploading {src} -> {dst}")
        env = os.environ.copy()
        result = subprocess.run(
            [
                rclone,
                "copy",
                str(src),
                dst,
                "--transfers",
                str(args.transfers),
                "--checkers",
                str(args.checkers),
                "--progress",
            ],
            env=env,
        )
        if result.returncode != 0:
            raise SystemExit(f"Upload failed for {remote}")


if __name__ == "__main__":
    main()
