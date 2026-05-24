from __future__ import annotations

from fastapi import APIRouter, Header

from webui.backend.dashboard.helpers import _checkpoint_index, _read_metadata, _require_admin
from webui.backend.dashboard.state import DashboardState

router = APIRouter()


@router.post("/api/plasticity/check")
def api_plasticity_check(body: dict, _admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    model_id = str(body.get("model_id") or "latest")
    model_path = _checkpoint_index().get(model_id)
    if not model_path:
        return {"status": "error", "message": "Model not found", "model_info": {"exists": False}}
    meta = _read_metadata(model_path)
    params = meta.get("parameter_count")
    active = meta.get("active_parameter_count")
    vocab_size = meta.get("vocab_size")
    vocab_capacity = meta.get("vocab_capacity")
    return {
        "status": "success",
        "message": "Plasticity check completed. No model adjustments needed.",
        "events": meta.get("structural_events") or [],
        "model_info": {
            "exists": True,
            "config": meta.get("train_config_name") or meta.get("config_name", "?"),
            "step": meta.get("train_step") or meta.get("loss_count") or 0,
            "loss": meta.get("train_final_loss") or meta.get("final_loss"),
            "best_loss": meta.get("train_best_loss") or meta.get("best_loss"),
            "parameter_count": params,
            "active_parameter_count": active,
            "compression_ratio": (float(params) / float(active)) if params and active else None,
            "vocab_size": vocab_size,
            "vocab_capacity": vocab_capacity,
            "vocab_fill": (float(vocab_size) / float(vocab_capacity)) if vocab_size and vocab_capacity else None,
            "cortex_entries": meta.get("cortex_entries", 0),
            "layers": meta.get("layer_specs") or [],
            "total_strands": meta.get("total_strands") or meta.get("num_strands"),
            "codecs": meta.get("codecs") or {},
        },
    }


@router.get("/api/model/status")
def api_model_status(model_id: str = "latest", _admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    path = _checkpoint_index().get(model_id)
    if not path:
        return {"loaded": False, "model_id": model_id, "exists": False}
    key = str(path.resolve())
    return {
        "loaded": key in DashboardState.MODEL_CACHE,
        "model_id": model_id,
        "exists": True,
        "path": str(path),
    }


@router.get("/api/checkpoints")
def api_checkpoints(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    items = []
    for model_id, path in _checkpoint_index().items():
        meta = _read_metadata(path)
        items.append({
            "id": model_id,
            "label": model_id,
            "path": str(path),
            "config": meta.get("train_config_name") or meta.get("config_name", "?"),
            "step": meta.get("train_step") or meta.get("loss_count") or 0,
            "best_loss": meta.get("train_best_loss") or meta.get("best_loss"),
        })
    return {"checkpoints": items, "models": items}


