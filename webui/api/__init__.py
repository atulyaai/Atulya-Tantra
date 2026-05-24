"""API route wrappers for the WebUI dashboard."""

from webui.backend.dashboard.routes import auth, automation, chat, cortex, model, openai, system, train

__all__ = [
    "auth",
    "automation",
    "chat",
    "cortex",
    "model",
    "openai",
    "system",
    "train",
]



