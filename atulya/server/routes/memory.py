"""The memory tree: what Atulya remembers about the signed-in user, as a drawable graph."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from atulya.memory.graph import build_memory_graph
from atulya.server.helpers import _require_auth
from atulya.server.routes.profile import _key, _store

router = APIRouter()


@router.get("/api/memory/graph")
def api_memory_graph(request: Request, user: dict = Depends(_require_auth)):
    return build_memory_graph(_store(request).view(_key(user)))
