from __future__ import annotations

import json
import time

from fastapi import APIRouter, Header

from webui.backend.dashboard.helpers import _require_admin
from webui.backend.dashboard.state import OUTPUTS_DIR

router = APIRouter()

JOBS_FILE = OUTPUTS_DIR / "automation_jobs.json"


def _load_jobs() -> list[dict]:
    if not JOBS_FILE.exists():
        return []
    try:
        return json.loads(JOBS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_jobs(jobs: list[dict]) -> None:
    JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    JOBS_FILE.write_text(json.dumps(jobs, indent=2), encoding="utf-8")


@router.get("/api/cron/jobs")
def api_cron_jobs(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    return {"jobs": _load_jobs()}


@router.post("/api/cron/jobs")
def api_cron_add_job(body: dict, _admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    jobs = _load_jobs()
    job = {
        "id": str(body.get("id") or int(time.time() * 1000)),
        "name": str(body.get("name") or "job"),
        "schedule": str(body.get("schedule") or ""),
        "command": str(body.get("command") or body.get("callback") or ""),
        "enabled": bool(body.get("enabled", True)),
        "created_at": time.time(),
    }
    jobs.append(job)
    _save_jobs(jobs)
    return {"ok": True, "job": job}


@router.delete("/api/cron/jobs/{job_id}")
def api_cron_delete_job(job_id: str, _admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    jobs = [job for job in _load_jobs() if str(job.get("id")) != job_id]
    _save_jobs(jobs)
    return {"ok": True, "jobs": jobs}
