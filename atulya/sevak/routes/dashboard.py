"""The action-engine dashboard: one read for every tile, and a few real controls.

Every number comes from something Atulya actually has: the brain router's measured speeds, the audit log of what
it did, the calendar and reminders, the home devices (marked *simulated* unless Home Assistant is connected).
"""
from __future__ import annotations

import os
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from atulya.envfile import set_env_value
from atulya.sevak.helpers import _require_auth

router = APIRouter()

SECTIONS = [
    {"id": "system", "label": "System status", "words": ["system", "status", "health", "brain"]},
    {"id": "pc", "label": "PC desktop automation", "words": ["pc", "desktop", "computer"]},
    {"id": "web", "label": "Web browser automation", "words": ["web", "browser", "workflow"]},
    {"id": "home", "label": "Smart home hub", "words": ["home", "smart home", "lights", "devices"]},
    {"id": "calendar", "label": "Calendar & reminders", "words": ["calendar", "reminders", "schedule", "meetings"]},
    {"id": "money", "label": "Money", "words": ["money", "spending", "expenses", "bills", "budget", "finance"]},
    {"id": "media", "label": "Audio media player", "words": ["music", "media", "player", "audio", "song"]},
]


def _web_flow(events: list[dict[str, Any]]) -> dict[str, Any]:
    """The latest web task, as steps (navigate, click, type …) with how it ended."""
    flow: list[dict[str, Any]] = []
    for e in events:
        kind = str(e.get("event", ""))
        if not kind.startswith("web_task."):
            continue
        if kind == "web_task.step":
            if flow and flow[-1].get("end"):
                flow = []  # a new task began after the last one ended
            flow.append({"label": str(e.get("action") or "step"), "url": e.get("url", "")})
        else:
            flow.append({"label": kind.split(".", 1)[1], "url": e.get("url", ""), "end": True,
                         "note": e.get("reason") or e.get("say") or ""})
    goal = next((e.get("goal") for e in reversed(events) if str(e.get("event", "")).startswith("web_task.")), "")
    ended = bool(flow and flow[-1].get("end"))
    return {"goal": goal, "steps": flow[-8:], "state": ("finished" if ended else "running") if flow else "idle"}


def build_dashboard(*, audit: list[dict[str, Any]], speeds: dict[str, dict[str, float]], ready: list[str],
                    calendar: list[dict[str, Any]], reminders: list[dict[str, Any]], devices: dict[str, dict[str, Any]],
                    simulated_home: bool, pc_on: bool, is_admin: bool, now: float | None = None,
                    money: dict[str, Any] | None = None, vault: dict[str, Any] | None = None,
                    fabric: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    now = now or time.time()
    measured = sorted(((n, v["avg"]) for n, v in speeds.items() if v.get("avg")), key=lambda x: x[1])
    tools_used = [e for e in audit if e.get("event") == "tool"]
    music = next((e for e in reversed(tools_used) if e.get("name") == "play_music"), None)
    data: dict[str, Any] = {
        "sections": SECTIONS,
        "calendar": {
            "events": [{"title": e["title"], "time": e["time"], "minutes": e.get("duration", 60)}
                       for e in sorted(calendar, key=lambda x: x["time"]) if now <= e["time"] <= now + 7 * 86400][:8],
            "reminders": [{"message": r.get("message", ""), "time": r.get("scheduled_time")}
                          for r in sorted(reminders, key=lambda x: x.get("scheduled_time") or 0)
                          if (r.get("scheduled_time") or 0) >= now][:8],
        },
        "media": {"now_playing": (music or {}).get("args", {}).get("query", "") if music else "",
                  "at": (music or {}).get("t")},
        "money": money or {},
        "fabric": fabric or [],
        "home": {"simulated": simulated_home,
                 "devices": [{"id": i, **d} for i, d in devices.items()]},
    }
    if is_admin:
        data["system"] = {"agent": "Atulya", "ready": ready, "brains": [{"name": n, "seconds": round(s, 2)} for n, s in measured],
                          "fastest": measured[0][0] if measured else (ready[0] if ready else "none"),
                          "latency": round(measured[0][1], 2) if measured else None, "vault": vault or {}}
        data["pc"] = {"control": pc_on, "recent": [{"name": e.get("name"), "t": e.get("t")} for e in tools_used
                                                    if str(e.get("name", "")).startswith("pc_")][-6:]}
        data["web"] = _web_flow(audit)
    return data


@router.get("/api/dashboard")
def api_dashboard(user: dict = Depends(_require_auth)):
    from atulya.yantra import tools
    from atulya.yantra.audit import recent
    from atulya.buddhi.intelligence import _SPEED, ProviderRouter
    from atulya.raksha import vault
    from atulya.upakaran.hub import get_hub
    from atulya.yantra import money, pc_control

    ready = [p.name() for p in ProviderRouter().providers if p.is_available() and p.name() != "No brain loaded"]
    return build_dashboard(
        audit=recent(200), speeds=_SPEED, ready=ready,
        calendar=list(tools._CALENDAR.values()), reminders=list(tools._reminders.values()),
        devices=tools._HOME_DEVICES if (os.environ.get("HOME_ASSISTANT_URL") or tools.simulated_home()) else {}, simulated_home=not os.environ.get("HOME_ASSISTANT_URL"),
        pc_on=pc_control.enabled(),
        is_admin=user.get("role") == "admin", money=money.snapshot(), vault=vault.status(),
        fabric=get_hub().describe(),
    )


@router.post("/api/dashboard/pc-control")
def api_toggle_pc(body: dict, user: dict = Depends(_require_auth)):
    """Switch PC control on or off (admin). It still asks before every action."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    on = bool(body.get("on"))
    set_env_value("ATULYA_PC_CONTROL", "on" if on else "")
    return {"control": on}


@router.post("/api/dashboard/media")
async def api_media(body: dict, user: dict = Depends(_require_auth)):
    from atulya.yantra.media import media_control

    action = str(body.get("action") or "")
    return {"message": await media_control(action)}


@router.post("/api/dashboard/home")
async def api_home(body: dict, user: dict = Depends(_require_auth)):
    """Turn a light or thermostat on/off from the dashboard. Locks are never touched here."""
    from atulya.yantra import tools

    device = tools._HOME_DEVICES.get(str(body.get("device_id")))
    action = str(body.get("action") or "")
    if device is None or device.get("type") == "lock" or action not in ("on", "off"):
        raise HTTPException(status_code=400, detail="Only lights and thermostats can be switched here")
    return {"message": await tools.home_control(str(body["device_id"]), action)}
