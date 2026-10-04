"""About you: what Atulya has learned about the signed-in user.

Every user sees and edits only their own profile.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from atulya.server.helpers import _require_auth

router = APIRouter()


def _store(request: Request):
    from atulya.cognition import get_kernel
    from atulya.llm import get_default_llm

    return get_kernel(getattr(request.app.state, "llm", None) or get_default_llm()).profiles


def _key(user: dict) -> str:
    return str(user.get("username") or "default")


@router.get("/api/profile")
def api_profile(request: Request, user: dict = Depends(_require_auth)):
    return _store(request).view(_key(user))


@router.post("/api/profile/facts")
def api_add_fact(request: Request, body: dict, user: dict = Depends(_require_auth)):
    """Teach Atulya something: {"text": "my wife's name is Priya"}."""
    from atulya.cognition.profile import describe_fact, extract_facts

    text = str(body.get("text") or "").strip()
    facts = extract_facts(text)
    if not facts and text:  # anything else is kept as a plain note, in the user's own words
        facts = [{"kind": "note", "key": "note", "value": text[:200]}]
    if not facts:
        raise HTTPException(status_code=400, detail="Tell me something about you")
    stored = _store(request).remember(_key(user), facts)
    return {"ok": True, "facts": [{**f, "text": describe_fact(f)} for f in stored]}


@router.delete("/api/profile/facts/{fact_id}")
def api_forget_fact(fact_id: str, request: Request, user: dict = Depends(_require_auth)):
    if not _store(request).forget(_key(user), fact_id=fact_id):
        raise HTTPException(status_code=404, detail="Fact not found")
    return {"ok": True}


@router.post("/api/profile/trust")
def api_trust(request: Request, body: dict, user: dict = Depends(_require_auth)):
    """Stop asking (trusted=true) or start asking again (false) before an action."""
    store = _store(request)
    key = str(body.get("key") or "")
    if bool(body.get("trusted")):
        known = {a["key"] for a in store.view(_key(user))["approvals"]}
        if key not in known or not store.trust(_key(user), key):
            raise HTTPException(status_code=400, detail="Atulya can only stop asking about actions you've approved")
    else:
        store.untrust(_key(user), key or None)
    return {"ok": True, "trusted": store.view(_key(user))["trusted"]}


@router.delete("/api/profile")
def api_forget_everything(request: Request, user: dict = Depends(_require_auth)):
    _store(request).forget_everything(_key(user))
    return {"ok": True}
