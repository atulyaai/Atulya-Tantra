from __future__ import annotations

import platform
import time

import psutil
from fastapi import APIRouter, Header

from atulya.sevak.helpers import _require_admin, _require_auth
from atulya.sevak.state import ADMIN_TOKEN_SOURCE, OUTPUTS_DIR

router = APIRouter()
START_TIME = time.time()


def _system_payload() -> dict:
    mem = psutil.virtual_memory()
    disk_root = OUTPUTS_DIR.parent
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
        "token_source": ADMIN_TOKEN_SOURCE,
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
        from atulya.buddhi.intelligence import ProviderRouter

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
    _require_admin(_admin)
    return _system_payload()


@router.get("/api/telemetry")
def api_telemetry(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(token)
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
    _require_admin(token)
    from atulya.buddhi.brain import describe

    return describe()


@router.get("/api/audit")
def api_audit(limit: int = 50, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    """The most recent things Atulya did on your behalf (admin only)."""
    _require_admin(token)
    from atulya.yantra.audit import recent

    return {"events": recent(max(1, min(limit, 500)))}


@router.get("/api/health")
def api_health(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(token)
    warnings = []

    # Check disk space
    mem = psutil.virtual_memory()
    disk_root = OUTPUTS_DIR.parent
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
    user = _require_auth(token)
    payload = {"user": user, "providers": []}
    if user.get("role") == "admin":  # which models and keys are set up is admin business
        payload["providers"] = _provider_registry()
        payload["system"] = _system_payload()
    return payload
