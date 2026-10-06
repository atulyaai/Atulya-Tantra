"""API: the server's API: accounts and sessions, chat history, sign-in, brains and keys, chat and voice, home and dashboard, automation."""
from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.parse import parse_qs

from pydantic import BaseModel
from fastapi import (
    Depends,
    Header,
    HTTPException,
    Request,
)

from atulya import actions as money
from atulya import companion as computer_agent
from atulya import phone as phone_store
from atulya import security as vault

from . import router
from atulya import api as _d

# ── money ────────────────────────────────────────────────────────────
_MAX_BYTES = 4000


async def _alert_text(request: Request) -> str:
    raw = (await request.body())[:_MAX_BYTES]
    text = raw.decode("utf-8", "ignore").strip()
    if text.startswith("{"):
        try:
            data = json.loads(text)
            return str(data.get("text") or data.get("message") or data.get("body") or data.get("sms") or "")
        except json.JSONDecodeError:
            return text
    if "=" in text and "\n" not in text and " " not in text.split("=", 1)[0]:
        form = parse_qs(text)
        for key in ("text", "message", "body", "sms"):
            if form.get(key):
                return form[key][0]
    return text


@router.post("/api/money/sms")
async def api_money_sms(request: Request):
    key = request.headers.get("x-atulya-inbox") or request.query_params.get("key")
    if not money.inbox_token_ok(key):
        raise HTTPException(status_code=401, detail="Bad inbox key")
    text = await _alert_text(request)
    if not text:
        raise HTTPException(status_code=400, detail="No message text")
    result = await money.record_alert_async(text, "sms")
    return {"status": result["status"], "message": money._alert_reply(result)}


@router.get("/api/money/inbox")
def api_money_inbox(request: Request, user: dict = Depends(_d._require_admin)):
    """The secret and the address to give your phone's SMS-forwarding app."""
    return {"key": money.inbox_token(), "path": "/api/money/sms", "origin": str(request.base_url).rstrip("/")}


@router.post("/api/money/inbox/rotate")
def api_money_inbox_rotate(user: dict = Depends(_d._require_admin)):
    return {"key": money.inbox_token(rotate=True)}


# ── paired phone companion ────────────────────────────────────────────────
def _require_phone_device(token: str | None, *, command: bool = False) -> dict[str, Any]:
    device = vault.paired_devices().authenticate(token)
    if not device:
        raise HTTPException(status_code=401, detail="A paired phone token is required.")
    if str(device.get("kind", "")).lower() not in {"phone", "termux", "android"}:
        raise HTTPException(status_code=403, detail="Pair this device as a phone before using phone sync.")
    if command and device.get("permission") != "full":
        raise HTTPException(status_code=403, detail="Phone commands require full permission.")
    return device


@router.post("/api/phone/{kind}")
async def api_phone_receive(kind: str, request: Request,
                            token: str | None = Header(default=None, alias="X-Atulya-Token")):
    """Receive SMS, notification, or location batches from a paired Termux phone."""
    device = _require_phone_device(token)
    if kind not in {"sms", "notifications", "location"}:
        raise HTTPException(status_code=404, detail="Unknown phone inbox type.")
    try:
        content_length = int(request.headers.get("content-length", "0"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid content length.") from exc
    if content_length > 512_000:
        raise HTTPException(status_code=413, detail="Phone sync batch is too large.")
    chunks = []
    received_bytes = 0
    async for chunk in request.stream():
        received_bytes += len(chunk)
        if received_bytes > 512_000:
            raise HTTPException(status_code=413, detail="Phone sync batch is too large.")
        chunks.append(chunk)
    try:
        body = json.loads(b"".join(chunks) or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Send a valid JSON body.") from exc
    if not isinstance(body, dict) or not isinstance(body.get("items"), list):
        raise HTTPException(status_code=422, detail="Send a JSON body with an items array.")
    try:
        result = phone_store.add_items(kind, device["id"], body["items"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    money.audit("phone.inbox", kind=kind, device_id=device["id"], added=result["added"])
    return {"ok": True, **result}


@router.get("/api/phone/inbox")
def api_phone_inbox(kind: str = "all", limit: int = 100, user: dict = Depends(_d._require_admin)):
    try:
        items = phone_store.list_items(kind, limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"items": items}


@router.delete("/api/phone/inbox")
def api_phone_clear(kind: str = "all", user: dict = Depends(_d._require_admin)):
    try:
        deleted = phone_store.clear_items(kind)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    money.audit("phone.inbox.cleared", by=user.get("username"), kind=kind, deleted=deleted)
    return {"ok": True, "deleted": deleted}


@router.get("/api/phone/devices")
def api_phone_devices(user: dict = Depends(_d._require_admin)):
    now = time.time()
    devices = [device for device in vault.paired_devices().list()
               if str(device.get("kind", "")).lower() in {"phone", "termux", "android"} and not device.get("revoked")]
    return {"devices": [{**device, "online": now - float(device.get("last_seen", 0)) < 120} for device in devices]}


class PhoneCommandBody(BaseModel):
    action: str


@router.post("/api/phone/devices/{device_id}/commands")
def api_phone_command(device_id: str, body: PhoneCommandBody, user: dict = Depends(_d._require_admin)):
    device = next((item for item in vault.paired_devices().list()
                   if item.get("id") == device_id and not item.get("revoked")), None)
    if not device or str(device.get("kind", "")).lower() not in {"phone", "termux", "android"}:
        raise HTTPException(status_code=404, detail="No paired phone with that id.")
    try:
        command = phone_store.enqueue(device_id, body.action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    money.audit("phone.command", by=user.get("username"), device_id=device_id, action=body.action)
    return {"ok": True, "command": command}


@router.get("/api/phone/commands")
def api_phone_commands(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    device = _require_phone_device(token, command=True)
    return {"commands": phone_store.poll(device["id"])}


@router.post("/api/phone/commands/{command_id}/result")
def api_phone_command_result(command_id: str, body: dict,
                             token: str | None = Header(default=None, alias="X-Atulya-Token")):
    device = _require_phone_device(token, command=True)
    result = body.get("result", {})
    if not isinstance(result, dict):
        raise HTTPException(status_code=422, detail="Command result must be an object.")
    if not phone_store.acknowledge(device["id"], command_id, result):
        raise HTTPException(status_code=404, detail="No pending command for this phone.")
    money.audit("phone.command.result", device_id=device["id"], command_id=command_id,
                ok=bool(result.get("ok")))
    return {"ok": True}


# ── outbound companion for a paired computer ─────────────────────────────────
def _require_computer_device(token: str | None) -> dict[str, Any]:
    device = vault.paired_devices().authenticate(token)
    if not device:
        raise HTTPException(status_code=401, detail="A paired computer token is required.")
    if str(device.get("kind", "")).lower() not in {"computer", "laptop", "workstation"}:
        raise HTTPException(status_code=403, detail="Pair this device as a computer before using the companion.")
    return device


class RemoteComputerCommandBody(BaseModel):
    device_id: str
    operation: str
    arguments: dict[str, Any] | None = None


@router.post("/api/agent/computer/commands")
def api_queue_computer_command(body: RemoteComputerCommandBody, user: dict = Depends(_d._require_admin)):
    device = next((row for row in vault.paired_devices().list()
                   if row.get("id") == body.device_id and not row.get("revoked")), None)
    if not device or str(device.get("kind", "")).lower() not in {"computer", "laptop", "workstation"}:
        raise HTTPException(status_code=404, detail="No paired computer with that id.")
    if device.get("permission") not in {"read", "files", "full"}:
        raise HTTPException(status_code=403, detail="The paired computer has no usable permission.")
    try:
        command = computer_agent.enqueue(body.device_id, body.operation, body.arguments or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    money.audit("computer.command", by=user.get("username"), device_id=body.device_id,
                operation=body.operation)
    return {"ok": True, "command": command}


@router.get("/agent/commands")
def api_computer_poll(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    device = _require_computer_device(token)
    return {"commands": computer_agent.poll(device["id"], device.get("permission", "read"))}


@router.post("/agent/results/{command_id}")
def api_computer_result(command_id: str, body: dict,
                        token: str | None = Header(default=None, alias="X-Atulya-Token")):
    device = _require_computer_device(token)
    result = body.get("result")
    if not isinstance(result, dict):
        raise HTTPException(status_code=422, detail="Command result must be an object.")
    if not computer_agent.result(device["id"], command_id, result):
        raise HTTPException(status_code=404, detail="No outstanding command for this computer.")
    money.audit("computer.command.result", device_id=device["id"], command_id=command_id,
                ok=bool(result.get("ok")))
    return {"ok": True}


# ── dashboard ────────────────────────────────────────────────────────────
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
def api_dashboard(user: dict = Depends(_d._require_auth)):
    from atulya import actions as money
    from atulya import actions as pc_control
    from atulya import actions as tools
    from atulya import security as vault
    from atulya.actions import recent
    from atulya.brain import _SPEED, ProviderRouter
    from atulya.devices import get_hub

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
def api_toggle_pc(body: dict, user: dict = Depends(_d._require_auth)):
    """Switch PC control on or off (admin). It still asks before every action."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    on = bool(body.get("on"))
    _d.set_env_value("ATULYA_PC_CONTROL", "on" if on else "")
    return {"control": on}


@router.post("/api/dashboard/media")
async def api_media(body: dict, user: dict = Depends(_d._require_auth)):
    from atulya.actions import media_control

    action = str(body.get("action") or "")
    return {"message": await media_control(action)}


@router.post("/api/dashboard/home")
async def api_home(body: dict, user: dict = Depends(_d._require_auth)):
    """Turn a light or thermostat on/off from the dashboard. Locks are never touched here."""
    from atulya import actions as tools

    device = tools._HOME_DEVICES.get(str(body.get("device_id")))
    action = str(body.get("action") or "")
    if device is None or device.get("type") == "lock" or action not in ("on", "off"):
        raise HTTPException(status_code=400, detail="Only lights and thermostats can be switched here")
    return {"message": await tools.home_control(str(body["device_id"]), action)}


