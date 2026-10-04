"""kosh (कोश, treasury): the one folder where Atulya keeps everything of yours (memory, accounts, keys, chat history).

It used to be called ``data``. On start-up an old ``data`` folder is moved to ``kosh`` once, so nothing is lost.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def migrate(root: str | Path = ".") -> str:
    """Move ``<root>/data`` to ``<root>/kosh`` if only the old one exists. Returns what happened, for logging and tests."""
    root = Path(root)
    old, new = root / "data", root / "kosh"
    if not old.is_dir() or new.exists():
        return "nothing to do"
    try:
        old.rename(new)
        return "moved data to kosh"
    except OSError:  # e.g. a file inside is open on Windows: copy instead, and leave the old folder as a backup
        try:
            shutil.copytree(old, new)
            logger.warning("Copied your data folder to kosh. You can delete the old data folder when you are sure.")
            return "copied data to kosh"
        except OSError as exc:
            logger.warning("Could not move data to kosh (%s). Close other Atulya windows and start again.", exc)
            return "failed"


def migrate_all() -> list[str]:
    """Run :func:`migrate` for the folder you started Atulya from and for the project folder (they are usually the same)."""
    roots = {Path.cwd().resolve(), Path(__file__).resolve().parents[1]}
    return [migrate(r) for r in sorted(roots)]
