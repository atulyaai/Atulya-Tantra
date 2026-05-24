"""Aggregate dashboard routers for WebUI-local imports."""
from __future__ import annotations

from webui.backend.dashboard.routes import auth, automation, chat, cortex, model, openai, system, train

routers = [
    auth.router,
    system.router,
    model.router,
    train.router,
    chat.router,
    cortex.router,
    automation.router,
    openai.router,
]

__all__ = ["routers"]



