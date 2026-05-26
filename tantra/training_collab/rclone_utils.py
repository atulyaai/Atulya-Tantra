"""Small helpers for locating rclone on Windows or PATH."""
from __future__ import annotations

import glob
import os
import shutil


def find_rclone() -> str | None:
    """Return a usable rclone executable path, if one is available."""
    candidates = [
        os.environ.get("RCLONE_PATH"),
        shutil.which("rclone"),
        shutil.which("rclone.exe"),
        os.path.expanduser("~/bin/rclone.exe"),
        os.path.expanduser("~/bin/rclone"),
    ]

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidates.extend(
            glob.glob(
                os.path.join(
                    local_appdata,
                    "Microsoft",
                    "WinGet",
                    "Packages",
                    "**",
                    "rclone.exe",
                ),
                recursive=True,
            )
        )

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return os.path.abspath(candidate)
    return None
