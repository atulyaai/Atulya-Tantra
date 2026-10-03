"""3D people Atulya shows while it talks.

The GLB files come from the TalkingHead project's example avatars and are
downloaded into ``runtime/avatars`` on first run (``python -m drishti.avatars``,
which start.bat calls). They are free for non-commercial use only:

- female: created at Avaturn (https://avaturn.me) for non-commercial use
- male:   created at Avatar SDK / MetaPerson (https://avatarsdk.com) for non-commercial use

To use your own avatar, drop a TalkingHead-compatible GLB (ARKit + Oculus
viseme blend shapes) into ``runtime/avatars`` as ``female.glb`` or ``male.glb``.
"""
from __future__ import annotations

import logging
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

AVATAR_DIR = Path(__file__).resolve().parents[1] / "runtime" / "avatars"
_SOURCE = "https://raw.githubusercontent.com/met4citizen/TalkingHead/main/avatars/{file}"
AVATARS = {
    "female": {"file": "avaturn.glb", "size": "~14 MB"},
    "male": {"file": "avatarsdk.glb", "size": "~12 MB"},
}


def avatar_path(name: str) -> Path:
    return AVATAR_DIR / f"{name}.glb"


def ensure_avatars() -> dict[str, bool]:
    """Download any missing avatar. Returns which ones are present afterwards."""
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    present = {}
    for name, spec in AVATARS.items():
        dest = avatar_path(name)
        if not dest.exists():
            tmp = dest.with_suffix(".part")
            try:
                print(f"   Downloading the {name} avatar ({spec['size']})...", flush=True)
                urllib.request.urlretrieve(_SOURCE.format(file=spec["file"]), str(tmp))
                tmp.replace(dest)
            except Exception as exc:  # offline: Atulya shows the orb instead
                logger.warning("Avatar %s download failed: %s", name, exc)
                tmp.unlink(missing_ok=True)
        present[name] = dest.exists()
    return present


if __name__ == "__main__":
    found = ensure_avatars()
    print("   Avatars: " + ", ".join(f"{k} {'ready' if v else 'missing (the orb is shown instead)'}"
                                   for k, v in found.items()))
