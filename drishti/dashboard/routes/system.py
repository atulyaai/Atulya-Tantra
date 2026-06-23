from __future__ import annotations

import platform
import time

import psutil
from fastapi import APIRouter, Header

from tantra.npdna.config import CONFIGS, PREFERRED_CONFIG_NAMES
from drishti.dashboard.helpers import (
    _checkpoint_index,
    _dataset_registry,
    _model_registry,
    _require_admin,
    _require_auth,
    _run_history,
    _read_status_file,
)
from drishti.dashboard.state import ADMIN_TOKEN_SOURCE, OUTPUTS_DIR

router = APIRouter()
START_TIME = time.time()


def _config_summary(name: str) -> dict:
    cfg = CONFIGS[name]
    layers = [
        {"name": spec.name, "num_strands": spec.num_strands, "top_k": spec.top_k}
        for spec in cfg.mesh_specs
    ] or [
        {"name": f"layer_{i + 1}", "num_strands": cfg.mesh.num_strands, "top_k": cfg.mesh.top_k}
        for i in range(cfg.num_layers)
    ]
    return {
        "name": name,
        "hidden_size": cfg.hidden_size,
        "state_size": cfg.state_size,
        "num_layers": cfg.num_layers,
        "total_strands": cfg.total_strands,
        "vocab_capacity": cfg.initial_vocab,
        "recommended": name == "atulya_small",
        "layers": layers,
    }


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
        from atulya.intelligence import ProviderRouter

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
    status = _read_status_file()
    phase = status.get("phase") or status.get("status") or "idle"
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
        {
            "title": "Training Monitor",
            "desc": f"Training phase: {phase}.",
            "type": "process" if phase in {"running", "training"} else "ready",
        },
    ]
    if status.get("last") or status.get("last_metric"):
        last = status.get("last") or status.get("last_metric") or {}
        loss = last.get("loss") or last.get("train_loss")
        step = last.get("step") or last.get("run_step")
        if loss is not None or step is not None:
            events.append({
                "title": "Latest Training Metric",
                "desc": f"Step {step or '--'}, loss {loss or '--'}.",
                "type": "process",
            })
    return events


@router.get("/api/system")
def api_system(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    return _system_payload()


@router.get("/api/telemetry")
def api_telemetry(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_auth(token)
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


@router.get("/api/configs")
def api_configs(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    return {"configs": [_config_summary(name) for name in PREFERRED_CONFIG_NAMES if name in CONFIGS]}


@router.get("/api/run-history")
def api_run_history(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    return {"runs": _run_history()}


@router.get("/api/datasets")
def api_datasets(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    return {"datasets": _dataset_registry()}


@router.get("/api/health")
def api_health(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_auth(token)
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

    # Check checkpoints for corruption
    checkpoints = _checkpoint_index()
    stale_count = 0
    for cid, cpath in checkpoints.items():
        if cid == "latest":
            continue
        meta = _read_metadata(cpath)
        if not meta or not meta.get("version_stage"):
            stale_count += 1
    if stale_count > 3:
        warnings.append({"severity": "medium", "message": f"{stale_count} checkpoints may be incomplete"})

    # Check dataset health
    datasets = _dataset_registry()
    empty_datasets = [d["name"] for d in datasets if d.get("rows") is None or d.get("rows", 0) == 0]
    if empty_datasets:
        warnings.append({"severity": "low", "message": f"Empty datasets: {', '.join(empty_datasets[:3])}"})

    return {"ok": True, "warnings": warnings, "healthy": len(warnings) == 0}


@router.get("/api/dashboard/bootstrap")
def api_dashboard_bootstrap(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    models = _model_registry()
    checkpoints = models
    checkpoint_ids = list(_checkpoint_index().keys())
    
    # If the user is admin, return everything. Otherwise return only basic model data.
    if user.get("role") == "admin":
        return {
            "user": user,
            "system": _system_payload(),
            "configs": {"configs": [_config_summary(name) for name in PREFERRED_CONFIG_NAMES if name in CONFIGS]},
            "history": {"runs": _run_history()},
            "models": models,
            "checkpoints": checkpoints,
            "providers": _provider_registry(),
            "datasets": _dataset_registry(),
            "checkpoint_ids": checkpoint_ids,
        }
    else:
        return {
            "user": user,
            "checkpoints": checkpoints,
            "providers": _provider_registry(),
            "checkpoint_ids": checkpoint_ids,
        }
