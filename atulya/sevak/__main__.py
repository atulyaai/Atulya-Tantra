"""Sevak (server) entrypoint.

The implementation lives in `atulya.sevak` so package users can keep using
the stable `atulya` namespace, while dashboard-owned launchers can run:

    python -m atulya.sevak
"""
from __future__ import annotations

import os



__all__ = ["main"]


def _brain_report() -> None:
    """Say which brains found a key, so a missing or misspelled key is obvious at startup."""
    from atulya.buddhi.intelligence import ProviderRouter

    names = [p.name() for p in ProviderRouter().providers if p.is_available() and p.name() != "No brain loaded"]
    print("  Brains ready: " + (", ".join(names) if names else "none. Add a key to .env (see .env.example)"))


def main() -> None:
    from atulya.envfile import load_env
    from atulya.raksha.lockdown import bind_host

    found = load_env()
    print("\n  Settings: " + (", ".join(str(p) for p in found) if found else "no .env file found next to start.bat"))
    _brain_report()

    host = bind_host("127.0.0.1")
    port = int(os.environ.get("ATULYA_PORT", 8501))

    import socket

    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            print(f"\n  Atulya is already running on port {port} (or another program is using it).")
            print(f"  Open http://127.0.0.1:{port}, close the other window first, or set ATULYA_PORT in .env.\n")
            raise SystemExit(1)

    scheme, ssl_args = "http", {}
    from atulya.sevak import https as https_mod

    if https_mod.enabled():
        cert_file, key_file = https_mod.ensure_certs()
        scheme, ssl_args = "https", {"ssl_certfile": cert_file, "ssl_keyfile": key_file}
    print("\n  Atulya")
    print(f"  Running on: {scheme}://{host}:{port}\n")
    if scheme == "https":
        print("  Your browser will warn once about the certificate (it is your own): choose Advanced > Continue.\n")
    from atulya.sevak import users
    users.seed_default_admin()
    
    print("  Loading FastAPI/PyTorch modules. First start can take 30-60 seconds...\n", flush=True)

    from atulya.sevak.app import app as dashboard_app
    from uvicorn.config import Config
    from uvicorn.server import Server

    Server(Config(dashboard_app, host=host, port=port, log_level="warning", **ssl_args)).run()


if __name__ == "__main__":
    main()



