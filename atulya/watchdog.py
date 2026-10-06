"""Self-healing watchdog for Atulya server.

Runs as a separate process (or systemd service on Linux, nssm on Windows).
Monitors /api/health endpoint and restarts the server if it becomes unhealthy.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

DEFAULT_HEALTH_URL = "http://127.0.0.1:8501/api/health"
DEFAULT_INTERVAL = 30
DEFAULT_TIMEOUT = 5
DEFAULT_MAX_FAILURES = 3
DEFAULT_START_CMD = "python -m atulya.sevak"
DEFAULT_CWD = str(Path(__file__).resolve().parent.parent)


class Watchdog:
    def __init__(
        self,
        health_url: str = DEFAULT_HEALTH_URL,
        interval: int = DEFAULT_INTERVAL,
        timeout: int = DEFAULT_TIMEOUT,
        max_failures: int = DEFAULT_MAX_FAILURES,
        start_cmd: str = DEFAULT_START_CMD,
        cwd: str = DEFAULT_CWD,
    ):
        self.health_url = health_url
        self.interval = interval
        self.timeout = timeout
        self.max_failures = max_failures
        self.start_cmd = start_cmd
        self.cwd = cwd
        self.health_headers: dict[str, str] | None = None
        self.process: asyncio.subprocess.Process | None = None
        self.failures = 0
        self._shutdown = False

    async def start_server(self) -> None:
        """Start the Atulya server as a subprocess."""
        logger.info("Starting server: %s", self.start_cmd)
        self.process = await asyncio.create_subprocess_shell(
            self.start_cmd,
            cwd=self.cwd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        # Give it time to start
        await asyncio.sleep(5)

    async def stop_server(self) -> None:
        """Stop the Atulya server gracefully."""
        if self.process and self.process.returncode is None:
            logger.info("Stopping server (PID %s)", self.process.pid)
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=10)
            except asyncio.TimeoutError:
                logger.warning("Server did not stop gracefully, killing")
                self.process.kill()
                await self.process.wait()
        self.process = None

    async def check_health(self) -> bool:
        """Check if the server is healthy via /api/health."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(self.health_url, headers=self.health_headers)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("healthy") is True
            logger.warning("Health check failed: %s", resp.status_code)
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning("Health check error: %s", exc)
            return False

    async def run(self) -> None:
        """Main watchdog loop."""
        await self.start_server()
        logger.info("Watchdog started, monitoring %s", self.health_url)

        while not self._shutdown:
            await asyncio.sleep(self.interval)

            healthy = await self.check_health()
            if healthy:
                self.failures = 0
                logger.debug("Health check OK")
            else:
                self.failures += 1
                logger.warning("Health check failed (%s/%s)", self.failures, self.max_failures)

                if self.failures >= self.max_failures:
                    logger.error("Max failures reached, restarting server")
                    await self.stop_server()
                    await self.start_server()
                    self.failures = 0

    def shutdown(self) -> None:
        self._shutdown = True


async def _run(args) -> None:
    if args.interval <= 0 or args.timeout <= 0 or args.max_failures <= 0:
        raise SystemExit("interval, timeout, and max-failures must be positive")

    token = args.token or os.environ.get("ATULYA_DASHBOARD_TOKEN")
    watchdog = Watchdog(
        health_url=args.url,
        interval=args.interval,
        timeout=args.timeout,
        max_failures=args.max_failures,
        start_cmd=args.cmd,
        cwd=args.cwd,
    )
    watchdog.health_headers = {"X-Atulya-Token": token} if token else None

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, watchdog.shutdown)
        except NotImplementedError:
            signal.signal(sig, lambda *_: loop.call_soon_threadsafe(watchdog.shutdown))

    try:
        await watchdog.run()
    finally:
        await watchdog.stop_server()


def main() -> None:
    parser = argparse.ArgumentParser(description="Atulya self-healing watchdog")
    parser.add_argument("--url", default=DEFAULT_HEALTH_URL, help="Health endpoint URL")
    parser.add_argument("--token", help="Dashboard admin token (defaults to ATULYA_DASHBOARD_TOKEN)")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL, help="Check interval (seconds)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Request timeout (seconds)")
    parser.add_argument("--max-failures", type=int, default=DEFAULT_MAX_FAILURES, help="Max failures before restart")
    parser.add_argument("--cmd", default=DEFAULT_START_CMD, help="Server start command")
    parser.add_argument("--cwd", default=DEFAULT_CWD, help="Working directory")
    parser.add_argument("--install-systemd", action="store_true", help="Generate systemd unit file")
    parser.add_argument("--install-nssm", action="store_true", help="Generate nssm install command (Windows)")
    args = parser.parse_args()

    if args.install_systemd:
        print(generate_systemd_unit(args))
        return
    if args.install_nssm:
        print(generate_nssm_command(args))
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    asyncio.run(_run(args))


def generate_systemd_unit(args) -> str:
    """Generate a systemd service unit file."""
    return f"""[Unit]
Description=Atulya Self-Healing Watchdog
After=network.target

[Service]
Type=simple
User=atulya
WorkingDirectory={args.cwd}
ExecStart={sys.executable} -m atulya.watchdog --url {args.url} --interval {args.interval} --timeout {args.timeout} --max-failures {args.max_failures} --cmd "{args.cmd}"
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""


def generate_nssm_command(args) -> str:
    """Generate nssm install command for Windows."""
    python_exe = sys.executable.replace("\\", "\\\\")
    script = f"{args.cwd}\\atulya\\watchdog.py".replace("\\", "\\\\")
    cmd = (
        f'nssm install AtulyaWatchdog "{python_exe}" "{script}" '
        f'--url {args.url} --interval {args.interval} --timeout {args.timeout} '
        f'--max-failures {args.max_failures} --cmd "{args.cmd}" --cwd "{args.cwd}"'
    )
    return cmd


if __name__ == "__main__":
    asyncio.run(main())
