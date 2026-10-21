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
import base64
import argparse
import getpass
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


def _display_toast(message: str) -> str:
    if SYSTEM == "Windows":
        try:
            encoded = base64.b64encode(message.encode("utf-8")).decode("ascii")
            cmd = ('Add-Type -AssemblyName System.Windows.Forms; '
                   f"$alertText = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{encoded}')); "
                   '[System.Windows.Forms.MessageBox]::Show($alertText, "Atulya Tantra Alert")')
            subprocess.Popen(["powershell", "-NoProfile", "-Command", cmd], creationflags=0x08000000)
            return "Windows accepted a visual notification request; user viewing is not verified."
        except Exception as exc:
            raise RuntimeError(f"Failed to request notification: {exc}") from exc
    elif SYSTEM == "Darwin":
        try:
            subprocess.run(["osascript", "-e", 'on run argv\ndisplay notification (item 1 of argv) with title "Atulya Tantra"\nend run', message], timeout=5, check=True)
            return "macOS accepted a notification request; user viewing is not verified."
        except Exception as exc:
            raise RuntimeError(f"Failed to request notification: {exc}") from exc
    elif SYSTEM == "Linux":
        try:
            subprocess.run(["notify-send", "--", "Atulya Tantra", message], timeout=5, check=True)
            return "Notification service accepted the request; user viewing is not verified."
        except Exception as exc:
            raise RuntimeError(f"Failed to request notification: {exc}") from exc
    raise ValueError(f"Visual notifications are not implemented on {SYSTEM}")


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
                return f"Failed to send media key: {exc}"
    raise ValueError(f"Media action '{action}' is not implemented on {SYSTEM}")


# --- file jobs (PLAN M18-1): everything stays inside the one granted folder ----------------------------
FILE_KINDS = {"file_search", "file_stat", "file_copy", "file_move", "file_rename", "file_write", "file_trash"}
MAX_WRITE_CHARS = 1500  # the whole job detail is capped at 2000 characters on the server


def _granted(folder) -> Path:
    if not folder:
        raise ValueError("Set ATULYA_AGENT_FOLDER to grant one folder; no folder access is enabled")
    return Path(folder).resolve(strict=True)


def _inside(base: Path, relative: str, *, exists: bool = True) -> Path:
    """A path inside the granted folder. Symlinks and '..' are resolved before the check, so neither can
    escape it; absolute paths elsewhere are refused the same way."""
    if not relative or "\x00" in relative:
        raise ValueError("A path inside the granted folder is required")
    candidate = base / relative
    resolved = candidate.resolve(strict=exists) if exists else candidate.parent.resolve(strict=True) / candidate.name
    if resolved == base or not resolved.is_relative_to(base):
        raise ValueError("That path is outside the granted folder")
    if not exists and resolved.exists():
        raise ValueError(f"{resolved.name} already exists; nothing was overwritten")
    return resolved


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_job(kind: str, detail: str, folder) -> str:
    """detail is JSON: {"path": ..., "to": ..., "text": ..., "base_sha256": ..., "query": ...}.
    Mutations return a receipt with the original path so the change can be undone by hand."""
    import shutil

    base = _granted(folder)
    try:
        args = json.loads(detail or "{}")
    except ValueError as exc:
        raise ValueError("File job details must be JSON") from exc
    if not isinstance(args, dict):
        raise ValueError("File job details must be a JSON object")

    if kind == "file_search":
        words = str(args.get("query", "")).lower().split()
        if not words:
            raise ValueError("Say what to look for")
        hits = [p for p in base.rglob("*") if p.is_file() and all(w in p.name.lower() for w in words)]
        hits.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return "\n".join(str(p.relative_to(base)) for p in hits[:50]) or "No matching files."

    source = _inside(base, str(args.get("path", "")))
    rel = lambda p: str(p.relative_to(base))  # noqa: E731
    if kind == "file_stat":
        info = source.stat()
        return json.dumps({"path": rel(source), "bytes": info.st_size, "modified": int(info.st_mtime),
                           "sha256": _sha256(source) if source.is_file() and info.st_size <= 50_000_000 else None})
    if kind == "file_trash":
        from send2trash import send2trash

        send2trash(str(source))
        return f"Moved {rel(source)} to the recycle bin; restore it from there. Original path: {rel(source)}"
    if kind == "file_write":
        text = str(args.get("text", ""))
        if len(text) > MAX_WRITE_CHARS:
            raise ValueError(f"Text is longer than {MAX_WRITE_CHARS} characters")
        if not source.is_file():
            raise ValueError("Only existing files can be edited")
        expected = str(args.get("base_sha256", ""))
        if not expected or expected != _sha256(source):
            raise ValueError("The file changed since it was read (or base_sha256 is missing); nothing was written")
        backup = source.with_name(source.name + f".atulya-{int(time.time())}.bak")
        shutil.copy2(source, backup)
        source.write_text(text, encoding="utf-8")
        return f"Wrote {len(text)} characters to {rel(source)}. Previous version kept as {rel(backup)}"
    if kind == "file_rename":
        new_name = str(args.get("to", ""))
        if not new_name or Path(new_name).name != new_name:
            raise ValueError("A new name without folders is required")
        target = _inside(base, str(source.parent.relative_to(base) / new_name), exists=False)
    else:
        target = _inside(base, str(args.get("to", "")), exists=False)
    if kind == "file_copy":
        (shutil.copytree if source.is_dir() else shutil.copy2)(source, target)
        return f"Copied {rel(source)} to {rel(target)}"
    free = shutil.disk_usage(target.parent).free
    if source.is_file() and source.stat().st_size > free:
        raise ValueError("Not enough free space at the destination")
    shutil.move(str(source), str(target))
    return f"Moved {rel(source)} to {rel(target)}. Original path: {rel(source)}"


def execute(kind: str, detail: str, folder=None):
    if kind == "ping":
        return f"{platform.node()} ({SYSTEM}) companion active; ready for instructions."

    if kind == "say":
        raise ValueError("Speech output is not implemented by this desktop companion; use display_message for a visual notification")

    if kind == "open_url":
        url = urlsplit(detail)
        if url.scheme != "https" or not url.hostname or url.username:
            raise ValueError("Only HTTPS links are allowed")
        if not webbrowser.open(detail):
            raise RuntimeError("The operating system did not accept the browser request")
        return f"Opened {detail} in default browser."

    if kind == "open_app":
        app_name = detail.strip()
        if not app_name:
            raise ValueError("Specify an application name to open")
        if SYSTEM == "Windows":
            os.startfile(app_name)
            return f"Windows accepted the request to open '{app_name}'. App readiness is not verified."
        elif SYSTEM == "Darwin":
            try:
                subprocess.Popen(["open", "-a", app_name])
                return f"Launched app '{app_name}' on macOS."
            except Exception as exc:
                raise RuntimeError(f"Failed to launch app: {exc}") from exc
        elif SYSTEM == "Linux":
            try:
                subprocess.Popen([app_name])
                return f"Launched '{app_name}' on Linux."
            except Exception as exc:
                raise RuntimeError(f"Failed to launch app: {exc}") from exc
        raise ValueError(f"Cannot launch app '{app_name}' on {SYSTEM}.")

    if kind == "list_files":
        if not folder:
            raise ValueError("Set ATULYA_AGENT_FOLDER to grant one folder; no folder access is enabled")
        base = Path(folder).resolve(strict=True)
        target = (base / (detail or ".")).resolve(strict=True)
        if not target.is_relative_to(base) or not target.is_dir():
            raise ValueError("Folder is outside the granted directory")
        return "\n".join(p.name for p in sorted(target.iterdir())[:100]) or "Folder is empty."

    if kind == "read_file":
        if not folder:
            raise ValueError("Set ATULYA_AGENT_FOLDER to grant one folder; no folder access is enabled")
        base = Path(folder).resolve(strict=True)
        target = (base / (detail or "")).resolve(strict=True)
        if not target.is_relative_to(base) or not target.is_file():
            raise ValueError("File is outside the granted directory or does not exist")
        if target.stat().st_size > 100_000:
            return f"File too large ({target.stat().st_size} bytes). Max 100KB."
        try:
            return target.read_text(encoding="utf-8", errors="replace")[:4000]
        except Exception as exc:
            return f"Error reading file: {exc}"

    if kind == "list_photos":
        pictures_dir = Path(folder) if folder else Path.home() / "Pictures"
        if not pictures_dir.exists():
            return "Pictures folder not found."
        extensions = {".jpg", ".jpeg", ".png", ".webp", ".mp4"}
        photos = [p.name for p in sorted(pictures_dir.rglob("*"), key=lambda x: x.stat().st_mtime, reverse=True) if p.suffix.lower() in extensions][:25]
        return "\n".join(photos) or "No photos found."

    if kind == "take_photo":
        try:
            import cv2  # type: ignore
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return "Camera unavailable or in use by another app."
            ret, frame = cap.read()
            cap.release()
            if not ret:
                return "Failed to grab frame from camera."
            save_dir = Path(folder) if folder else Path.home() / "Pictures"
            save_dir.mkdir(parents=True, exist_ok=True)
            filename = f"capture_{int(time.time())}.jpg"
            save_path = save_dir / filename
            cv2.imwrite(str(save_path), frame)
            return f"Photo captured and saved to {save_path.name}"
        except ImportError:
            return "Camera capture module (OpenCV) not installed on companion device."
        except Exception as exc:
            return f"Camera capture failed: {exc}"

    if kind == "media_control":
        return _media_control(detail)

    if kind == "display_message":
        return _display_toast(detail)

    if kind == "battery_status":
        return _get_battery_status()

    if kind in FILE_KINDS:
        return _file_job(kind, detail, folder)

    if kind in {"send_sms", "place_call"}:
        raise ValueError(f"This desktop companion cannot execute {kind}; use a connected Android executor")

    raise ValueError(f"This companion does not implement action: {kind}")


def poll_once(client, *, folder=None, executor=execute, pending=None, persist=lambda pending: None):
    """Execute one poll batch and require the server to accept each receipt."""
    pending = pending if pending is not None else {}
    completed = []

    def flush():
        for job_id, body in list(pending.items()):
            receipt = client.post("/api/agents/result", json=body)
            receipt.raise_for_status()
            if not receipt.json().get("ok"):
                raise RuntimeError("Server rejected the execution receipt; check Devices before retrying the action")
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
    parser = argparse.ArgumentParser(description="Connect this computer to an Atulya server with a per-device token")
    parser.add_argument("--url", default=os.environ.get("ATULYA_AGENT_URL", ""))
    parser.add_argument("--once", action="store_true", help="Poll once and exit; useful for connection tests")
    parser.add_argument("--check", action="store_true", help="Verify the paired credential without executing jobs")
    parser.add_argument("--saved", action="store_true", help="Use this Windows user's saved companion connection")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between polls (0.5–60; default 2)")
    args = parser.parse_args()
    connection_lock = None
    if args.saved:
        from atulya.secrets_store import load_protected
        from tools.companion_paths import connection_directory
        directory = connection_directory()
        directory.mkdir(parents=True, exist_ok=True)
        connection_lock = (directory / "connection.lock").open("a+b")
        connection_lock.write(b"0"); connection_lock.flush(); connection_lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(connection_lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(connection_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise SystemExit("A saved Atulya companion is already running. Reuse it or stop it before reconnecting.") from None
        load_protected(directory)
        args.url = args.url or os.environ.get("ATULYA_AGENT_URL", "")
    if not 0.5 <= args.interval <= 60:
        parser.error("--interval must be between 0.5 and 60 seconds")
    origin = args.url.rstrip("/")
    token = os.environ.get("ATULYA_AGENT_TOKEN", "")
    if not token and origin:
        token = getpass.getpass("Device token from Atulya → Devices (hidden): ").strip()
    device_name = os.environ.get("ATULYA_DEVICE_NAME", platform.node())
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or not token:
        raise SystemExit("Set an HTTPS ATULYA_AGENT_URL and a paired ATULYA_AGENT_TOKEN")
    with httpx.Client(base_url=origin, timeout=15, headers={"Authorization": "Bearer " + token}) as client:
        response = client.post("/api/agents/register")
        response.raise_for_status()
        device_name = response.json().get("name", device_name)
        print(f"Paired companion '{device_name}' connected to {origin}. Ctrl+C stops it.", flush=True)
        if args.check:
            print("Credential accepted. Run Devices → Test connection to verify an execution receipt.")
            return
        pending = {}
        persist = lambda pending: None
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
                results = poll_once(client, folder=os.environ.get("ATULYA_AGENT_FOLDER"), pending=pending, persist=persist)
                for result in results:
                    print(f"Receipt accepted: {result['id']} · {'executed' if result['success'] else 'failed'}", flush=True)
                if args.once:
                    return
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    raise SystemExit("Device credential revoked or invalid; pair again") from None
                if args.once:
                    raise
                print(f"Server returned HTTP {exc.response.status_code}; waiting to retry...")
            except httpx.HTTPError:
                if args.once:
                    raise
                print("Server temporarily unavailable; waiting to retry...")
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
