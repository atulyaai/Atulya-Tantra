"""Current weather lookup using Open-Meteo's public APIs.

Speed: one shared keep-alive client, place lookups cached for the process lifetime,
and forecasts cached for 10 minutes (Open-Meteo updates current conditions every 15).
"""
import asyncio
import re
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


CONDITIONS = {0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "foggy", 48: "freezing fog",
              51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 56: "freezing drizzle", 57: "freezing drizzle",
              61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
              71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains", 80: "rain showers",
              81: "rain showers", 82: "heavy rain showers", 85: "snow showers", 86: "heavy snow showers",
              95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail"}
_full: dict[tuple[float, float], tuple[float, dict]] = {}
_air: dict[tuple[float, float], tuple[float, dict]] = {}
_addresses: dict[tuple[float, float], str] = {}
_osm_places: dict[tuple[str, tuple | None], dict | None] = {}
OSM_HEADERS = {"User-Agent": "Atulya-Tantra/1.0 (+https://atulya.atulvij.com)", "Accept-Language": "en"}


PIN_CODE = re.compile(r"\b\d{6}\b")  # Indian postal PIN


def _best(hits: list[dict], wanted: str = "") -> dict | None:
    """Prefer an exact name match ("Nehru Place", not "Motilal Nehru Place"), then a locality/town, then the top hit."""
    wanted = wanted.casefold().strip()
    exact = [h for h in hits if wanted and str(h.get("name", "")).casefold() == wanted]
    for pool in (exact, hits):
        found = next((h for h in pool if h.get("category", h.get("class")) in PLACE_CLASSES), None)
        if found:
            return found
    return exact[0] if exact else (hits[0] if hits else None)


PLACE_CLASSES = {"place", "boundary"}  # towns, villages, suburbs, colonies, districts (not shops or bus stops)


async def _osm_search(query: str, near: tuple[float, float] | None = None) -> list[dict]:
    params = {"q": query, "format": "jsonv2", "limit": 5, "addressdetails": 1}
    if near:  # only the user's own city area (~35 km): "Sangam Vihar" = the one in their city, but "Shimla" =
        # the famous town, not a same-named village 130 km away
        d = 0.35
        params.update(viewbox=f"{near[1] - d},{near[0] + d},{near[1] + d},{near[0] - d}", bounded=1)
    try:
        response = await _http().get("https://nominatim.openstreetmap.org/search", params=params, headers=OSM_HEADERS)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        return []


def _osm_label(hit: dict, name: str) -> dict:
    parts = hit.get("address", {})
    pieces = [hit.get("name")] + [parts.get(k) for k in ("suburb", "city", "town", "village", "state", "country")]
    seen: list[str] = []
    for piece in pieces:
        if piece and piece not in seen:
            seen.append(piece)
    return {"latitude": float(hit["lat"]), "longitude": float(hit["lon"]),
            "label": ", ".join(seen) or hit.get("display_name", name)}


async def find_place(name: str, near: tuple[float, float] | None = None) -> dict | None:
    """Geocode any place: colony, sector, landmark, street, town or city (OpenStreetMap).
    Order: a locality/town with that name near the user (`near` = their device/home coordinates) → the best
    locality/town anywhere → any nearby match (a landmark like "Nehru Place") → Open-Meteo city search.
    Returns {latitude, longitude, label} or None."""
    name = " ".join(name.split())
    if not name or len(name) > 120:
        return None
    area = (round(near[0], 1), round(near[1], 1)) if near else None
    key = (name.casefold(), area)
    if key not in _osm_places and ("," in name or PIN_CODE.search(name)):
        # Full addresses ("Sangam Vihar, New Delhi, Delhi 110062") often fail because one part doesn't match
        # OpenStreetMap's names. Try: the locality (first part) near the user, locality + PIN, then the full text.
        parts = [part.strip() for part in name.split(",") if part.strip()]
        pin = PIN_CODE.search(name)
        locality = PIN_CODE.sub("", parts[0]).strip() if parts else ""
        tries = []
        if len(parts) >= 2 and locality:  # "Sector 62, Noida": a generic name needs its city
            tries.append(locality + ", " + PIN_CODE.sub("", parts[1]).strip())
        if pin and locality:
            tries.append(locality + " " + pin.group(0))
        if locality:
            tries.append(locality)  # the locality near the user
        tries.append(", ".join(parts))
        full = ", ".join(parts)
        city_words = [w for w in re.findall(r"[a-z]+", PIN_CODE.sub("", " ".join(parts[1:])).casefold())
                      if len(w) > 3 and w not in {"india", "new", "near", "road"}]
        tries = [t for t in dict.fromkeys(tries) if t and t != full] + [full]  # the full text is the last resort
        for attempt in tries:
            if "," not in attempt and not PIN_CODE.search(attempt):
                found = await find_place(attempt, near)
                if found and city_words and not any(word in found["label"].casefold() for word in city_words):
                    found = None  # "Bandra" in Bihar is not "Bandra, Mumbai"
            else:
                hits = await _osm_search(attempt)
                # "Bandra West" matches "Bandra"; "Motilal Nehru Place" does not match "Nehru Place"
                exact = [h for h in hits if str(h.get("name", "")).casefold().startswith(locality.casefold())]
                # A qualified search counts only on an exact name match (else "Motilal Nehru Place" wins);
                # the last resort (the full text) takes the best available.
                hit = _best(exact or (hits if attempt == full else []), locality)
                found = _osm_label(hit, name) if hit else None
            if found:
                _osm_places[key] = found
                return found
            await asyncio.sleep(1.0)  # OpenStreetMap fair use: one request per second
    if key not in _osm_places:
        nearby = await _osm_search(name, near) if near else []
        exact_near = [h for h in nearby if str(h.get("name", "")).casefold() == name.casefold()]
        choice = _best(exact_near, name) or next((h for h in nearby if h.get("category", h.get("class")) in PLACE_CLASSES), None)
        if choice is None:
            if near:
                await asyncio.sleep(1.0)  # OpenStreetMap's fair-use limit: one request per second
            anywhere = await _osm_search(name)
            choice = _best(anywhere, name) if anywhere else (nearby[0] if nearby else None)
        _osm_places[key] = _osm_label(choice, name) if choice else None
    if _osm_places[key] is not None:
        return _osm_places[key]
    # Fallback: Open-Meteo city search (no rate limit)
    city_key = name.casefold()
    if city_key not in _places:
        geo = await _http().get("https://geocoding-api.open-meteo.com/v1/search",
                                params={"name": name, "count": 1, "language": "en", "format": "json"})
        geo.raise_for_status()
        found = geo.json().get("results") or []
        _places[city_key] = found[0] if found else None
    place = _places[city_key]
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
            headers=OSM_HEADERS)
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


def _wind_words(kmh) -> str:
    try:
        kmh = float(kmh)
    except (TypeError, ValueError):
        return "wind unknown"
    for limit, words in ((2, "calm"), (12, "light breeze"), (20, "gentle breeze"), (29, "moderate breeze"),
                         (39, "fresh breeze"), (50, "strong wind"), (62, "near gale"), (88, "gale")):
        if kmh < limit:
            return words
    return "storm-force wind"


def _compass(degrees) -> str:
    try:
        return ("N", "NE", "E", "SE", "S", "SW", "W", "NW")[int((float(degrees) % 360 + 22.5) // 45) % 8]
    except (TypeError, ValueError):
        return ""


def _aqi_words(aqi) -> str:
    """US EPA AQI bands (India's CPCB scale differs; we say which scale)."""
    try:
        aqi = float(aqi)
    except (TypeError, ValueError):
        return "unknown"
    for limit, words in ((50, "good"), (100, "moderate"), (150, "unhealthy for sensitive groups"),
                         (200, "unhealthy"), (300, "very unhealthy")):
        if aqi <= limit:
            return words
    return "hazardous"


def _feels(max_c) -> str:
    """Plain-language day feel from the day's high (for 'is it hot/cold tomorrow?')."""
    try:
        t = float(max_c)
    except (TypeError, ValueError):
        return ""
    for limit, words in ((5, "very cold"), (12, "cold"), (18, "cool"), (25, "pleasant"), (30, "warm"),
                         (35, "hot"), (40, "very hot")):
        if t < limit:
            return words
    return "extremely hot"


async def _weather_data(latitude: float, longitude: float) -> dict:
    coords = (round(latitude, 2), round(longitude, 2))
    cached = _full.get(coords)
    if cached and time.monotonic() - cached[0] < FORECAST_TTL:
        return cached[1]
    response = await _http().get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": latitude, "longitude": longitude, "timezone": "auto", "forecast_days": 7,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,precipitation,rain,"
                   "snowfall,cloud_cover,wind_speed_10m,wind_direction_10m,wind_gusts_10m,visibility,is_day",
        "hourly": "temperature_2m,precipitation_probability,weather_code",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,"
                 "apparent_temperature_min,precipitation_probability_max,precipitation_sum,rain_sum,snowfall_sum,"
                 "wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant,uv_index_max,sunrise,sunset",
    })
    response.raise_for_status()
    data = response.json()
    _full[coords] = (time.monotonic(), data)
    return data


async def _air_data(latitude: float, longitude: float) -> dict:
    coords = (round(latitude, 2), round(longitude, 2))
    cached = _air.get(coords)
    if cached and time.monotonic() - cached[0] < FORECAST_TTL:
        return cached[1]
    try:
        response = await _http().get("https://air-quality-api.open-meteo.com/v1/air-quality", params={
            "latitude": latitude, "longitude": longitude, "timezone": "auto", "forecast_days": 3,
            "current": "us_aqi,pm2_5,pm10,nitrogen_dioxide,ozone,carbon_monoxide,dust",
            "hourly": "us_aqi,pm2_5"})
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError):
        data = {}
    _air[coords] = (time.monotonic(), data)
    return data


def _air_lines(air: dict, when: str) -> list[str]:
    current = air.get("current") or {}
    lines = []
    if current.get("us_aqi") is not None:
        lines.append(f"Air now: AQI {current['us_aqi']} ({_aqi_words(current['us_aqi'])}, US scale), "
                     f"PM2.5 {current.get('pm2_5', '?')} µg/m³, PM10 {current.get('pm10', '?')} µg/m³, "
                     f"NO2 {current.get('nitrogen_dioxide', '?')}, ozone {current.get('ozone', '?')} µg/m³.")
    hourly = air.get("hourly") or {}
    times, aqi = hourly.get("time", []), hourly.get("us_aqi", [])
    if when in {"tomorrow", "week"} and times and aqi:
        day = times[0][:10]
        tomorrow = [a for t, a in zip(times, aqi) if t[:10] > day and a is not None][:24]
        if tomorrow:
            lines.append(f"Air tomorrow: AQI {min(tomorrow)}–{max(tomorrow)} (worst {_aqi_words(max(tomorrow))}).")
    return lines


def _day_line(daily: dict, i: int, name: str) -> str:
    try:
        snow = daily["snowfall_sum"][i] or 0
        gusts = daily["wind_gusts_10m_max"][i]
        return (f"{name}: {_condition(daily['weather_code'][i])}, {daily['temperature_2m_min'][i]}–"
                f"{daily['temperature_2m_max'][i]}°C (feels {daily['apparent_temperature_min'][i]}–"
                f"{daily['apparent_temperature_max'][i]}°C, {_feels(daily['temperature_2m_max'][i])}), "
                f"rain chance {daily['precipitation_probability_max'][i]}% ({daily['rain_sum'][i]} mm rain"
                f"{f', {snow} cm snow' if snow else ''}), wind {_wind_words(daily['wind_speed_10m_max'][i])} "
                f"up to {daily['wind_speed_10m_max'][i]} km/h from {_compass(daily['wind_direction_10m_dominant'][i])}"
                f"{f', gusts {gusts} km/h' if gusts else ''}, UV {daily['uv_index_max'][i]}, "
                f"sunrise {str(daily['sunrise'][i])[-5:]}, sunset {str(daily['sunset'][i])[-5:]}.")
    except (KeyError, IndexError, TypeError):
        return f"{name}: forecast unavailable."


def _compare(daily: dict, a: int, b: int, a_name: str, b_name: str) -> str:
    """'Is tomorrow hotter/colder/rainier than today?' answered with numbers."""
    try:
        dmax = daily["temperature_2m_max"][b] - daily["temperature_2m_max"][a]
        dmin = daily["temperature_2m_min"][b] - daily["temperature_2m_min"][a]
        drain = (daily["precipitation_probability_max"][b] or 0) - (daily["precipitation_probability_max"][a] or 0)
    except (KeyError, IndexError, TypeError):
        return ""
    def words(delta: float, warm: str, cool: str) -> str:
        return "about the same" if abs(delta) < 1 else f"{abs(delta):.1f}°C {warm if delta > 0 else cool}"
    return (f"{b_name} vs {a_name}: daytime {words(dmax, 'hotter', 'cooler')}, night {words(dmin, 'warmer', 'colder')}, "
            f"rain chance {drain:+d} points.")


async def forecast(latitude: float, longitude: float, label: str, when: str = "now") -> str:
    """Conditions + outlook: now | next_hours | today | tomorrow | week, with air quality and comparisons."""
    data = await _weather_data(latitude, longitude)
    air = await _air_data(latitude, longitude)
    current, daily, hourly = data.get("current", {}), data.get("daily", {}), data.get("hourly", {})
    updated = str(current.get("time", ""))[-5:]
    rain_now = current.get("rain") or 0
    snow_now = current.get("snowfall") or 0
    visibility = current.get("visibility")
    lines = [f"{label} (updated {updated} local time; Open-Meteo):",
             f"Now: {_condition(current.get('weather_code'))}, {current.get('temperature_2m', '?')}°C "
             f"(feels {current.get('apparent_temperature', '?')}°C), humidity {current.get('relative_humidity_2m', '?')}%, "
             f"clouds {current.get('cloud_cover', '?')}%, {_wind_words(current.get('wind_speed_10m'))} "
             f"{current.get('wind_speed_10m', '?')} km/h from {_compass(current.get('wind_direction_10m'))}"
             f" (gusts {current.get('wind_gusts_10m', '?')} km/h)"
             f"{f', raining {rain_now} mm/h' if rain_now else ''}{f', snowing {snow_now} cm/h' if snow_now else ''}"
             f"{f', visibility {round(visibility / 1000, 1)} km' if isinstance(visibility, (int, float)) else ''}."]
    lines += _air_lines(air, when)
    if when in {"next_hours", "today", "now"}:
        times = hourly.get("time", [])
        now_key = str(current.get("time", ""))[:13]
        start = next((i for i, t in enumerate(times) if str(t)[:13] >= now_key), 0)
        upcoming = [f"{str(times[i])[-5:]} {hourly['temperature_2m'][i]}°C {hourly['precipitation_probability'][i]}% rain"
                    for i in range(start, min(start + 12, len(times)), 3)]
        if upcoming:
            lines.append("Next hours: " + "; ".join(upcoming) + ".")
    if when in {"today", "now"}:
        lines.append(_day_line(daily, 0, "Today"))
    if when == "tomorrow":
        lines.append(_day_line(daily, 0, "Today"))
        lines.append(_day_line(daily, 1, "Tomorrow"))
        lines.append(_compare(daily, 0, 1, "today", "Tomorrow"))
    if when == "week":
        names = ["Today", "Tomorrow"] + [str(d) for d in daily.get("time", [])[2:]]
        lines.extend(_day_line(daily, i, names[i]) for i in range(min(7, len(daily.get("time", [])))))
        if len(daily.get("time", [])) > 1:
            highs = daily["temperature_2m_max"]
            hottest, coolest = highs.index(max(highs)), highs.index(min(highs))
            wettest = daily["precipitation_probability_max"].index(max(daily["precipitation_probability_max"]))
            lines.append(f"Week: hottest {names[hottest]} ({highs[hottest]}°C), coolest {names[coolest]} "
                         f"({highs[coolest]}°C), most likely rain {names[wettest]} "
                         f"({daily['precipitation_probability_max'][wettest]}%).")
    return "\n".join(line for line in lines if line)
