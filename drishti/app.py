"""Drishti backend entrypoint.

The implementation lives in `drishti.dashboard` so package users can keep using
the stable `atulya` namespace, while dashboard-owned launchers can run:

    python -m drishti.app
"""
from __future__ import annotations

import os



__all__ = ["main"]


def main() -> None:
    from atulya.lockdown import bind_host

    host = bind_host("127.0.0.1")
    port = int(os.environ.get("ATULYA_PORT", 8501))

    import socket

    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            print(f"\n  Atulya is already running on port {port} (or another program is using it).")
            print(f"  Open http://127.0.0.1:{port}, close the other window first, or set ATULYA_PORT in .env.\n")
            raise SystemExit(1)

    print("\n  Atulya Tantra Drishti")
    print(f"  Running on: http://{host}:{port}\n")
    
    from drishti.dashboard import users
    users.seed_default_admin()
    
    print("  Loading FastAPI/PyTorch modules. First start can take 30-60 seconds...\n", flush=True)

    from drishti.dashboard.app import app as dashboard_app
    from uvicorn.config import Config
    from uvicorn.server import Server

    Server(Config(dashboard_app, host=host, port=port, log_level="warning")).run()


if __name__ == "__main__":
    main()



