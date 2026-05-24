from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from webui.backend.dashboard.helpers import _model_registry
from webui.backend.dashboard import helpers

router = APIRouter()


def _require_bearer(authorization: str | None) -> None:
    expected = f"Bearer {helpers.ADMIN_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/v1/models")
def list_models(authorization: str | None = Header(default=None, alias="Authorization")):
    _require_bearer(authorization)
    return {"object": "list", "data": [{"id": item["id"], "object": "model", **item} for item in _model_registry()]}


