"""Drishti backend entrypoint.

The implementation lives in `drishti.dashboard` so package users can keep using
the stable `atulya` namespace, while dashboard-owned launchers can run:

    python -m drishti.app
"""
from __future__ import annotations

import os



app = None

__all__ = ["main"]


def main() -> None:
    host = os.environ.get("ATULYA_HOST", "127.0.0.1")
    port = int(os.environ.get("ATULYA_PORT", 8501))
    
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



