"""Split large JSONL datasets into manageable chunks for streaming training.

Chunks are saved to data/chunks/{name}/chunk_{N:04d}.jsonl.
Large files (conversation.jsonl, math.jsonl, translation.jsonl) get chunked.
Smaller files are symlinked/copied directly.
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("chunk_datasets")

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Target chunk size in bytes (~500 MB lines per chunk)
TARGET_CHUNK_BYTES = 500 * 1024 * 1024

# Files to chunk (others will be linked directly)
# conversation.jsonl is 68 GB — needs streaming, not chunking
LARGE_FILES_TO_CHUNK = ["math.jsonl", "translation.jsonl"]

# Files to include as-is (small enough to load fully)
SMALL_FILES = [
    "general.jsonl",
    "reasoning.jsonl",
    "code.jsonl",
    "factual.jsonl",
    "agentic.jsonl",
    "tagged_dataset.jsonl",
    "all_datasets.jsonl",
    "identity.jsonl",
]


def count_lines(path: Path) -> int:
    """Fast line count using iterative read."""
    count = 0
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        for _ in f:
            count += 1
    return count


def chunk_file(input_path: Path, output_dir: Path) -> list[Path]:
    """Split a JSONL file into ~TARGET_CHUNK_BYTES chunks."""
    output_dir.mkdir(parents=True, exist_ok=True)
    chunks: list[Path] = []
    chunk_index = 0
    chunk_bytes = 0
    outf = None
    total_lines = 0
    t0 = time.time()

    with open(input_path, encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            if outf is None or chunk_bytes >= TARGET_CHUNK_BYTES:
                if outf:
                    outf.close()
                chunk_index += 1
                chunk_path = output_dir / f"chunk_{chunk_index:04d}.jsonl"
                outf = open(chunk_path, "w", encoding="utf-8")
                chunks.append(chunk_path)
                chunk_bytes = 0
                logger.info("  Creating %s (%s)", chunk_path.name, human_bytes(TARGET_CHUNK_BYTES))

            outf.write(line)
            chunk_bytes += len(line.encode("utf-8"))
            total_lines += 1

    if outf:
        outf.close()

    elapsed = time.time() - t0
    logger.info(
        "Chunked %s → %d chunks (%d lines) in %.1fs",
        input_path.name, chunk_index, total_lines, elapsed,
    )
    return chunks


def human_bytes(b: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if b < 1024:
            return f"{b:.1f}{unit}"
        b /= 1024
    return f"{b:.1f}TB"


def main():
    data_dir = _ROOT / "data"
    chunks_dir = _ROOT / "data" / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1: Chunk large files
    for fname in LARGE_FILES_TO_CHUNK:
        src = data_dir / fname
        if not src.exists():
            logger.warning("  SKIP %s — not found", fname)
            continue
        dst_dir = chunks_dir / src.stem  # data/chunks/math/
        logger.info("Chunking %s (%s)...", fname, human_bytes(src.stat().st_size))
        nlines = count_lines(src)
        logger.info("  Lines: %d", nlines)
        chunk_file(src, dst_dir)

    # Phase 2: Copy/link smaller files
    for fname in SMALL_FILES:
        src = data_dir / fname
        if not src.exists():
            logger.warning("  SKIP %s — not found", fname)
            continue
        dst = chunks_dir / fname
        if dst.exists():
            continue
        shutil.copy2(src, dst)
        logger.info("  Copied %s → chunks/", fname)

    # Phase 3: Create a manifest for the training pipeline
    manifest: dict[str, list[str]] = {}
    for item in sorted(chunks_dir.iterdir()):
        if item.is_dir():
            chunk_files = sorted(item.glob("chunk_*.jsonl"))
            if chunk_files:
                manifest[item.name] = [str(c) for c in chunk_files]
        elif item.suffix == ".jsonl":
            manifest[item.stem] = [str(item)]

    manifest_path = chunks_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info("\nDone! Manifest: %s", manifest_path)
    total_gb = sum(
        sum(Path(p).stat().st_size for p in files)
        for files in manifest.values()
    )
    logger.info("Total chunked data: %s (%d datasets)", human_bytes(total_gb), len(manifest))

    # Print sizes
    for name, paths in sorted(manifest.items()):
        size = sum(Path(p).stat().st_size for p in paths) / (1024**3)
        logger.info("  %s: %d chunks, %.1f GB", name, len(paths), size)


if __name__ == "__main__":
    main()
