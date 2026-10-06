"""Dwar (द्वार, gate): the server's API: accounts and sessions, chat history, sign-in, brains and keys, chat and voice, home and dashboard, automation."""
from __future__ import annotations

import asyncio
import os
import platform
import time

import psutil
from fastapi import (
    Depends,
    Header,
    HTTPException,
    Request,
)

from atulya import raksha as vault
from atulya.mastishk import BY_ID, CATALOG

from . import router
from atulya import dwar as _d

# ── system ────────────────────────────────────────────────────────────
START_TIME = time.time()


def _system_payload() -> dict:
    mem = psutil.virtual_memory()
    disk_root = _d.OUTPUTS_DIR.parent
    disk_root.mkdir(parents=True, exist_ok=True)
    disk = psutil.disk_usage(str(disk_root))
    return {
        "cpu_pct": psutil.cpu_percent(interval=0.0),
        "cpu_count": psutil.cpu_count(logical=True),
        "ram_pct": mem.percent,
        "ram_total_gb": round(mem.total / (1024 ** 3), 2),
        "ram_avail_gb": round(mem.available / (1024 ** 3), 2),
        "disk_free_gb": round(disk.free / (1024 ** 3), 2),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "token_source": _d.ADMIN_TOKEN_SOURCE,
    }


def _format_uptime(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _provider_registry() -> list[dict]:
    try:
        from atulya.mastishk import ProviderRouter

        providers = []
        for provider in ProviderRouter().providers:
            name = provider.name()
            provider_id = name.split(" ", 1)[0].lower()
            providers.append({
                "id": provider_id,
                "name": name,
                "available": bool(provider.is_available()),
            })
        return [{"id": "auto", "name": "Auto Provider", "available": True}] + providers
    except Exception:
        return [{"id": "auto", "name": "Auto Provider", "available": True}]


def _telemetry_events(system: dict, providers: list[dict]) -> list[dict]:
    ready_providers = [item["name"] for item in providers if item.get("available") and item.get("id") != "auto"]
    events = [
        {
            "title": "System Telemetry",
            "desc": f"CPU {system['cpu_pct']}%, RAM {system['ram_pct']}%, disk free {system['disk_free_gb']} GB.",
            "type": "ready" if system["cpu_pct"] < 85 and system["ram_pct"] < 90 else "warning",
        },
        {
            "title": "Provider Router",
            "desc": f"{len(ready_providers)} provider(s) available: {', '.join(ready_providers[:4]) or 'local/offline fallback only'}.",
            "type": "ready" if ready_providers else "standby",
        },
    ]
    return events


@router.get("/api/system")
def api_system(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _d._require_admin(_admin)
    return _system_payload()


@router.get("/api/telemetry")
def api_telemetry(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    _d._require_admin(token)
    system = _system_payload()
    providers = _provider_registry()
    return {
        "system": {
            **system,
            "uptime_seconds": int(time.time() - START_TIME),
            "uptime": _format_uptime(time.time() - START_TIME),
        },
        "providers": providers,
        "events": _telemetry_events(system, providers),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


@router.get("/api/brain")
def api_brain(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    """Active brain tier (ATULYA_BRAIN), its local model, and the available tiers (admin only)."""
    _d._require_admin(token)
    from atulya.mastishk import describe

    return describe()


@router.get("/api/audit/verify")
def api_audit_verify(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    """Is the activity log intact? Any edited, removed or reordered line breaks the chain (admin only)."""
    _d._require_admin(token)
    from atulya.kriya import verify_audit

    return verify_audit()


@router.get("/api/audit")
def api_audit(limit: int = 50, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    """The most recent things Atulya did on your behalf (admin only)."""
    _d._require_admin(token)
    from atulya.kriya import recent

    return {"events": recent(max(1, min(limit, 500)))}


@router.get("/api/health")
def api_health(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    _d._require_admin(token)
    warnings = []

    # Check disk space
    mem = psutil.virtual_memory()
    disk_root = _d.OUTPUTS_DIR.parent
    try:
        disk = psutil.disk_usage(str(disk_root))
        if disk.free / (1024**3) < 5:
            warnings.append({"severity": "high", "message": f"Low disk space: {disk.free / (1024**3):.1f} GB free"})
        elif disk.free / (1024**3) < 20:
            warnings.append({"severity": "medium", "message": f"Disk space getting low: {disk.free / (1024**3):.1f} GB free"})
    except Exception:
        pass

    # Check RAM
    if mem.percent > 90:
        warnings.append({"severity": "high", "message": f"Critical RAM usage: {mem.percent}%"})
    elif mem.percent > 80:
        warnings.append({"severity": "medium", "message": f"High RAM usage: {mem.percent}%"})

    return {"ok": True, "warnings": warnings, "healthy": len(warnings) == 0}


@router.get("/api/dashboard/bootstrap")
def api_dashboard_bootstrap(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _d._require_auth(token)
    payload = {"user": user, "providers": []}
    if user.get("role") == "admin":  # which models and keys are set up is admin business
        payload["providers"] = _provider_registry()
        payload["system"] = _system_payload()
    return payload


# ── profile ────────────────────────────────────────────────────────────
def _store(request: Request):
    from atulya.buddhi import get_kernel
    from atulya.mastishk import get_default_llm

    return get_kernel(getattr(request.app.state, "llm", None) or get_default_llm()).profiles


def _key(user: dict) -> str:
    return str(user.get("profile_user") or user.get("username") or "default")


@router.get("/api/profile")
def api_profile(request: Request, user: dict = Depends(_d._require_auth)):
    profile = _store(request).view(_key(user))
    profile["display_name"] = (user.get("profile_display_name") or user.get("display_name") or "")
    return profile


@router.post("/api/profile/facts")
def api_add_fact(request: Request, body: dict, user: dict = Depends(_d._require_auth)):
    """Teach Atulya something: {"text": "my wife's name is Priya"}."""
    from atulya.buddhi import describe_fact, extract_facts

    text = str(body.get("text") or "").strip()
    facts = extract_facts(text)
    if not facts and text:  # anything else is kept as a plain note, in the user's own words
        facts = [{"kind": "note", "key": "note", "value": text[:200]}]
    if not facts:
        raise HTTPException(status_code=400, detail="Tell me something about you")
    stored = _store(request).remember(_key(user), facts)
    return {"ok": True, "facts": [{**f, "text": describe_fact(f)} for f in stored]}


@router.delete("/api/profile/facts/{fact_id}")
def api_forget_fact(fact_id: str, request: Request, user: dict = Depends(_d._require_auth)):
    if not _store(request).forget(_key(user), fact_id=fact_id):
        raise HTTPException(status_code=404, detail="Fact not found")
    return {"ok": True}


@router.post("/api/profile/trust")
def api_trust(request: Request, body: dict, user: dict = Depends(_d._require_auth)):
    """Stop asking (trusted=true) or start asking again (false) before an action."""
    store = _store(request)
    key = str(body.get("key") or "")
    if bool(body.get("trusted")):
        known = {a["key"] for a in store.view(_key(user))["approvals"]}
        if key not in known or not store.trust(_key(user), key):
            raise HTTPException(status_code=400, detail="Atulya can only stop asking about actions you've approved")
    else:
        store.untrust(_key(user), key or None)
    return {"ok": True, "trusted": store.view(_key(user))["trusted"]}


@router.delete("/api/profile")
def api_forget_everything(request: Request, user: dict = Depends(_d._require_auth)):
    _store(request).forget_everything(_key(user))
    return {"ok": True}


# ── providers ────────────────────────────────────────────────────────────
def _mask(value: str) -> str:
    return ("…" + value[-4:]) if len(value) >= 8 else ("set" if value else "")


def _row(spec) -> dict:
    key = os.environ.get(spec.key_var, "")
    row = {"id": spec.id, "label": spec.label, "free": spec.free, "docs": spec.docs, "configured": bool(key),
           "key_hint": _mask(key), "model": os.environ.get(spec.model_var, "") or spec.default_model,
           "default_model": spec.default_model, "needs_url": spec.id == "custom"}
    if spec.id == "custom":
        row["url"] = os.environ.get("ATULYA_CUSTOM_URL", "")
        row["configured"] = bool(row["url"])
    return row


def _provider(spec):
    from atulya.mastishk import OpenAICompatProvider, ProviderRouter

    if not spec.builtin:
        return OpenAICompatProvider(spec)
    wanted = {"anthropic": "Claude", "openai": "OpenAI", "gemini": "Gemini", "groq": "Groq", "nvidia": "NVIDIA",
              "openrouter": "OpenRouter", "opencode": "OpenCode Go"}[spec.id]
    for p in ProviderRouter().providers:
        if wanted.lower() in p.name().lower():
            return p
    raise HTTPException(status_code=404, detail="Provider not found")


@router.get("/api/providers")
def api_providers(user: dict = Depends(_d._require_admin)):
    from atulya.mastishk import speed_report

    rows = [_row(s) for s in CATALOG]
    return {"providers": rows, **speed_report(linked_cloud=sum(1 for r in rows if r["configured"] and r["id"] != "custom"))}


@router.post("/api/providers/{provider_id}")
def api_set_provider(provider_id: str, body: dict, user: dict = Depends(_d._require_admin)):
    """{"key": "...", "model": "...", "url": "..."}: any field left out is unchanged; "" removes it."""
    spec = BY_ID.get(provider_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Unknown provider")
    try:
        if "key" in body:
            _d.set_env_value(spec.key_var, str(body["key"]).strip())
        if "model" in body:
            _d.set_env_value(spec.model_var, str(body["model"]).strip())
        if spec.id == "custom" and "url" in body:
            _d.set_env_value("ATULYA_CUSTOM_URL", str(body["url"]).strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not write .env: {exc}") from exc
    return _row(spec)


@router.post("/api/providers/{provider_id}/test")
async def api_test_provider(provider_id: str, user: dict = Depends(_d._require_admin)):
    spec = BY_ID.get(provider_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Unknown provider")
    provider = _provider(spec)
    if not provider.is_available():
        return {"ok": False, "error": "No key is set yet."}
    started = time.monotonic()
    try:
        text = await asyncio.wait_for(provider.chat("Reply with the single word: ready", "You are a connection test."), 40)
    except Exception as exc:  # noqa: BLE001 - show the provider's own message
        return {"ok": False, "error": str(exc)[:300]}
    return {"ok": True, "seconds": round(time.monotonic() - started, 1), "reply": str(text)[:80]}


# ── vault ────────────────────────────────────────────────────────────
@router.get("/api/vault")
def api_vault_status(user: dict = Depends(_d._require_admin)):
    return vault.status()


@router.post("/api/vault/encrypt-now")
def api_vault_encrypt(user: dict = Depends(_d._require_admin)):
    try:
        return {"converted": vault.encrypt_tree(), **vault.status()}
    except vault.VaultLocked as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


