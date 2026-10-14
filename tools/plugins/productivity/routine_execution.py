"""Factual routine actions, with no model-generated execution claims."""
import asyncio
from datetime import datetime

from .briefing import build_briefing


async def render_routine(item, city, calendar, owner="web", user_id="admin"):
    action = item.get("action")
    if action == "message":
        return {"text": str(item.get("message") or "").strip(), "links": []}
    if action == "briefing":
        return await build_briefing(city, calendar, owner, user_id)
    if action == "calendar":
        rows = await asyncio.to_thread(calendar.list, owner, 50, user_id)
        now = datetime.now().astimezone()
        upcoming = [e for e in rows if 0 <= (datetime.fromisoformat(e["starts_at"]) - now).total_seconds() <= 7200]
        return {"text": "📅 Next two hours\n" + "\n".join(
            f"• {datetime.fromisoformat(e['starts_at']).astimezone().strftime('%H:%M')} · {e['title']}"
            for e in upcoming), "links": []} if upcoming else None
    if action in {"weather", "rain"}:
        from tools.plugins.information.weather import find_place, forecast, _weather_data
        if not city:
            return {"text": "📍 Set your city to enable weather updates.", "links": []}
        spot = await find_place(city)
        if not spot:
            return {"text": "🌦️ Weather location unavailable.", "links": []}
        if action == "rain":
            data = await _weather_data(spot["latitude"], spot["longitude"])
            probability = data.get("daily", {}).get("precipitation_probability_max", [])
            if not probability or not isinstance(probability[0], (float, int)) or probability[0] < 50:
                return None
        return {"text": await forecast(spot["latitude"], spot["longitude"], city, "today"), "links": []}
    raise ValueError("Unsupported routine action")
