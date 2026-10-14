"""Authenticated weather cards with real daily graph data."""
import asyncio

from fastapi import HTTPException, Request, Query


def register_weather_routes(app, profiles):
    @app.get("/api/weather")
    async def weather(request: Request, city: str = Query(default="", max_length=100), when: str = "today"):
        from tools.plugins.information.weather import find_place, _weather_data, _air_data, compact_weather
        if when not in {"today", "tomorrow", "week"}:
            raise HTTPException(422,"Choose today, tomorrow or week")
        profile=await asyncio.to_thread(profiles.get,str(request.state.user_id))
        name=city.strip() or profile.get("city","")
        if not name:
            raise HTTPException(422,"Enter a city to see weather")
        try:
            place=await find_place(name)
            if not place:
                raise HTTPException(404,"City not found")
            data,air=await asyncio.gather(_weather_data(place["latitude"],place["longitude"]),_air_data(place["latitude"],place["longitude"]))
            return {"summary":compact_weather(data,air,place["label"],when),"daily":data.get("daily",{}),
                    "updated":data.get("current",{}).get("time"),"source":"Open-Meteo"}
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(503,"Weather service unavailable; no forecast was verified") from exc
