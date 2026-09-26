"""Trigger rules (event-driven proactivity) and a view of the event bus.

Admin-only, like automation jobs: a rule can run commands on the user's behalf.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from drishti.dashboard.helpers import _require_admin

router = APIRouter()


def _engine(request: Request):
    engine = getattr(request.app.state, "triggers", None)
    if engine is None:  # app started without lifespan (e.g. some tests)
        from atulya.cognition.triggers import TriggerEngine

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
    from yantra.events import default_bus

    event_type = str(body.get("type") or "").strip()
    if not event_type:
        raise HTTPException(status_code=400, detail="type is required")
    payload: dict[str, Any] = body.get("payload") if isinstance(body.get("payload"), dict) else {}
    event = await default_bus.emit(event_type, payload)
    return {"ok": True, "type": event.type}


@router.get("/api/events/recent")
def api_recent_events(limit: int = 50, _admin: dict = Depends(_require_admin)):
    """The assistant's recent 'nervous system' activity."""
    from yantra.events import default_bus

    limit = max(1, min(int(limit), 500))
    return {"events": [
        {"type": e.type, "payload": e.payload, "timestamp": getattr(e, "timestamp", None)}
        for e in default_bus.history(limit)
    ]}
