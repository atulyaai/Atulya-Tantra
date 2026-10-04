"""Brains & keys: link, test and remove API keys for every supported provider (admin only).

Key values are never sent back to the browser; only whether one is set and its last four characters.
"""
from __future__ import annotations

import asyncio
import os
import time

from fastapi import APIRouter, Depends, HTTPException

from atulya.envfile import set_env_value
from atulya.buddhi.providers_catalog import BY_ID, CATALOG
from atulya.sevak.helpers import _require_admin

router = APIRouter()


def _mask(value: str) -> str:
    return ("…" + value[-4:]) if len(value) >= 8 else ("set" if value else "")


def _row(spec) -> dict:
    key = os.environ.get(spec.key_var, "")
    row = {"id": spec.id, "label": spec.label, "free": spec.free, "docs": spec.docs, "configured": bool(key),
           "key_hint": _mask(key), "model": os.environ.get(spec.model_var, "") or spec.default_model,
           "default_model": spec.default_model, "needs_url": spec.id == "custom"}
    if spec.id == "custom":
        row["url"] = os.environ.get("ATULYA_CUSTOM_URL", "")
        row["configured"] = bool(row["url"])
    return row


def _provider(spec):
    from atulya.buddhi.intelligence import OpenAICompatProvider, ProviderRouter

    if not spec.builtin:
        return OpenAICompatProvider(spec)
    wanted = {"anthropic": "Claude", "openai": "OpenAI", "gemini": "Gemini", "groq": "Groq", "nvidia": "NVIDIA",
              "openrouter": "OpenRouter", "opencode": "OpenCode Go"}[spec.id]
    for p in ProviderRouter().providers:
        if wanted.lower() in p.name().lower():
            return p
    raise HTTPException(status_code=404, detail="Provider not found")


@router.get("/api/providers")
def api_providers(user: dict = Depends(_require_admin)):
    return {"providers": [_row(s) for s in CATALOG]}


@router.post("/api/providers/{provider_id}")
def api_set_provider(provider_id: str, body: dict, user: dict = Depends(_require_admin)):
    """{"key": "...", "model": "...", "url": "..."}: any field left out is unchanged; "" removes it."""
    spec = BY_ID.get(provider_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Unknown provider")
    try:
        if "key" in body:
            set_env_value(spec.key_var, str(body["key"]).strip())
        if "model" in body:
            set_env_value(spec.model_var, str(body["model"]).strip())
        if spec.id == "custom" and "url" in body:
            set_env_value("ATULYA_CUSTOM_URL", str(body["url"]).strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not write .env: {exc}") from exc
    return _row(spec)


@router.post("/api/providers/{provider_id}/test")
async def api_test_provider(provider_id: str, user: dict = Depends(_require_admin)):
    spec = BY_ID.get(provider_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Unknown provider")
    provider = _provider(spec)
    if not provider.is_available():
        return {"ok": False, "error": "No key is set yet."}
    started = time.monotonic()
    try:
        text = await asyncio.wait_for(provider.chat("Reply with the single word: ready", "You are a connection test."), 40)
    except Exception as exc:  # noqa: BLE001 - show the provider's own message
        return {"ok": False, "error": str(exc)[:300]}
    return {"ok": True, "seconds": round(time.monotonic() - started, 1), "reply": str(text)[:80]}
