"""Interactive local setup: credentials stay on this PC, encrypted with Windows DPAPI."""
from pathlib import Path
import os
import subprocess
import sys
import threading
from urllib.parse import urlsplit

import httpx
from tools.companion_paths import connection_directory

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = connection_directory()


def verify_connection(origin, token):
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Use the HTTPS address of your Atulya server without credentials or query parameters")
    if not token.strip():
        raise ValueError("Paste the device credential created in Atulya → Devices")
    with httpx.Client(base_url=origin.rstrip("/"), timeout=15, headers={"Authorization": "Bearer " + token.strip()}) as client:
        response = client.post("/api/agents/register")
        if response.status_code == 401:
            raise ValueError("Device credential rejected. Create a new credential in Atulya Devices.")
        response.raise_for_status()
        return response.json()["name"]


def main():
    import tkinter as tk
    from tkinter import ttk
    from atulya.secrets_store import set_secret

    window = tk.Tk()
    window.title("Connect this PC to Atulya")
    window.geometry("680x440")
    panel = ttk.Frame(window, padding=20); panel.pack(fill="both", expand=True)
    ttk.Label(panel, text="Connect this PC", font=("Segoe UI", 16)).pack(anchor="w")
    ttk.Label(panel, text="In your signed-in Chrome: open Atulya → Devices.\nCreate a device named This-PC with ping and battery_status checked.\nPaste its credential below. No password or token needs to go into chat.", wraplength=590).pack(anchor="w", pady=12)
    ttk.Label(panel, text="Atulya server").pack(anchor="w")
    origin = tk.StringVar(value="https://atulya.atulvij.com")
    ttk.Entry(panel, textvariable=origin).pack(fill="x", pady=4)
    ttk.Label(panel, text="Device credential (hidden; stored encrypted for this Windows user)").pack(anchor="w")
    token = tk.StringVar()
    entry = ttk.Entry(panel, textvariable=token, show="•"); entry.pack(fill="x", pady=4)
    status = tk.StringVar(value="Only grant the actions you want this server to run on this PC.")
    ttk.Label(panel, textvariable=status, wraplength=590).pack(anchor="w", pady=12)

    def start_saved():
        DIRECTORY.mkdir(parents=True, exist_ok=True)
        log = (DIRECTORY / "companion.log").open("ab")
        executable = Path(sys.executable).with_name("pythonw.exe")
        command = ([sys.executable, "--run-companion", "--saved"] if getattr(sys, "frozen", False) else
                   [str(executable if executable.exists() else sys.executable), "-u", "-m", "tools.device_companion", "--saved"])
        child = subprocess.Popen(command, cwd=Path(sys.executable).parent if getattr(sys, "frozen", False) else ROOT, stdout=log, stderr=log,
                                 creationflags=0x08000000 if os.name == "nt" else 0)
        log.close()
        (DIRECTORY / "process.pid").write_text(str(child.pid), encoding="ascii")
        return child

    def connect():
        address, credential = origin.get().strip().rstrip("/"), token.get().strip()
        button.config(state="disabled"); status.set("Testing the per-device credential…")
        def work():
            try:
                name = verify_connection(address, credential)
                set_secret(DIRECTORY, "ATULYA_AGENT_URL", address)
                set_secret(DIRECTORY, "ATULYA_AGENT_TOKEN", credential)
                child = start_saved()
                def done():
                    token.set("")
                    if child.poll() is not None:
                        status.set(f"The companion exited or is already running. Inspect {DIRECTORY / 'companion.log'}, then refresh Devices in Chrome.")
                    else:
                        status.set(f"Started {name} (process {child.pid}). Refresh Devices in Chrome; verify a ping receipt. Logs: {DIRECTORY / 'companion.log'}")
                    button.config(state="normal")
                window.after(750, done)
            except Exception as exc:
                message = str(exc) if isinstance(exc, ValueError) else f"Connection failed ({type(exc).__name__}). Check the server address and network."
                window.after(0, lambda: (status.set(message), button.config(state="normal")))
        threading.Thread(target=work, daemon=True).start()

    button = ttk.Button(panel, text="Connect and run companion", command=connect); button.pack(anchor="w")
    ttk.Label(panel, text="Keep the companion running for remote actions. Revoke this device in Atulya to disconnect it.", wraplength=590).pack(anchor="w", pady=12)
    window.mainloop()


if __name__ == "__main__":
    main()
