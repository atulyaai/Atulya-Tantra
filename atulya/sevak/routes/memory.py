"""The memory tree: what Atulya remembers about the signed-in user, as a drawable graph."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from atulya.smriti.graph import build_memory_graph
from atulya.sevak.helpers import _require_auth
from atulya.sevak.routes.profile import _key, _store

router = APIRouter()


def _vector_count() -> int:
    try:
        import json
        from pathlib import Path

        total = 0
        for f in Path("data/memory").glob("*.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            total += len(data) if isinstance(data, (list, dict)) else 0
        return total
    except Exception:  # noqa: BLE001 - a count only decorates the view
        return 0


@router.get("/api/memory/graph")
def api_memory_graph(request: Request, user: dict = Depends(_require_auth)):
    from atulya.yantra.agent.tools import TOOL_REGISTRY
    from atulya.bhava.emotion import MoodState
    from atulya.buddhi.intelligence import _SPEED
    from atulya.buddhi.llm import get_default_llm
    from atulya.sevak import chat_history

    llm = getattr(request.app.state, "llm", None) or get_default_llm()
    mood = getattr(llm, "mood", None) or MoodState.load()
    episodes = [m for m in chat_history.list_messages(user, 60) if m.get("role") == "user"][-24:][::-1]
    brains = [{"name": n, "seconds": round(v["avg"], 1)} for n, v in _SPEED.items() if v.get("avg")]
    return build_memory_graph(
        _store(request).view(_key(user)),
        episodes=episodes,
        skills=[(n, str(t.get("description", ""))) for n, t in TOOL_REGISTRY.items()],
        mood={"mood": mood.label, "energy": round(mood.energy, 2), "valence": round(mood.valence, 2)},
        brains=brains,
        vectors=_vector_count(),
    )
