"""Build the web app only when it is out of date, so node_modules can be deleted and rebuilt on demand.

Run by start.bat. Exit code 0 means ``frontend/dist/index.html`` is ready.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parent
DIST = WEB / "dist" / "index.html"
MODULES = WEB / "node_modules"
# Everything the build is made from: the flat folder's own files (not dist, node_modules or the Python tools).
SOURCES = sorted(p for p in WEB.iterdir() if p.is_file() and p.suffix in {".jsx", ".js", ".html", ".css", ".json", ".svg", ".bin", ".webmanifest"} and p.name != "package-lock.json")


def newest(paths: list[Path]) -> float:
    latest = 0.0
    for path in paths:
        if path.is_dir():
            files = [p for p in path.rglob("*") if p.is_file() and "node_modules" not in p.parts]
            latest = max([latest] + [p.stat().st_mtime for p in files])
        elif path.exists():
            latest = max(latest, path.stat().st_mtime)
    return latest


STAMP = WEB / "dist" / ".source-hash"


def source_hash() -> str:
    """Hash of what the build is made from. File times lie after a git pull or a copy; content does not."""
    digest = hashlib.sha256()
    for path in SOURCES:
        files = sorted(p for p in path.rglob("*") if p.is_file() and "node_modules" not in p.parts) if path.is_dir() else [path]
        for file in files:
            if file.exists():
                digest.update(file.name.encode())
                digest.update(file.read_bytes())
    return digest.hexdigest()


def needs_install() -> bool:
    marker = MODULES / ".package-lock.json"
    return not MODULES.exists() or not marker.exists() or (WEB / "package.json").stat().st_mtime > marker.stat().st_mtime


def needs_build() -> bool:
    if not DIST.exists() or not STAMP.exists():
        return True
    return STAMP.read_text().strip() != source_hash()


def run(cmd: list[str]) -> int:
    npm = shutil.which("npm")
    if npm is None:
        print("  Node.js (npm) not found. Install Node.js 18+ from https://nodejs.org")
        return 1
    return subprocess.call([npm, *cmd], cwd=WEB, shell=sys.platform == "win32")


def main() -> int:
    if not needs_build():
        print("  Web app is up to date.")
        return 0
    if needs_install():
        print("  Installing web app tools (first time only)...")
        if run(["install", "--silent", "--no-audit", "--no-fund"]) != 0:
            return 1
    print("  Building the web app...")
    if DIST.exists():
        DIST.unlink()  # a failed build must never leave an out-of-date app behind
    if run(["run", "build", "--silent"]) != 0 or not DIST.exists():
        print("  WARNING: the web app failed to build. Try: cd frontend && npm run build")
        return 1
    STAMP.write_text(source_hash())
    return 0


if __name__ == "__main__":
    sys.exit(main())
