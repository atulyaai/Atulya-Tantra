"""Keep frontend package metadata aligned with atulya.__version__."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sync(check: bool = False) -> bool:
    source = (ROOT / "atulya" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', source, re.MULTILINE)
    if not match:
        raise ValueError("atulya.__version__ was not found")
    version = match.group(1)
    changed = False
    for filename in ("package.json", "package-lock.json"):
        path = ROOT / "drishti" / filename
        data = json.loads(path.read_text(encoding="utf-8"))
        data["version"] = version
        if filename == "package-lock.json" and isinstance(data.get("packages", {}).get(""), dict):
            data["packages"][""]["version"] = version
        rendered = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        if path.read_text(encoding="utf-8") != rendered:
            if check:
                return False
            path.write_text(rendered, encoding="utf-8")
            changed = True
    return not changed if check else True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if frontend versions are out of sync")
    args = parser.parse_args()
    if not sync(args.check):
        raise SystemExit("Frontend package version does not match atulya.__version__; run python drishti/sync_version.py")
