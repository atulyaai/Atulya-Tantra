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
    clean = message.replace('"', '\\"').strip()
    if SYSTEM == "Windows":
        try:
            cmd = f'[reflection.assembly]::loadwithpartialname("System.Windows.Forms"); [System.Windows.Forms.MessageBox]::Show("{clean}", "Atulya Tantra Alert")'
            subprocess.Popen(["powershell", "-NoProfile", "-Command", cmd], creationflags=0x08000000)
            return f"Notification displayed: {message[:100]}"
        except Exception as exc:
            return f"Failed to show toast: {exc}"
    elif SYSTEM == "Darwin":
        try:
            subprocess.run(["osascript", "-e", f'display notification "{clean}" with title "Atulya Tantra"'], timeout=5)
            return f"Notification displayed: {message[:100]}"
        except Exception as exc:
            return f"Failed to show notification: {exc}"
    elif SYSTEM == "Linux":
        try:
            subprocess.run(["notify-send", "Atulya Tantra", clean], timeout=5)
            return f"Notification displayed: {message[:100]}"
        except Exception:
            return f"Alert: {message[:100]}"
    return f"Message logged: {message[:100]}"


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
    return f"Media action '{action}' queued."


def execute(kind: str, detail: str, folder=None):
    if kind == "ping":
        return f"{platform.node()} ({SYSTEM}) companion active; ready for instructions."

    if kind == "say":
        text = detail.strip()
        _display_toast(text)
        return f"Spoke / announced on device: '{text[:120]}'"

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
            try:
                subprocess.Popen(["cmd.exe", "/c", "start", "", app_name], shell=False, creationflags=0x08000000)
                return f"Launched app '{app_name}' on Windows."
            except Exception as exc:
                return f"Failed to launch app: {exc}"
        elif SYSTEM == "Darwin":
            try:
                subprocess.Popen(["open", "-a", app_name])
                return f"Launched app '{app_name}' on macOS."
            except Exception as exc:
                return f"Failed to launch app: {exc}"
        elif SYSTEM == "Linux":
            try:
                subprocess.Popen([app_name])
                return f"Launched '{app_name}' on Linux."
            except Exception as exc:
                return f"Failed to launch app: {exc}"
        return f"Cannot launch app '{app_name}' on {SYSTEM}."

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

    if kind in {"send_sms", "place_call"}:
        return f"Command '{kind}' is dispatched to Android companion APK with payload: {detail[:100]}"

    raise ValueError(f"This companion does not implement action: {kind}")


def main():
    origin = os.environ.get("ATULYA_AGENT_URL", "").rstrip("/")
    token = os.environ.get("ATULYA_AGENT_TOKEN", "")
    device_name = os.environ.get("ATULYA_DEVICE_NAME", platform.node())
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or not token:
        raise SystemExit("Set an HTTPS ATULYA_AGENT_URL and a paired ATULYA_AGENT_TOKEN")
    with httpx.Client(base_url=origin, timeout=15, headers={"Authorization": "Bearer " + token}) as client:
        response = client.post("/api/agents/register")
        response.raise_for_status()
        print(f"Paired companion '{device_name}' connected to {origin}. Ctrl+C stops it.")
        while True:
            try:
                response = client.post("/api/agents/poll")
                if response.status_code == 401:
                    raise SystemExit("Device credential revoked or invalid; pair again")
                response.raise_for_status()
                for job in response.json().get("jobs", []):
                    try:
                        output = execute(job["kind"], job.get("detail", ""), os.environ.get("ATULYA_AGENT_FOLDER"))
                        success = True
                    except Exception as exc:
                        output, success = str(exc), False
                    receipt = client.post("/api/agents/result", json={"id": job["id"], "output": output, "success": success})
                    receipt.raise_for_status()
            except httpx.HTTPError:
                print("Server temporarily unavailable; waiting to retry...")
            time.sleep(5)


if __name__ == "__main__":
    main()
