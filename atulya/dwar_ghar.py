"""The memory tree: what Atulya remembers about the signed-in user, as a drawable graph."""
from __future__ import annotations

import html
import json
import logging
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse

from atulya import dhan as money
from atulya.dwar_khata import _key, _store
from atulya.khata import _jwt_encode, _require_admin, _require_auth
from atulya.parivesh import set_env_value
from atulya.smriti import build_memory_graph
from atulya.upakaran import DeviceError
from atulya.upakaran_hub import discover, get_hub

# ── notifications ────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)
router = APIRouter()

SUBS_FILE = Path(__file__).resolve().parents[1] / "kosh" / "push_subs.json"

@router.post("/api/notifications/subscribe")
def subscribe(body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    sub = body.get("subscription")
    if not sub:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Missing subscription")
    username = user.get("username", "unknown")
    SUBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    subs = {}
    if SUBS_FILE.exists():
        subs = json.loads(SUBS_FILE.read_text())
    if username not in subs:
        subs[username] = []
    subs[username].append(sub)
    SUBS_FILE.write_text(json.dumps(subs, indent=2))
    return {"ok": True}

@router.post("/api/notifications/unsubscribe")
def unsubscribe(body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    sub = body.get("subscription")
    username = user.get("username", "unknown")
    if not SUBS_FILE.exists():
        return {"ok": True}
    subs = json.loads(SUBS_FILE.read_text())
    if username in subs and sub in subs[username]:
        subs[username].remove(sub)
        SUBS_FILE.write_text(json.dumps(subs, indent=2))
    return {"ok": True}

@router.post("/api/notifications/test")
def test_notification(body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_auth(token)
    from atulya.khata import _require_admin
    _require_admin(token)
    title = body.get("title", "Test")
    message = body.get("message", "This is a test notification")
    from fastapi.responses import JSONResponse
    return JSONResponse({"ok": True, "sent": True, "title": title, "message": message})


# ── memory ────────────────────────────────────────────────────────────
def _vector_count() -> int:
    try:
        import json
        from pathlib import Path

        total = 0
        for f in Path("kosh/memory").glob("*.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            total += len(data) if isinstance(data, (list, dict)) else 0
        return total
    except Exception:  # noqa: BLE001 - a count only decorates the view
        return 0


@router.get("/api/memory/graph")
def api_memory_graph(request: Request, user: dict = Depends(_require_auth)):
    from atulya import khata as chat_history
    from atulya.bhasha import get_default_llm
    from atulya.bhava import MoodState
    from atulya.kriya import TOOL_REGISTRY
    from atulya.vahak import _SPEED

    llm = getattr(request.app.state, "llm", None) or get_default_llm()
    mood = getattr(llm, "mood", None) or MoodState.load()
    episodes = [m for m in chat_history.list_messages(user, 60) if m.get("role") == "user"][-24:][::-1]
    brains = [{"name": n, "seconds": round(v["avg"], 1)} for n, v in _SPEED.items() if v.get("avg")]
    return build_memory_graph(
        _store(request).view(_key(user)),
        episodes=episodes,
        skills=[(n, str(t.get("description", ""))) for n, t in TOOL_REGISTRY.items()],
        mood={"mood": mood.label, "energy": round(mood.energy, 2), "valence": round(mood.valence, 2)},
        brains=brains,
        vectors=_vector_count(),
    )


# ── mood ────────────────────────────────────────────────────────────
@router.get("/api/mood")
def api_mood(request: Request, user: dict = Depends(_require_auth)):
    from atulya.bhasha import get_default_llm
    from atulya.bhava import MoodState

    llm = getattr(request.app.state, "llm", None) or get_default_llm()
    mood = getattr(llm, "mood", None) or MoodState.load()
    return {"label": mood.label, "valence": round(mood.valence, 2), "energy": round(mood.energy, 2)}


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
def api_money_inbox(request: Request, user: dict = Depends(_require_auth)):
    """The secret and the address to give your phone's SMS-forwarding app."""
    return {"key": money.inbox_token(), "path": "/api/money/sms", "origin": str(request.base_url).rstrip("/")}


@router.post("/api/money/inbox/rotate")
def api_money_inbox_rotate(user: dict = Depends(_require_auth)):
    return {"key": money.inbox_token(rotate=True)}


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
def api_dashboard(user: dict = Depends(_require_auth)):
    from atulya import dhan as money
    from atulya import kriya as tools
    from atulya import raksha as vault
    from atulya import sahayak as pc_control
    from atulya.lekha import recent
    from atulya.upakaran_hub import get_hub
    from atulya.vahak import _SPEED, ProviderRouter

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
    from atulya.sahayak import media_control

    action = str(body.get("action") or "")
    return {"message": await media_control(action)}


@router.post("/api/dashboard/home")
async def api_home(body: dict, user: dict = Depends(_require_auth)):
    """Turn a light or thermostat on/off from the dashboard. Locks are never touched here."""
    from atulya import kriya as tools

    device = tools._HOME_DEVICES.get(str(body.get("device_id")))
    action = str(body.get("action") or "")
    if device is None or device.get("type") == "lock" or action not in ("on", "off"):
        raise HTTPException(status_code=400, detail="Only lights and thermostats can be switched here")
    return {"message": await tools.home_control(str(body["device_id"]), action)}


# ── fabric ────────────────────────────────────────────────────────────
@router.get("/api/fabric")
def api_fabric(user: dict = Depends(_require_auth)):
    return {"devices": get_hub().describe()}


@router.post("/api/fabric/discover")
async def api_fabric_discover(user: dict = Depends(_require_admin)):
    hub = get_hub()
    found = await discover(profiles=hub.profiles)
    have = {(d.driver, d.address, str(sorted(d.config.items()))) for d in hub.devices.values()}
    fresh = [c for c in found if (c.driver, c.host, str(sorted(c.config.items()))) not in have]
    hub.last_candidates = {c.id: c for c in fresh}
    hub.last_order = [c.id for c in fresh]
    return {"found": [c.to_dict() for c in fresh[:60]]}


@router.post("/api/fabric/add")
async def api_fabric_add(body: dict, user: dict = Depends(_require_admin)):
    try:
        dev = await get_hub().add_candidate(str(body.get("candidate", "")), str(body.get("name", "")), str(body.get("room", "")))
    except DeviceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": dev.id, "name": dev.name, "can": [c.name for c in dev.capabilities]}


@router.post("/api/fabric/{device_id}/do")
async def api_fabric_do(device_id: str, body: dict, user: dict = Depends(_require_auth)):
    hub = get_hub()
    action = str(body.get("action", ""))
    if hub.is_risky(device_id, action) and not body.get("confirmed"):
        raise HTTPException(status_code=409, detail="This needs your confirmation.")
    dev = hub.find(device_id)
    cap = dev.cap(action) if dev else None
    args = {}
    if cap and cap.params and str(body.get("value", "")).strip():
        args[next(iter(cap.params))] = body["value"]
    if body.get("times"):
        args["times"] = body["times"]
    try:
        return {"message": await hub.act(device_id, action, args)}
    except DeviceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/fabric/{device_id}")
def api_fabric_remove(device_id: str, user: dict = Depends(_require_admin)):
    try:
        return {"removed": get_hub().remove(device_id)}
    except DeviceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── senses ────────────────────────────────────────────────────────────
def _senses(request: Request):
    senses = getattr(request.app.state, "senses", None)
    if senses is None:  # app started without lifespan (e.g. tests)
        from atulya.ghatna import default_bus
        from atulya.indriya import Senses

        senses = Senses(default_bus)
        request.app.state.senses = senses
    return senses


@router.get("/api/senses")
def api_senses(request: Request, _admin: dict = Depends(_require_admin)):
    return _senses(request).status()


@router.post("/api/senses/cameras")
async def api_add_camera(request: Request, body: dict, _admin: dict = Depends(_require_admin)):
    try:
        camera = await _senses(request).add_camera(str(body.get("name") or ""), str(body.get("source") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "camera": camera}


@router.delete("/api/senses/cameras/{name}")
async def api_remove_camera(name: str, request: Request, _admin: dict = Depends(_require_admin)):
    if not await _senses(request).remove_camera(name):
        raise HTTPException(status_code=404, detail="Camera not found")
    return {"ok": True}


@router.get("/api/senses/cameras/{name}/snapshot")
def api_camera_snapshot(
    name: str,
    request: Request,
    token: str | None = Query(default=None),
    header_token: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    """The camera's latest 'someone is here' snapshot. Accepts ?token= so an <img> can load it."""
    _require_admin(header_token or token)
    watcher = _senses(request).cameras.get(name)
    path = getattr(watcher, "last_snapshot", "")
    if not path:
        raise HTTPException(status_code=404, detail="No snapshot yet")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/api/senses/heartbeat")
def api_listener_heartbeat(request: Request, body: dict, user: dict = Depends(_require_auth)):
    """An always-listening device checking in (see ``python -m atulya.shruti``)."""
    return {"ok": True, "listener": _senses(request).heartbeat(body, user=str(user.get("username") or ""))}


DEVICE_TOKEN_DAYS = 90


@router.post("/api/senses/device-token")
def api_device_token(body: dict, user: dict = Depends(_require_auth)):
    """A long-lived sign-in for an always-listening device (sessions expire daily).

    It acts as the signed-in user — same role, same confirmations.
    """
    device = str(body.get("device") or "listener")[:60]
    token = _jwt_encode({"sub": user.get("username"), "role": user.get("role", "user"),
                         "name": user.get("display_name", ""), "device": device},
                        expires_in=DEVICE_TOKEN_DAYS * 86400)
    return {"token": token, "device": device, "expires_in": DEVICE_TOKEN_DAYS * 86400}


# ── google ────────────────────────────────────────────────────────────
def redirect_uri(request: Request) -> str:
    """Where Google sends the user back. Set ATULYA_PUBLIC_URL behind a proxy."""
    base = os.environ.get("ATULYA_PUBLIC_URL", "").rstrip("/") or str(request.base_url).rstrip("/")
    return f"{base}/api/google/callback"


@router.get("/api/google/status")
def api_google_status(request: Request, user: dict = Depends(_require_auth)):
    from atulya.google import GoogleAccount, client_config

    cfg = client_config()
    return {
        "configured": bool(cfg["client_id"]),
        "client_source": cfg["source"],
        "redirect_uri": redirect_uri(request),
        "account": GoogleAccount(str(user.get("username") or "")).status(),
        "is_admin": user.get("role") == "admin",
    }


@router.post("/api/google/client")
def api_google_client(body: dict, _admin: dict = Depends(_require_admin)):
    """Save the OAuth client (from Google Cloud Console) — admin only, stored owner-only."""
    from atulya.google import GoogleError, save_client_config

    try:
        save_client_config(str(body.get("client_id") or ""), str(body.get("client_secret") or ""))
    except GoogleError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@router.post("/api/google/connect")
def api_google_connect(request: Request, user: dict = Depends(_require_auth)):
    from atulya.google import GoogleError, begin_sign_in

    try:
        url = begin_sign_in(str(user.get("username") or ""), redirect_uri(request))
    except GoogleError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"url": url}


def _page(title: str, message: str, ok: bool) -> HTMLResponse:
    colour = "#2eb85c" if ok else "#f05a44"
    target = "/?google=connected" if ok else "/?google=failed"
    body = (
        "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
        f"<meta http-equiv='refresh' content='3;url={target}'><title>{html.escape(title)}</title></head>"
        "<body style=\"background:#0a0d1f;color:#fbf6ee;font-family:system-ui;display:grid;place-items:center;"
        "min-height:100vh;margin:0\"><div style='text-align:center;padding:24px'>"
        f"<h1 style='color:{colour}'>{html.escape(title)}</h1><p>{html.escape(message)}</p>"
        f"<p><a style='color:#ff9933' href='{target}'>Back to Atulya</a></p></div></body></html>"
    )
    return HTMLResponse(body, status_code=200 if ok else 400)


@router.get("/api/google/callback")
async def api_google_callback(state: str = "", code: str = "", error: str = ""):
    """Google redirects here after the consent screen. The single-use state is the proof."""
    from atulya.google import GoogleError, finish_sign_in

    if error:
        return _page("Google sign-in cancelled", "Nothing was connected.", ok=False)
    try:
        _user, email = await finish_sign_in(state, code)
    except GoogleError as exc:
        return _page("Couldn't connect Google", str(exc), ok=False)
    return _page("Google connected", f"Atulya can now use Gmail and Calendar for {email or 'your account'}.", ok=True)


@router.post("/api/google/disconnect")
async def api_google_disconnect(user: dict = Depends(_require_auth)):
    from atulya.google import GoogleAccount

    return {"ok": await GoogleAccount(str(user.get("username") or "")).disconnect()}

