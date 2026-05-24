"""Merge JSONL datasets into one clean instruction/output JSONL file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_SYSTEM = "You are Atulya. Answer clearly in the user's language."


def _from_messages(messages: list[dict[str, Any]]) -> dict[str, str] | None:
    system = DEFAULT_SYSTEM
    user = ""
    assistant = ""
    for msg in messages:
        role = str(msg.get("role", "")).lower()
        content = str(msg.get("content", "")).strip()
        if not content:
            continue
        if role == "system":
            system = content
        elif role == "user":
            user = content
        elif role == "assistant":
            assistant = content
    if not user or not assistant:
        return None
    return {"instruction": user, "output": assistant, "system": system}


def normalize_record(record: dict[str, Any]) -> dict[str, str] | None:
    if record.get("instruction") and record.get("output"):
        return {
            "instruction": str(record["instruction"]).strip(),
            "output": str(record["output"]).strip(),
            "system": str(record.get("system") or DEFAULT_SYSTEM).strip(),
        }

    text = record.get("text")
    if isinstance(text, str):
        stripped = text.strip()
        if stripped.startswith("["):
            try:
                messages = json.loads(stripped)
            except json.JSONDecodeError:
                messages = None
            if isinstance(messages, list):
                return _from_messages(messages)
        if stripped:
            return {
                "instruction": "Continue or answer clearly.",
                "output": stripped,
                "system": DEFAULT_SYSTEM,
            }

    messages = record.get("messages")
    if isinstance(messages, list):
        return _from_messages(messages)

    return None


def merge(inputs: list[Path], output: Path) -> dict[str, int]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    stats = {"read": 0, "written": 0, "duplicates": 0, "bad": 0}

    for path in inputs:
        with path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.strip():
                    continue
                stats["read"] += 1
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    stats["bad"] += 1
                    continue
                if not isinstance(raw, dict):
                    stats["bad"] += 1
                    continue
                row = normalize_record(raw)
                if not row or not row["instruction"] or not row["output"]:
                    stats["bad"] += 1
                    continue
                key = row["instruction"].strip().casefold()
                if key in seen:
                    stats["duplicates"] += 1
                    continue
                seen.add(key)
                rows.append(row)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    stats["written"] = len(rows)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge JSONL datasets.")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("inputs", nargs="+", type=Path)
    args = parser.parse_args()
    stats = merge(args.inputs, args.output)
    print(json.dumps({"output": str(args.output), **stats}, indent=2))


if __name__ == "__main__":
    main()
