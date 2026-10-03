"""Atulya Agent API routes — thin layer over tool registry + agent loop."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from drishti.dashboard.helpers import _require_auth, _require_admin

logger = logging.getLogger(__name__)
router = APIRouter()

_AGENT = None


def set_agent(agent):
    global _AGENT
    _AGENT = agent


def _get_agent():
    if _AGENT is None:
        raise HTTPException(status_code=503, detail="Atulya Agent not initialized")
    return _AGENT


@router.get("/api/agent/status")
async def agent_status(user: dict = Depends(_require_admin)):
    a = _get_agent()
    return {"tools": a.list_tools(), "status": "ready"}


@router.post("/api/agent/process")
async def agent_process(request: Request, user: dict = Depends(_require_auth)):
    body = await request.json()
    user_input = body.get("input", "")
    history = body.get("history")
    if not user_input:
        return {"status": "error", "message": "No input"}
    a = _get_agent()
    reply = await a.process(user_input, history, user=user)
    return {"status": "success", "reply": reply}


@router.get("/api/agent/tools")
async def agent_tools(user: dict = Depends(_require_admin)):
    a = _get_agent()
    return {"tools": a.list_tools()}


@router.get("/api/agent/schemas")
async def agent_schemas(user: dict = Depends(_require_admin)):
    a = _get_agent()
    return {"schemas": a.get_tool_schemas()}
