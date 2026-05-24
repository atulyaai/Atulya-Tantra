"""WebUI backend entrypoint.

The implementation lives in `webui.backend.dashboard` so package users can keep using
the stable `atulya` namespace, while dashboard-owned launchers can run:

    python -m webui.backend.app
"""
from __future__ import annotations

import os

from webui.backend.dashboard.state import ADMIN_TOKEN, ADMIN_TOKEN_SOURCE

app = None

__all__ = ["main"]


def main() -> None:
    print("\n  Atulya Tantra WebUI")
    print("  http://localhost:8501\n")
    if not os.environ.get("ATULYA_DASHBOARD_TOKEN"):
        print(f"  Session token: {ADMIN_TOKEN}")
        print(f"  Token source: {ADMIN_TOKEN_SOURCE}\n")
    print("  Loading FastAPI/PyTorch modules. First start can take 30-60 seconds...\n", flush=True)

    from webui.backend.dashboard.app import app as dashboard_app
    from uvicorn.config import Config
    from uvicorn.server import Server

    Server(Config(dashboard_app, host="127.0.0.1", port=8501, log_level="warning")).run()


if __name__ == "__main__":
    main()



