"""PC control: apps, typing, hotkeys, files, clipboard, screen and commands."""
from __future__ import annotations

import asyncio
import os
import platform
import subprocess
from typing import Any, Callable



from atulya import actions as _d

# ── pc_control ────────────────────────────────────────────────────────────
APP_ALLOWLIST: dict[str, list[str]] = {
    "notepad": ["notepad.exe"], "calculator": ["calc.exe"], "explorer": ["explorer.exe"],
    "paint": ["mspaint.exe"], "chrome": ["chrome.exe"], "edge": ["msedge.exe"],
    "vscode": ["code"], "terminal": ["wt.exe"], "spotify": ["spotify.exe"],
}
BLOCKED_HOTKEYS = {("win", "r"), ("alt", "f4"), ("ctrl", "alt", "delete"), ("ctrl", "shift", "esc")}
DISABLED = "PC control is switched off. Set ATULYA_PC_CONTROL=on to allow it."


def enabled() -> bool:
    return os.environ.get("ATULYA_PC_CONTROL", "").strip().lower() in ("on", "1", "true", "yes")


def _not_allowed(level: str = "full") -> str | None:
    """The sentence to say if whoever is asking may not do this on the computer, else None."""
    from atulya import computer

    try:
        computer.require(level)
    except computer.Refused as exc:
        return str(exc)
    return None


def _gui():
    from atulya.computer import get_gui

    return get_gui()


@_d.tool("pc_open_app", "Open an application on this computer (from a safe list)", {
    "app": {"type": "string", "description": "notepad, calculator, explorer, paint, chrome, edge, vscode, terminal, spotify"},
})
async def pc_open_app(app: str) -> str:
    if not enabled():
        return DISABLED
    if (denied := _not_allowed()):
        return denied
    cmd = APP_ALLOWLIST.get(app.strip().lower())
    _d.audit("pc_open_app", app=app, allowed=bool(cmd))
    if cmd is None:
        return f"I only open: {', '.join(APP_ALLOWLIST)}."
    if platform.system() != "Windows":
        return "App launching is only wired up on Windows so far."
    await asyncio.to_thread(subprocess.Popen, cmd)
    return f"Opening {app}."


@_d.tool("pc_type", "Type text into the window that is currently focused", {
    "text": {"type": "string", "description": "What to type"},
})
async def pc_type(text: str) -> str:
    if not enabled():
        return DISABLED
    if (denied := _not_allowed()):
        return denied
    _d.audit("pc_type", chars=len(text))
    await asyncio.to_thread(_gui().write, text[:500], 0.01)
    return "Typed it."


@_d.tool("pc_hotkey", "Press a keyboard shortcut, e.g. ctrl+c", {
    "keys": {"type": "string", "description": "Keys joined with +, e.g. 'ctrl+s'"},
})
async def pc_hotkey(keys: str) -> str:
    if not enabled():
        return DISABLED
    if (denied := _not_allowed()):
        return denied
    combo = tuple(k.strip().lower() for k in keys.split("+") if k.strip())
    _d.audit("pc_hotkey", keys=combo)
    if not combo or combo in BLOCKED_HOTKEYS:
        return "I won't press that shortcut."
    await asyncio.to_thread(_gui().hotkey, *combo)
    return f"Pressed {'+'.join(combo)}."


@_d.tool("pc_screenshot", "Take a screenshot of the screen and save it", {})
async def pc_screenshot() -> str:
    if not enabled():
        return DISABLED
    if (denied := _not_allowed()):
        return denied
    path = os.path.join(os.environ.get("ATULYA_AGENT_DATA_DIR", "data/agent"), "screenshot.png")
    _d.audit("pc_screenshot", path=path)
    await asyncio.to_thread(_gui().screenshot, path)
    return f"Saved a screenshot to {path}."


# ── your computer: files, clipboard, screen, commands (rules and code live in computer.py) ──────────────────────
async def _on_computer(label: str, log: dict[str, Any], fn: Callable[..., Any], *args: Any) -> str:
    """Run a computer action off the event loop; always audited (only what `log` says, never file contents); refusals
    come back as plain sentences."""
    from atulya import computer

    if not enabled():
        return DISABLED
    _d.audit(label, **log)
    try:
        return str(await asyncio.to_thread(fn, *args))
    except computer.Refused as exc:
        return str(exc)
    except Exception as exc:  # noqa: BLE001 - a missing tool or a busy file should not crash the chat
        return f"That did not work: {type(exc).__name__}: {exc}"


@_d.tool("files", "Work with files on this computer: list a folder, find, read, copy, move, delete (to trash), write, edit, open or print", {
    "action": {"type": "string", "description": "list, find, read, copy, move, delete, folder, write, edit, open, print"},
    "path": {"type": "string", "description": "File or folder (e.g. Documents/report.docx). For find: the words to look for", "default": ""},
    "to": {"type": "string", "description": "Where to copy or move it, or the folder to search in", "default": ""},
    "text": {"type": "string", "description": "write: the new text. edit: the new wording", "default": ""},
    "old": {"type": "string", "description": "edit: the exact text to replace", "default": ""},
    "overwrite": {"type": "boolean", "description": "Replace an existing file", "default": False},
})
async def files(action: str, path: str = "", to: str = "", text: str = "", old: str = "", overwrite: bool = False) -> str:
    from atulya import computer as s

    table: dict[str, tuple[Callable[..., Any], tuple[Any, ...]]] = {
        "list": (s.list_dir, (path,)), "find": (s.find_files, (path, to)), "read": (s.read_file, (path,)),
        "copy": (s.copy_file, (path, to, overwrite)), "move": (s.move_file, (path, to, overwrite)),
        "delete": (s.delete_file, (path,)), "folder": (s.make_folder, (path,)),
        "write": (s.write_file, (path, text, overwrite)), "edit": (s.edit_file, (path, old, text)),
        "open": (s.open_path, (path,)), "print": (s.print_file, (path, to)),
    }
    act = (action or "").strip().lower()
    if act not in table:
        return f"files can: {', '.join(table)}."
    fn, args = table[act]
    return await _d._on_computer(f"files.{act}", {"path": path, "to": to, "overwrite": overwrite}, fn, *args)


@_d.tool("clipboard", "Read what is on the clipboard, or put text on it", {
    "action": {"type": "string", "description": "get or set"},
    "text": {"type": "string", "description": "set: the text to copy", "default": ""},
})
async def clipboard(action: str, text: str = "") -> str:
    from atulya import computer as s

    if (action or "").strip().lower() == "set":
        return await _d._on_computer("clipboard.set", {"chars": len(text)}, s.clipboard_set, text)
    return await _d._on_computer("clipboard.get", {}, s.clipboard_get)


@_d.tool("screen", "See and use the screen: read what is on it, list or switch windows, click, move or scroll the mouse", {
    "action": {"type": "string", "description": "read, windows, focus, click_text, click, double_click, right_click, move, scroll"},
    "title": {"type": "string", "description": "focus: part of the window title", "default": ""},
    "text": {"type": "string", "description": "click_text: exact visible label to click", "default": ""},
    "x": {"type": "integer", "description": "click/move: pixels from the left", "default": 0},
    "y": {"type": "integer", "description": "click/move: pixels from the top", "default": 0},
    "amount": {"type": "integer", "description": "scroll: positive up, negative down", "default": 0},
})
async def screen(action: str, title: str = "", x: int = 0, y: int = 0, amount: int = 0,
                 text: str = "") -> str:
    from atulya import computer as s

    act = (action or "").strip().lower()
    if act == "read":
        return await _d._on_computer("screen.read", {}, s.read_screen)
    if act == "windows":
        return await _d._on_computer("screen.windows", {}, s.window_list)
    if act == "focus":
        return await _d._on_computer("screen.focus", {"title": title}, s.window_focus, title)
    if act == "click_text":
        return await _d._on_computer("screen.click_text", {"text": text}, s.click_text, text)
    return await _d._on_computer(f"screen.{act}", {"x": x, "y": y, "amount": amount}, s.mouse, act, x, y, amount)


@_d.tool("run_command", "Run one command on this computer and show what it printed (no pipes or chaining)", {
    "command": {"type": "string", "description": "e.g. 'ipconfig /all' or 'git status'"},
    "folder": {"type": "string", "description": "Optional folder to run it in", "default": ""},
})
async def run_command(command: str, folder: str = "") -> str:
    from atulya import computer as s

    return await _d._on_computer("run_command", {"command": command, "folder": folder}, s.run_command, command, folder)


@_d.tool("install_software", "Install a program with the computer's package manager (winget, brew or apt)", {
    "package": {"type": "string", "description": "The package id, e.g. 'VideoLAN.VLC' on Windows or 'vlc' on Linux/Mac"},
})
async def install_software(package: str) -> str:
    from atulya import computer as s

    return await _d._on_computer("install_software", {"package": package}, s.install_software, package)


@_d.tool("check_computer", "Check this computer's health (disk, memory, processor, internet, busiest programs) and say what to fix", {})
async def check_computer() -> str:
    from atulya import computer as s

    return await _d._on_computer("check_computer", {}, s.diagnose)


