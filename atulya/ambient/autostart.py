"""Start the listener when you log in (or at boot on a headless Linux box).

  Windows  a launcher in the Startup folder (runs with pythonw: no console)
  macOS    a LaunchAgent (~/Library/LaunchAgents/ai.atulya.listener.plist)
  Linux    an XDG autostart entry for desktop logins, or a systemd user
           service for headless devices such as a Raspberry Pi
"""
from __future__ import annotations

import platform
import shlex
import sys
from pathlib import Path
from xml.sax.saxutils import escape

LABEL = "ai.atulya.listener"


def autostart_entry(system: str | None = None, python: str | None = None, home: Path | None = None,
                    args: list[str] | None = None, mode: str = "desktop") -> tuple[Path, str]:
    """(file to write, its contents) for this platform."""
    system = system or platform.system()
    python = python or sys.executable
    home = home or Path.home()
    args = list(args or [])
    if system == "Windows":
        pythonw = python[:-10] + "pythonw.exe" if python.lower().endswith("python.exe") else python
        path = home / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / \
            "Atulya Listener.bat"
        line = " ".join(['start ""', f'"{pythonw}"', "-m", "atulya.ambient", *(f'"{a}"' for a in args)])
        return path, f"@echo off\r\n{line}\r\n"
    if system == "Darwin":
        path = home / "Library" / "LaunchAgents" / f"{LABEL}.plist"
        program = "".join(f"\n    <string>{escape(a)}</string>" for a in [python, "-m", "atulya.ambient", *args])
        return path, (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0">\n<dict>\n'
            f"  <key>Label</key>\n  <string>{LABEL}</string>\n"
            f"  <key>ProgramArguments</key>\n  <array>{program}\n  </array>\n"
            "  <key>RunAtLoad</key>\n  <true/>\n  <key>KeepAlive</key>\n  <true/>\n"
            "</dict>\n</plist>\n"
        )
    command = shlex.join([python, "-m", "atulya.ambient", *args])
    if mode == "systemd":
        path = home / ".config" / "systemd" / "user" / "atulya-listener.service"
        return path, (
            "[Unit]\nDescription=Atulya always-listening assistant\nAfter=network-online.target sound.target\n\n"
            f"[Service]\nExecStart={command} --no-tray\nRestart=on-failure\nRestartSec=5\n\n"
            "[Install]\nWantedBy=default.target\n"
        )
    path = home / ".config" / "autostart" / "atulya-listener.desktop"
    return path, (
        "[Desktop Entry]\nType=Application\nName=Atulya Listener\nComment=Always-listening Atulya assistant\n"
        f"Exec={command}\nX-GNOME-Autostart-enabled=true\n"
    )


def install(mode: str = "desktop", **kwargs) -> tuple[Path, str]:
    """Write the autostart file; returns (path, what to do next)."""
    path, content = autostart_entry(mode=mode, **kwargs)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if path.suffix == ".service":
        hint = "Enable it with: systemctl --user enable --now atulya-listener"
    elif path.suffix == ".plist":
        hint = f"Starts at next login, or now with: launchctl load {path}"
    else:
        hint = "Starts at your next login."
    return path, hint


def uninstall(mode: str = "desktop", **kwargs) -> bool:
    path, _ = autostart_entry(mode=mode, **kwargs)
    if path.exists():
        path.unlink()
        return True
    return False
