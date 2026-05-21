"""Obsidian Wiki export — Markdown with [[wikilinks]]."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class ObsidianExporter:
    def __init__(self, vault_dir: str | Path = "data/obsidian"):
        self.vault_dir = Path(vault_dir)
        self.vault_dir.mkdir(parents=True, exist_ok=True)

    def export_all(self, entries: list[dict[str, Any]], topics: dict[str, list[dict[str, Any]]] | None = None):
        """Export all entries to Obsidian vault format."""
        # Create topic files
        if topics:
            for topic, topic_entries in topics.items():
                self._export_topic(topic, topic_entries)
        else:
            # Group by topic from entries
            grouped: dict[str, list] = {}
            for entry in entries:
                topic = entry.get("topic", "general")
                grouped.setdefault(topic, []).append(entry)
            for topic, topic_entries in grouped.items():
                self._export_topic(topic, topic_entries)

        # Create index
        self._create_index(entries)

    def _export_topic(self, topic: str, entries: list[dict[str, Any]]):
        topic_dir = self.vault_dir / "topics"
        topic_dir.mkdir(parents=True, exist_ok=True)
        slug = self._slugify(topic)
        filepath = topic_dir / f"{slug}.md"

        content = f"# {topic}\n\n"
        for entry in entries:
            content += f"## {entry.get('id', 'unknown')}\n\n"
            content += f"{entry.get('content', '')}\n\n"
            # Add wikilinks to related topics
            if entry.get("metadata", {}).get("related_topics"):
                content += "**Related:** "
                links = [f"[[{self._slugify(t)}]]" for t in entry["metadata"]["related_topics"]]
                content += " ".join(links)
                content += "\n\n"

        filepath.write_text(content)

    def _create_index(self, entries: list[dict[str, Any]]):
        topics = set(e.get("topic", "general") for e in entries)
        content = "# Memory Index\n\n"
        for topic in sorted(topics):
            slug = self._slugify(topic)
            content += f"- [[{slug}]]\n"
        (self.vault_dir / "index.md").write_text(content)

    @staticmethod
    def _slugify(text: str) -> str:
        return re.sub(r'[^a-z0-9]+', '-', text.lower().strip('-'))
