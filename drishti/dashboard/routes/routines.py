"""Routines: named multi-step plans ("Guests are coming", "Good night"…).

Admin-only to change, like trigger rules and automations, because a routine
runs actions on the household's behalf.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from drishti.dashboard.helpers import _require_admin

router = APIRouter()


def _kernel(request: Request):
    from atulya.cognition import get_kernel
    from atulya.llm import get_default_llm

    return get_kernel(getattr(request.app.state, "llm", None) or get_default_llm())


@router.get("/api/routines")
def api_list_routines(request: Request, _admin: dict = Depends(_require_admin)):
    from atulya.cognition.planner import routine_steps

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
    from atulya.cognition.planner import Plan, routine_steps

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
    from atulya.cognition.planner import steps_for_clause

    text = str(body.get("text") or "").strip()
    plan = _kernel(request).planner.plan(text)
    if plan is not None:
        return {"plan": plan.to_dict()}
    steps = steps_for_clause(text) or []
    return {"plan": {"goal": text, "title": text, "source": "single" if steps else "brain",
                     "steps": [{"command": s.command, "tool": s.tool, "arguments": s.arguments} for s in steps]}}
