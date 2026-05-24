"""Data ingestion pipeline for NP-DNA Tantra.

Processes source files in data/ and organizes them into categorized/.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from npdna.tokenizer import AtulyaTokenizer  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("ingest")

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
TOKENIZER_PATH = DATA_DIR / "tokenizer.json"
CATEGORIZED_DIR = DATA_DIR / "categorized"

# Source → category mapping
SOURCE_CATEGORY = {
    "hf_databricks-dolly-15k": "general_qa",
    "wikipedia_en": "wikipedia_en",
    "wikipedia_hi": "wikipedia_hi",
    "wikipedia_sa": "wikipedia_sa",
    "code": "code_snippets",
}

# Subset files — skip these because they're covered by the master file
SUBSET_FILES = {"dolly_data.jsonl", "training_data.jsonl"}


def load_tokenizer() -> AtulyaTokenizer | None:
    if TOKENIZER_PATH.exists():
        logger.info("Tokenizer loaded (%d vocab)", len(json.loads(TOKENIZER_PATH.read_text(encoding="utf-8"))["token_to_id"]))
        return AtulyaTokenizer.load(str(TOKENIZER_PATH))
    logger.warning("Tokenizer not found at %s", TOKENIZER_PATH)
    return None


def count_tokens(tok: AtulyaTokenizer, text: str) -> int:
    return len(tok.encode(text))


def clean_record(record: dict[str, Any]) -> dict[str, Any] | None:
    cleaned = {}
    for key in ("instruction", "output", "input", "system", "source", "topic", "category", "lang", "text"):
        if key in record:
            val = record[key]
            if isinstance(val, str):
                val = val.strip()
            if val:
                cleaned[key] = val
    has_instr = bool(cleaned.get("instruction") or cleaned.get("input"))
    has_output = bool(cleaned.get("output"))
    return cleaned if (has_instr and has_output) else None


def process_jsonl(filepath: Path, tok: AtulyaTokenizer) -> dict[str, Any]:
    rel = filepath.name
    stats: dict[str, Any] = {
        "source": rel,
        "type": "jsonl",
        "samples": 0,
        "tokens": 0,
        "action": "saved",
        "categories": {},
    }

    records = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            cleaned = clean_record(rec)
            if cleaned:
                text = " ".join(
                    str(cleaned.get(k, ""))
                    for k in ("instruction", "input", "output", "system")
                    if cleaned.get(k)
                )
                cleaned["_tokens"] = count_tokens(tok, text)
                records.append(cleaned)

    if not records:
        stats["action"] = "skipped"
        return stats

    stats["samples"] = len(records)
    stats["tokens"] = sum(r.get("_tokens", 0) for r in records)

    # Categorize
    groups: dict[str, list[dict]] = {}
    for rec in records:
        cat = rec.get("category", "")
        if cat in ("identity", "conversation", "knowledge"):
            group = cat
        else:
            src = rec.get("source", "unknown")
            group = SOURCE_CATEGORY.get(src, src)
        groups.setdefault(group, []).append(rec)

    for gname, grecs in sorted(groups.items()):
        outpath = CATEGORIZED_DIR / f"{gname}.jsonl"
        with open(outpath, "a", encoding="utf-8") as fout:
            for r in grecs:
                out = {k: v for k, v in r.items() if not k.startswith("_")}
                fout.write(json.dumps(out, ensure_ascii=False) + "\n")
        stats["categories"][gname] = len(grecs)
        logger.info("  → %s  (%d samples)", outpath.name, len(grecs))

    return stats


def process_identity_json(filepath: Path, tok: AtulyaTokenizer) -> dict[str, Any]:
    """Convert identity.json to training records."""
    rel = filepath.name
    stats = {"source": rel, "type": "json", "samples": 0, "tokens": 0, "action": "saved", "categories": {}}

    with open(filepath, encoding="utf-8") as f:
        config = json.load(f)

    name = config.get("name", "Atulya")
    tagline = config.get("tagline", "")

    # Generate instruction-output pairs from the identity config
    records = []
    config.get("personality", {})
    self_knowledge = config.get("self_knowledge", {})
    behavior = config.get("behavior", {})

    # Who are you
    records.append({
        "instruction": "Who are you?",
        "output": f"I'm {name}. {self_knowledge.get('what_i_am', '')}",
        "system": f"You are {name}. {tagline}",
        "category": "identity",
        "source": "identity_config",
    })

    # How do you work
    records.append({
        "instruction": "How do you work?",
        "output": self_knowledge.get("how_i_work", ""),
        "system": f"You are {name}. {tagline}",
        "category": "identity",
        "source": "identity_config",
    })

    # What can you do
    can_do = self_knowledge.get("what_i_can_do", [])
    if can_do:
        records.append({
            "instruction": "What can you do?",
            "output": "I can: " + "; ".join(can_do) + ".",
            "system": f"You are {name}. {tagline}",
            "category": "identity",
            "source": "identity_config",
        })

    # What are your limitations
    cannot_do = self_knowledge.get("what_i_cannot_do", [])
    if cannot_do:
        records.append({
            "instruction": "What are your limitations?",
            "output": "; ".join(cannot_do) + ".",
            "system": f"You are {name}. {tagline}",
            "category": "identity",
            "source": "identity_config",
        })

    # Languages
    records.append({
        "instruction": "What languages do you speak?",
        "output": "I work in " + ", ".join(self_knowledge.get("languages", ["English"])) + ".",
        "system": f"You are {name}. {tagline}",
        "category": "identity",
        "source": "identity_config",
    })

    # Behavior rules (capped at a few)
    for rule in behavior.get("when_unsure", "").split(".")[:2]:
        if rule.strip():
            records.append({
                "instruction": "What do you do when you're unsure?",
                "output": rule.strip() + ".",
                "system": f"You are {name}. {tagline}",
                "category": "identity",
                "source": "identity_config",
            })

    # Tokenize
    for rec in records:
        text = " ".join(str(rec.get(k, "")) for k in ("instruction", "output", "system") if rec.get(k))
        rec["_tokens"] = count_tokens(tok, text)

    stats["samples"] = len(records)
    stats["tokens"] = sum(r["_tokens"] for r in records)

    # Append to identity.jsonl in categorized
    outpath = CATEGORIZED_DIR / "identity.jsonl"
    with open(outpath, "a", encoding="utf-8") as fout:
        for r in records:
            out = {k: v for k, v in r.items() if not k.startswith("_")}
            fout.write(json.dumps(out, ensure_ascii=False) + "\n")
    stats["categories"]["identity"] = len(records)
    logger.info("  → identity.jsonl  (%d generated samples)", len(records))

    return stats


def main() -> None:
    CATEGORIZED_DIR.mkdir(parents=True, exist_ok=True)
    tok = load_tokenizer()
    if tok is None:
        print("ERROR: Tokenizer required. Aborting.")
        return

    results = []

    # Master file: all_datasets.jsonl (covers everything)
    master = DATA_DIR / "all_datasets.jsonl"
    if master.exists():
        done_marker = DATA_DIR / "all_datasets.jsonl.done"
        if not done_marker.exists():
            logger.info("=== Processing master file: all_datasets.jsonl ===")
            stats = process_jsonl(master, tok)
            results.append(stats)
            done_marker.write_text(f"Processed at {datetime.now().isoformat()}\n")

    # code.jsonl (different format with category field)
    code_src = DATA_DIR / "code.jsonl"
    if code_src.exists():
        done_marker = DATA_DIR / "code.jsonl.done"
        if not done_marker.exists():
            logger.info("=== Processing: code.jsonl ===")
            stats = process_jsonl(code_src, tok)
            results.append(stats)
            done_marker.write_text(f"Processed at {datetime.now().isoformat()}\n")

    # identity.json (config → training records)
    identity_src = DATA_DIR / "identity.json"
    if identity_src.exists():
        done_marker = DATA_DIR / "identity.json.done"
        if not done_marker.exists():
            logger.info("=== Processing: identity.json ===")
            stats = process_identity_json(identity_src, tok)
            results.append(stats)
            done_marker.write_text(f"Processed at {datetime.now().isoformat()}\n")

    if not results:
        print("No new files.")
        return

    # Output table
    print()
    print(f"{'Source':<30} | {'Type':<8} | {'Samples':<7} | {'Tokens':<8} | {'Action':<10}")
    print("-" * 75)
    for r in results:
        print(f"{r['source']:<30} | {r['type']:<8} | {r['samples']:<7} | {r['tokens']:<8} | {r['action']:<10}")
        for cat_name, count in r.get("categories", {}).items():
            print(f"  ├─ {cat_name:<26} |          | {count:<7} |          |")


if __name__ == "__main__":
    main()
