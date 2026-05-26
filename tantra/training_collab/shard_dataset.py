#!/usr/bin/env python3
"""Split large text datasets into small per-account chunks.

Example:
    python training_collab/shard_dataset.py --input tantra/data --accounts 10 --chunk-mb 512
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


TEXT_EXTENSIONS = {".jsonl", ".txt"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="tantra/data", help="Input file or directory.")
    parser.add_argument("--output", default="training_collab/shards", help="Output shard directory.")
    parser.add_argument("--accounts", type=int, default=10, help="Number of account shards.")
    parser.add_argument("--chunk-mb", type=int, default=512, help="Target chunk size in MB.")
    parser.add_argument("--clear", action="store_true", help="Delete existing output directory first.")
    return parser.parse_args()


def iter_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*") if p.is_file())


def account_dir(output: Path, account_index: int) -> Path:
    return output / f"account_{account_index + 1:02d}" / "dataset"


def split_text_file(path: Path, output: Path, accounts: int, chunk_bytes: int, next_chunk: int) -> tuple[int, list[dict]]:
    manifest = []
    account_index = next_chunk % accounts
    chunk_index = next_chunk
    current_size = 0
    out_file = None
    out_path = None

    def open_next():
        nonlocal account_index, chunk_index, current_size, out_file, out_path
        if out_file:
            out_file.close()
        dst_dir = account_dir(output, account_index)
        dst_dir.mkdir(parents=True, exist_ok=True)
        out_path = dst_dir / f"{path.stem}.chunk_{chunk_index:05d}{path.suffix}"
        out_file = out_path.open("wb")
        current_size = 0
        manifest.append(
            {
                "source": str(path),
                "account": account_index + 1,
                "file": str(out_path),
            }
        )
        account_index = (account_index + 1) % accounts
        chunk_index += 1

    open_next()
    with path.open("rb") as src:
        for line in src:
            if current_size and current_size + len(line) > chunk_bytes:
                open_next()
            out_file.write(line)
            current_size += len(line)

    if out_file:
        out_file.close()
    return chunk_index, manifest


def copy_small_file(path: Path, output: Path, accounts: int, next_chunk: int) -> tuple[int, list[dict]]:
    account_index = next_chunk % accounts
    dst_dir = account_dir(output, account_index)
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / path.name
    shutil.copy2(path, dst)
    return next_chunk + 1, [{"source": str(path), "account": account_index + 1, "file": str(dst)}]


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output = Path(args.output)
    chunk_bytes = args.chunk_mb * 1024 * 1024

    if args.clear and output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    manifest = {
        "input": str(input_path),
        "accounts": args.accounts,
        "chunk_mb": args.chunk_mb,
        "chunks": [],
    }
    next_chunk = 0

    for path in iter_files(input_path):
        if path.suffix.lower() in TEXT_EXTENSIONS:
            next_chunk, records = split_text_file(path, output, args.accounts, chunk_bytes, next_chunk)
        else:
            next_chunk, records = copy_small_file(path, output, args.accounts, next_chunk)
        manifest["chunks"].extend(records)

    manifest_path = output / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Created {len(manifest['chunks'])} chunk(s) in {output}")
    for i in range(args.accounts):
        total = sum(p.stat().st_size for p in account_dir(output, i).rglob("*") if p.is_file()) if account_dir(output, i).exists() else 0
        print(f"  account_{i + 1:02d}: {total / (1024 ** 3):.2f} GiB")


if __name__ == "__main__":
    main()
