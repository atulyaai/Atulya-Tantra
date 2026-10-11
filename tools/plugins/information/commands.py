"""Online weather and headline command plugin."""
from __future__ import annotations

import re

import httpx

from tools.plugins.registry import PluginContext
from .news import headlines
from .weather import weather


async def handle(command: str, _context: PluginContext) -> str | None:
    match = re.fullmatch(r"(?:what(?:'s| is) the )?weather(?: like)?(?: in| for)\s+(.+?)\??", command, re.I)
    if match:
        try:
            return await weather(match.group(1))
        except (httpx.HTTPError, ValueError):
            return "I couldn't reach the weather service just now."
    if re.fullmatch(r"(?:give me )?(?:the )?(?:latest )?(?:news|headlines)(?: headlines)?\??", command, re.I):
        try:
            return await headlines()
        except (httpx.HTTPError, RuntimeError):
            return "I couldn't reach the news feed just now."
    return None
