"""Combine JSONL datasets into one training file.

The dashboard trains from one JSONL path at a time. This utility creates a
single mixed file from the datasets under the allowed dataset roots, preserving
valid JSON records and optionally capping records per source.

Usage:
  python training/dataset/combine_jsonl.py --output data/combined_datasets.jsonl
  python training/dataset/combine_jsonl.py --limit-per-file 50000 --output data/combined_50k_each.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent


def default_roots() -> list[Path]:
    roots = [ROOT / "data"]
    raw = os.environ.get("ATULYA_DATASET_ROOTS")
    if raw:
        roots.extend(Path(p) for p in raw.split(os.pathsep) if p.strip())
    else:
        roots.append(Path(r"F:\datasets"))
    return [p.resolve() for p in roots if p.exists()]


def iter_sources(roots: list[Path], output: Path) -> list[Path]:
    output = output.resolve()
    sources: list[Path] = []
    for root in roots:
        for path in sorted(root.rglob("*.jsonl")):
            if path.resolve() == output:
                continue
            sources.append(path.resolve())
    return sources


def combine(
    sources: list[Path],
    output: Path,
    limit_per_file: int | None = None,
) -> dict[str, object]:
    output.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    invalid_rows = 0
    per_file: dict[str, int] = {}

    with output.open("w", encoding="utf-8") as out:
        for source in sources:
            written_for_source = 0
            with source.open(encoding="utf-8", errors="replace") as src:
                for line in src:
                    if limit_per_file is not None and written_for_source >= limit_per_file:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        invalid_rows += 1
                        continue
                    out.write(json.dumps(record, ensure_ascii=False) + "\n")
                    written_for_source += 1
                    rows_written += 1
            per_file[str(source)] = written_for_source

    return {
        "output": str(output.resolve()),
        "sources": len(sources),
        "rows_written": rows_written,
        "invalid_rows": invalid_rows,
        "per_file": per_file,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Combine dashboard JSONL datasets.")
    parser.add_argument("--output", default=str(ROOT / "data" / "combined_datasets.jsonl"))
    parser.add_argument("--root", action="append", dest="roots", help="Dataset root to scan. May repeat.")
    parser.add_argument("--limit-per-file", type=int, default=None)
    args = parser.parse_args()

    roots = [Path(p).resolve() for p in args.roots] if args.roots else default_roots()
    output = Path(args.output)
    result = combine(iter_sources(roots, output), output, args.limit_per_file)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
