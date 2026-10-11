"""Atulya command-line entry point."""
from __future__ import annotations

import argparse
import logging
import os

from dotenv import load_dotenv

from .logging_setup import configure_logging, scrub_log_file
from .settings import PROJECT_ROOT, Settings


def _load_secrets() -> None:
    from .secrets_store import load_protected

    try:
        load_protected(Settings.from_environment().data_dir)
    except (OSError, ValueError) as exc:
        print(f"Warning: encrypted secrets could not be loaded ({exc}).")


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    _load_secrets()
    parser = argparse.ArgumentParser(prog="atulya", description="Run the Atulya assistant.")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("serve", help="serve the WebUI and local API")
    commands.add_parser("pc-host", help="run Atulya as a persistent personal-computer host")
    commands.add_parser("mcp", help="run the local Atulya MCP server over stdio")
    commands.add_parser("doctor", help="check basic local configuration")
    password = commands.add_parser("set-password", help="set a password (read from stdin or prompt) for a user")
    password.add_argument("--user", default="admin")
    alias = commands.add_parser("add-login", help="let a user sign in with another name or email")
    alias.add_argument("alias")
    alias.add_argument("--user", default="admin")
    secrets = commands.add_parser("secrets", help="encrypt API keys/tokens from .env at rest")
    secrets.add_argument("action", choices=["protect", "status", "set"])
    secrets.add_argument("name", nargs="?", help="for 'set': the variable name; the value is read from stdin")
    selftest = commands.add_parser("selftest", help="run real end-to-end checks against the running server")
    selftest.add_argument("--actions", action="store_true", help="also approve a real PC action (opens Calculator)")
    remote = commands.add_parser("remote", help="reach Atulya from your devices anywhere via Tailscale")
    remote.add_argument("--enable", action="store_true", help="serve Atulya over private HTTPS on your tailnet")
    remote.add_argument("--disable", action="store_true", help="stop serving on your tailnet")
    remote.add_argument("--cloudflare", metavar="HOSTNAME", help="public HTTPS on your domain via Cloudflare Tunnel")
    args = parser.parse_args()
    if args.command == "add-login":
        from .auth import AuthStore

        AuthStore(Settings.from_environment().data_dir).add_alias(args.alias, args.user)
        print(f"'{args.alias}' now signs in as '{args.user}'.")
        return
    if args.command == "set-password":
        import getpass
        import sys

        from .auth import AuthStore

        secret = sys.stdin.readline().rstrip("\r\n") if not sys.stdin.isatty() else getpass.getpass("New password: ")
        AuthStore(Settings.from_environment().data_dir).set_password(args.user.strip().lower(), secret)
        print(f"Password set for '{args.user}'. It is stored only as a scrypt hash in data/auth.sqlite3.")
        return
    if args.command == "secrets":
        from .secrets_store import SECRET_KEY, protect, secrets_path

        data_dir = Settings.from_environment().data_dir
        if args.action == "set":
            import sys

            from .secrets_store import set_secret

            set_secret(data_dir, (args.name or "").upper(), sys.stdin.readline().strip())
            print(f"Stored {args.name.upper()} encrypted.")
            return
        if args.action == "protect":
            moved = protect(PROJECT_ROOT / ".env", data_dir)
            print("Encrypted: " + (", ".join(moved) if moved else "nothing new (no plain-text secrets in .env)"))
        else:
            plain = [line.split("=", 1)[0] for line in (PROJECT_ROOT / ".env").read_text(encoding="utf-8").splitlines()
                     if "=" in line and not line.lstrip().startswith("#") and SECRET_KEY.search(line.split("=", 1)[0].strip())
                     and line.split("=", 1)[1].split("#")[0].strip()]
            print(f"Encrypted store: {'present' if secrets_path(data_dir).is_file() else 'none'}")
            print("Plain-text secrets still in .env: " + (", ".join(plain) if plain else "none"))
        return
    if args.command == "selftest":
        from tools.selftest import main as selftest_main

        raise SystemExit(selftest_main(actions=args.actions))
    if args.command == "remote":
        from tools.remote_access import cloudflare, main as remote_main

        if args.cloudflare:
            raise SystemExit(cloudflare(args.cloudflare.strip().lower()))
        raise SystemExit(remote_main(enable=args.enable, disable=args.disable))
    if args.command == "mcp":
        try:
            from tools.mcp.server import main as run_mcp_server
        except ImportError as exc:
            raise SystemExit("The optional MCP SDK is missing. Run Atulya setup to install the pinned dependencies.") from exc
        run_mcp_server()
        return

    settings = Settings.from_environment()

    if args.command == "doctor":
        print(f"Assistant name: {settings.assistant_name}")
        print(f"WebUI folder: {(PROJECT_ROOT / 'webui').is_dir()}")
        print(f"Model provider configured: {bool(settings.model_provider)}")
        print(f"Data folder: {settings.data_dir}")
        return

    if args.command == "pc-host":
        log_path = settings.data_dir / "logs" / "pc-host.log"
        for old_log in log_path.parent.glob("*.log*"):
            scrub_log_file(old_log)
        configure_logging(log_path)
        if os.name == "nt" and os.environ.get("ATULYA_KEEP_AWAKE", "1").strip().lower() not in {"0", "false", "no"}:
            try:
                import ctypes

                class SystemPowerStatus(ctypes.Structure):
                    _fields_ = [
                        ("ACLineStatus", ctypes.c_byte),
                        ("BatteryFlag", ctypes.c_byte),
                        ("BatteryLifePercent", ctypes.c_byte),
                        ("SystemStatusFlag", ctypes.c_byte),
                        ("BatteryLifeTime", ctypes.c_ulong),
                        ("BatteryFullLifeTime", ctypes.c_ulong),
                    ]

                power_status = SystemPowerStatus()
                on_ac_power = bool(ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(power_status))) and power_status.ACLineStatus == 1
                continuous = 0x80000000
                system_required = 0x00000001
                if on_ac_power and not ctypes.windll.kernel32.SetThreadExecutionState(continuous | system_required):
                    logging.getLogger(__name__).warning("Windows did not accept the keep-awake request")
                elif not on_ac_power:
                    logging.getLogger(__name__).info("Not requesting keep-awake because AC power is not confirmed")
            except (AttributeError, OSError):
                logging.getLogger(__name__).exception("Could not request Windows keep-awake while hosting")
        logging.getLogger(__name__).info(
            "Personal-computer host starting on %s:%s; public origin configured=%s",
            settings.host,
            settings.port,
            bool(settings.public_origin),
        )

    if args.command != "pc-host":
        configure_logging()

    runtime = None
    if settings.model_provider == "local" and not settings.model_provider_auto:
        from tools.plugins.brain.local_llm import LocalLlamaRuntime

        runtime = LocalLlamaRuntime(settings.models_dir)
        try:
            runtime.start()
        except Exception as exc:
            raise SystemExit(f"Atulya local chat setup failed: {exc}") from exc

    tunnel = None
    if args.command == "pc-host":
        from tools.remote_access import start_tunnel

        tunnel = start_tunnel()
        if tunnel is not None:
            logging.getLogger(__name__).info("Cloudflare tunnel started for %s", settings.public_origin)

    import uvicorn
    import uvicorn.config
    try:
        uvicorn.run(
            "atulya.server:app",
            host=settings.host,
            port=settings.port,
            reload=False,
            proxy_headers=True,
            forwarded_allow_ips=settings.trusted_proxy_ips,
            # pc-host logs to its rotating file; serve uses uvicorn's built-in console config.
            log_config=None if args.command == "pc-host" else uvicorn.config.LOGGING_CONFIG,
        )
    finally:
        if runtime is not None:
            runtime.stop()
        if tunnel is not None:
            tunnel.terminate()


if __name__ == "__main__":
    main()
