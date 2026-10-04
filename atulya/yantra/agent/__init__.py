"""Atulya Agent — tool-based skills with generic ReAct/TAO agent loop.

Every skill is a plain async function + JSON schema (see tools.py).
Adding a new skill = one @tool decorator + one function = ~5 minutes.
"""
from __future__ import annotations

from .core import AgentCore
from . import tools as agent_tools

__all__ = ["AgentCore", "agent_tools"]
