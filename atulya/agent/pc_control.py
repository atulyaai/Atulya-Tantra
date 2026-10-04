"""Control this computer — off by default, always confirmed, always audited.

Turn it on with ``ATULYA_PC_CONTROL=on``. Every tool here also needs the
user's confirmation each time (see ``cognition/safety.py``), may only launch
apps from a fixed allowlist, and writes to the audit log.
"""
from __future__ import annotations

import asyncio
import os
import platform
import subprocess

from atulya.agent.audit import audit
from atulya.agent.tools import tool

APP_ALLOWLIST: dict[str, list[str]] = {
    "notepad": ["notepad.exe"], "calculator": ["calc.exe"], "explorer": ["explorer.exe"],
    "paint": ["mspaint.exe"], "chrome": ["chrome.exe"], "edge": ["msedge.exe"],
    "vscode": ["code"], "terminal": ["wt.exe"], "spotify": ["spotify.exe"],
}
BLOCKED_HOTKEYS = {("win", "r"), ("alt", "f4"), ("ctrl", "alt", "delete"), ("ctrl", "shift", "esc")}
DISABLED = "PC control is switched off. Set ATULYA_PC_CONTROL=on to allow it."


def enabled() -> bool:
    return os.environ.get("ATULYA_PC_CONTROL", "").strip().lower() in ("on", "1", "true", "yes")


def _gui():
    import pyautogui

    pyautogui.FAILSAFE = True  # slam the mouse into a corner to abort
    return pyautogui


@tool("pc_open_app", "Open an application on this computer (from a safe list)", {
    "app": {"type": "string", "description": "notepad, calculator, explorer, paint, chrome, edge, vscode, terminal, spotify"},
})
async def pc_open_app(app: str) -> str:
    if not enabled():
        return DISABLED
    cmd = APP_ALLOWLIST.get(app.strip().lower())
    audit("pc_open_app", app=app, allowed=bool(cmd))
    if cmd is None:
        return f"I only open: {', '.join(APP_ALLOWLIST)}."
    if platform.system() != "Windows":
        return "App launching is only wired up on Windows so far."
    await asyncio.to_thread(subprocess.Popen, cmd)
    return f"Opening {app}."


@tool("pc_type", "Type text into the window that is currently focused", {
    "text": {"type": "string", "description": "What to type"},
})
async def pc_type(text: str) -> str:
    if not enabled():
        return DISABLED
    audit("pc_type", chars=len(text))
    await asyncio.to_thread(_gui().write, text[:500], 0.01)
    return "Typed it."


@tool("pc_hotkey", "Press a keyboard shortcut, e.g. ctrl+c", {
    "keys": {"type": "string", "description": "Keys joined with +, e.g. 'ctrl+s'"},
})
async def pc_hotkey(keys: str) -> str:
    if not enabled():
        return DISABLED
    combo = tuple(k.strip().lower() for k in keys.split("+") if k.strip())
    audit("pc_hotkey", keys=combo)
    if not combo or combo in BLOCKED_HOTKEYS:
        return "I won't press that shortcut."
    await asyncio.to_thread(_gui().hotkey, *combo)
    return f"Pressed {'+'.join(combo)}."


@tool("pc_screenshot", "Take a screenshot of the screen and save it", {})
async def pc_screenshot() -> str:
    if not enabled():
        return DISABLED
    path = os.path.join(os.environ.get("ATULYA_AGENT_DATA_DIR", "data/agent"), "screenshot.png")
    audit("pc_screenshot", path=path)
    await asyncio.to_thread(_gui().screenshot, path)
    return f"Saved a screenshot to {path}."
