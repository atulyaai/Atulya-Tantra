"""Atulya's current mood, so the hologram can show it (colour, energy)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from atulya.server.helpers import _require_auth

router = APIRouter()


@router.get("/api/mood")
def api_mood(request: Request, user: dict = Depends(_require_auth)):
    from atulya.emotion import MoodState
    from atulya.llm import get_default_llm

    llm = getattr(request.app.state, "llm", None) or get_default_llm()
    mood = getattr(llm, "mood", None) or MoodState.load()
    return {"label": mood.label, "valence": round(mood.valence, 2), "energy": round(mood.energy, 2)}
