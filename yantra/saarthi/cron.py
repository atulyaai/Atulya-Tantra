"""Cron/scheduling system with persistence."""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class CronJob:
    id: str
    name: str
    schedule: str  # cron expression or interval in seconds
    callback: str  # function name or command
    enabled: bool = True
    last_run: float = 0.0
    next_run: float = 0.0
    run_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class CronScheduler:
    def __init__(self, data_dir: str | Path = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, CronJob] = {}
        self._callbacks: dict[str, Callable] = {}
        self._running = False
        self._load()

    def _load(self):
        jobs_file = self.data_dir / "cron_jobs.json"
        if jobs_file.exists():
            data = json.loads(jobs_file.read_text())
            for j in data.get("jobs", []):
                job = CronJob(**j)
                self._jobs[job.id] = job

    def _save(self):
        jobs_file = self.data_dir / "cron_jobs.json"
        data = {"jobs": [vars(j) for j in self._jobs.values()]}
        jobs_file.write_text(json.dumps(data, indent=2))

    def register_callback(self, name: str, callback: Callable):
        self._callbacks[name] = callback

    def add_job(self, name: str, schedule: str, callback: str) -> str:
        job_id = f"cron_{int(time.time())}"
        interval = self._parse_schedule(schedule)
        job = CronJob(id=job_id, name=name, schedule=schedule, callback=callback, next_run=time.time() + interval)
        self._jobs[job_id] = job
        self._save()
        return job_id

    def remove_job(self, job_id: str):
        self._jobs.pop(job_id, None)
        self._save()

    def enable_job(self, job_id: str):
        if job_id in self._jobs:
            self._jobs[job_id].enabled = True
            self._save()

    def disable_job(self, job_id: str):
        if job_id in self._jobs:
            self._jobs[job_id].enabled = False
            self._save()

    async def start(self):
        self._running = True
        while self._running:
            await self._tick()
            await asyncio.sleep(1)

    async def stop(self):
        self._running = False

    async def _tick(self):
        now = time.time()
        for job in self._jobs.values():
            if job.enabled and job.next_run <= now:
                await self._run_job(job)

    async def _run_job(self, job: CronJob):
        callback = self._callbacks.get(job.callback)
        if callback:
            try:
                if hasattr(callback, "__await__"):
                    await callback()
                else:
                    callback()
                job.last_run = time.time()
                job.run_count += 1
                interval = self._parse_schedule(job.schedule)
                job.next_run = time.time() + interval
            except Exception as e:
                job.metadata["last_error"] = str(e)
        self._save()

    def _parse_schedule(self, schedule: str) -> float:
        """Parse schedule string to interval in seconds."""
        try:
            return float(schedule)
        except ValueError:
            # Simple cron-like parsing
            parts = schedule.split()
            if len(parts) == 5:
                minute, hour, day, month, weekday = parts
                if minute == "*" and hour == "*" and day == "*" and month == "*" and weekday == "*":
                    return 60  # every minute
                if hour != "*" and minute == "0":
                    return 3600  # every hour
            return 3600  # default 1 hour

    def list_jobs(self) -> list[dict[str, Any]]:
        return [
            {"id": j.id, "name": j.name, "schedule": j.schedule, "enabled": j.enabled,
             "last_run": j.last_run, "next_run": j.next_run, "run_count": j.run_count}
            for j in self._jobs.values()
        ]
