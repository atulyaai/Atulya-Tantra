"""Streaming dataset loader for large-scale NP-DNA training.

Reads JSONL files on-the-fly, tokenizes incrementally, and emits
fixed-length sequences without loading everything into memory.
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path

logger = logging.getLogger(__name__)


def _format_record(record: dict, append_eos: bool = False) -> str:
    if "text" in record and "instruction" not in record:
        return str(record["text"])
    system = record.get("system", "You are Atulya. Be warm, thoughtful, and direct.")
    instruction = record.get("instruction", "")
    output = record.get("output", "")
    context = record.get("context", "")
    parts = [f"System: {system}"]
    if context:
        parts.append(f"Context: {context}")
    parts.append(f"User: {instruction}")
    parts.append(f"Assistant: {output}")
    if append_eos:
        parts.append("<eos>")
    return "\n".join(parts)


def _discover_jsonl_files(data_dir: str | Path) -> list[Path]:
    paths = sorted(Path(data_dir).glob("*.jsonl"))
    if not paths:
        raise FileNotFoundError(f"No JSONL files found in {data_dir}")
    return paths


class StreamingDataset:
    """Streaming JSONL dataset that yields fixed-length token sequences.

    Reads files sequentially, tokenizes each record on-the-fly,
    packs tokens into ``seq_limit``-sized chunks, and yields them
    one at a time.  When all files are exhausted the stream wraps
    around (infinite iteration, controlled by ``max_steps``).
    """

    def __init__(
        self,
        data_dir: str | Path,
        core,
        seq_limit: int = 256,
        append_eos: bool = True,
        shuffle_files: bool = True,
        shuffle_lines: bool = True,
        max_file_mb: int = 256,
    ):
        self.files = _discover_jsonl_files(data_dir)
        self.core = core
        self.seq_limit = seq_limit
        self.append_eos = append_eos
        self.shuffle_files = shuffle_files
        self.shuffle_lines = shuffle_lines
        self.max_file_mb = max_file_mb

        self._buffer: list[int] = []
        self._file_index = 0
        self._line_iter = None
        self._total_samples = 0
        self._current_file_handle = None
        self._reset_file_iter()

    def _reset_file_iter(self):
        if self.shuffle_files:
            random.shuffle(self.files)
        self._file_index = 0

    def _open_next_file(self):
        if self._current_file_handle is not None:
            self._current_file_handle.close()
        if self._file_index >= len(self.files):
            self._reset_file_iter()
        path = self.files[self._file_index]
        self._file_index += 1
        logger.info("Streaming: opening %s", path)

        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb <= self.max_file_mb and self.shuffle_lines:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
            lines = [l for l in (x.strip() for x in lines) if l]
            random.shuffle(lines)
            return iter(lines)
        else:
            if size_mb > self.max_file_mb:
                logger.info("Streaming: %s is %.0f MB, streaming without shuffle", path.name, size_mb)
            self._current_file_handle = path.open(encoding="utf-8-sig")
            return self._file_line_gen(self._current_file_handle)

    @staticmethod
    def _file_line_gen(fh):
        for line in fh:
            stripped = line.strip()
            if stripped:
                yield stripped

    def _tokenize_record(self, line: str) -> list[int]:
        record = json.loads(line)
        text = _format_record(record, append_eos=self.append_eos)
        ids = self.core.encode(text)[:self.seq_limit]
        return ids

    def _drain_buffer(self):
        while len(self._buffer) >= self.seq_limit:
            yield self._buffer[:self.seq_limit]
            self._buffer = self._buffer[self.seq_limit:]

    def sequences(self, max_steps: int | None = None):
        """Yield fixed-length token sequences indefinitely (or up to ``max_steps``).

        Each yielded sequence has length ``seq_limit`` (except possibly
        the first partial sequence, which is discarded).
        """
        step = 0
        if self._line_iter is None:
            self._line_iter = self._open_next_file()

        while max_steps is None or step < max_steps:
            try:
                line = next(self._line_iter)
            except StopIteration:
                self._line_iter = self._open_next_file()
                continue

            try:
                ids = self._tokenize_record(line)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning("Streaming: skipping bad line: %s", e)
                continue

            if len(ids) < 2:
                continue

            self._total_samples += 1
            self._buffer.extend(ids)

            for seq in self._drain_buffer():
                yield seq
                step += 1
                if max_steps is not None and step >= max_steps:
                    return

    @property
    def total_samples_seen(self) -> int:
        return self._total_samples


class StreamingPackDataset(StreamingDataset):
    """Like StreamingDataset but packs short sequences into ``seq_limit``
    chunks (similar to the ``--pack`` flag behaviour).
    """

    def sequences(self, max_steps: int | None = None):
        step = 0
        if self._line_iter is None:
            self._line_iter = self._open_next_file()

        while max_steps is None or step < max_steps:
            try:
                line = next(self._line_iter)
            except StopIteration:
                self._line_iter = self._open_next_file()
                continue

            try:
                ids = self._tokenize_record(line)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning("Streaming: skipping bad line: %s", e)
                continue

            if len(ids) < 2:
                continue

            self._total_samples += 1

            if len(self._buffer) + len(ids) <= self.seq_limit:
                self._buffer.extend(ids)
            else:
                if len(self._buffer) >= 2:
                    yield self._buffer[:self.seq_limit]
                    step += 1
                    self._buffer = self._buffer[self.seq_limit:]
                    if max_steps is not None and step >= max_steps:
                        return
                self._buffer = ids

        # Flush remaining
        if len(self._buffer) >= 2:
            while len(self._buffer) >= self.seq_limit:
                yield self._buffer[:self.seq_limit]
                self._buffer = self._buffer[self.seq_limit:]
