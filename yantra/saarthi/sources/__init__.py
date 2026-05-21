"""Source ingestion — RSS, git repos, markdown vaults."""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SourceEntry:
    id: str
    source_type: str
    title: str
    content: str
    url: str = ""
    ingested_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class RSSIngestor:
    def __init__(self, data_dir: str | Path = "data/sources"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def ingest(self, feed_url: str) -> list[SourceEntry]:
        """Ingest RSS feed."""
        entries = []
        try:
            import feedparser
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:20]:
                source_entry = SourceEntry(
                    id=f"rss_{int(time.time())}_{len(entries)}",
                    source_type="rss",
                    title=entry.get("title", ""),
                    content=entry.get("summary", entry.get("description", "")),
                    url=entry.get("link", ""),
                    metadata={"feed_url": feed_url, "published": entry.get("published", "")},
                )
                entries.append(source_entry)
                self._save_entry(source_entry)
        except ImportError:
            pass  # feedparser not available
        return entries

    def _save_entry(self, entry: SourceEntry):
        filepath = self.data_dir / f"{entry.id}.json"
        filepath.write_text(json.dumps({
            "id": entry.id, "source_type": entry.source_type,
            "title": entry.title, "content": entry.content,
            "url": entry.url, "ingested_at": entry.ingested_at,
            "metadata": entry.metadata,
        }))


class GitRepoIngestor:
    def __init__(self, data_dir: str | Path = "data/sources"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def ingest(self, repo_url: str, branch: str = "main") -> list[SourceEntry]:
        """Clone and summarize git repo."""
        entries = []
        try:
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                subprocess.run(["git", "clone", "--depth", "1", "-b", branch, repo_url, tmp],
                             capture_output=True, timeout=60)
                # Read README and key files
                for name in ["README.md", "CONTRIBUTING.md", "docs/overview.md"]:
                    filepath = Path(tmp) / name
                    if filepath.exists():
                        entry = SourceEntry(
                            id=f"git_{int(time.time())}_{name}",
                            source_type="git",
                            title=name,
                            content=filepath.read_text()[:5000],
                            url=repo_url,
                            metadata={"repo": repo_url, "branch": branch, "file": name},
                        )
                        entries.append(entry)
                        self._save_entry(entry)
        except Exception:
            pass
        return entries

    def _save_entry(self, entry: SourceEntry):
        filepath = self.data_dir / f"{entry.id}.json"
        filepath.write_text(json.dumps({
            "id": entry.id, "source_type": entry.source_type,
            "title": entry.title, "content": entry.content,
            "url": entry.url, "ingested_at": entry.ingested_at,
            "metadata": entry.metadata,
        }))


class MarkdownVaultIngestor:
    def __init__(self, data_dir: str | Path = "data/sources"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def ingest(self, vault_path: str | Path) -> list[SourceEntry]:
        """Ingest markdown vault."""
        entries = []
        vault = Path(vault_path)
        if not vault.exists():
            return entries
        for md_file in vault.rglob("*.md"):
            content = md_file.read_text()
            entry = SourceEntry(
                id=f"md_{int(time.time())}_{md_file.name}",
                source_type="markdown_vault",
                title=md_file.stem,
                content=content[:5000],
                url=str(md_file),
                metadata={"path": str(md_file), "size": md_file.stat().st_size},
            )
            entries.append(entry)
            self._save_entry(entry)
        return entries

    def _save_entry(self, entry: SourceEntry):
        filepath = self.data_dir / f"{entry.id}.json"
        filepath.write_text(json.dumps({
            "id": entry.id, "source_type": entry.source_type,
            "title": entry.title, "content": entry.content,
            "url": entry.url, "ingested_at": entry.ingested_at,
            "metadata": entry.metadata,
        }))
