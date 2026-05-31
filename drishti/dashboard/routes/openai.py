from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from drishti.dashboard.helpers import _model_registry
from drishti.dashboard import helpers

router = APIRouter()


def _require_bearer(authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ")[1]
    if token == helpers.ADMIN_TOKEN:
        return
    from drishti.dashboard import users
    if not users.get_session(token):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/v1/models")
def list_models(authorization: str | None = Header(default=None, alias="Authorization")):
    _require_bearer(authorization)
    return {"object": "list", "data": [{"id": item["id"], "object": "model", **item} for item in _model_registry()]}


