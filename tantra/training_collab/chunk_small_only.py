#!/usr/bin/env python3
"""Chunk only files under 600 MB for a fast Colab preparation pass."""

import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SRC = PROJECT / "tantra" / "data"
DST = PROJECT / "data" / "chunks"
INDEX = DST / "data_chunks.json"
MAX_BYTES = 400 * 1024 * 1024
MAX_SOURCE_BYTES = 600 * 1024 * 1024

DST.mkdir(parents=True, exist_ok=True)

# Load existing index
existing = []
if INDEX.exists():
    with open(INDEX) as f:
        data = json.load(f)
    existing = data.get("chunks", [])
    processed_sources = set(c.get("source", "") for c in existing)

# Find small unprocessed files
files = sorted(SRC.glob("*.jsonl"))
new_chunks = []

def chunk_file(src: Path) -> list[dict]:
    """Chunk one file, return list of chunk metadata."""
    result = []
    out_name = src.stem
    chunk_lines = []
    pb = 0
    idx = 0

    def flush():
        nonlocal idx, chunk_lines, pb
        if not chunk_lines:
            return
        idx += 1
        fname = f"{out_name}_chunk_{idx:03d}.jsonl"
        with open(DST / fname, "w", encoding="utf-8") as f:
            f.writelines(chunk_lines)
        sz = sum(len(line.encode("utf-8")) for line in chunk_lines)
        result.append({"name": fname, "size_bytes": sz, "lines": len(chunk_lines), "source": src.name})
        print(f"  {fname}: {sz/1e6:.1f}MB ({len(chunk_lines)} lines)")
        chunk_lines = []
        pb = 0

    with open(src, "r", encoding="utf-8") as f:
        for line in f:
            lb = len(line.encode("utf-8"))
            if pb + lb > MAX_BYTES and chunk_lines:
                flush()
            chunk_lines.append(line)
            pb += lb
    flush()
    return result

for src in files:
    if src.name in {"all_datasets.jsonl", "incoming"} or src.name in processed_sources:
        print(f"⏭️  {src.name} (already processed)")
        continue
    if src.stat().st_size > MAX_SOURCE_BYTES:
        print(f"⏭️  {src.name} ({src.stat().st_size/1e9:.1f}GB) too large, skipping")
        continue

    total = src.stat().st_size
    print(f"\n📄 {src.name} ({total/1e6:.1f}MB)")
    new_chunks.extend(chunk_file(src))

# Merge index
all_chunks = existing + new_chunks
total_bytes = sum(c.get("size_bytes", 0) for c in all_chunks)
with open(INDEX, "w") as f:
    json.dump({"chunks": all_chunks, "chunk_size_bytes": MAX_BYTES, "total_bytes": total_bytes,
               "total_lines": None, "total_chunks": len(all_chunks), "source_files": len(files)}, f, indent=2)

print(f"\n{'='*50}")
print(f"✅ {len(new_chunks)} new chunks added")
print(f"   Total: {len(all_chunks)} chunks ({total_bytes/1e9:.2f}GB)")
