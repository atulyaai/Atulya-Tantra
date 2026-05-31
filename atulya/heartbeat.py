"""Heartbeat system with task and maintenance integration."""
from __future__ import annotations

import json
import time
import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class HealthCheck:
    name: str
    status: str = "ok"
    message: str = ""
    timestamp: float = field(default_factory=time.time)


class HeartbeatSystem:
    def __init__(self, data_dir: str | Path = "assets"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._checks: list[HealthCheck] = []
        self._running = False
        self._interval = 60.0

    async def start(self):
        self._running = True
        while self._running:
            await self._run_checks()
            await asyncio.sleep(self._interval)

    async def stop(self):
        self._running = False

    async def _run_checks(self):
        self._checks = [
            await self._memory_check(),
            await self._disk_check(),
            await self._task_check(),
            await self._maintenance_check(),
            await self._model_check(),
            await self._provider_check(),
            await self._cortex_check(),
        ]
        self._save_status()

    async def _memory_check(self) -> HealthCheck:
        try:
            import psutil
            mem = psutil.virtual_memory()
            if mem.percent > 90:
                return HealthCheck("memory", "warning", f"Memory usage: {mem.percent}%")
            return HealthCheck("memory", "ok", f"Memory usage: {mem.percent}%")
        except ImportError:
            return HealthCheck("memory", "ok", "psutil not available")

    async def _disk_check(self) -> HealthCheck:
        try:
            import shutil
            total, used, free = shutil.disk_usage(self.data_dir)
            usage_pct = (used / total) * 100
            if usage_pct > 90:
                return HealthCheck("disk", "warning", f"Disk usage: {usage_pct:.1f}%")
            return HealthCheck("disk", "ok", f"Disk usage: {usage_pct:.1f}%")
        except Exception as e:
            return HealthCheck("disk", "error", str(e))

    async def _model_check(self) -> HealthCheck:
        try:
            from tantra.npdna import NpDnaCore
            core = NpDnaCore.from_config("seed")
            ids = core.encode("health", allow_growth=False)
            if ids:
                return HealthCheck("model", "ok", "NP-DNA encode check passed")
            return HealthCheck("model", "warning", "NP-DNA returned no tokens")
        except Exception as e:
            return HealthCheck("model", "warning", str(e))

    async def _provider_check(self) -> HealthCheck:
        try:
            from atulya.intelligence import ProviderRouter
            router = ProviderRouter()
            available = [p.name() for p in router.providers if p.is_available()]
            if not available:
                return HealthCheck("provider", "warning", "No intelligence providers are available")
            return HealthCheck("provider", "ok", f"Available providers: {', '.join(available)}")
        except Exception as e:
            return HealthCheck("provider", "warning", str(e))


    async def _cortex_check(self) -> HealthCheck:
        try:
            cortex_dir = self.data_dir / "cortex"
            if not cortex_dir.exists():
                return HealthCheck("cortex", "info", "No cortex data directory yet")
            last_write = max((p.stat().st_mtime for p in cortex_dir.rglob("*") if p.is_file()), default=0)
            return HealthCheck("cortex", "ok", f"Last cortex write: {last_write:.0f}")
        except Exception as e:
            return HealthCheck("cortex", "warning", str(e))

    async def _task_check(self) -> HealthCheck:
        """Check for pending tasks from Kanban system."""
        try:
            kanban_dir = self.data_dir / "kanban"
            pending = 0
            if kanban_dir.exists():
                for f in kanban_dir.glob("*.json"):
                    data = json.loads(f.read_text())
                    for task in data.get("tasks", {}).values():
                        if task.get("status") in ["todo", "in_progress"]:
                            pending += 1
            if pending > 0:
                return HealthCheck("tasks", "info", f"{pending} pending tasks")
            return HealthCheck("tasks", "ok", "No pending tasks")
        except Exception:
            return HealthCheck("tasks", "ok", "No task system")

    async def _maintenance_check(self) -> HealthCheck:
        """Check if maintenance is needed (log cleanup, memory compaction, etc.)."""
        issues = []
        # Check log size
        logs_dir = self.data_dir / "logs"
        if logs_dir.exists():
            log_size = sum(f.stat().st_size for f in logs_dir.glob("*.log"))
            if log_size > 100 * 1024 * 1024:  # 100MB
                issues.append(f"Logs: {log_size / 1024 / 1024:.1f}MB")

        # Check memory DB size
        memory_dir = self.data_dir / "memory"
        if memory_dir.exists():
            db_size = sum(f.stat().st_size for f in memory_dir.glob("*.db"))
            if db_size > 500 * 1024 * 1024:  # 500MB
                issues.append(f"Memory DB: {db_size / 1024 / 1024:.1f}MB")

        if issues:
            return HealthCheck("maintenance", "warning", "; ".join(issues))
        return HealthCheck("maintenance", "ok", "Maintenance complete")

    def _save_status(self):
        status_file = self.data_dir / "heartbeat_status.json"
        status_file.write_text(json.dumps({
            "last_check": time.time(),
            "checks": [{"name": c.name, "status": c.status, "message": c.message} for c in self._checks],
        }, indent=2))

    def get_status(self) -> dict[str, Any]:
        status_file = self.data_dir / "heartbeat_status.json"
        if status_file.exists():
            return json.loads(status_file.read_text())
        return {"last_check": 0, "checks": []}
