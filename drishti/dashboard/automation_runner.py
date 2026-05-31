"""Background automation runner for stored cron jobs."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

try:
    from croniter import croniter
except ImportError:  # pragma: no cover
    croniter = None


class AutomationRunner:
    def __init__(self, jobs_file: str | Path, llm: Any, interval: float = 1.0):
        self.jobs_file = Path(jobs_file)
        self.llm = llm
        self.interval = interval
        self._running = False

    async def start(self) -> None:
        self._running = True
        while self._running:
            await self.tick()
            await asyncio.sleep(self.interval)

    async def stop(self) -> None:
        self._running = False

    async def tick(self) -> None:
        jobs = self._load_jobs()
        now = time.time()
        changed = False
        for job in jobs:
            if not job.get("enabled", True):
                continue
            next_run = float(job.get("next_run") or 0)
            if next_run <= 0:
                job["next_run"] = self._next_run(str(job.get("schedule") or "60"), now)
                changed = True
                continue
            if next_run > now:
                continue
            command = str(job.get("command") or job.get("callback") or "").strip()
            if command:
                await self.run_job(job)
            job["last_run"] = now
            job["run_count"] = int(job.get("run_count") or 0) + 1
            job["next_run"] = self._next_run(str(job.get("schedule") or "60"), now)
            changed = True
        if changed:
            self._save_jobs(jobs)

    def _load_jobs(self) -> list[dict[str, Any]]:
        if not self.jobs_file.exists():
            return []
        try:
            return json.loads(self.jobs_file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_jobs(self, jobs: list[dict[str, Any]]) -> None:
        self.jobs_file.parent.mkdir(parents=True, exist_ok=True)
        self.jobs_file.write_text(json.dumps(jobs, indent=2), encoding="utf-8")

    async def run_job(self, job: dict[str, Any]) -> dict[str, Any]:
        command = str(job.get("command") or job.get("callback") or "").strip()
        if not command:
            job["last_error"] = "No command configured"
            return job
        try:
            response = await self.llm.ask(command, tools_enabled=True)
            job["last_result"] = response.text[:2000]
            job["last_provider"] = response.provider
            job["last_error"] = ""
        except Exception as exc:
            job["last_error"] = str(exc)
        return job

    @staticmethod
    def _next_run(schedule: str, now: float) -> float:
        try:
            return now + max(float(schedule), 1.0)
        except ValueError:
            if croniter is None:
                return now + 60.0
            return croniter(schedule, now).get_next(float)
