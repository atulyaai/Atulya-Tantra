"""Model-callable tools — restores from base64 parts (temporary recovery path)."""
from __future__ import annotations
import base64
from pathlib import Path

_dir = Path(__file__).resolve().parent
_b64 = "".join(
    (_dir / f"_toolkit_b64_{i}.txt").read_text(encoding="ascii").strip()
    for i in range(4)
)
exec(compile(base64.b64decode(_b64), str(_dir / "toolkit.py"), "exec"), globals())
