"""Opt-in outbound laptop companion. No shell execution or arbitrary file reads.

Set ATULYA_AGENT_URL, ATULYA_AGENT_TOKEN (from Devices pairing) and optionally
ATULYA_AGENT_FOLDER (one approved folder). Stop the process or revoke its device
to disconnect. Run on the target laptop, never as a second Telegram bot.
"""
import os
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlsplit

import httpx


def execute(kind: str, detail: str, folder=None):
    if kind == "ping":
        return "Laptop agent responded; no device action performed."
    if kind == "open_url":
        url = urlsplit(detail)
        if url.scheme != "https" or not url.hostname or url.username:
            raise ValueError("Only HTTPS links are allowed")
        if not webbrowser.open(detail):
            raise RuntimeError("The operating system did not accept the browser request")
        return "Operating system accepted browser opening. Page load or music playback is not verified."
    if kind == "list_files":
        if not folder:
            raise ValueError("Set ATULYA_AGENT_FOLDER to grant one folder; no folder access is enabled")
        base = Path(folder).resolve(strict=True)
        target = (base / (detail or ".")).resolve(strict=True)
        if not target.is_relative_to(base) or not target.is_dir():
            raise ValueError("Folder is outside the granted directory")
        return "\n".join(p.name for p in sorted(target.iterdir())[:100]) or "Folder is empty."
    raise ValueError("This companion does not implement that action")


def main():
    origin = os.environ.get("ATULYA_AGENT_URL", "").rstrip("/")
    token = os.environ.get("ATULYA_AGENT_TOKEN", "")
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or not token:
        raise SystemExit("Set an HTTPS ATULYA_AGENT_URL and a paired ATULYA_AGENT_TOKEN")
    with httpx.Client(base_url=origin, timeout=15, headers={"Authorization": "Bearer " + token}) as client:
        response = client.post("/api/agents/register")
        response.raise_for_status()
        print("Paired companion connected. Ctrl+C stops it.")
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
                print("Server temporarily unavailable; no automatic job replay.")
            time.sleep(5)


if __name__ == "__main__":
    main()
