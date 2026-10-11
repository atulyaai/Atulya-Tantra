"""Current weather lookup using Open-Meteo's public APIs."""
import httpx


async def weather(city: str) -> str:
    city = city.strip()
    if not city or len(city) > 100:
        raise ValueError("Tell me the city, for example: weather in Bengaluru")
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
        geo = await client.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": city, "count": 1, "language": "en", "format": "json"})
        geo.raise_for_status()
        results = geo.json().get("results") or []
        if not results:
            return f"I couldn't find a location named {city}."
        place = results[0]
        forecast = await client.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": place["latitude"], "longitude": place["longitude"],
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
            "timezone": "auto",
        })
        forecast.raise_for_status()
        current = forecast.json().get("current", {})
    code = int(current.get("weather_code", -1))
    conditions = {0:"clear",1:"mostly clear",2:"partly cloudy",3:"overcast",45:"foggy",48:"foggy",
                  51:"light drizzle",53:"drizzle",55:"heavy drizzle",61:"light rain",63:"rain",65:"heavy rain",
                  71:"light snow",73:"snow",75:"heavy snow",80:"rain showers",81:"rain showers",82:"heavy rain showers",
                  95:"thunderstorm",96:"thunderstorm with hail",99:"thunderstorm with hail"}.get(code, "conditions unavailable")
    label = ", ".join(str(x) for x in (place.get("name"), place.get("admin1"), place.get("country") if place.get("country_code") else None) if x)
    return (f"{label}: {conditions}, {current.get('temperature_2m', '?')}°C "
            f"(feels like {current.get('apparent_temperature', '?')}°C), humidity {current.get('relative_humidity_2m', '?')}%, "
            f"wind {current.get('wind_speed_10m', '?')} km/h. Source: Open-Meteo.")
