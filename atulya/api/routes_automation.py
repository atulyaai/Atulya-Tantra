"""API: the server's API: accounts and sessions, chat history, sign-in, brains and keys, chat and voice, home and dashboard, automation."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from fastapi import (
    Depends,
    HTTPException,
    Request,
)


from . import router
from atulya import api as _d

# ── api_automation ────────────────────────────────────────────────────────────
# ── automation_runner ────────────────────────────────────────────────────────────
try:
    from croniter import croniter
except ImportError:  # pragma: no cover
    croniter = None


def _next_job_run(schedule: str, now: float) -> float:
    """Calculate the next interval or cron run without runner state."""
    try:
        return now + max(float(schedule), 1.0)
    except ValueError:
        if croniter is None:
            return now + 60.0
        return croniter(schedule, now).get_next(float)


class AutomationRunner:
    """Run scheduled assistant jobs with persisted lifecycle state and bounds."""

    MAX_RUN_SECONDS = 300
    RUN_STATE_TTL = 7 * 24 * 60 * 60

    def __init__(self, jobs_file: str | Path, llm: Any, interval: float = 1.0):
        self.jobs_file = Path(jobs_file)
        self.llm = llm
        self.interval = interval
        self._running = False
        self._tasks: dict[str, asyncio.Task] = {}

    async def start(self) -> None:
        self._running = True
        while self._running:
            await self.tick()
            await asyncio.sleep(self.interval)

    async def stop(self) -> None:
        self._running = False
        tasks = list(self._tasks.values())
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def tick(self) -> None:
        jobs = self._load_jobs()
        now = time.time()
        changed = False
        for job in jobs:
            if not job.get("enabled", True):
                continue
            if job.get("run_status") == "running":
                if str(job.get("id") or "") in self._tasks:
                    continue
                # The previous process disappeared mid-run. Do not replay a
                # possibly completed side effect after restart; move to the
                # next occurrence and make the interruption visible.
                job.update({"run_status": "interrupted", "run_phase": "server_restarted",
                            "run_progress": 100, "run_updated_at": now,
                            "last_error": "Server restarted during this run; it was not replayed."})
                job["next_run"] = self._next_run(str(job.get("schedule") or "60"), now)
                changed = True
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
                # Persist the next occurrence before any action starts. A
                # process crash can miss this occurrence, but cannot repeat
                # an action whose completion was uncertain.
                job["last_run"] = now
                job["run_count"] = int(job.get("run_count") or 0) + 1
                job["next_run"] = self._next_run(str(job.get("schedule") or "60"), now)
                self._save_jobs(jobs)
                await self.run_job(job)
                changed = False
                continue
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
        job_id = str(job.get("id") or "")
        started = time.time()
        job.update({"run_status": "running", "run_progress": 0, "run_phase": "starting",
                    "run_started_at": started, "run_updated_at": started,
                    "run_expires_at": started + self.RUN_STATE_TTL})
        self._persist_run_state(job)
        if not command:
            job["last_error"] = "No command configured"
            job.update({"run_status": "failed", "run_progress": 100,
                        "run_phase": "finished", "run_updated_at": time.time()})
            self._persist_run_state(job)
            await self._notify_job(job, error="No command configured")
            return job
        try:
            # Through the cognitive kernel: clear actions ("turn off the lights")
            # run deterministically — the job was authorized when it was
            # created — and open-ended commands ("summarize my unread email")
            # go to the brain. Actions are remembered and published as events.
            from atulya.pipeline import get_kernel

            job.update({"run_progress": 10, "run_phase": "thinking", "run_updated_at": time.time()})
            self._persist_run_state(job)
            response = await asyncio.wait_for(
                get_kernel(self.llm).handle(command, user="automation", source="automation"),
                timeout=self.MAX_RUN_SECONDS,
            )
            job["last_result"] = (response.text or "")[:2000] if response.text is not None else ""
            job["last_provider"] = response.provider if response.provider is not None else ""
            job["last_error"] = ""
            if getattr(response, "needs_approval", False):
                job.update({"run_status": "needs_approval", "run_phase": "waiting_for_owner",
                            "pending_tool": getattr(response, "pending_tool", None)})
            else:
                job.update({"run_status": "completed", "run_phase": "finished", "run_progress": 100})
        except asyncio.CancelledError:
            job.update({"run_status": "cancelled", "run_phase": "cancelled", "last_error": "Cancelled by owner"})
            raise
        except Exception as exc:
            job["last_error"] = "Job exceeded its time limit" if isinstance(exc, asyncio.TimeoutError) else str(exc)
            job["last_result"] = ""
            job["last_provider"] = ""
            job.update({"run_status": "failed", "run_phase": "finished"})
        finally:
            job["run_progress"] = int(job.get("run_progress") or 0) if job.get("run_status") == "needs_approval" else 100
            job["run_updated_at"] = time.time()
            self._persist_run_state(job)
            if job_id:
                self._tasks.pop(job_id, None)
        if job.get("run_status") == "needs_approval":
            await self._notify_job(job, error="Approval required")
        else:
            await self._notify_job(job, error=job.get("last_error") or "")
        return job

    async def start_job(self, job: dict[str, Any]) -> dict[str, Any]:
        """Start a manual run in the background and return its persisted state."""
        job_id = str(job.get("id") or "")
        current = self._tasks.get(job_id)
        if current and not current.done():
            return {**job, "run_status": "running"}
        task = asyncio.create_task(self.run_job(job))
        self._tasks[job_id] = task
        # Yield once so the initial `running` state is written before returning.
        await asyncio.sleep(0)
        return dict(job)

    async def cancel_job(self, job_id: str) -> dict[str, Any] | None:
        """Cancel a running job and wait for its cancelled state to be saved."""
        task = self._tasks.get(job_id)
        if task is None or task.done():
            return None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return next((job for job in self._load_jobs() if str(job.get("id")) == job_id), None)

    def _persist_run_state(self, job: dict[str, Any]) -> None:
        """Persist only lifecycle/result fields, preserving concurrent job edits."""
        if not job.get("id"):
            return
        jobs = self._load_jobs()
        current = next((item for item in jobs if str(item.get("id")) == str(job["id"])), None)
        if current is None:
            current = {"id": str(job["id"])}
            jobs.append(current)
        for key in ("run_status", "run_progress", "run_phase", "run_started_at", "run_updated_at",
                    "run_expires_at", "last_result", "last_provider", "last_error", "pending_tool"):
            if key in job:
                current[key] = job[key]
        self._save_jobs(jobs)

    async def _notify_job(self, job: dict[str, Any], error: str = "") -> None:
        """Emit a completion event for a finished automation job.

        Best-effort: broadcasts to WebSocket listeners and, when a notification
        channel is configured, forwards to the dashboard's own notifier.
        Never lets a notification failure abort the job itself.
        """
        name = job.get("name") or job.get("id") or "automation job"
        try:
            # Publish on the event bus so trigger rules can react (e.g. alert on failure).
            from atulya.settings import default_bus
            event_name = "automation.failed" if error and error != "Approval required" else (
                "automation.pending_approval" if error == "Approval required" else "automation.completed")
            await default_bus.emit(event_name, {
                "job": name,
                "result": str(job.get("last_result") or "")[:500],
                "error": error,
                "source": "automation",
            })
        except Exception:  # pragma: no cover - events are best-effort
            pass

        try:
            desc = (error or "job finished")[:280]
            await _d.broadcast_event(
                f"Automation job: {name}",
                desc,
                event_type="warning" if error == "Approval required" else ("success" if not error else "error"),
            )
        except Exception:  # pragma: no cover - notifications are best-effort
            pass

        try:
            from atulya.channels import NotificationSystem
            await NotificationSystem().send(
                f"{name}: {'failed' if error else 'completed'}",
                channel="console",
                title="Automation",
            )
        except Exception:  # pragma: no cover - notifications are best-effort
            pass

    @staticmethod
    def _next_run(schedule: str, now: float) -> float:
        return _next_job_run(schedule, now)


# ── api_agent ────────────────────────────────────────────────────────────
# ── automation ────────────────────────────────────────────────────────────

JOBS_FILE = _d.OUTPUTS_DIR / "automation_jobs.json"


def _load_jobs() -> list[dict]:
    if not _d.JOBS_FILE.exists():
        return []
    try:
        jobs = json.loads(_d.JOBS_FILE.read_text(encoding="utf-8"))
        now = time.time()
        changed = False
        for job in jobs:
            expires = float(job.get("run_expires_at") or 0)
            if expires and expires <= now:
                for key in ("run_status", "run_progress", "run_phase", "run_started_at", "run_updated_at",
                            "run_expires_at", "last_result", "last_provider", "last_error", "pending_tool"):
                    job.pop(key, None)
                changed = True
        if changed:
            _save_jobs(jobs)
        return jobs
    except Exception:
        return []


def _save_jobs(jobs: list[dict]) -> None:
    _d.JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _d.JOBS_FILE.write_text(json.dumps(jobs, indent=2), encoding="utf-8")


def _valid_job_schedule(value: Any) -> bool:
    """Accept bounded interval seconds or a valid cron expression."""
    schedule = str(value or "").strip()
    if not schedule or len(schedule) > 100:
        return False
    try:
        interval = float(schedule)
        return 1 <= interval <= 365 * 24 * 60 * 60
    except ValueError:
        return bool(croniter and croniter.is_valid(schedule))


def _seed_default_jobs() -> None:
    """Provision a small set of proactive jobs on first launch.

    The AutomationRunner executes each job's command through the LLM with tools
    on its schedule, so Atulya acts without being prompted. Existing files are
    left untouched (idempotent).
    """
    if not _d.JOBS_FILE.exists():
        defaults = [
            {
                "id": "seed_proactive_morning",
                "name": "Morning Initiative",
                "schedule": "86400",
                "command": (
                    "Proactively check current todos, memory notes, and pending "
                    "automation, then summarize what is most important today."
                ),
                "enabled": True,
                "created_at": time.time(),
            },
            {
                "id": "seed_proactive_cleanup",
                "name": "Periodic Cleanup Review",
                "schedule": "43200",
                "command": (
                    "Review recent memory and chat history for stale or outdated notes"
                    " and leave a short maintenance summary."
                ),
                "enabled": False,
                "created_at": time.time(),
            },
        ]
        _save_jobs(defaults)


@router.get("/api/cron/jobs")
def api_cron_jobs(_admin: dict = Depends(_d._require_admin)):
    return {"jobs": _load_jobs()}


@router.post("/api/cron/jobs")
def api_cron_add_job(body: dict, _admin: dict = Depends(_d._require_admin)):
    jobs = _load_jobs()
    name = str(body.get("name") or "job").strip()
    schedule = str(body.get("schedule") or "").strip()
    command = str(body.get("command") or body.get("callback") or "").strip()
    if not name or len(name) > 80:
        raise HTTPException(status_code=400, detail="Job name must be 1–80 characters")
    if not _valid_job_schedule(schedule):
        raise HTTPException(status_code=400, detail="Schedule must be 1–31536000 seconds or a valid cron expression")
    if not command or len(command) > 1000:
        raise HTTPException(status_code=400, detail="Job command must be 1–1000 characters")
    job = {
        "id": str(body.get("id") or int(time.time() * 1000)),
        "name": name,
        "schedule": schedule,
        "command": command,
        "enabled": bool(body.get("enabled", True)),
        "created_at": time.time(),
    }
    jobs.append(job)
    _save_jobs(jobs)
    return {"ok": True, "job": job}


@router.delete("/api/cron/jobs/{job_id}")
def api_cron_delete_job(job_id: str, _admin: dict = Depends(_d._require_admin)):
    jobs = [job for job in _load_jobs() if str(job.get("id")) != job_id]
    _save_jobs(jobs)
    return {"ok": True, "jobs": jobs}


@router.patch("/api/cron/jobs/{job_id}")
def api_cron_update_job(job_id: str, body: dict, _admin: dict = Depends(_d._require_admin)):
    jobs = _load_jobs()
    for job in jobs:
        if str(job.get("id")) != job_id:
            continue
        for key in ("name", "schedule", "command"):
            if key in body:
                value = str(body.get(key) or "").strip()
                if key == "name" and (not value or len(value) > 80):
                    raise HTTPException(status_code=400, detail="Job name must be 1–80 characters")
                if key == "schedule" and not _valid_job_schedule(value):
                    raise HTTPException(status_code=400, detail="Schedule must be 1–31536000 seconds or a valid cron expression")
                if key == "command" and (not value or len(value) > 1000):
                    raise HTTPException(status_code=400, detail="Job command must be 1–1000 characters")
                job[key] = value
        if "enabled" in body:
            job["enabled"] = bool(body["enabled"])
        job["updated_at"] = time.time()
        _save_jobs(jobs)
        return {"ok": True, "job": job}
    return {"ok": False, "error": "Job not found"}


@router.post("/api/cron/jobs/{job_id}/run")
async def api_cron_run_job(
    request: Request,
    job_id: str,
    _admin: dict = Depends(_d._require_admin),
):
    jobs = _load_jobs()
    for job in jobs:
        if str(job.get("id")) != job_id:
            continue
        runner = getattr(request.app.state, "automation_runner", None)
        if runner is None:
            from atulya.brain import get_default_llm
            runner = _d.AutomationRunner(_d.JOBS_FILE, get_default_llm())
            request.app.state.automation_runner = runner
        started = time.time()
        job["last_run"] = started
        job["run_count"] = int(job.get("run_count") or 0) + 1
        job["next_run"] = _next_job_run(str(job.get("schedule") or "60"), started)
        _save_jobs(jobs)
        job = await runner.start_job(job)
        return {"ok": True, "job": job}
    return {"ok": False, "error": "Job not found"}


@router.post("/api/cron/jobs/{job_id}/cancel")
async def api_cron_cancel_job(
    request: Request,
    job_id: str,
    _admin: dict = Depends(_d._require_admin),
):
    """Cancel an active manual job. Scheduled jobs remain configured."""
    runner = getattr(request.app.state, "automation_runner", None)
    if runner is None:
        return {"ok": False, "error": "No active job runner"}
    job = await runner.cancel_job(job_id)
    if job is None:
        return {"ok": False, "error": "Job is not running"}
    return {"ok": True, "job": job}


