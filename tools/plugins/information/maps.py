"""Maps: places near me, routes and travel time via OpenStreetMap/OSRM."""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_osrm_client: httpx.AsyncClient | None = None
_osm_client: httpx.AsyncClient | None = None


def _osrm() -> httpx.AsyncClient:
    global _osrm_client
    if _osrm_client is None or _osrm_client.is_closed:
        _osrm_client = httpx.AsyncClient(
            base_url="https://router.project-osrm.org",
            timeout=httpx.Timeout(10, connect=5),
            headers={"User-Agent": "Atulya-Tantra/1.0"},
        )
    return _osrm_client


def _osm() -> httpx.AsyncClient:
    global _osm_client
    if _osm_client is None or _osm_client.is_closed:
        _osm_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10, connect=5),
            headers={"User-Agent": "Atulya-Tantra/1.0 (+https://atulya.atulvij.com)"},
        )
    return _osm_client


async def search_places(query: str, near: tuple[float, float] | None = None, limit: int = 5) -> list[dict]:
    """Search for places (pharmacies, hospitals, shops, etc.) near a location."""
    client = _osm()
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": min(limit, 10),
        "addressdetails": 1,
    }
    if near:
        d = 0.2
        params.update(viewbox=f"{near[1]-d},{near[0]+d},{near[1]+d},{near[0]-d}", bounded=1)
    try:
        resp = await client.get("https://nominatim.openstreetmap.org/search", params=params)
        resp.raise_for_status()
        results = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Place search failed: %s", type(exc).__name__)
        return []
    places = []
    for hit in results[:limit]:
        addr = hit.get("address", {})
        name = hit.get("name", "")
        if not name:
            name = addr.get("amenity", addr.get("shop", addr.get("healthcare", "")))
        display = hit.get("display_name", "")
        places.append({
            "name": name or display.split(",")[0],
            "display": display,
            "lat": float(hit["lat"]),
            "lon": float(hit["lon"]),
            "type": hit.get("type", hit.get("class", "")),
            "address": addr,
        })
    return places


async def route_duration(
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
    profile: str = "driving",
) -> dict | None:
    """Get route duration and distance via OSRM."""
    client = _osrm()
    coords = f"{from_lon},{from_lat};{to_lon},{to_lat}"
    try:
        resp = await client.get(
            f"/route/v1/{profile}/{coords}",
            params={"overview": "false", "steps": "false"},
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Route lookup failed: %s", type(exc).__name__)
        return None
    routes = data.get("routes", [])
    if not routes:
        return None
    route = routes[0]
    return {
        "duration_seconds": route.get("duration", 0),
        "duration_minutes": round(route.get("duration", 0) / 60),
        "distance_km": round(route.get("distance", 0) / 1000, 1),
    }


async def route_text(
    from_label: str,
    from_lat: float,
    from_lon: float,
    to_label: str,
    to_lat: float,
    to_lon: float,
) -> str:
    """Human-readable route summary."""
    result = await route_duration(from_lat, from_lon, to_lat, to_lon)
    if result is None:
        return f"I couldn't find a route from {from_label} to {to_label}."
    mins = result["duration_minutes"]
    km = result["distance_km"]
    if mins < 60:
        return f"{from_label} → {to_label}: about {mins} min ({km} km) by car."
    hours = mins // 60
    rem = mins % 60
    return f"{from_label} → {to_label}: about {hours} h {rem} min ({km} km) by car."
