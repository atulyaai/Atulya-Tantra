from __future__ import annotations

import platform

import psutil
from fastapi import APIRouter, Header

from tantra.npdna.config import CONFIGS, PREFERRED_CONFIG_NAMES
from webui.backend.dashboard.helpers import (
    _checkpoint_index,
    _dataset_registry,
    _model_registry,
    _require_admin,
    _run_history,
)
from webui.backend.dashboard.state import ADMIN_TOKEN_SOURCE, OUTPUTS_DIR

router = APIRouter()


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
    disk = psutil.disk_usage(str(OUTPUTS_DIR.parent))
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


@router.get("/api/system")
def api_system(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    return _system_payload()


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


@router.get("/api/dashboard/bootstrap")
def api_dashboard_bootstrap(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    models = _model_registry()
    return {
        "system": _system_payload(),
        "configs": {"configs": [_config_summary(name) for name in PREFERRED_CONFIG_NAMES if name in CONFIGS]},
        "history": {"runs": _run_history()},
        "models": models,
        "checkpoints": models,
        "datasets": _dataset_registry(),
        "checkpoint_ids": list(_checkpoint_index().keys()),
    }
