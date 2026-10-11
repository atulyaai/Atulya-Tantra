"""Atulya command-line entry point."""
from __future__ import annotations

import argparse
import logging
import os

from dotenv import load_dotenv

from .logging_setup import configure_logging, scrub_log_file
from .settings import PROJECT_ROOT, Settings


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(prog="atulya", description="Run the Atulya assistant.")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("serve", help="serve the WebUI and local API")
    commands.add_parser("pc-host", help="run Atulya as a persistent personal-computer host")
    commands.add_parser("mcp", help="run the local Atulya MCP server over stdio")
    commands.add_parser("doctor", help="check basic local configuration")
    remote = commands.add_parser("remote", help="reach Atulya from your devices anywhere via Tailscale")
    remote.add_argument("--enable", action="store_true", help="serve Atulya over private HTTPS on your tailnet")
    remote.add_argument("--disable", action="store_true", help="stop serving on your tailnet")
    args = parser.parse_args()
    if args.command == "remote":
        from tools.remote_access import main as remote_main

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

    import uvicorn
    try:
        uvicorn.run(
            "atulya.server:app",
            host=settings.host,
            port=settings.port,
            reload=False,
            proxy_headers=True,
            forwarded_allow_ips=settings.trusted_proxy_ips,
            log_config=None if args.command == "pc-host" else "default",
        )
    finally:
        if runtime is not None:
            runtime.stop()


if __name__ == "__main__":
    main()
