"""Reach Atulya from your phone/laptop anywhere through Tailscale (private HTTPS, no open ports).

    python -m atulya.cli remote            # show status and what to do next
    python -m atulya.cli remote --enable   # tailscale serve -> https://<pc>.<tailnet>.ts.net
    python -m atulya.cli remote --disable  # stop serving and clear the public origin

Only devices signed in to your tailnet can reach the address. Tailscale itself
(install, sign-in, enabling HTTPS certificates) needs your one-time action.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"
INSTALL_HINT = {
    "Windows": "winget install --id Tailscale.Tailscale   (or https://tailscale.com/download/windows)",
    "Darwin": "brew install --cask tailscale   (or the Mac App Store)",
    "Linux": "curl -fsSL https://tailscale.com/install.sh | sh",
}


def find_tailscale() -> str | None:
    found = shutil.which("tailscale")
    if found:
        return found
    for candidate in (r"C:\Program Files\Tailscale\tailscale.exe",
                      "/Applications/Tailscale.app/Contents/MacOS/Tailscale"):
        if Path(candidate).is_file():
            return candidate
    return None


def _run(binary: str, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run([binary, *args], capture_output=True, text=True, timeout=timeout)


def status(binary: str) -> dict:
    result = _run(binary, "status", "--json")
    try:
        return json.loads(result.stdout or "{}")
    except ValueError:
        return {}


def set_env(key: str, value: str) -> None:
    """Set or replace one KEY=value line in .env, keeping every other line."""
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.is_file() else []
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    replaced = False
    for index, line in enumerate(lines):
        if pattern.match(line):
            lines[index] = f"{key}={value}"
            replaced = True
    if not replaced:
        lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(enable: bool = False, disable: bool = False) -> int:
    port = os.environ.get("ATULYA_PORT", "8501").strip() or "8501"
    binary = find_tailscale()
    if binary is None:
        print("Tailscale is not installed. Install it, sign in, then run this again:")
        print("  " + INSTALL_HINT.get(platform.system(), INSTALL_HINT["Linux"]))
        print("Install Tailscale on your phone too and sign in with the same account.")
        return 1
    info = status(binary)
    if info.get("BackendState") != "Running":
        print(f"Tailscale is installed but not connected (state: {info.get('BackendState', 'unknown')}).")
        print(f"Sign in with:  \"{binary}\" up")
        return 1
    host = str((info.get("Self") or {}).get("DNSName", "")).rstrip(".")
    if not host:
        print("Tailscale did not report a MagicDNS name. Enable MagicDNS in the Tailscale admin console (DNS page).")
        return 1
    origin = f"https://{host}"
    if disable:
        _run(binary, "serve", "--https=443", "off")
        set_env("ATULYA_PUBLIC_ORIGIN", "")
        print("Stopped serving Atulya on your tailnet. Restart Atulya to apply.")
        return 0
    if enable:
        result = _run(binary, "serve", "--bg", "--https=443", f"http://127.0.0.1:{port}", timeout=60)
        if result.returncode != 0:
            message = (result.stderr or result.stdout).strip()
            print("Tailscale could not start HTTPS serving:\n  " + message[:500])
            if "HTTPS" in message or "cert" in message.lower():
                print("Enable 'HTTPS Certificates' in the Tailscale admin console (DNS page), then retry.")
            return 1
        set_env("ATULYA_PUBLIC_ORIGIN", origin)
        set_env("ATULYA_TRUSTED_PROXY_IPS", "127.0.0.1,::1")
        print(f"Atulya is now served privately at {origin}")
        print("Next steps:")
        print("  1. Restart Atulya so it accepts the new address.")
        print(f"  2. On this PC open http://localhost:{port} > USERS > LINK MY PHONE / ANOTHER DEVICE.")
        print("  3. Open that link on your phone (signed in to Tailscale) and create a passkey there.")
        return 0
    serving = _run(binary, "serve", "status").stdout.strip()
    print(f"Tailscale connected as {host}.")
    print(f"Serve status:\n{serving or '  (not serving)'}")
    print("Run with --enable to serve Atulya at " + origin)
    return 0
