"""Online weather and headline command plugin."""
from __future__ import annotations

import re

import httpx

from tools.plugins.registry import PluginContext
from .news import headlines
from .weather import find_place, forecast


async def handle(command: str, _context: PluginContext) -> str | None:
    match = re.fullmatch(r"(?:what(?:'s| is) the )?weather(?: like)?(?: in| for)\s+(.+?)\??", command, re.I)
    if match:
        place_name = match.group(1).strip()
        # "weather in Delhi tomorrow / this week / kal": the model's forecast tool handles timing.
        if re.search(r"\b(tomorrow|today|tonight|week|weekend|next|hour|hours|forecast|kal|parso|morning|evening)\b",
                     place_name, re.I):
            return None
        try:
            place = await find_place(place_name)
            if place is None:
                return f"I couldn't find a place named {place_name}."
            return await forecast(place["latitude"], place["longitude"], place["label"], "today")
        except (httpx.HTTPError, ValueError):
            return "I couldn't reach the weather service just now."
    if re.fullmatch(r"(?:give me )?(?:the )?(?:latest )?(?:news|headlines)(?: headlines)?\??", command, re.I):
        try:
            return await headlines()
        except (httpx.HTTPError, RuntimeError):
            return "I couldn't reach the news feed just now."
    return None
