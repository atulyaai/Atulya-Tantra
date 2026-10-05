"""Sharir (शरीर, "body"): what Atulya can do on a computer, as plain functions.

Files, clipboard, windows, mouse, screen, commands, software, printing. It knows nothing about the brain: the
assistant's tools (kriya.py) and the helper that runs on your other computers (dut.py) both call it, so the rules
live in one place:

* files stay inside the folders you allow (default: Documents, Downloads, Desktop, Pictures, Music, Videos), and a few
  places are never touched (SSH and cloud keys, browser profiles, Atulya's own data, .env files);
* deleting moves to Atulya's own trash, nothing is overwritten unless asked, and edited files are backed up first;
* commands never go through a shell, a short list of destructive ones is refused, and output is capped;
* a paired device carries a permission level (read < files < full) that is checked before anything runs.
"""
from __future__ import annotations

import fnmatch
import os
import platform
import re
import shlex
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from atulya.bhava import current_access

LEVELS = ("read", "files", "full")
MAX_READ = 200_000  # characters handed back from a file
MAX_OUTPUT = 4000   # characters handed back from a command


class Refused(Exception):
    """A request the rules do not allow; the message is safe to say to the user."""


def system() -> str:
    return platform.system()


# ── who is asking, and may they? ──────────────────────────────────────────────────────────────────────────
def caller_level() -> str | None:
    """The permission of whoever is asking: paired devices carry their own, ordinary web users get none, and the
    owner (admin, or local use such as routines and the command line) gets everything."""
    access = current_access.get() or {}
    role = access.get("role", "")
    if role == "device":
        level = access.get("permission")
        return level if level in LEVELS else None
    if role == "user":
        return None
    return "full"


def require(level: str) -> None:
    have = caller_level()
    if have is None:
        raise Refused("Only the owner can do that on this computer.")
    if LEVELS.index(have) < LEVELS.index(level):
        raise Refused(f"This device is paired for “{have}” only; that needs “{level}”.")


# ── which files ───────────────────────────────────────────────────────────────────────────────────────────
def allowed_roots() -> list[Path]:
    raw = os.environ.get("ATULYA_ALLOWED_FOLDERS", "")
    if raw.strip():
        roots = [Path(p).expanduser() for p in raw.split(os.pathsep) if p.strip()]
    else:
        home = Path.home()
        roots = [home / name for name in ("Documents", "Downloads", "Desktop", "Pictures", "Music", "Videos")]
    return [r.resolve() for r in roots if r.is_dir()]


_NEVER = (".ssh", ".aws", ".gnupg", ".kube", ".docker", "gcloud", ".azure", "kosh", "AppData", "Library")
_NEVER_NAMES = ("id_rsa", "id_ed25519", "known_hosts", "credentials", "secrets", "passwords")
_NEVER_SUFFIX = (".pem", ".key", ".p12", ".pfx", ".kdbx", ".env")


def _forbidden(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    if any(n.lower() in parts for n in _NEVER) or path.name.startswith(".env"):
        return True
    low = path.name.lower()
    return low.endswith(_NEVER_SUFFIX) or any(low.startswith(n) for n in _NEVER_NAMES)


def resolve(path: str, *, must_exist: bool = True) -> Path:
    """Turn what the user said into a real path that is inside an allowed folder, or refuse."""
    roots = allowed_roots()
    if not roots:
        raise Refused("No folders are allowed yet. Set ATULYA_ALLOWED_FOLDERS, or create Documents/Downloads/Desktop.")
    text = (path or "").strip().strip('"').strip("'")
    if not text:
        raise Refused("Which file or folder?")
    p = Path(text).expanduser()
    if not p.is_absolute():
        head = p.parts[0].lower() if p.parts else ""
        named = next((r for r in roots if r.name.lower() == head), None)
        if named:
            p = named.joinpath(*p.parts[1:])
        else:
            cands = [r / p for r in roots]
            p = next((c for c in cands if c.exists()), cands[0])
    real = p.resolve()
    if not any(real == r or r in real.parents for r in roots):
        raise Refused(f"That is outside the folders I may use ({', '.join(r.name for r in roots)}).")
    if _forbidden(real):
        raise Refused("I never touch that kind of file (keys, passwords, browser data or Atulya's own data).")
    if must_exist and not real.exists():
        raise Refused(f"I can't find {text}.")
    return real


def _size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n} B"


# ── files: look ───────────────────────────────────────────────────────────────────────────────────────────
def list_dir(path: str = "", limit: int = 100) -> str:
    require("read")
    if not path.strip():
        return "I may use: " + ", ".join(str(r) for r in allowed_roots())
    folder = resolve(path)
    if not folder.is_dir():
        raise Refused(f"{folder.name} is a file, not a folder.")
    rows = []
    for item in sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[: max(1, min(limit, 300))]:
        if _forbidden(item):
            continue
        kind = "folder" if item.is_dir() else _size(item.stat().st_size)
        rows.append(f"{item.name}{'/' if item.is_dir() else ''}  ({kind})")
    return f"{folder}:\n" + ("\n".join(rows) or "(empty)")


def find_files(query: str, where: str = "", limit: int = 30) -> str:
    """Find by name (words or a pattern like *.pdf), newest first."""
    require("read")
    roots = [resolve(where)] if where.strip() else allowed_roots()
    words = [w for w in re.split(r"\s+", (query or "").lower().strip()) if w]
    if not words:
        raise Refused("What should I look for?")
    found: list[tuple[float, Path]] = []
    for root in roots:
        for base, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and not _forbidden(Path(base) / d)]
            for name in names:
                low = name.lower()
                ok = all(fnmatch.fnmatch(low, w) if any(c in w for c in "*?") else w in low for w in words)
                full = Path(base) / name
                if ok and not _forbidden(full):
                    found.append((full.stat().st_mtime, full))
            if len(found) > 2000:
                break
    found.sort(reverse=True)
    if not found:
        return f"No files match “{query}”."
    lines = [f"{p}  ({datetime.fromtimestamp(t):%d %b %Y})" for t, p in found[: max(1, min(limit, 100))]]
    return f"{len(found)} match{'es' if len(found) != 1 else ''}:\n" + "\n".join(lines)


def read_file(path: str) -> str:
    """Text of a file: plain text, Word, Excel or PDF."""
    require("read")
    p = resolve(path)
    if p.is_dir():
        raise Refused(f"{p.name} is a folder. Ask me to list it.")
    suffix = p.suffix.lower()
    if suffix == ".docx":
        try:
            import docx

            text = "\n".join(par.text for par in docx.Document(str(p)).paragraphs)
        except ImportError as exc:
            raise Refused("Reading Word files needs python-docx: pip install python-docx") from exc
    elif suffix in (".xlsx", ".xlsm"):
        try:
            import openpyxl

            book = openpyxl.load_workbook(str(p), read_only=True, data_only=True)
            rows = []
            for sheet in book.worksheets[:3]:
                rows.append(f"[{sheet.title}]")
                rows += ["\t".join("" if c is None else str(c) for c in row) for row in sheet.iter_rows(values_only=True, max_row=200)]
            text = "\n".join(rows)
        except ImportError as exc:
            raise Refused("Reading Excel files needs openpyxl: pip install openpyxl") from exc
    elif suffix == ".pdf":
        try:
            import pypdf

            text = "\n".join((page.extract_text() or "") for page in pypdf.PdfReader(str(p)).pages[:40])
        except ImportError as exc:
            raise Refused("Reading PDFs needs pypdf: pip install pypdf") from exc
    else:
        raw = p.read_bytes()[: MAX_READ * 2]
        if b"\0" in raw[:2048]:
            raise Refused(f"{p.name} looks like a program or picture, not text.")
        text = raw.decode("utf-8", errors="replace")
    return text[:MAX_READ] + ("\n…(cut)" if len(text) > MAX_READ else "")


# ── files: change ─────────────────────────────────────────────────────────────────────────────────────────
def _trash_dir() -> Path:
    base = Path(os.environ.get("ATULYA_AGENT_DATA_DIR", "kosh/agent")) / "trash"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _to_trash(p: Path) -> Path:
    dest = _trash_dir() / f"{time.strftime('%Y%m%d-%H%M%S')}-{p.name}"
    shutil.move(str(p), str(dest))
    return dest


def _target(src: Path, dst: str) -> Path:
    out = resolve(dst, must_exist=False)
    return out / src.name if out.is_dir() else out


def copy_file(src: str, dst: str, overwrite: bool = False) -> str:
    require("files")
    s = resolve(src)
    d = _target(s, dst)
    if d.exists() and not overwrite:
        raise Refused(f"{d.name} already exists there. Say “overwrite” if you want it replaced.")
    d.parent.mkdir(parents=True, exist_ok=True)
    if s.is_dir():
        shutil.copytree(s, d, dirs_exist_ok=overwrite)
    else:
        if d.exists():
            _to_trash(d)
        shutil.copy2(s, d)
    return f"Copied {s.name} to {d.parent}."


def move_file(src: str, dst: str, overwrite: bool = False) -> str:
    require("files")
    s = resolve(src)
    d = _target(s, dst)
    if d.exists() and not overwrite:
        raise Refused(f"{d.name} already exists there. Say “overwrite” if you want it replaced.")
    d.parent.mkdir(parents=True, exist_ok=True)
    if d.exists():
        _to_trash(d)
    shutil.move(str(s), str(d))
    return f"Moved {s.name} to {d.parent}."


def delete_file(path: str) -> str:
    """Never really deletes: moves to Atulya's own trash, from where it can be put back."""
    require("files")
    p = resolve(path)
    if p in allowed_roots():
        raise Refused("I won't delete a whole top-level folder.")
    dest = _to_trash(p)
    return f"Moved {p.name} to the trash ({dest.parent})."


def make_folder(path: str) -> str:
    require("files")
    p = resolve(path, must_exist=False)
    p.mkdir(parents=True, exist_ok=True)
    return f"Made the folder {p}."


def write_file(path: str, content: str, overwrite: bool = False) -> str:
    require("files")
    p = resolve(path, must_exist=False)
    if p.exists() and not overwrite:
        raise Refused(f"{p.name} already exists. Say “overwrite” to replace it, or ask me to edit it.")
    if p.exists():
        shutil.copy2(p, _trash_dir() / f"{time.strftime('%Y%m%d-%H%M%S')}-{p.name}.bak")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Wrote {p.name} ({_size(len(content.encode('utf-8')))})."


def edit_file(path: str, find: str, replace: str, all_matches: bool = False) -> str:
    require("files")
    p = resolve(path)
    if not find:
        raise Refused("What text should I change?")
    text = p.read_text(encoding="utf-8")
    hits = text.count(find)
    if hits == 0:
        raise Refused(f"I can't find that text in {p.name}.")
    if hits > 1 and not all_matches:
        raise Refused(f"That text appears {hits} times in {p.name}. Tell me which, or say “all of them”.")
    shutil.copy2(p, _trash_dir() / f"{time.strftime('%Y%m%d-%H%M%S')}-{p.name}.bak")
    p.write_text(text.replace(find, replace) if all_matches else text.replace(find, replace, 1), encoding="utf-8")
    return f"Changed {hits if all_matches else 1} place{'s' if all_matches and hits != 1 else ''} in {p.name}."


def open_path(path: str) -> str:
    require("files")
    p = resolve(path)
    if system() == "Windows":
        os.startfile(str(p))  # type: ignore[attr-defined]  # noqa: S606
    else:
        subprocess.Popen(["open" if system() == "Darwin" else "xdg-open", str(p)])  # noqa: S603
    return f"Opened {p.name}."


def print_file(path: str, printer: str = "") -> str:
    require("files")
    p = resolve(path)
    if system() == "Windows":
        subprocess.run(["powershell", "-NoProfile", "-Command", f"Start-Process -FilePath '{p}' -Verb Print"],  # noqa: S603, S607
                       check=True, timeout=60)
    else:
        cmd = ["lp"] + (["-d", printer] if printer else []) + [str(p)]
        subprocess.run(cmd, check=True, timeout=60)  # noqa: S603
    return f"Sent {p.name} to the printer."


# ── clipboard ─────────────────────────────────────────────────────────────────────────────────────────────
def _clip_cmds(write: bool) -> list[list[str]]:
    s = system()
    if s == "Windows":
        return [["clip"]] if write else [["powershell", "-NoProfile", "-Command", "Get-Clipboard"]]
    if s == "Darwin":
        return [["pbcopy"]] if write else [["pbpaste"]]
    if write:
        return [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]
    return [["wl-paste"], ["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"]]


def clipboard_get() -> str:
    require("read")
    for cmd in _clip_cmds(False):
        if shutil.which(cmd[0]):
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)  # noqa: S603
            return out.stdout[:MAX_READ] or "The clipboard is empty."
    raise Refused("No clipboard tool found (on Linux install xclip or wl-clipboard).")


def clipboard_set(text: str) -> str:
    require("files")
    for cmd in _clip_cmds(True):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, input=text, text=True, timeout=10, check=True)  # noqa: S603
            return "Copied to the clipboard."
    raise Refused("No clipboard tool found (on Linux install xclip or wl-clipboard).")


# ── screen, mouse, windows ────────────────────────────────────────────────────────────────────────────────
def _gui():
    import pyautogui

    pyautogui.FAILSAFE = True  # slam the mouse into a corner to abort
    return pyautogui


def screenshot(path: str = "") -> str:
    require("read")
    out = Path(path) if path else Path(os.environ.get("ATULYA_AGENT_DATA_DIR", "kosh/agent")) / "screenshot.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    _gui().screenshot(str(out))
    return str(out)


def read_screen() -> str:
    """Take a screenshot and read the words on it (needs the tesseract OCR program)."""
    require("read")
    shot = screenshot()
    try:
        import pytesseract
        from PIL import Image

        text = pytesseract.image_to_string(Image.open(shot)).strip()
    except Exception as exc:  # noqa: BLE001 - missing OCR is the common case
        raise Refused(f"I saved a screenshot ({shot}) but can't read it: install tesseract and pytesseract. ({type(exc).__name__})") from exc
    return text[:MAX_READ] or "I couldn't find any text on the screen."


def mouse(action: str, x: int = 0, y: int = 0, amount: int = 0) -> str:
    require("full")
    g = _gui()
    w, h = g.size()
    if action in ("click", "double_click", "right_click", "move"):
        if not (0 <= int(x) < w and 0 <= int(y) < h):
            raise Refused(f"That point is off the screen ({w}x{h}).")
        if action == "move":
            g.moveTo(int(x), int(y), duration=0.2)
        else:
            {"click": g.click, "double_click": g.doubleClick, "right_click": g.rightClick}[action](int(x), int(y))
        return f"{action.replace('_', ' ').capitalize()} at {x},{y}."
    if action == "scroll":
        g.scroll(int(amount))
        return f"Scrolled {amount}."
    raise Refused("Mouse actions: click, double_click, right_click, move, scroll.")


def window_list() -> str:
    require("read")
    s = system()
    if s == "Windows":
        cmd = ["powershell", "-NoProfile", "-Command", "Get-Process | Where-Object {$_.MainWindowTitle} | ForEach-Object {$_.MainWindowTitle}"]
    elif s == "Darwin":
        cmd = ["osascript", "-e", 'tell application "System Events" to get name of (processes where background only is false)']
    elif shutil.which("wmctrl"):
        cmd = ["wmctrl", "-l"]
    else:
        raise Refused("Listing windows needs wmctrl on Linux.")
    return subprocess.run(cmd, capture_output=True, text=True, timeout=15).stdout.strip()[:MAX_OUTPUT] or "No windows found."  # noqa: S603


def window_focus(title: str) -> str:
    require("full")
    s = system()
    clean = re.sub(r"[^\w .\-]", "", title or "")[:80]
    if not clean:
        raise Refused("Which window?")
    if s == "Windows":
        cmd = ["powershell", "-NoProfile", "-Command",
               f"(New-Object -ComObject WScript.Shell).AppActivate('{clean}')"]
    elif s == "Darwin":
        cmd = ["osascript", "-e", f'tell application "{clean}" to activate']
    elif shutil.which("wmctrl"):
        cmd = ["wmctrl", "-a", clean]
    else:
        raise Refused("Switching windows needs wmctrl on Linux.")
    subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)  # noqa: S603
    return f"Switched to {clean}."


# ── commands and software ─────────────────────────────────────────────────────────────────────────────────
_BLOCKED = (
    r"\brm\s+(-\w*\s+)*-?\w*r\w*f?\w*\s+(/|~|\*)", r"\bmkfs", r"\bdd\s+if=", r"\bformat\b", r"\bdiskpart\b",
    r"\breg\s+delete", r"\bdel\s+/[sfq]", r"\brd\s+/s", r":\(\)\s*\{", r"\bchmod\s+-R\s+777\s+/", r"\bshutdown\b.*\b/?-?[rs]\b",
    r"\|\s*(sh|bash|zsh|powershell|pwsh|cmd)\b", r"\bcurl\b.*\|", r"\bwget\b.*\|", r"\bnet\s+user\b", r">\s*/dev/sd",
)
_WINDOWS_BUILTINS = {"dir", "type", "echo", "ver", "vol", "set", "where"}


def _run(argv: list[str], timeout: int, cwd: str | None = None) -> str:
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, cwd=cwd)  # noqa: S603
    except subprocess.TimeoutExpired as exc:
        raise Refused(f"That took longer than {timeout} seconds, so I stopped it.") from exc
    except FileNotFoundError as exc:
        raise Refused(f"There is no program called {argv[0]} on this computer.") from exc
    text = ((done.stdout or "") + (done.stderr or "")).strip()
    tail = text[-MAX_OUTPUT:] if len(text) > MAX_OUTPUT else text
    return f"{tail or '(no output)'}\n[exit code {done.returncode}]"


def run_command(command: str, folder: str = "", timeout: int = 30) -> str:
    """Run one program with its arguments. No pipes or shell tricks; a short list of destructive commands is refused."""
    require("full")
    text = (command or "").strip()
    if not text:
        raise Refused("What should I run?")
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in _BLOCKED):
        raise Refused("I won't run that: it could destroy data or hand control to a downloaded script.")
    if any(c in text for c in "|&;`$<>\n"):
        raise Refused("Give me one plain command without pipes, redirects or chaining.")
    argv = shlex.split(text, posix=system() != "Windows")
    if system() == "Windows" and argv and argv[0].lower() in _WINDOWS_BUILTINS:
        argv = ["cmd", "/c", *argv]
    cwd = str(resolve(folder)) if folder.strip() else None
    return _run(argv, max(1, min(int(timeout), 120)), cwd)


_PACKAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,79}$")


def install_software(package: str) -> str:
    """Install through the system's own package manager (winget, brew or apt). Always asked about first."""
    require("full")
    if not _PACKAGE.match(package or ""):
        raise Refused("That does not look like a package name (letters, digits, dots and dashes only).")
    s = system()
    if s == "Windows" and shutil.which("winget"):
        argv = ["winget", "install", "-e", "--id", package, "--accept-package-agreements", "--accept-source-agreements", "--silent"]
    elif s == "Darwin" and shutil.which("brew"):
        argv = ["brew", "install", package]
    elif shutil.which("apt-get"):
        argv = (["sudo", "-n"] if os.geteuid() != 0 else []) + ["apt-get", "install", "-y", package]  # type: ignore[attr-defined]
    else:
        raise Refused("I couldn't find winget, brew or apt on this computer.")
    return _run(argv, 600)


def diagnose() -> str:
    """A quick health check in plain words: disk, memory, load, network and the busiest programs."""
    require("read")
    import psutil

    lines, advice = [], []
    for part in {p.mountpoint: p for p in psutil.disk_partitions(all=False)}.values():
        try:
            use = psutil.disk_usage(part.mountpoint)
        except OSError:
            continue
        lines.append(f"Disk {part.mountpoint}: {100 - use.percent:.0f}% free ({_size(use.free)} of {_size(use.total)})")
        if use.percent > 90:
            advice.append(f"{part.mountpoint} is almost full: I can look for big files in Downloads to clear.")
    mem = psutil.virtual_memory()
    lines.append(f"Memory: {mem.percent:.0f}% in use ({_size(mem.available)} free)")
    if mem.percent > 90:
        advice.append("Memory is nearly full: close heavy programs (see the list below).")
    lines.append(f"Processor: {psutil.cpu_percent(interval=0.5):.0f}% busy, {psutil.cpu_count()} cores")
    try:
        import socket

        socket.create_connection(("1.1.1.1", 53), timeout=3).close()
        lines.append("Internet: reachable")
    except OSError:
        lines.append("Internet: NOT reachable")
        advice.append("No internet: check the router and Wi-Fi, then ask me to test again.")
    procs = sorted(psutil.process_iter(["name", "memory_percent"]), key=lambda p: p.info.get("memory_percent") or 0, reverse=True)[:5]
    lines.append("Biggest programs: " + ", ".join(f"{p.info['name']} ({p.info['memory_percent']:.0f}%)" for p in procs))
    return "\n".join(lines + (["", "What I would do:"] + [f"- {a}" for a in advice] if advice else ["", "Nothing looks wrong."]))


def summary(tool: str, args: dict[str, Any]) -> str:
    """One line for the activity log."""
    return f"{tool} {', '.join(f'{k}={str(v)[:60]}' for k, v in args.items() if k != 'content')}"
