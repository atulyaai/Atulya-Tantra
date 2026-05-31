"""Tag all_datasets.jsonl with topic categories using NP-DNA classifier.

Usage:
    python -m tantra.scripts.tag_dataset
    python -m tantra.scripts.tag_dataset --input data/all_datasets.jsonl --output data/tagged_dataset.jsonl
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Project root
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tantra.npdna.classifier import NpDnaTopicClassifier, CATEGORIES


def tag_dataset(
    input_path: str | Path = "data/all_datasets.jsonl",
    output_path: str | Path = "data/tagged_dataset.jsonl",
    batch_size: int = 100,
) -> None:
    """Tag every example in a JSONL dataset with its topic category."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    if not input_path.is_absolute():
        input_path = _ROOT / input_path
    if not output_path.is_absolute():
        output_path = _ROOT / output_path

    classifier = NpDnaTopicClassifier()

    total = 0
    tagged = 0
    errors = 0
    category_counts: dict[str, int] = {c: 0 for c in CATEGORIES}
    category_counts["unknown"] = 0

    print(f"Tagging {input_path} → {output_path}")
    print(f"Categories: {', '.join(CATEGORIES)}")
    print()

    with open(input_path, "r", encoding="utf-8") as inf:
        with open(output_path, "w", encoding="utf-8") as outf:
            for line in inf:
                line = line.strip()
                if not line:
                    continue
                total += 1
                try:
                    example = json.loads(line)
                    text = example.get("instruction", "") + " " + example.get("output", "")
                    result = classifier.classify(text)
                    example["category"] = result.category
                    example["category_score"] = round(result.confidence, 3)
                    outf.write(json.dumps(example, ensure_ascii=False) + "\n")
                    tagged += 1
                    cat = result.category or "unknown"
                    category_counts[cat] = category_counts.get(cat, 0) + 1
                except Exception as e:
                    errors += 1
                    # Write untagged as fallback
                    try:
                        ex2 = json.loads(line)
                        ex2["category"] = "unknown"
                        ex2["category_score"] = 0.0
                        outf.write(json.dumps(ex2, ensure_ascii=False) + "\n")
                    except Exception:
                        pass

                if total % batch_size == 0:
                    print(f"  Processed {total}...")

    print()
    print(f"Done: {tagged} tagged, {errors} errors, {total} total")
    print("Category distribution:")
    for cat in sorted(category_counts, key=lambda c: category_counts[c], reverse=True):
        if category_counts[cat]:
            print(f"  {cat}: {category_counts[cat]}")
    print(f"\nOutput: {output_path}")
    print(f"Size: {output_path.stat().st_size / 1024:.1f} KB")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Tag dataset with NP-DNA categories")
    parser.add_argument("--input", default="data/all_datasets.jsonl",
                        help="Input JSONL file (default: data/all_datasets.jsonl)")
    parser.add_argument("--output", default="data/tagged_dataset.jsonl",
                        help="Output JSONL file (default: data/tagged_dataset.jsonl)")
    parser.add_argument("--batch-size", type=int, default=100,
                        help="Log progress every N lines")
    args = parser.parse_args()
    tag_dataset(args.input, args.output, args.batch_size)


if __name__ == "__main__":
    main()
