"""PC control actions for the computer Atulya runs on (Windows, macOS, Linux).

Every action here is only reachable through a pending, user-approved request
(see tools/plugins/toolkit.py: ActionQueue). Nothing runs a shell string: apps
are launched from Start-menu/Applications/.desktop entries that match a name,
URLs must be http(s), media keys are fixed, and file search is read-only and
bounded to the user's home folders.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import time
import webbrowser
from datetime import datetime
from pathlib import Path

SYSTEM = platform.system()
HOME = Path.home()
SEARCH_ROOTS = [HOME / name for name in ("Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos")]
SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "AppData", "Library", ".cache"}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


# --- apps -------------------------------------------------------------------

_START_APPS: tuple[float, dict[str, str]] = (0.0, {})


def _windows_start_apps() -> dict[str, str]:
    """Name -> AppID for every Start-menu app, including Store apps (cached 10 minutes)."""
    global _START_APPS
    if time.monotonic() - _START_APPS[0] < 600 and _START_APPS[1]:
        return _START_APPS[1]
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=20, creationflags=0x08000000,
        ).stdout
        rows = json.loads(out or "[]")
    except (OSError, ValueError, subprocess.SubprocessError):
        rows = []
    apps = {_norm(row["Name"]): row["AppID"] for row in (rows if isinstance(rows, list) else [rows])
            if isinstance(row, dict) and row.get("Name") and row.get("AppID")
            and "uninstall" not in str(row["Name"]).lower()}
    _START_APPS = (time.monotonic(), apps)
    return apps


def _app_entries() -> dict[str, Path | str]:
    """Map display names to launchable entries found in the usual app menus."""
    entries: dict[str, Path | str] = {}
    if SYSTEM == "Windows":
        entries.update(_windows_start_apps())
    elif SYSTEM == "Darwin":
        for root in (Path("/Applications"), Path("/System/Applications"), HOME / "Applications"):
            if root.is_dir():
                for app in root.glob("*.app"):
                    entries.setdefault(_norm(app.stem), app)
    else:
        for root in (Path("/usr/share/applications"), HOME / ".local/share/applications"):
            if root.is_dir():
                for desktop in root.glob("*.desktop"):
                    try:
                        name = re.search(r"^Name=(.+)$", desktop.read_text(errors="ignore"), re.M)
                    except OSError:
                        continue
                    entries.setdefault(_norm(name.group(1) if name else desktop.stem), desktop)
    return entries


def find_app(name: str) -> tuple[str, Path | str] | None:
    wanted = _norm(name)
    if not wanted:
        return None
    entries = _app_entries()
    if wanted in entries:
        return wanted, entries[wanted]
    starts = sorted((key for key in entries if key.startswith(wanted)), key=len)
    contains = sorted((key for key in entries if wanted in key), key=len)
    for key in starts + contains:
        return key, entries[key]
    return None


def open_app(name: str) -> str:
    found = find_app(name)
    if found is None:
        return f"No installed app matches '{name}'."
    label, entry = found
    if SYSTEM == "Windows":
        # A Start-menu AppID, launched through the shell's Apps folder, never a command line.
        subprocess.Popen(["explorer.exe", "shell:AppsFolder\\" + str(entry)], creationflags=0x08000000)
    elif SYSTEM == "Darwin":
        subprocess.Popen(["open", "-a", str(entry)])
    else:
        launcher = shutil.which("gtk-launch")
        if launcher:
            subprocess.Popen([launcher, entry.stem])
        else:
            subprocess.Popen(["xdg-open", str(entry)])
    return f"Opened {label.title()}."


def open_url(url: str) -> str:
    if not re.fullmatch(r"https?://[^\s]{1,2000}", url.strip()):
        return "Only http(s) web addresses can be opened."
    webbrowser.open(url.strip())
    return f"Opened {url.strip()} in the browser."


# --- files ------------------------------------------------------------------

def search_files(query: str, limit: int = 15, budget_seconds: float = 4.0) -> str:
    terms = _norm(query).split()
    if not terms:
        return "Say what file name to look for."
    deadline = time.monotonic() + budget_seconds
    hits: list[tuple[float, Path]] = []
    for root in SEARCH_ROOTS:
        if not root.is_dir():
            continue
        for current, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            for filename in files:
                if all(term in _norm(filename) for term in terms):
                    path = Path(current) / filename
                    try:
                        hits.append((path.stat().st_mtime, path))
                    except OSError:
                        continue
            if time.monotonic() > deadline:
                break
    if not hits:
        return f"No files matching '{query}' in Desktop, Documents, Downloads, Pictures, Music or Videos."
    hits.sort(reverse=True)
    lines = [f"- {path.relative_to(HOME)} ({datetime.fromtimestamp(mtime):%Y-%m-%d})" for mtime, path in hits[:limit]]
    more = f"\n…and {len(hits) - limit} more." if len(hits) > limit else ""
    return "Newest matches:\n" + "\n".join(lines) + more


# --- media and volume -----------------------------------------------------------

MEDIA_COMMANDS = ("play_pause", "next", "previous", "volume_up", "volume_down", "mute")
_WINDOWS_KEYS = {"play_pause": 0xB3, "next": 0xB0, "previous": 0xB1,
                 "volume_up": 0xAF, "volume_down": 0xAE, "mute": 0xAD}


def media_control(command: str, steps: int = 1) -> str:
    if command not in MEDIA_COMMANDS:
        return f"Unknown media command. Use one of: {', '.join(MEDIA_COMMANDS)}."
    repeat = max(1, min(int(steps), 10)) if command.startswith("volume") else 1
    if SYSTEM == "Windows":
        import ctypes

        key = _WINDOWS_KEYS[command]
        for _ in range(repeat):
            ctypes.windll.user32.keybd_event(key, 0, 0, 0)
            ctypes.windll.user32.keybd_event(key, 0, 2, 0)
    elif SYSTEM == "Darwin":
        scripts = {
            "volume_up": f"set volume output volume ((output volume of (get volume settings)) + {6 * repeat})",
            "volume_down": f"set volume output volume ((output volume of (get volume settings)) - {6 * repeat})",
            "mute": "set volume output muted not (output muted of (get volume settings))",
            "play_pause": 'tell application "Music" to playpause',
            "next": 'tell application "Music" to next track',
            "previous": 'tell application "Music" to previous track',
        }
        subprocess.run(["osascript", "-e", scripts[command]], check=False, timeout=5)
    else:
        if command.startswith("volume") or command == "mute":
            if not shutil.which("pactl"):
                return "Volume control needs PulseAudio/PipeWire (pactl)."
            arg = {"volume_up": f"+{5 * repeat}%", "volume_down": f"-{5 * repeat}%"}.get(command)
            subprocess.run(["pactl", "set-sink-mute" if arg is None else "set-sink-volume", "@DEFAULT_SINK@",
                            "toggle" if arg is None else arg], check=False, timeout=5)
        else:
            if not shutil.which("playerctl"):
                return "Media control needs playerctl."
            subprocess.run(["playerctl", {"play_pause": "play-pause"}.get(command, command)], check=False, timeout=5)
    return {"play_pause": "Toggled play/pause.", "next": "Skipped to the next track.",
            "previous": "Went back a track.", "mute": "Toggled mute."}.get(
        command, f"Volume {'up' if command == 'volume_up' else 'down'} {repeat} step(s).")


# --- screenshots ----------------------------------------------------------------

def take_screenshot(data_dir: Path) -> str:
    folder = data_dir / "screenshots"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"screenshot-{datetime.now():%Y%m%d-%H%M%S}.png"
    if SYSTEM == "Windows":
        script = (
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
            "$b=[System.Windows.Forms.SystemInformation]::VirtualScreen;"
            "$i=New-Object System.Drawing.Bitmap $b.Width,$b.Height;"
            "$g=[System.Drawing.Graphics]::FromImage($i);"
            "$g.CopyFromScreen($b.Left,$b.Top,0,0,$i.Size);"
            "$i.Save($env:ATULYA_SHOT,[System.Drawing.Imaging.ImageFormat]::Png)"
        )
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], check=False,
                       timeout=20, env={**os.environ, "ATULYA_SHOT": str(target)}, creationflags=0x08000000)
    elif SYSTEM == "Darwin":
        subprocess.run(["screencapture", "-x", str(target)], check=False, timeout=20)
    else:
        for command in (["gnome-screenshot", "-f", str(target)], ["grim", str(target)],
                        ["import", "-window", "root", str(target)]):
            if shutil.which(command[0]):
                subprocess.run(command, check=False, timeout=20)
                break
    if not target.is_file():
        return "The screenshot could not be captured on this system."
    return f"Screenshot saved: {target.name}"
