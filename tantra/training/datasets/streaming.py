"""Streaming dataset loader for NP-DNA training.

Handles large JSONL files (68 GB conversation.jsonl) by reading line-by-line,
never loading more than one chunk/file into memory.

Two modes:
  1. Manifest mode — reads from data/chunks/manifest.json (uses chunk datasets)
  2. Direct file mode — pass a list of JSONL paths directly

Usage:
    from tantra.training.datasets.streaming import StreamDataset

    # Mode 1: From manifest (chunks + small files)
    ds = StreamDataset("data/chunks/manifest.json", shuffle=True)
    for text in ds:
        ...  # each text is a formatted training string

    # Mode 2: Direct large files (for conversation.jsonl)
    ds = StreamDataset(["data/conversation.jsonl", "data/math.jsonl"], shuffle=True)

    # Mode 3: Batch iterator (tokenized)
    for batch in ds.iter_batches(batch_size=4, seq_limit=256):
        model.train(batch)
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Iterator, Sequence

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM = "You are Atulya. Be warm, thoughtful, and direct."


class StreamDataset:
    """Streaming dataset that reads JSONL files one at a time.

    Args:
        source: Path to manifest JSON, list of path strings/Paths, or a dict.
                Manifest format: {"dataset_name": ["path1.jsonl", ...], ...}
                Dict format: same as manifest.
        max_chunks_in_memory: Files to load at once (default 1).
                              Higher = better shuffling, more RAM.
        shuffle: Shuffle items within each loaded file's buffer.
        append_eos: Append <eos> token after each formatted record.
        seed: RNG seed.
    """

    def __init__(
        self,
        source: str | Path | dict[str, list[str]] | list[str],
        max_chunks_in_memory: int = 1,
        shuffle: bool = True,
        append_eos: bool = False,
        seed: int = 42,
    ):
        self._shuffle = shuffle
        self._append_eos = append_eos
        self._rng = random.Random(seed)
        self._max_files = max(1, max_chunks_in_memory)

        # Resolve source into list of (dataset_name, path) tuples
        self._files: list[tuple[str, Path]] = []
        if isinstance(source, (str, Path)):
            src_path = Path(source)
            if not src_path.exists():
                raise FileNotFoundError(f"Source not found: {source}")
            if src_path.suffix == ".json":
                # Manifest JSON
                with open(src_path) as f:
                    manifest = json.load(f)
                for ds_name, paths in manifest.items():
                    for p in paths:
                        self._files.append((ds_name, Path(p)))
            else:
                # Single JSONL file
                self._files.append((src_path.stem, src_path))
        elif isinstance(source, dict):
            for ds_name, paths in source.items():
                for p in paths:
                    self._files.append((ds_name, Path(p)))
        elif isinstance(source, list):
            for p in source:
                pp = Path(p)
                self._files.append((pp.stem, pp))
        else:
            raise TypeError(f"Unsupported source type: {type(source)}")

        # Remove non-existent files
        self._files = [(n, p) for n, p in self._files if p.exists()]
        if not self._files:
            raise FileNotFoundError("No valid JSONL files found in source")

        logger.info("StreamDataset: %d files, %.1f GB total",
                     len(self._files),
                     sum(p.stat().st_size for _, p in self._files) / (1024**3))

        # State
        self._current_file_idx = 0
        self._buffer: list[str] = []

    def __iter__(self):
        self._current_file_idx = 0
        self._buffer = []
        return self

    def __next__(self) -> str:
        """Return next formatted training string."""
        while not self._buffer:
            if self._current_file_idx >= len(self._files):
                raise StopIteration
            self._load_next_files()

        if self._shuffle:
            idx = self._rng.randint(0, len(self._buffer) - 1)
            return self._buffer.pop(idx)
        else:
            return self._buffer.pop(0)

    def _load_next_files(self):
        """Load 1+ files into buffer."""
        self._buffer = []
        for _ in range(self._max_files):
            if self._current_file_idx >= len(self._files):
                break
            name, path = self._files[self._current_file_idx]
            self._current_file_idx += 1
            count = 0
            try:
                with open(path, encoding="utf-8-sig", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                            text = _format_record(record, self._append_eos)
                            self._buffer.append(text)
                            count += 1
                        except json.JSONDecodeError:
                            continue
                logger.debug("Loaded %d samples from %s", count, name)
            except Exception as e:
                logger.warning("Error loading %s (%s): %s", path, name, e)

        if self._shuffle:
            self._rng.shuffle(self._buffer)

    def iter_batches(self, batch_size: int = 1, seq_limit: int = 256):
        """Yield batches of tokenized tensors.

        Each batch is a dict with 'input_ids' and 'labels' tensors.
        Pads truncates to seq_limit. Uses NP-DNA tokenizer.
        """
        from tantra.npdna.tokenizer import AtulyaTokenizer

        tokenizer = AtulyaTokenizer()
        batch_inputs: list = []
        batch_labels: list = []

        for text in self:
            import torch
            tokens = tokenizer.encode(text)[:seq_limit]
            if len(tokens) < 2:
                continue

            input_ids = torch.tensor(tokens[:-1], dtype=torch.long)
            labels = torch.tensor(tokens[1:], dtype=torch.long)

            batch_inputs.append(input_ids)
            batch_labels.append(labels)

            if len(batch_inputs) >= batch_size:
                yield _collate(batch_inputs, batch_labels, seq_limit)
                batch_inputs = []
                batch_labels = []

        if batch_inputs:
            yield _collate(batch_inputs, batch_labels, seq_limit)

    def shuffle_epoch(self):
        """Shuffle file order for a new epoch."""
        self._rng.shuffle(self._files)
        self._current_file_idx = 0
        self._buffer = []


def _collate(
    input_ids: list,
    labels: list,
    seq_limit: int,
) -> dict:
    """Collate variable-length sequences into padded tensors."""
    import torch

    batch_size = len(input_ids)
    pad_id = 0

    padded_inputs = torch.full((batch_size, seq_limit), pad_id, dtype=torch.long)
    padded_labels = torch.full((batch_size, seq_limit), -100, dtype=torch.long)

    for i, (inp, lbl) in enumerate(zip(input_ids, labels)):
        length = min(len(inp), seq_limit)
        padded_inputs[i, :length] = inp[:length]
        padded_labels[i, :length] = lbl[:length]

    return {"input_ids": padded_inputs, "labels": padded_labels}


def _format_record(record: dict, append_eos: bool = False) -> str:
    """Convert a dataset record to training text string."""
    if "text" in record and "instruction" not in record:
        return str(record["text"])

    system = record.get("system", _DEFAULT_SYSTEM)
    instruction = record.get("instruction", "")
    output = record.get("output", "")
    context = record.get("context", "")

    parts = [f"System: {system}"]
    if context:
        parts.append(f"Context: {context}")
    if instruction:
        parts.append(f"User: {instruction}")
    if output:
        parts.append(f"Assistant: {output}")
    if append_eos:
        parts.append("<eos>")
    return "\n".join(parts)


def build_manifest(data_dir: str | Path = "data") -> dict[str, list[str]]:
    """Auto-build a manifest from chunks/ dir and data/*.jsonl files.

    - data/chunks/{name}/chunk_*.jsonl → grouped as {name}
    - data/*.jsonl → included as individual datasets
    - Skips conversation.jsonl (68 GB — stream separately)
    """
    data_dir = Path(data_dir)
    manifest: dict[str, list[str]] = {}

    # Chunks directory
    chunks_dir = data_dir / "chunks"
    if chunks_dir.exists():
        for item in sorted(chunks_dir.iterdir()):
            if item.is_dir():
                chunk_files = sorted(item.glob("chunk_*.jsonl"))
                if chunk_files:
                    manifest[item.name] = [str(c) for c in chunk_files]

    # Small files from data/
    for f in sorted(data_dir.glob("*.jsonl")):
        if f.name == "conversation.jsonl":
            continue  # too big, stream separately
        if f.stat().st_size > 2 * 1024**3:  # >2 GB
            continue
        key = f.stem
        manifest[key] = [str(f)]

    return manifest


def manifest_summary(manifest: dict[str, list[str]]) -> str:
    """Print a human-readable summary of a manifest."""
    lines = []
    total_gb = 0.0
    for name, paths in sorted(manifest.items()):
        size_gb = sum(Path(p).stat().st_size for p in paths) / (1024**3)
        total_gb += size_gb
        lines.append(f"  {name}: {len(paths)} file(s), {size_gb:.1f} GB")
    lines.append(f"  Total: {total_gb:.1f} GB across {len(manifest)} datasets")
    return "\n".join(lines)
