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


CONDITIONS = {0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "foggy", 48: "foggy",
              51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
              71: "light snow", 73: "snow", 75: "heavy snow", 80: "rain showers", 81: "rain showers",
              82: "heavy rain showers", 95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail"}
_full: dict[tuple[float, float], tuple[float, dict]] = {}
_addresses: dict[tuple[float, float], str] = {}


async def find_place(name: str) -> dict | None:
    """Geocode a place name (cached). Returns {latitude, longitude, label} or None."""
    name = name.strip()
    if not name or len(name) > 100:
        return None
    key = name.casefold()
    if key not in _places:
        geo = await _http().get("https://geocoding-api.open-meteo.com/v1/search",
                                params={"name": name, "count": 1, "language": "en", "format": "json"})
        geo.raise_for_status()
        results = geo.json().get("results") or []
        _places[key] = results[0] if results else None
    place = _places[key]
    if place is None:
        return None
    label = ", ".join(str(x) for x in (place.get("name"), place.get("admin1"), place.get("country")) if x)
    return {"latitude": place["latitude"], "longitude": place["longitude"], "label": label}


async def address(latitude: float, longitude: float) -> str:
    """Reverse geocode coordinates to a readable address (OpenStreetMap Nominatim, cached ~100 m)."""
    key = (round(latitude, 3), round(longitude, 3))
    if key not in _addresses:
        response = await _http().get("https://nominatim.openstreetmap.org/reverse", params={
            "lat": latitude, "lon": longitude, "format": "jsonv2", "zoom": 16, "addressdetails": 1},
            headers={"User-Agent": "Atulya-Tantra/1.0 (+https://atulya.atulvij.com)", "Accept-Language": "en"})
        response.raise_for_status()
        data = response.json()
        parts = data.get("address", {})
        pieces = [parts.get(k) for k in ("road", "suburb", "neighbourhood", "city", "town", "village",
                                         "state_district", "state", "postcode", "country")]
        seen: list[str] = []
        for piece in pieces:
            if piece and piece not in seen:
                seen.append(piece)
        _addresses[key] = ", ".join(seen) or data.get("display_name", "") or f"{latitude:.4f}, {longitude:.4f}"
    return _addresses[key]


def _condition(code) -> str:
    try:
        return CONDITIONS.get(int(code), "mixed conditions")
    except (TypeError, ValueError):
        return "mixed conditions"


async def forecast(latitude: float, longitude: float, label: str, when: str = "now") -> str:
    """Current conditions plus the requested outlook: now | next_hours | today | tomorrow | week."""
    coords = (round(latitude, 2), round(longitude, 2))
    cached = _full.get(coords)
    if cached and time.monotonic() - cached[0] < FORECAST_TTL:
        data = cached[1]
    else:
        response = await _http().get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": latitude, "longitude": longitude, "timezone": "auto", "forecast_days": 7,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
            "hourly": "temperature_2m,precipitation_probability,weather_code",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
                     "precipitation_sum,wind_speed_10m_max,uv_index_max,sunrise,sunset",
        })
        response.raise_for_status()
        data = response.json()
        _full[coords] = (time.monotonic(), data)
    current, daily, hourly = data.get("current", {}), data.get("daily", {}), data.get("hourly", {})
    updated = str(current.get("time", ""))[-5:]
    lines = [f"{label} (updated {updated} local time, Open-Meteo):",
             f"Now: {_condition(current.get('weather_code'))}, {current.get('temperature_2m', '?')}°C "
             f"(feels {current.get('apparent_temperature', '?')}°C), humidity {current.get('relative_humidity_2m', '?')}%, "
             f"wind {current.get('wind_speed_10m', '?')} km/h."]

    def day(i: int, name: str) -> str:
        try:
            return (f"{name}: {_condition(daily['weather_code'][i])}, {daily['temperature_2m_min'][i]}–"
                    f"{daily['temperature_2m_max'][i]}°C, rain chance {daily['precipitation_probability_max'][i]}% "
                    f"({daily['precipitation_sum'][i]} mm), wind up to {daily['wind_speed_10m_max'][i]} km/h, "
                    f"UV {daily['uv_index_max'][i]}, sunrise {str(daily['sunrise'][i])[-5:]}, "
                    f"sunset {str(daily['sunset'][i])[-5:]}.")
        except (KeyError, IndexError):
            return f"{name}: forecast unavailable."

    if when in {"next_hours", "today", "now"}:
        times = hourly.get("time", [])
        now_key = str(current.get("time", ""))[:13]
        start = next((i for i, t in enumerate(times) if str(t)[:13] >= now_key), 0)
        upcoming = []
        for i in range(start, min(start + 12, len(times)), 3):
            upcoming.append(f"{str(times[i])[-5:]} {hourly['temperature_2m'][i]}°C "
                            f"{hourly['precipitation_probability'][i]}% rain")
        if upcoming:
            lines.append("Next hours: " + "; ".join(upcoming) + ".")
    if when in {"today", "now"}:
        lines.append(day(0, "Today"))
    if when == "tomorrow":
        lines.append(day(1, "Tomorrow"))
    if when == "week":
        names = ["Today", "Tomorrow"] + [str(d) for d in daily.get("time", [])[2:]]
        lines.extend(day(i, names[i]) for i in range(min(7, len(daily.get("time", [])))))
    return "\n".join(lines)
