"""Obsidian Wiki export — Markdown with [[wikilinks]], auto-sync from memory."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any


class ObsidianExporter:
    def __init__(self, vault_dir: str | Path = "assets/obsidian"):
        self.vault_dir = Path(vault_dir)
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        (self.vault_dir / "topics").mkdir(parents=True, exist_ok=True)

    def export_all(self, entries: list[dict[str, Any]],
                   topics: dict[str, list[dict[str, Any]]] | None = None):
        if topics:
            for topic, topic_entries in topics.items():
                self._export_topic(topic, topic_entries)
        else:
            grouped: dict[str, list] = {}
            for entry in entries:
                topic = entry.get("topic", "general")
                grouped.setdefault(topic, []).append(entry)
            for topic, topic_entries in grouped.items():
                self._export_topic(topic, topic_entries)
        self._create_index(entries)

    def _export_topic(self, topic: str, entries: list[dict[str, Any]]):
        topic_dir = self.vault_dir / "topics"
        slug = self._slugify(topic)
        filepath = topic_dir / f"{slug}.md"

        content = f"# {topic}\n\n"
        content += f"*Auto-synced: {time.strftime('%Y-%m-%d %H:%M')}*\n\n"
        content += "---\n\n"

        for entry in entries:
            ts = entry.get("created_at", entry.get("timestamp", 0))
            if isinstance(ts, float):
                date_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
            else:
                date_str = str(ts)
            content += f"## {entry.get('id', 'entry')}\n\n"
            content += f"*{date_str}*\n\n"
            content += f"{entry.get('content', '')}\n\n"

            meta = entry.get("metadata", {}) or {}
            if meta.get("related_topics"):
                content += "**Related:** "
                links = [f"[[{self._slugify(t)}]]" for t in meta["related_topics"]]
                content += " ".join(links)
                content += "\n\n"
            if entry.get("tags"):
                content += "Tags: " + " ".join(f"#{t}" for t in entry["tags"]) + "\n\n"
            content += "---\n\n"

        filepath.write_text(content, encoding="utf-8")

    def _create_index(self, entries: list[dict[str, Any]]):
        topics = sorted(set(e.get("topic", "general") for e in entries))
        content = "# Memory Index\n\n"
        content += f"*Auto-synced: {time.strftime('%Y-%m-%d %H:%M')}*\n\n"
        content += "---\n\n"
        for topic in topics:
            slug = self._slugify(topic)
            content += f"- [[{slug}]]\n"
        content += "\n---\n\n"
        content += "## Stats\n\n"
        content += f"- Total entries: {len(entries)}\n"
        content += f"- Topics: {len(topics)}\n"
        content += f"- Last synced: {time.strftime('%Y-%m-%d %H:%M')}\n"
        (self.vault_dir / "index.md").write_text(content, encoding="utf-8")

    def sync_from_memory_provider(self, provider):
        """Auto-sync all entries from a memory provider to the Obsidian vault."""
        entries = provider._entries if hasattr(provider, '_entries') else []
        if not entries:
            return {"synced": 0, "topics": 0}
        topics: dict[str, list] = {}
        for e in entries:
            topic = e.get("topic", "general") if isinstance(e, dict) else getattr(e, "topic", "general")
            topics.setdefault(topic, []).append(e)
        self.export_all(entries, topics)
        return {"synced": len(entries), "topics": len(topics)}

    def create_daily_note(self, highlights: list[str]):
        """Create a daily note with memory highlights."""
        date_str = time.strftime("%Y-%m-%d")
        filepath = self.vault_dir / f"daily-{date_str}.md"
        content = [
            f"# Daily Note: {date_str}",
            f"",
            f"*Created: {time.strftime('%Y-%m-%d %H:%M')}*",
            f"",
            f"---",
            f"",
            f"## Highlights",
            f"",
        ]
        for h in highlights:
            content.append(f"- {h}")
        content.extend([
            "",
            "## Memory Sync",
            "",
            "Connected topics: [[index]]",
        ])
        filepath.write_text("\n".join(content), encoding="utf-8")
        return filepath

    @staticmethod
    def _slugify(text: str) -> str:
        return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
