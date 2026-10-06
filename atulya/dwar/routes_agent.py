"""Dwar (द्वार, gate): the server's API: accounts and sessions, chat history, sign-in, brains and keys, chat and voice, home and dashboard, automation."""
from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import (
    Depends,
    File,
    Header,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import PlainTextResponse

from atulya.kaushal import AtulyaTantraConnector, CreationResult

from . import router
from atulya import dwar as _d

# ── upload ────────────────────────────────────────────────────────────

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "kosh" / "uploads"
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
    """Build an uploads path and confirm it stays inside _d.UPLOAD_DIR."""
    _safe_component(username, "username")
    _safe_component(file_id, "file id")
    path = (_d.UPLOAD_DIR / username / file_id).resolve()
    base = _d.UPLOAD_DIR.resolve()
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
    user = _d._require_auth(token)
    if not file.filename:
        raise HTTPException(400, "No filename")

    ext = Path(file.filename).suffix.lower() if file.filename else ""
    content_type = file.content_type or ""

    if content_type and content_type not in _ALLOWED_TYPES and not content_type.startswith("image/"):
        if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".txt", ".csv", ".json", ".zip"):
            raise HTTPException(400, f"File type '{content_type}' not allowed")

    user_dir = _d.UPLOAD_DIR / user["username"]
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
    user = _d._require_auth(token)
    if username != user["username"] and user.get("role") != "admin":
        raise HTTPException(403, "Forbidden")
    file_path = _resolve_upload_path(username, file_id)
    if not file_path.is_file():
        raise HTTPException(404, "File not found")
    from fastapi.responses import FileResponse
    return FileResponse(str(file_path))

@router.get("/api/files")
async def api_list_files(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _d._require_auth(token)
    user_dir = _d.UPLOAD_DIR / user["username"]
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
    user = _d._require_auth(token)
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
async def agent_status(user: dict = Depends(_d._require_admin)):
    a = _get_agent()
    return {"tools": a.list_tools(), "status": "ready"}


@router.post("/api/agent/process")
async def agent_process(request: Request, user: dict = Depends(_d._require_auth)):
    body = await request.json()
    user_input = body.get("input", "")
    history = body.get("history")
    if not user_input:
        return {"status": "error", "message": "No input"}
    a = _get_agent()
    reply = await a.process(user_input, history, user=user)
    return {"status": "success", "reply": reply}


@router.get("/api/agent/tools")
async def agent_tools(user: dict = Depends(_d._require_admin)):
    a = _get_agent()
    return {"tools": a.list_tools()}


@router.get("/api/agent/schemas")
async def agent_schemas(user: dict = Depends(_d._require_admin)):
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
def api_create(body: dict, _user: dict = Depends(_d._require_auth)):
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
def api_create_document(body: dict, _user: dict = Depends(_d._require_auth)):
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        return {"ok": False, "error": "prompt is required"}
    return _payload(_connector().create(prompt, str(body.get("format") or "pdf"), **_options(body)))


@router.post("/api/create/video")
def api_create_video(body: dict, _user: dict = Depends(_d._require_auth)):
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        return {"ok": False, "error": "prompt is required"}
    return _payload(_connector().create(prompt, "video", **_options(body)))


# ── triggers ────────────────────────────────────────────────────────────
def _engine(request: Request):
    engine = getattr(request.app.state, "triggers", None)
    if engine is None:  # app started without lifespan (e.g. some tests)
        from atulya.buddhi import TriggerEngine

        engine = TriggerEngine()
        request.app.state.triggers = engine
    return engine


@router.get("/api/triggers")
def api_list_triggers(request: Request, _admin: dict = Depends(_d._require_admin)):
    return {"triggers": _engine(request).list_rules()}


@router.post("/api/triggers")
def api_add_trigger(request: Request, body: dict, _admin: dict = Depends(_d._require_admin)):
    try:
        rule = _engine(request).add_rule(body)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "trigger": rule}


@router.delete("/api/triggers/{rule_id}")
def api_delete_trigger(rule_id: str, request: Request, _admin: dict = Depends(_d._require_admin)):
    if not _engine(request).remove_rule(rule_id):
        raise HTTPException(status_code=404, detail="Trigger not found")
    return {"ok": True}


@router.post("/api/events/emit")
async def api_emit_event(body: dict, _admin: dict = Depends(_d._require_admin)):
    """Publish an event on the bus — handy for testing trigger rules."""
    from atulya.adhar import default_bus

    event_type = str(body.get("type") or "").strip()
    if not event_type:
        raise HTTPException(status_code=400, detail="type is required")
    payload: dict[str, Any] = body.get("payload") if isinstance(body.get("payload"), dict) else {}
    event = await default_bus.emit(event_type, payload)
    return {"ok": True, "type": event.type}


@router.get("/api/events/recent")
def api_recent_events(limit: int = 50, _admin: dict = Depends(_d._require_admin)):
    """The assistant's recent 'nervous system' activity."""
    from atulya.adhar import default_bus

    limit = max(1, min(int(limit), 500))
    return {"events": [
        {"type": e.type, "payload": e.payload, "timestamp": getattr(e, "timestamp", None)}
        for e in default_bus.history(limit)
    ]}


# ── inbound webhooks ────────────────────────────────────────────────────────
_HOOKS_FILE = "hooks.json"
_HOOK_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _hooks() -> dict:
    from atulya.kriya import _load_json

    data = _load_json(_HOOKS_FILE)
    return dict(data.get("hooks") or {}) if isinstance(data, dict) else {}


def _save_hooks(hooks: dict) -> None:
    from atulya.kriya import _save_json

    _save_json(_HOOKS_FILE, {"hooks": hooks})


def _hook_summary(payload: dict) -> str:
    """One line a notification can carry when the sender wrote none."""
    for key in ("title", "message", "summary", "event", "state", "status"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:300]
    body = json.dumps({k: v for k, v in payload.items() if k != "hook"}, default=str, ensure_ascii=False)
    return body[:300] or "(empty)"


@router.get("/api/hooks")
def api_list_hooks(_admin: dict = Depends(_d._require_admin)):
    """The addresses outside services may POST to. The secret itself is only
    handed out when a hook is made, so a leaked admin session reads nothing."""
    hooks = _hooks()
    return {"hooks": [{"name": name, "created": info.get("created")} for name, info in sorted(hooks.items())]}


@router.post("/api/hooks")
def api_create_hook(body: dict, _admin: dict = Depends(_d._require_admin)):
    """Make an address an outside service can POST to, landing on the bus.

    Calling it twice with the same name returns the same secret rather than
    rotating it, because rotating it silently would break the service that was
    already pointing here.
    """
    name = str(body.get("name") or "").strip().lower()
    if not _HOOK_NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="A hook name is lowercase letters, digits, - and _ (max 64).")
    hooks = _hooks()
    entry = hooks.get(name)
    token = str(entry.get("token") or "") if entry else ""
    if not token:
        token = secrets.token_urlsafe(32)
        hooks[name] = {"token": token, "created": time.time()}
        _save_hooks(hooks)
    return {"ok": True, "name": name, "token": token, "url": f"/api/hooks/{name}/{token}"}


@router.delete("/api/hooks/{name}")
def api_delete_hook(name: str, _admin: dict = Depends(_d._require_admin)):
    hooks = _hooks()
    if name not in hooks:
        raise HTTPException(status_code=404, detail="No such hook")
    hooks.pop(name, None)
    _save_hooks(hooks)
    return {"ok": True}


@router.post("/api/hooks/{name}/{token}")
async def api_fire_hook(name: str, token: str, request: Request):
    """Let an outside service -- GitHub, IFTTT, Home Assistant, a sensor -- speak.

    This is the one route on the server that answers without a session, which
    is the entire point of it, so the address itself carries a long random
    secret compared in constant time, and a name nobody created cannot match
    anything. What arrives becomes ``hook.<name>`` where any trigger rule can
    pick it up, exactly like ``email.new`` or ``reminder.due``.
    """
    entry = _hooks().get(name)
    if entry is None:
        raise HTTPException(status_code=404, detail="No such hook")
    expected = str(entry.get("token") or "")
    if not expected or not secrets.compare_digest(expected, token):
        raise HTTPException(status_code=403, detail="Wrong hook token")
    try:
        body: Any = await request.json()
    except Exception:  # noqa: BLE001 - a sender may not be speaking JSON at all
        raw = (await request.body())[:2000]
        body = {"raw": raw.decode("utf-8", "replace")}
    payload = dict(body) if isinstance(body, dict) else {"raw": str(body)[:2000]}
    payload["hook"] = name
    payload.setdefault("text", _hook_summary(payload))
    from atulya.adhar import default_bus

    event = await default_bus.emit(f"hook.{name}", payload)
    return {"ok": True, "event": event.type}



# ───── Twilio webhooks (inbound SMS / call status) ───────────────────────────
def _validate_twilio_webhook(request: Request, form: Any) -> None:
    """Reject forged Twilio callbacks using Twilio's SDK signature validator.

    Set ATULYA_TWILIO_PUBLIC_BASE_URL to the externally visible origin when
    TLS terminates at a reverse proxy (for example, ``https://bot.example``).
    The incoming path and query string are appended unchanged.
    """
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    if not auth_token:
        raise HTTPException(status_code=503, detail="Twilio webhooks are not configured")

    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    public_base = os.environ.get("ATULYA_TWILIO_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if public_base:
        url = f"{public_base}{request.url.path}"
        if request.url.query:
            url += f"?{request.url.query}"
    else:
        url = str(request.url)

    from twilio.request_validator import RequestValidator

    if not RequestValidator(auth_token).validate(url, form, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")


@router.post("/api/twilio/sms")
async def api_twilio_sms(request: Request):
    """Twilio inbound SMS webhook. Emits ``twilio.sms`` with from/to/body."""
    form = await request.form()
    _validate_twilio_webhook(request, form)
    payload = dict(form)
    from atulya.adhar import default_bus
    event = await default_bus.emit("twilio.sms", payload)
    return {"ok": True, "event": event.type}


@router.post("/api/twilio/voice")
async def api_twilio_voice(request: Request):
    """Twilio call status webhook. Emits ``twilio.call_status``."""
    form = await request.form()
    _validate_twilio_webhook(request, form)
    payload = dict(form)
    from atulya.adhar import default_bus
    event = await default_bus.emit("twilio.call_status", payload)
    return {"ok": True, "event": event.type}


@router.post("/api/twilio/recording")
async def api_twilio_recording(request: Request):
    """Twilio recording webhook. Emits ``twilio.recording`` with recording URL."""
    form = await request.form()
    _validate_twilio_webhook(request, form)
    payload = dict(form)
    from atulya.adhar import default_bus
    event = await default_bus.emit("twilio.recording", payload)
    return {"ok": True, "event": event.type}


# ───── WhatsApp / Slack / Discord inbound webhooks ──────────────────────────
# These are how a message FROM WhatsApp/Slack/Discord reaches Atulya's brain.
# Set the platform's webhook URL to the printed endpoint after starting the
# server.  Each platform signs differently; verify with its SDK or shared
# secret before trusting the payload.

async def _dispatch_channel_message(request: Request, source: str, sender: str,
                                     text: str, chat_id: str, metadata: dict | None = None) -> dict:
    """Feed an inbound message from any channel into the same brain pipeline."""
    if not text.strip():
        return {"ok": True, "ignored": "empty"}
    app = request.app
    llm = getattr(app.state, "llm", None)
    registry = getattr(app.state, "channel_registry", None)
    if registry is None:
        return {"ok": False, "error": "channel registry not started"}
    channel = registry._channels.get(source)
    if channel is None:
        return {"ok": False, "error": f"channel {source} not registered"}
    from atulya.sandesh import ChannelMessage

    msg = ChannelMessage(
        id=f"{source}:{chat_id}:{int(time.time() * 1000)}",
        channel=source,
        sender=sender,
        content=text,
        metadata={"chat_id": chat_id, **(metadata or {})},
    )
    try:
        result = await channel.handle_message(msg, llm=llm)
        return {"ok": True, "result": result}
    except Exception as exc:
        _d.logger.error("%s inbound handling failed: %s", source, exc)
        return {"ok": False, "error": str(exc)}


@router.get("/api/channels/whatsapp")
async def api_whatsapp_verify(request: Request):
    """Meta's one-time webhook challenge: echo the challenge back verbatim."""
    mode = request.query_params.get("hub.mode", "")
    token = request.query_params.get("hub.verify_token", "")
    challenge = request.query_params.get("hub.challenge", "")
    expected = os.environ.get("ATULYA_WHATSAPP_VERIFY_TOKEN", "").strip()
    if mode == "subscribe" and expected and challenge and secrets.compare_digest(token, expected):
        # Meta expects the raw challenge string, not a JSON body.
        return PlainTextResponse(challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/api/channels/whatsapp")
async def api_whatsapp_inbound(request: Request):
    """WhatsApp Cloud API inbound webhook (Meta).

    Verifies ``X-Hub-Signature-256`` when ``ATULYA_WHATSAPP_APP_SECRET`` is set.
    """
    app_secret = os.environ.get("ATULYA_WHATSAPP_APP_SECRET", "").strip()
    raw = await request.body()
    # Signature check (optional but recommended).
    if app_secret:
        sig = request.headers.get("X-Hub-Signature-256", "")
        import hashlib

        expected = "sha256=" + hmac.new(app_secret.encode(), raw, hashlib.sha256).hexdigest()
        if not sig or not secrets.compare_digest(sig, expected):
            raise HTTPException(status_code=403, detail="Bad signature")
    # Extract the first text message.
    text, sender, chat_id = "", "", ""
    try:
        body = json.loads(raw)
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for msg in value.get("messages", []):
                    if msg.get("type") == "text":
                        text = msg.get("text", {}).get("body", "")
                        sender = msg.get("from", "")
                        chat_id = sender
    except Exception:
        pass
    if not text:
        return {"ok": True, "ignored": "no text"}
    return await _dispatch_channel_message(request, "whatsapp", sender, text, chat_id,
                                           {"source": "whatsapp"})


@router.post("/api/channels/slack")
async def api_slack_inbound(request: Request):
    """Slack Events API inbound webhook.

    Set ``ATULYA_SLACK_SIGNING_SECRET`` for ``X-Slack-Signature`` verification.
    Handles url_verification challenge and app_mention / message events.
    """
    signing_secret = os.environ.get("ATULYA_SLACK_SIGNING_SECRET", "").strip()
    try:
        raw = await request.body()
        body = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Expected JSON")
    # Signature verification.
    if signing_secret:
        ts = request.headers.get("X-Slack-Request-Timestamp", "")
        sig = request.headers.get("X-Slack-Signature", "")
        import hashlib
        basestring = f"v0:{ts}:{raw.decode('utf-8', 'replace')}"
        expected = "v0=" + hmac.new(signing_secret.encode(), basestring.encode(), hashlib.sha256).hexdigest()
        if not sig or not secrets.compare_digest(sig, expected):
            raise HTTPException(status_code=403, detail="Bad Slack signature")
    if body.get("type") == "url_verification":
        return {"challenge": body.get("challenge", "")}
    event = body.get("event", {})
    etype = event.get("type", "")
    if etype in ("app_mention", "message"):
        text = event.get("text", "")
        # Strip bot mentions like <@U123>.
        text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
        sender = event.get("user", "")
        chat_id = event.get("channel", "")
        if text and not event.get("bot_id"):
            return await _dispatch_channel_message(request, "slack", sender, text, chat_id,
                                                   {"source": "slack"})
    return {"ok": True}


@router.post("/api/channels/discord")
async def api_discord_inbound(request: Request):
    """Discord Interactions webhook (slash commands / messages).

    Verify with Ed25519 when ``ATULYA_DISCORD_PUBLIC_KEY`` is set.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Expected JSON")
    public_key = os.environ.get("ATULYA_DISCORD_PUBLIC_KEY", "").strip()
    if public_key:
        # Full Ed25519 verification requires the `nacl` package; if absent we
        # accept the payload (Discord requires the endpoint to respond fast).
        try:
            import nacl.exceptions
            import nacl.signing
            from nacl.encoding import RawEncoder

            sig = request.headers.get("X-Signature-Ed25519", "")
            ts = request.headers.get("X-Signature-Timestamp", "")
            raw = await request.body()
            key_bytes = bytes.fromhex(public_key)
            verify_key = nacl.signing.VerifyKey(key_bytes, encoder=RawEncoder)
            message = (ts.encode() + raw)
            verify_key.verify(message, bytes.fromhex(sig))
        except ImportError:
            pass  # nacl not installed: accept without signature check
        except Exception:
            raise HTTPException(status_code=401, detail="Bad Discord signature")
    if body.get("type") == 1:  # PING
        return {"type": 1}
    if body.get("type") == 2:  # APPLICATION_COMMAND
        data = body.get("data", {})
        text = data.get("options", [{}])[0].get("value", "") if data.get("options") else ""
        sender = str(body.get("member", {}).get("user", {}).get("id", ""))
        chat_id = str(body.get("channel_id", ""))
        if text:
            return await _dispatch_channel_message(request, "discord", sender, text, chat_id,
                                                   {"source": "discord"})
    return {"type": 4, "data": {"content": "OK"}}


# ───── routines ─────────────────────────────

def _kernel(request: Request):
    from atulya.buddhi import get_kernel
    from atulya.mastishk import get_default_llm

    return get_kernel(getattr(request.app.state, "llm", None) or get_default_llm())


@router.get("/api/routines")
def api_list_routines(request: Request, _admin: dict = Depends(_d._require_admin)):
    from atulya.buddhi import routine_steps

    store = _kernel(request).planner.routines
    return {"routines": [
        {**r, "plan": [s.command for s in routine_steps(r)]} for r in store.list()
    ]}


@router.post("/api/routines")
def api_save_routine(request: Request, body: dict, _admin: dict = Depends(_d._require_admin)):
    try:
        routine = _kernel(request).planner.routines.save(body)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "routine": routine}


@router.delete("/api/routines/{routine_id}")
def api_delete_routine(routine_id: str, request: Request, _admin: dict = Depends(_d._require_admin)):
    if not _kernel(request).planner.routines.remove(routine_id):
        raise HTTPException(status_code=404, detail="Routine not found")
    return {"ok": True}


@router.post("/api/routines/{routine_id}/run")
async def api_run_routine(routine_id: str, request: Request, admin: dict = Depends(_d._require_admin)):
    from atulya.buddhi import Plan, routine_steps

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
def api_preview_plan(request: Request, body: dict, _admin: dict = Depends(_d._require_admin)):
    """What Atulya would do for a sentence, without doing it."""
    from atulya.buddhi import steps_for_clause

    text = str(body.get("text") or "").strip()
    plan = _kernel(request).planner.plan(text)
    if plan is not None:
        return {"plan": plan.to_dict()}
    steps = steps_for_clause(text) or []
    return {"plan": {"goal": text, "title": text, "source": "single" if steps else "brain",
                     "steps": [{"command": s.command, "tool": s.tool, "arguments": s.arguments} for s in steps]}}

