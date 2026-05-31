from __future__ import annotations

from fastapi import APIRouter, Header

from drishti.dashboard.helpers import _checkpoint_index, _read_metadata, _require_admin

router = APIRouter()


@router.get("/api/cortex/stats")
@router.get("/api/cortex/status")
def api_cortex_stats(model_id: str = "latest", _admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    path = _checkpoint_index().get(model_id)
    if not path:
        return {"exists": False, "entries": 0}
    meta = _read_metadata(path)
    cortex_dir = path / "cortex"
    return {
        "exists": cortex_dir.exists(),
        "model_id": model_id,
        "entries": int(meta.get("cortex_entries") or 0),
        "dim": int(meta.get("cortex_dim") or meta.get("hidden_size") or 0),
        "max_entries": int(meta.get("cortex_max_entries") or 0),
        "top_k": int(meta.get("cortex_top_k") or 0),
        "path": str(cortex_dir),
    }


@router.get("/api/cortex/entries")
def api_cortex_entries(
    model_id: str = "latest",
    page: int = 1,
    limit: int = 50,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _require_admin(_admin)
    path = _checkpoint_index().get(model_id)
    if not path:
        return {"entries": [], "total": 0, "page": page, "limit": limit}
    meta_path = path / "cortex" / "cortex_meta.json"
    if not meta_path.exists():
        return {"entries": [], "total": 0, "page": page, "limit": limit}
    import json

    entries = json.loads(meta_path.read_text(encoding="utf-8"))
    start = max(0, (page - 1) * limit)
    return {"entries": entries[start:start + limit], "total": len(entries), "page": page, "limit": limit}
