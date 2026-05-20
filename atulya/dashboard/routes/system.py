"""NP-DNA Dashboard System Routes.
"""
from __future__ import annotations
import logging
import platform
import shutil
from pathlib import Path
import psutil
from fastapi import APIRouter, Header, Request, HTTPException

from atulya.core.npdna.config import CONFIGS, _estimate_params
from atulya.dashboard.state import OUTPUTS_DIR, DashboardState
from atulya.dashboard.helpers import (
    _check_request_origin,
    _require_admin,
    _scan_datasets,
    _auto_config_name,
    _read_run_history,
    _dataset_preview,
    _training_preset,
    _stop_training,
)

logger = logging.getLogger("atulya.dashboard.routes.system")
router = APIRouter()


@router.get("/api/datasets")
def api_datasets(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    return {"datasets": _scan_datasets()}


@router.get("/api/configs")
def api_configs(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    vm = psutil.virtual_memory()
    recommended = _auto_config_name()
    configs_list = []
    for k, v in CONFIGS.items():
        params = _estimate_params(v)
        if params >= 1_000_000:
            params_label = f"{params/1_000_000:.1f}M"
        else:
            params_label = f"{params/1_000:.0f}K"
        configs_list.append({
            "name": k,
            "params": params,
            "params_label": params_label,
            "layers": v.num_layers,
            "strands": v.mesh.num_strands,
            "top_k": v.mesh.top_k,
            "vocab": v.initial_vocab,
            "hidden": v.hidden_size,
            "recommended": k == recommended,
        })
    return {
        "configs": configs_list,
        "recommended": recommended,
        "ram_gb": round(vm.total / (1024**3), 1),
    }


@router.get("/api/system")
def api_system(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    vm = psutil.virtual_memory()
    cpu_val = psutil.cpu_percent(interval=0.1)
    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "cpu_count": psutil.cpu_count(logical=False),
        "cpu_logical": psutil.cpu_count(logical=True),
        "ram_total_gb": round(vm.total / (1024**3), 1),
        "ram_avail_gb": round(vm.available / (1024**3), 1),
        "ram_pct": round(vm.percent, 1),
        "cpu_pct": round(cpu_val, 1),
        "python_version": platform.python_version(),
    }


@router.get("/api/run-history")
def api_run_history(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    return {"runs": _read_run_history(50)}


@router.get("/api/dataset-preview/{data_id}")
def api_dataset_preview_route(
    data_id: str,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _require_admin(_admin)
    res = _dataset_preview(data_id)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.get("/api/train/preset/{data_id}")
def api_train_preset_route(
    data_id: str,
    config: str | None = None,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _require_admin(_admin)
    res = _training_preset(data_id, config)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.post("/api/system/reset")
def api_system_reset(
    request: Request,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    """Factory reset: delete all model outputs but keep datasets."""
    _check_request_origin(request)
    _require_admin(_admin)

    # 1. Stop any running training
    _stop_training()

    # 2. Delete everything inside OUTPUTS_DIR
    deleted = []
    if OUTPUTS_DIR.exists():
        for item in OUTPUTS_DIR.iterdir():
            try:
                if item.is_file():
                    item.unlink()
                    deleted.append(item.name)
                elif item.is_dir():
                    shutil.rmtree(item)
                    deleted.append(item.name + "/")
            except Exception as e:
                logger.error("Failed to delete %s: %s", item, e)

    # 3. Clear cache
    DashboardState.MODEL_CACHE.clear()
    DashboardState.MODEL_CACHE_MTIME.clear()

    return {"status": "reset_complete", "deleted": deleted}
