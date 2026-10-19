"""Unified multi-device companion for Atulya-Tantra (Jarvis).

Runs on:
- 📱 Phone (Android via Termux or native APK bridge)
- 📺 Smart TV (Android TV, Fire TV, Raspberry Pi media box)
- 📟 Tablet (iPad/Android)
- 💻 Laptop / Desktop (Windows, macOS, Linux)

Capabilities:
- ping: liveness probe
- say: voice/audio notification announcement
- open_url: open web links in default browser
- open_app: launch installed applications
- list_files: browse files in granted directory
- read_file: read text/content from granted directory
- take_photo: take snapshot from connected webcam / camera
- list_photos: list pictures in Pictures or granted folder
- media_control: play, pause, next, prev, mute
- display_message: display on-screen toast / notification
- battery_status: check device battery level and charging state
"""
from __future__ import annotations

import json
import argparse
import os
import platform
import subprocess
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlsplit

import httpx

SYSTEM = platform.system()


def _get_battery_status() -> str:
    try:
        import psutil  # type: ignore
        battery = psutil.sensors_battery()
        if battery is None:
            return "No battery detected (Desktop or AC power)."
        plugged = "Charging / Plugged in" if battery.power_plugged else "Discharging"
        return f"Battery: {battery.percent}% · {plugged} · Time left: {int(battery.secsleft / 60) if battery.secsleft > 0 else 'N/A'} mins"
    except Exception:
        # Fallback for Windows WMIC / PowerShell
        if SYSTEM == "Windows":
            try:
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", "Get-CimInstance -ClassName Win32_Battery | Select-Object -Property EstimatedChargeRemaining, BatteryStatus | ConvertTo-Json"],
                    capture_output=True, text=True, timeout=5, creationflags=0x08000000
                )
                data = json.loads(res.stdout or "{}")
                if "EstimatedChargeRemaining" in data:
                    return f"Battery: {data['EstimatedChargeRemaining']}% (Status: {data.get('BatteryStatus')})"
            except Exception:
                pass
        return "Battery status is unavailable on this platform."


def _granted_path(folder, relative: str) -> Path:
    """A path inside the one folder the owner granted (ATULYA_AGENT_FOLDER); hidden files and folders
    (".env", ".ssh", ".git" …) are never readable or listed."""
    if not folder:
        raise ValueError("Set ATULYA_AGENT_FOLDER to grant one folder; no folder access is enabled")
    base = Path(folder).resolve(strict=True)
    target = (base / (relative or ".")).resolve(strict=True)
    if not target.is_relative_to(base):
        raise ValueError("Outside the granted directory")
    if any(part.startswith(".") for part in target.relative_to(base).parts):
        raise ValueError("Hidden files and folders are private and never shared")
    return target


def _display_toast(message: str) -> str:
    # The text is passed as data (environment / argv), never pasted into a script: "$(...)" or quotes in a
    # message must not run anything.
    clean = message.strip()[:500]
    if SYSTEM == "Windows":
        try:
            script = ('[reflection.assembly]::loadwithpartialname("System.Windows.Forms") | Out-Null; '
                      '[System.Windows.Forms.MessageBox]::Show($env:ATULYA_MESSAGE, "Atulya")')
            subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                             env={**os.environ, "ATULYA_MESSAGE": clean}, creationflags=0x08000000)
            return "Windows accepted a visual notification request; user viewing is not verified."
        except Exception as exc:
            raise RuntimeError(f"Failed to show notification: {exc}") from exc
    elif SYSTEM == "Darwin":
        try:
            subprocess.run(["osascript", "-e", "on run argv", "-e", 'display notification (item 1 of argv) with title "Atulya"',
                            "-e", "end run", clean], timeout=5, check=True)
            return f"Notification displayed: {clean[:100]}"
        except Exception as exc:
            raise RuntimeError(f"Failed to show notification: {exc}") from exc
    elif SYSTEM == "Linux":
        try:
            subprocess.run(["notify-send", "--", "Atulya", clean], timeout=5, check=True)
            return f"Notification displayed: {clean[:100]}"
        except Exception as exc:
            raise RuntimeError("No notification service on this device; nothing was shown.") from exc
    raise ValueError("No notification service on this device; nothing was shown.")


def _media_control(action: str) -> str:
    action = action.lower().strip()
    if SYSTEM == "Windows":
        vk_map = {
            "play": 0xB3, "pause": 0xB3, "play_pause": 0xB3,
            "next": 0xB0, "prev": 0xB1, "previous": 0xB1,
            "mute": 0xAD, "volume_up": 0xAF, "volume_down": 0xAE,
        }
        vk = vk_map.get(action)
        if vk is not None:
            try:
                import ctypes
                ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
                ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
                return f"Media key '{action}' triggered."
            except Exception as exc:
                raise RuntimeError(f"Failed to send media key: {exc}") from exc
    raise ValueError(f"Media action '{action}' is not supported on this companion")


def execute(kind: str, detail: str, folder=None):
    if kind == "ping":
        return f"{platform.node()} ({SYSTEM}) companion active; ready for instructions."

    if kind == "say":
        return _display_toast(detail) + " (shown as text; this companion has no voice)"

    if kind == "open_url":
        url = urlsplit(detail)
        if url.scheme != "https" or not url.hostname or url.username:
            raise ValueError("Only HTTPS links are allowed")
        if not webbrowser.open(detail):
            raise RuntimeError("The operating system did not accept the browser request")
        return f"Opened {detail} in default browser."

    if kind == "open_app":
        # Only apps listed in the Start menu / Applications / .desktop entries, matched by name and launched
        # without a shell. A name like "notepad & del ..." can never become a command.
        from tools.plugins.system.actions import open_app
        result = open_app(detail.strip()[:80])
        if not result.startswith("Opened "):
            raise ValueError(result)
        return result

    if kind == "list_files":
        target = _granted_path(folder, detail or ".")
        if not target.is_dir():
            raise ValueError("Not a folder inside the granted directory")
        names = [p.name for p in sorted(target.iterdir()) if not p.name.startswith(".")]
        return "\n".join(names[:100]) or "Folder is empty."

    if kind == "read_file":
        target = _granted_path(folder, detail)
        if not target.is_file():
            raise ValueError("Not a file inside the granted directory")
        if target.stat().st_size > 100_000:
            return f"File too large ({target.stat().st_size} bytes). Max 100KB."
        try:
            return target.read_text(encoding="utf-8", errors="replace")[:4000]
        except Exception as exc:
            return f"Error reading file: {exc}"

    if kind == "list_photos":
        # Only the folder the owner granted; never Pictures by default, never hidden folders.
        base = _granted_path(folder, ".")
        extensions = {".jpg", ".jpeg", ".png", ".webp", ".mp4"}
        found = [p for p in base.rglob("*") if p.suffix.lower() in extensions and p.is_file()
                 and not any(part.startswith(".") for part in p.relative_to(base).parts)]
        photos = [p.name for p in sorted(found, key=lambda x: x.stat().st_mtime, reverse=True)][:25]
        return "\n".join(photos) or "No photos found."

    if kind == "take_photo":
        save_dir = _granted_path(folder, ".")
        try:
            import cv2  # type: ignore
            cap = cv2.VideoCapture(0)
            try:
                if not cap.isOpened():
                    raise RuntimeError("Camera unavailable or in use by another app.")
                ret, frame = cap.read()
            finally:
                cap.release()
            if not ret:
                raise RuntimeError("Failed to grab frame from camera.")
            filename = f"capture_{int(time.time())}.jpg"
            save_path = save_dir / filename
            if not cv2.imwrite(str(save_path), frame):
                raise RuntimeError("Camera image could not be saved.")
            return f"Photo captured and saved to {save_path.name}"
        except ImportError as exc:
            raise RuntimeError("Camera capture module (OpenCV) not installed on companion device.") from exc
        except Exception as exc:
            raise RuntimeError(f"Camera capture failed: {exc}") from exc

    if kind == "media_control":
        return _media_control(detail)

    if kind == "display_message":
        return _display_toast(detail)

    if kind == "battery_status":
        return _get_battery_status()

    if kind in {"send_sms", "place_call"}:
        raise ValueError("SMS and calls run on the Atulya Android app (paired automatically after sign-in), not on this device")

    raise ValueError(f"This companion does not implement action: {kind}")


def poll_once(client, *, folder=None, executor=execute, pending=None, persist=lambda pending: None):
    """Retry accepted-result acknowledgements without executing the job again."""
    pending = pending if pending is not None else {}
    completed = []

    def flush():
        for job_id, body in list(pending.items()):
            receipt = client.post("/api/agents/result", json=body)
            receipt.raise_for_status()
            if not receipt.json().get("ok"):
                raise RuntimeError("Execution receipt rejected; inspect Devices before retrying the action")
            completed.append({"id": job_id, "success": body["success"]})
            del pending[job_id]
            persist(pending)

    flush()
    response = client.post("/api/agents/poll")
    response.raise_for_status()
    for job in response.json().get("jobs", []):
        try:
            output = executor(job["kind"], job.get("detail", ""), folder)
            success = True
        except Exception as exc:
            output, success = str(exc), False
        pending[job["id"]] = {"id": job["id"], "output": str(output)[:4000], "success": success}
        persist(pending)
    flush()
    return completed


def main():
    parser = argparse.ArgumentParser(description="Run the paired Atulya device companion")
    parser.add_argument("--saved", action="store_true", help="Use the credential saved by the PC setup window")
    args = parser.parse_args()
    if args.saved:
        from atulya.secrets_store import _decode
        from tools.companion_paths import connection_directory, acquire_connection_lock
        directory = connection_directory()
        try:
            _connection_lock = acquire_connection_lock(directory)  # retained for the worker's lifetime
        except ValueError as exc:
            raise SystemExit(str(exc)) from None
        saved = _decode((directory / "secrets.enc").read_bytes())
    else:
        saved = os.environ
    origin = saved.get("ATULYA_AGENT_URL", "").rstrip("/")
    token = saved.get("ATULYA_AGENT_TOKEN", "")
    device_name = os.environ.get("ATULYA_DEVICE_NAME", platform.node())
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or not token:
        raise SystemExit("Set an HTTPS ATULYA_AGENT_URL and a paired ATULYA_AGENT_TOKEN")
    with httpx.Client(base_url=origin, timeout=15, headers={"Authorization": "Bearer " + token}) as client:
        response = client.post("/api/agents/register")
        response.raise_for_status()
        print(f"Paired companion '{device_name}' connected to {origin}. Ctrl+C stops it.")
        pending = {}
        def persist(pending):
            pass
        if args.saved:
            from atulya.secrets_store import _encode, _decode
            outbox = directory / "receipts.enc"
            pending = _decode(outbox.read_bytes()) if outbox.exists() else {}
            def persist(pending):
                temporary = outbox.with_suffix(".tmp")
                temporary.write_bytes(_encode(pending))
                if os.name != "nt":
                    temporary.chmod(0o600)
                os.replace(temporary, outbox)
        while True:
            try:
                poll_once(client, folder=os.environ.get("ATULYA_AGENT_FOLDER"), pending=pending, persist=persist)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    raise SystemExit("Device credential revoked or invalid; pair again") from None
                print(f"Server returned HTTP {exc.response.status_code}; waiting to retry...")
            except httpx.HTTPError:
                print("Server temporarily unavailable; waiting to retry...")
            time.sleep(2)


if __name__ == "__main__":
    main()
