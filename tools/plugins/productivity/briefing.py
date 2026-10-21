"""Morning briefing: weather, headlines, and today's meetings, written by the model with tools.

Configured with ATULYA_BRIEFING_CITY and ATULYA_BRIEFING_TIME (HH:MM, local time;
empty disables the scheduled Telegram delivery). The WebUI asks for it on the
first visit of the day.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path


def briefing_city() -> str:
    return os.environ.get("ATULYA_BRIEFING_CITY", "").strip()


def briefing_time() -> tuple[int, int] | None:
    match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", os.environ.get("ATULYA_BRIEFING_TIME", "").strip())
    return (int(match.group(1)), int(match.group(2))) if match else None


def briefing_prompt(city: str) -> str:
    today = datetime.now().astimezone().strftime("%A %d %B")
    weather = (f"current weather for {city}, " if city else
               "no weather (no home city is saved; end with one short line: say 'my city is <name>' to add it), ")
    return (
        f"Morning briefing for {today}. Use tools to verify {weather}meetings today, "
        "local news for the saved city, India news and world news. "
        "Use short sections with emoji labels and clickable source links, at most 180 words. "
        "State unavailable sections honestly; do not invent headlines or claim phone actions."
    )



class BriefingLog:
    """Remembers which day each recipient last got a briefing, so restarts don't resend."""

    def __init__(self, data_dir: Path) -> None:
        self._path = data_dir / "briefings.json"

    def _load(self) -> dict:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def sent_today(self, recipient: str) -> bool:
        return self._load().get(recipient) == datetime.now().astimezone().date().isoformat()

    def mark(self, recipient: str) -> None:
        data = self._load()
        data[recipient] = datetime.now().astimezone().date().isoformat()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data), encoding="utf-8")


async def build_briefing(city: str, calendar=None, owner: str = "web", user_id: str = "admin", topics: list[str] | None = None) -> dict:
    """Use real data directly so scheduled briefings cannot fabricate tool results."""
    import asyncio
    from tools.plugins.information.news import briefing_news
    from tools.plugins.information.weather import find_place, forecast

    async def weather_section():
        if not city:
            return "📍 Set your home city to include weather and local news."
        try:
            place = await find_place(city)
            if not place:
                return "🌦️ Weather: location not found."
            return await forecast(place["latitude"], place["longitude"], place["label"], "today")
        except Exception:
            return "🌦️ Weather temporarily unavailable."

    weather, news = await asyncio.gather(weather_section(), briefing_news(city, topics))
    lines = ["🌅 Your morning briefing · " + datetime.now().astimezone().strftime("%a %d %b"), "", weather]
    buttons = []
    labels = {"local": "📍 Local", "india": "🇮🇳 India", "world": "🌍 World"}
    for group in news:
        lines.extend(["", labels[group["kind"]]])
        if not group["items"]:
            lines.append("No recent city-matching headlines found." if group["status"] == "no_recent_matching_headlines"
                         else "City not set." if group["status"] == "city_not_set" else "Feed unavailable.")
        for item in group["items"]:
            lines.append(f"• {item['title']} ({item['source']})")
            buttons.append({"label": f"{labels[group['kind']]} · {item['title'][:45]}", "url": item["url"]})
    if calendar is not None:
        try:
            events = await asyncio.to_thread(calendar.list, owner, 50, user_id)
            today = datetime.now().astimezone().date()
            upcoming = [e for e in events if datetime.fromisoformat(e["starts_at"]).astimezone().date() == today]
            lines.extend(["", "📅 Today"])
            lines.extend(f"• {datetime.fromisoformat(e['starts_at']).astimezone().strftime('%H:%M')} · {e['title']}"
                         for e in upcoming[:3])
            if not upcoming:
                lines.append("No saved meetings today.")
        except Exception:
            lines.extend(["", "📅 Calendar unavailable."])
    return {"text": "\n".join(lines)[:3800], "links": buttons, "news": news}


def apply_briefing_schedule(data_dir, settings: dict) -> str:
    """Keep the Morning briefing routine on the same clock and switch the user just chose."""
    from tools.plugins.productivity.routines import RoutineStore

    store = RoutineStore(data_dir)
    enabled = bool(settings.get("enabled", True) and settings.get("channel") != "off")
    try:
        store.edit("Morning briefing", when=settings["time"], enabled=enabled)
        return "Updated the Morning briefing routine."
    except ValueError:
        if not enabled:
            return "Morning briefing is off. No routine was added."
        store.add("Morning briefing", settings["time"], "weekdays", "briefing", "")
        return "Added a weekday Morning briefing routine."
