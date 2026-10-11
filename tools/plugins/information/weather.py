"""Current weather lookup using Open-Meteo's public APIs.

Speed: one shared keep-alive client, place lookups cached for the process lifetime,
and forecasts cached for 10 minutes (Open-Meteo updates current conditions every 15).
"""
import time

import httpx

_client: httpx.AsyncClient | None = None
_places: dict[str, dict | None] = {}
_forecasts: dict[tuple[float, float], tuple[float, dict]] = {}
FORECAST_TTL = 600


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(8, connect=4), follow_redirects=False,
                                    limits=httpx.Limits(max_keepalive_connections=4, keepalive_expiry=120))
    return _client


async def weather(city: str) -> str:
    city = city.strip()
    if not city or len(city) > 100:
        raise ValueError("Tell me the city, for example: weather in Bengaluru")
    client = _http()
    key = city.casefold()
    if key not in _places:
        geo = await client.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": city, "count": 1, "language": "en", "format": "json"})
        geo.raise_for_status()
        results = geo.json().get("results") or []
        _places[key] = results[0] if results else None
    place = _places[key]
    if place is None:
        return f"I couldn't find a location named {city}."
    coords = (round(place["latitude"], 2), round(place["longitude"], 2))
    cached = _forecasts.get(coords)
    if cached and time.monotonic() - cached[0] < FORECAST_TTL:
        current = cached[1]
    else:
        forecast = await client.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": place["latitude"], "longitude": place["longitude"],
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
            "timezone": "auto",
        })
        forecast.raise_for_status()
        current = forecast.json().get("current", {})
        _forecasts[coords] = (time.monotonic(), current)
    code = int(current.get("weather_code", -1))
    conditions = {0:"clear",1:"mostly clear",2:"partly cloudy",3:"overcast",45:"foggy",48:"foggy",
                  51:"light drizzle",53:"drizzle",55:"heavy drizzle",61:"light rain",63:"rain",65:"heavy rain",
                  71:"light snow",73:"snow",75:"heavy snow",80:"rain showers",81:"rain showers",82:"heavy rain showers",
                  95:"thunderstorm",96:"thunderstorm with hail",99:"thunderstorm with hail"}.get(code, "conditions unavailable")
    label = ", ".join(str(x) for x in (place.get("name"), place.get("admin1"), place.get("country") if place.get("country_code") else None) if x)
    return (f"{label}: {conditions}, {current.get('temperature_2m', '?')}°C "
            f"(feels like {current.get('apparent_temperature', '?')}°C), humidity {current.get('relative_humidity_2m', '?')}%, "
            f"wind {current.get('wind_speed_10m', '?')} km/h. Source: Open-Meteo.")
