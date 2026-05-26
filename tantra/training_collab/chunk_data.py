#!/usr/bin/env python3
"""Split large JSONL datasets into Colab-ready chunks.

Usage:
    python training_collab/chunk_data.py                 # default: ~400MB chunks
    python training_collab/chunk_data.py --max-size 500  # 500MB chunks
    python training_collab/chunk_data.py --only-new      # skip unchanged files

Output:
    data/chunks/
      conversation_chunk_001.jsonl
      conversation_chunk_002.jsonl
      ...
      data_chunks.json   (index with name, size_bytes, lines, source)
"""
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT / "tantra" / "data"
CHUNKS_DIR = PROJECT / "data" / "chunks"
INDEX_FILE = CHUNKS_DIR / "data_chunks.json"

# Target ~400MB per chunk by default
DEFAULT_MAX_BYTES = 400 * 1024 * 1024

# Extensions to consider for chunking
VALID_EXT = {".jsonl", ".txt"}

# Exclude these files (metadata, etc.)
EXCLUDE = {"incoming", "all_datasets.jsonl"}


def get_target_size() -> int:
    for arg in sys.argv:
        if arg.startswith("--max-size="):
            return int(arg.split("=", 1)[1]) * 1024 * 1024
        if arg.startswith("--max-size"):
            idx = sys.argv.index(arg)
            if idx + 1 < len(sys.argv):
                return int(sys.argv[idx + 1]) * 1024 * 1024
    return DEFAULT_MAX_BYTES


def gather_source_files() -> list[Path]:
    files = []
    for entry in sorted(DATA_DIR.iterdir()):
        if entry.name in EXCLUDE or not entry.is_file():
            continue
        if entry.suffix.lower() in VALID_EXT:
            files.append(entry)
    return files


def chunk_file(src: Path, max_bytes: int, only_new: bool) -> list[dict]:
    """Split a single JSONL file into chunks, return chunk metadata."""
    out_name = src.stem  # e.g. "conversation"
    chunks = []
    chunk_idx = 0
    chunk_lines = []
    chunk_bytes = 0

    def flush_chunk():
        nonlocal chunk_idx, chunk_lines, chunk_bytes
        if not chunk_lines:
            return
        chunk_idx += 1
        fname = f"{out_name}_chunk_{chunk_idx:03d}.jsonl"
        dest = CHUNKS_DIR / fname

        # Skip if only_new and file exists with same size
        if only_new and dest.exists() and dest.stat().st_size == chunk_bytes:
            chunks.append({"name": fname, "size_bytes": chunk_bytes, "source": src.name})
            chunk_lines = []
            chunk_bytes = 0
            return

        with open(dest, "w", encoding="utf-8") as f:
            f.writelines(chunk_lines)
        chunks.append({"name": fname, "size_bytes": chunk_bytes, "lines": len(chunk_lines), "source": src.name})
        print(f"  {fname}: {chunk_bytes/1e6:.1f}MB ({len(chunk_lines)} lines)")
        chunk_lines = []
        chunk_bytes = 0

    total_size = src.stat().st_size
    print(f"\n📄 {src.name} ({total_size/1e9:.1f}GB)" if total_size > 1e9 else f"\n📄 {src.name} ({total_size/1e6:.1f}MB)")

    with open(src, "r", encoding="utf-8") as f:
        for line in f:
            line_bytes = len(line.encode("utf-8"))
            # If single line exceeds max_bytes, force split (rare for JSONL)
            if line_bytes > max_bytes:
                flush_chunk()
                fname = f"{out_name}_chunk_{chunk_idx + 1:03d}_oversized.jsonl"
                dest = CHUNKS_DIR / fname
                with open(dest, "w", encoding="utf-8") as f_out:
                    f_out.write(line)
                chunk_idx += 1
                chunks.append({"name": fname, "size_bytes": line_bytes, "lines": 1, "source": src.name, "oversized": True})
                print(f"  {fname}: {line_bytes/1e6:.1f}MB (1 line, oversized)")
                continue

            if chunk_bytes + line_bytes > max_bytes and chunk_lines:
                flush_chunk()

            chunk_lines.append(line)
            chunk_bytes += line_bytes

    flush_chunk()
    return chunks


def build_index() -> dict:
    """Read existing index or return empty."""
    if INDEX_FILE.exists():
        try:
            with open(INDEX_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"chunks": [], "chunk_size_bytes": 0, "total_lines": 0, "total_bytes": 0, "total_chunks": 0}


def main():
    max_bytes = get_target_size()
    only_new = "--only" in sys.argv or "--only-new" in sys.argv

    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    files = gather_source_files()
    print(f"Target chunk size: {max_bytes / 1e6:.0f}MB")
    print(f"Source files: {len(files)}")
    if only_new:
        print("Mode: only-new (skip chunks that already exist with matching sizes)")

    all_chunks = []
    for src in files:
        try:
            chunks = chunk_file(src, max_bytes, only_new)
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"  ❌ Error chunking {src.name}: {e}")

    total_bytes = sum(c.get("size_bytes", 0) for c in all_chunks)
    total_lines = sum(c.get("lines", 0) for c in all_chunks if c.get("lines"))

    index = {
        "chunks": all_chunks,
        "chunk_size_bytes": max_bytes,
        "total_bytes": total_bytes,
        "total_lines": total_lines,
        "total_chunks": len(all_chunks),
    }
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f, indent=2)

    print(f"\n{'='*50}")
    print(f"✅ {len(all_chunks)} chunks created")
    print(f"   Total size: {total_bytes/1e9:.2f}GB")
    print(f"   Total lines: {total_lines:,}")
    print(f"   Index: {INDEX_FILE}")


if __name__ == "__main__":
    main()
