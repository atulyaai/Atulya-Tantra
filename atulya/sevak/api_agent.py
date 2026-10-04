"""Atulya Agent API routes — thin layer over tool registry + agent loop."""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile

from atulya.sevak.helpers import _require_admin, _require_auth
from atulya.sevak.state import OUTPUTS_DIR
from atulya.yantra.connector import AtulyaTantraConnector, CreationResult

# ── automation ────────────────────────────────────────────────────────────
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


def _seed_default_jobs() -> None:
    """Provision a small set of proactive jobs on first launch.

    The AutomationRunner executes each job's command through the LLM with tools
    on its schedule, so Atulya acts without being prompted. Existing files are
    left untouched (idempotent).
    """
    if not JOBS_FILE.exists():
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
def api_cron_jobs(_admin: dict = Depends(_require_admin)):
    return {"jobs": _load_jobs()}


@router.post("/api/cron/jobs")
def api_cron_add_job(body: dict, _admin: dict = Depends(_require_admin)):
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
def api_cron_delete_job(job_id: str, _admin: dict = Depends(_require_admin)):
    jobs = [job for job in _load_jobs() if str(job.get("id")) != job_id]
    _save_jobs(jobs)
    return {"ok": True, "jobs": jobs}


@router.patch("/api/cron/jobs/{job_id}")
def api_cron_update_job(job_id: str, body: dict, _admin: dict = Depends(_require_admin)):
    jobs = _load_jobs()
    for job in jobs:
        if str(job.get("id")) != job_id:
            continue
        for key in ("name", "schedule", "command"):
            if key in body:
                job[key] = str(body.get(key) or "")
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
    _admin: dict = Depends(_require_admin),
):
    jobs = _load_jobs()
    for job in jobs:
        if str(job.get("id")) != job_id:
            continue
        runner = getattr(request.app.state, "automation_runner", None)
        if runner is None:
            from atulya.buddhi.llm import get_default_llm
            from atulya.sevak.automation_runner import AutomationRunner
            runner = AutomationRunner(JOBS_FILE, get_default_llm())
        await runner.run_job(job)
        job["last_run"] = time.time()
        job["run_count"] = int(job.get("run_count") or 0) + 1
        _save_jobs(jobs)
        return {"ok": True, "job": job}
    return {"ok": False, "error": "Job not found"}


# ── upload ────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "kosh" / "uploads"
_MAX_SIZE = 50 * 1024 * 1024  # 50MB


def _safe_component(value: str, label: str = "identifier") -> str:
    """Reject any path-like input so it can't traverse outside the uploads dir.

    A valid username / file_id is a single path component with no separators,
    no parent references, and no null bytes. Anything else is a traversal
    attempt (e.g. '..', 'a/../../etc', '%2e%2e').
    """
    if not value or value in (".", "..") or "/" in value or "\\" in value or "\x00" in value:
        raise HTTPException(400, f"Invalid {label}")
    if os.path.basename(value) != value:
        raise HTTPException(400, f"Invalid {label}")
    return value


def _resolve_upload_path(username: str, file_id: str) -> Path:
    """Build an uploads path and confirm it stays inside UPLOAD_DIR."""
    _safe_component(username, "username")
    _safe_component(file_id, "file id")
    path = (UPLOAD_DIR / username / file_id).resolve()
    base = UPLOAD_DIR.resolve()
    if base not in path.parents:
        raise HTTPException(400, "Invalid path")
    return path
_ALLOWED_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf", "text/plain", "text/csv",
    "application/json", "application/zip",
}

@router.post("/api/upload")
async def api_upload(
    file: UploadFile = File(...),
    token: str | None = Header(default=None, alias="X-Atulya-Token")
):
    user = _require_auth(token)
    if not file.filename:
        raise HTTPException(400, "No filename")

    ext = Path(file.filename).suffix.lower() if file.filename else ""
    content_type = file.content_type or ""

    if content_type and content_type not in _ALLOWED_TYPES and not content_type.startswith("image/"):
        if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".txt", ".csv", ".json", ".zip"):
            raise HTTPException(400, f"File type '{content_type}' not allowed")

    user_dir = UPLOAD_DIR / user["username"]
    user_dir.mkdir(parents=True, exist_ok=True)

    file_id = f"{uuid.uuid4().hex}{ext}"
    dest = user_dir / file_id

    content = await file.read()
    if len(content) > _MAX_SIZE:
        raise HTTPException(400, f"File too large (max {_MAX_SIZE // 1024 // 1024}MB)")

    dest.write_bytes(content)

    return {
        "ok": True,
        "file_id": file_id,
        "filename": file.filename,
        "size": len(content),
        "url": f"/api/files/{user['username']}/{file_id}",
    }

@router.get("/api/files/{username}/{file_id}")
async def api_get_file(username: str, file_id: str, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    if username != user["username"] and user.get("role") != "admin":
        raise HTTPException(403, "Forbidden")
    file_path = _resolve_upload_path(username, file_id)
    if not file_path.is_file():
        raise HTTPException(404, "File not found")
    from fastapi.responses import FileResponse
    return FileResponse(str(file_path))

@router.get("/api/files")
async def api_list_files(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    user_dir = UPLOAD_DIR / user["username"]
    if not user_dir.exists():
        return {"files": []}
    files = []
    for f in user_dir.iterdir():
        if f.is_file():
            files.append({
                "file_id": f.name,
                "size": f.stat().st_size,
                "modified": f.stat().st_mtime,
            })
    return {"files": sorted(files, key=lambda x: x["modified"], reverse=True)}

@router.delete("/api/files/{file_id}")
async def api_delete_file(file_id: str, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    file_path = _resolve_upload_path(user["username"], file_id)
    if not file_path.is_file():
        raise HTTPException(404, "File not found")
    file_path.unlink()
    return {"ok": True}


# ── agent ────────────────────────────────────────────────────────────
_AGENT = None


def set_agent(agent):
    global _AGENT
    _AGENT = agent


def _get_agent():
    if _AGENT is None:
        raise HTTPException(status_code=503, detail="Atulya Agent not initialized")
    return _AGENT


@router.get("/api/agent/status")
async def agent_status(user: dict = Depends(_require_admin)):
    a = _get_agent()
    return {"tools": a.list_tools(), "status": "ready"}


@router.post("/api/agent/process")
async def agent_process(request: Request, user: dict = Depends(_require_auth)):
    body = await request.json()
    user_input = body.get("input", "")
    history = body.get("history")
    if not user_input:
        return {"status": "error", "message": "No input"}
    a = _get_agent()
    reply = await a.process(user_input, history, user=user)
    return {"status": "success", "reply": reply}


@router.get("/api/agent/tools")
async def agent_tools(user: dict = Depends(_require_admin)):
    a = _get_agent()
    return {"tools": a.list_tools()}


@router.get("/api/agent/schemas")
async def agent_schemas(user: dict = Depends(_require_admin)):
    a = _get_agent()
    return {"schemas": a.get_tool_schemas()}


# ── create ────────────────────────────────────────────────────────────
def _connector() -> AtulyaTantraConnector:
    return AtulyaTantraConnector("kosh/creations")


def _payload(result: CreationResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "format": result.format,
        "path": result.path,
        "fallback": result.fallback,
        "metadata": result.metadata,
        "error": result.error,
    }


def _options(body: dict) -> dict[str, Any]:
    return {key: value for key, value in body.items() if key not in {"prompt", "format", "formats"}}


@router.post("/api/create")
def api_create(body: dict, _user: dict = Depends(_require_auth)):
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        return {"ok": False, "error": "prompt is required"}
    connector = _connector()
    formats = body.get("formats")
    if isinstance(formats, list) and formats:
        results = connector.create_multi(prompt, [str(item) for item in formats])
        return {"ok": all(item.ok for item in results), "results": [_payload(item) for item in results]}
    return _payload(connector.create(prompt, str(body.get("format") or "auto"), **_options(body)))


@router.post("/api/create/document")
def api_create_document(body: dict, _user: dict = Depends(_require_auth)):
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        return {"ok": False, "error": "prompt is required"}
    return _payload(_connector().create(prompt, str(body.get("format") or "pdf"), **_options(body)))


@router.post("/api/create/video")
def api_create_video(body: dict, _user: dict = Depends(_require_auth)):
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        return {"ok": False, "error": "prompt is required"}
    return _payload(_connector().create(prompt, "video", **_options(body)))


# ── triggers ────────────────────────────────────────────────────────────
def _engine(request: Request):
    engine = getattr(request.app.state, "triggers", None)
    if engine is None:  # app started without lifespan (e.g. some tests)
        from atulya.buddhi.triggers import TriggerEngine

        engine = TriggerEngine()
        request.app.state.triggers = engine
    return engine


@router.get("/api/triggers")
def api_list_triggers(request: Request, _admin: dict = Depends(_require_admin)):
    return {"triggers": _engine(request).list_rules()}


@router.post("/api/triggers")
def api_add_trigger(request: Request, body: dict, _admin: dict = Depends(_require_admin)):
    try:
        rule = _engine(request).add_rule(body)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "trigger": rule}


@router.delete("/api/triggers/{rule_id}")
def api_delete_trigger(rule_id: str, request: Request, _admin: dict = Depends(_require_admin)):
    if not _engine(request).remove_rule(rule_id):
        raise HTTPException(status_code=404, detail="Trigger not found")
    return {"ok": True}


@router.post("/api/events/emit")
async def api_emit_event(body: dict, _admin: dict = Depends(_require_admin)):
    """Publish an event on the bus — handy for testing trigger rules."""
    from atulya.events import default_bus

    event_type = str(body.get("type") or "").strip()
    if not event_type:
        raise HTTPException(status_code=400, detail="type is required")
    payload: dict[str, Any] = body.get("payload") if isinstance(body.get("payload"), dict) else {}
    event = await default_bus.emit(event_type, payload)
    return {"ok": True, "type": event.type}


@router.get("/api/events/recent")
def api_recent_events(limit: int = 50, _admin: dict = Depends(_require_admin)):
    """The assistant's recent 'nervous system' activity."""
    from atulya.events import default_bus

    limit = max(1, min(int(limit), 500))
    return {"events": [
        {"type": e.type, "payload": e.payload, "timestamp": getattr(e, "timestamp", None)}
        for e in default_bus.history(limit)
    ]}


# ── routines ────────────────────────────────────────────────────────────
def _kernel(request: Request):
    from atulya.buddhi import get_kernel
    from atulya.buddhi.llm import get_default_llm

    return get_kernel(getattr(request.app.state, "llm", None) or get_default_llm())


@router.get("/api/routines")
def api_list_routines(request: Request, _admin: dict = Depends(_require_admin)):
    from atulya.buddhi.planner import routine_steps

    store = _kernel(request).planner.routines
    return {"routines": [
        {**r, "plan": [s.command for s in routine_steps(r)]} for r in store.list()
    ]}


@router.post("/api/routines")
def api_save_routine(request: Request, body: dict, _admin: dict = Depends(_require_admin)):
    try:
        routine = _kernel(request).planner.routines.save(body)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "routine": routine}


@router.delete("/api/routines/{routine_id}")
def api_delete_routine(routine_id: str, request: Request, _admin: dict = Depends(_require_admin)):
    if not _kernel(request).planner.routines.remove(routine_id):
        raise HTTPException(status_code=404, detail="Routine not found")
    return {"ok": True}


@router.post("/api/routines/{routine_id}/run")
async def api_run_routine(routine_id: str, request: Request, admin: dict = Depends(_require_admin)):
    from atulya.buddhi.planner import Plan, routine_steps

    kernel = _kernel(request)
    routine = kernel.planner.routines.get(routine_id)
    if routine is None:
        raise HTTPException(status_code=404, detail="Routine not found")
    plan = Plan(goal=str(routine["name"]), title=str(routine["name"]), source="routine",
                steps=routine_steps(routine), routine_id=routine_id)
    response = await kernel.start_plan(plan, user=admin, source="chat")
    return {
        "response": response.text,
        "needs_approval": response.needs_approval,
        "pending_tool": response.pending_tool,
        "trace": response.trace,
        "steps": response.tool_steps,
    }


@router.post("/api/plan/preview")
def api_preview_plan(request: Request, body: dict, _admin: dict = Depends(_require_admin)):
    """What Atulya would do for a sentence, without doing it."""
    from atulya.buddhi.planner import steps_for_clause

    text = str(body.get("text") or "").strip()
    plan = _kernel(request).planner.plan(text)
    if plan is not None:
        return {"plan": plan.to_dict()}
    steps = steps_for_clause(text) or []
    return {"plan": {"goal": text, "title": text, "source": "single" if steps else "brain",
                     "steps": [{"command": s.command, "tool": s.tool, "arguments": s.arguments} for s in steps]}}

