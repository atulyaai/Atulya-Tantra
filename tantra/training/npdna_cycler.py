#!/usr/bin/env python3
"""
NP-DNA Full-Dataset Training Cycler

Iterates through all data categories, splits them into chunks on-demand,
trains the model on each chunk sequentially, and auto-resumes.

Generates chunks lazily (one category at a time) so we don't block
on huge files like conversation.jsonl (68GB) until needed.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
_LOGGING_DIR = ROOT / "outputs" / "npdna_full"
_LOG_INITIALIZED = False

def _init_logging():
    global _LOG_INITIALIZED
    if _LOG_INITIALIZED:
        return
    _LOG_INITIALIZED = True
    _LOGGING_DIR.mkdir(parents=True, exist_ok=True)
    log_file = _LOGGING_DIR / "cycler_log.txt"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(str(log_file), mode="a"),
        ],
    )
logger = logging.getLogger("Cycler")

TANTRA_DIR = ROOT / "tantra"
DATA_DIR = TANTRA_DIR / "data"
OUTPUT_DIR = ROOT / "outputs" / "npdna_full"
CHUNKS_DIR = DATA_DIR / "chunks"
STATE_FILE = OUTPUT_DIR / "cycler_state.json"

# Source categories in processing order (smallest first)
# (name, source_path, lines_per_chunk, max_steps)
SOURCES = [
    ("agentic",     "agentic.jsonl",       200_000, 1500),
    ("code",        "code.jsonl",          200_000, 1500),
    ("factual",     "factual.jsonl",       200_000, 1500),
    ("reasoning",   "reasoning.jsonl",     200_000, 1500),
    ("math",        "math.jsonl",          200_000, 1500),
    ("translation", "translation.jsonl",   200_000, 1500),
    ("general",     "general.jsonl",       200_000, 1500),
    ("conversation","conversation.jsonl",  200_000, 1500),
]


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"epoch": 1, "src_idx": 0, "chunk_idx": 0, "completed": [], "failed": []}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def ensure_chunks_for_source(name: str, fname: str, lines_per_chunk: int) -> list[Path]:
    """Ensure chunk files exist for a category. Generate them if missing."""
    out_dir = CHUNKS_DIR / name
    existing = sorted(out_dir.glob("chunk_*.jsonl"))
    if existing:
        logger.info("  %s: %d existing chunks", name, len(existing))
        return existing

    src_path = DATA_DIR / fname
    if not src_path.exists():
        logger.warning("  %s: source not found, skipping", src_path)
        return []

    logger.info("  Splitting %s into chunks...", fname)
    out_dir.mkdir(parents=True, exist_ok=True)

    chunk_idx = 0
    current_lines: list[str] = []
    line_count = 0

    with open(src_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            current_lines.append(line + "\n")
            line_count += 1

            if line_count >= lines_per_chunk:
                cp = out_dir / f"chunk_{chunk_idx+1:04d}.jsonl"
                with open(cp, "w", encoding="utf-8") as cf:
                    cf.writelines(current_lines)
                current_lines = []
                line_count = 0
                chunk_idx += 1

    if current_lines:
        cp = out_dir / f"chunk_{chunk_idx+1:04d}.jsonl"
        with open(cp, "w", encoding="utf-8") as cf:
            cf.writelines(current_lines)

    chunks = sorted(out_dir.glob("chunk_*.jsonl"))
    logger.info("  %s: %d chunks generated", name, len(chunks))
    return chunks


def run_one_chunk(chunk_path: Path, max_steps: int, name: str, src_idx: int, chunk_idx: int, total: int) -> bool:
    """Train model on one chunk."""
    logger.info("=" * 60)
    logger.info("CHUNK [%d/%d] %s — %s", chunk_idx + 1, total, name, chunk_path.name)
    logger.info("  Steps: %d, Device: CPU", max_steps)
    logger.info("=" * 60)

    cmd = [
        sys.executable, "-m", "tantra.training.npdna_train",
        "--config", "nano",
        "--steps", str(max_steps),
        "--lr", "2e-3",
        "--output", str(OUTPUT_DIR),
        "--data", str(chunk_path),
        "--resume", str(OUTPUT_DIR),
        "--log-every", "10",
        "--checkpoint-every", "0",
        "--seq-limit", "256",
    ]

    try:
        result = subprocess.run(cmd, cwd=str(ROOT), capture_output=False, timeout=86400)
        ok = result.returncode == 0
        if ok:
            logger.info("  ✓ %s done — loss: see live_metrics.jsonl", chunk_path.name)
        else:
            logger.error("  ✗ %s FAILED (exit=%d, see error above)", chunk_path.name, result.returncode)
        return ok
    except subprocess.TimeoutExpired:
        logger.error("  ✗ %s TIMEOUT (>24h)", chunk_path.name)
        return False
    except Exception as e:
        logger.error("  ✗ %s EXCEPTION: %s", chunk_path.name, e)
        return False


def main():
    _init_logging()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()
    epoch = state["epoch"]
    completed = set(state.get("completed", []))
    failed = set(state.get("failed", []))

    logger.info("=" * 60)
    logger.info("Full-Dataset Training Cycler")
    logger.info("  Output: %s", OUTPUT_DIR)
    logger.info("  Data: %s", DATA_DIR)
    logger.info("  Config: nano, LR=2e-3")
    logger.info("  Epoch: %d", epoch)

    # Process categories in order
    total_chunks_globally = 0
    for src_idx in range(state["src_idx"], len(SOURCES)):
        name, fname, lpc, max_steps = SOURCES[src_idx]
        chunks = ensure_chunks_for_source(name, fname, lpc)
        if not chunks:
            continue

        # Determine starting chunk within this category
        start_chunk = state["chunk_idx"] if src_idx == state["src_idx"] else 0
        n_chunks = len(chunks)

        for ci in range(start_chunk, n_chunks):
            chunk_path = chunks[ci]
            key = f"{name}/{chunk_path.name}"
            total_chunks_globally += 1
            logger.info("Remaining categories to process: %d/%d categories", src_idx, len(SOURCES))

            if key in completed:
                logger.info("  Skipping completed: %s", key)
                continue

            logger.info("")
            ok = run_one_chunk(chunk_path, max_steps, name, src_idx, ci, n_chunks)

            if ok:
                completed.add(key)
                failed.discard(key)
                state["src_idx"] = src_idx
                state["chunk_idx"] = ci + 1
                state["completed"] = sorted(completed)
                save_state(state)
            else:
                failed.add(key)
                state["failed"] = sorted(failed)
                save_state(state)
                logger.info("✗ Cycler paused at %s due to error — fix and re-run", key)
                sys.exit(1)

        # Reset chunk_idx for next category
        state["chunk_idx"] = 0

    # Epoch complete
    logger.info("=" * 60)
    logger.info("✓ Epoch %d complete — all categories processed", epoch)
    state["epoch"] += 1
    state["src_idx"] = 0
    state["chunk_idx"] = 0
    save_state(state)
    logger.info("Starting Epoch %d next run", state["epoch"])


if __name__ == "__main__":
    main()
