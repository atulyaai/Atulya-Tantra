"""Read ``.env`` into the environment, so keys work however Atulya is started.

``start.bat`` used to be the only thing that read ``.env``, with a parser that broke on quotes, spaces and the
byte-order mark Notepad adds. This reader handles those, never overrides a variable that is already set, and
looks next to the project (the folder with ``start.bat``) and in the current folder.
"""
from __future__ import annotations

import os
from pathlib import Path


def parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.lstrip("﻿").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.lower().startswith("export "):
            line = line[7:].lstrip()
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if value[:1] in ("'", '"') and value.count(value[0]) >= 2:
            value = value[1:value.index(value[0], 1)]
        else:
            value = value.split(" #", 1)[0].strip()
        if key:
            values[key] = value
    return values


def load_env(paths: list[Path] | None = None) -> list[Path]:
    """Load the first-found values from each file; returns the files that were read."""
    root = Path(__file__).resolve().parents[1]
    read: list[Path] = []
    for path in paths or [root / ".env", Path.cwd() / ".env"]:
        try:
            values = parse_env(path.read_text(encoding="utf-8-sig"))
        except OSError:
            continue
        read.append(path)
        for key, value in values.items():
            if value and not os.environ.get(key):
                os.environ[key] = value
    return read


def env_path() -> Path:
    """The .env that Atulya writes to: the one next to start.bat."""
    return Path(__file__).resolve().parents[1] / ".env"


def set_env_value(key: str, value: str, path: Path | None = None) -> None:
    """Set (or, with an empty value, remove) one variable in .env and in this running process."""
    if not key.replace("_", "").isalnum() or any(c in value for c in "\r\n\0"):
        raise ValueError("Invalid key or value")
    path = path or env_path()
    lines = path.read_text(encoding="utf-8-sig").splitlines() if path.exists() else []
    out, done = [], False
    for line in lines:
        name = line.split("=", 1)[0].strip().removeprefix("export ").strip()
        if "=" in line and not line.lstrip().startswith("#") and name == key:
            if value and not done:
                out.append(f"{key}={value}")
            done = True
        else:
            out.append(line)
    if value and not done:
        out.append(f"{key}={value}")
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
    try:
        tmp.chmod(0o600)  # keys: readable by you only (a no-op on Windows)
    except OSError:
        pass
    tmp.replace(path)
    if value:
        os.environ[key] = value
    else:
        os.environ.pop(key, None)
