from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from drishti.dashboard import helpers

router = APIRouter()


def _model_registry() -> list[dict]:
    """The assistant is exposed as a single model; the brain routes behind it."""
    return [{"id": "atulya", "label": "Atulya", "owned_by": "atulya"}]


def _require_bearer(authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    parts = authorization.split(" ")
    if len(parts) != 2:
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = parts[1]
    if token == helpers.ADMIN_TOKEN:
        return
    from drishti.dashboard import users
    if not users.get_session(token):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/v1/models")
def list_models(authorization: str | None = Header(default=None, alias="Authorization")):
    _require_bearer(authorization)
    return {"object": "list", "data": [{"id": item["id"], "object": "model", **item} for item in _model_registry()]}


