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
    if action == "mail":
        from tools.plugins.information.google_api import gmail_search
        try:
            text = await gmail_search(user_id, "is:unread newer_than:1d", 4)
        except Exception:
            return None
        if not text or text.startswith("No matching"):
            return None
        lines = [line for line in text.splitlines() if line.startswith("ID ")][:4]
        if not lines:
            return None
        short = []
        for line in lines:
            parts = [part.strip() for part in line.split("|")]
            sender = parts[2] if len(parts) > 2 else "someone"
            subject = parts[3] if len(parts) > 3 else "(no subject)"
            short.append(f"• {sender} — {subject[:80]}")
        return {"text": "Unread mail. Say remove the unread mail routine if you do not want this.\n" + "\n".join(short), "links": []}
    raise ValueError("Unsupported routine action")
