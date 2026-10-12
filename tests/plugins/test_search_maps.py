"""H4 tests: web search, read page, places near me, route time."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

from tools.plugins.information.maps import route_duration, route_text, search_places
from tools.plugins.information.search import read_page, search_web
from tools.plugins.registry import PluginContext
from tools.plugins.toolkit import _near


def test_search_web_returns_results() -> None:
    """search_web parses DuckDuckGo results."""
    mock_response = {
        "Heading": "Python (programming language)",
        "AbstractText": "Python is a high-level programming language.",
        "AbstractURL": "https://en.wikipedia.org/wiki/Python_(programming_language)",
        "RelatedTopics": [
            {"Text": "Python is widely used in data science", "FirstURL": "https://example.com/python-ds"},
            {"Text": "Python was created by Guido van Rossum", "FirstURL": "https://example.com/guido"},
        ],
    }

    async def run():
        with patch("tools.plugins.information.search._client") as mock_client:
            mock_resp = Mock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = lambda: None
            mock_client.return_value.get = AsyncMock(return_value=mock_resp)
            results = await search_web("Python programming")
        return results

    results = asyncio.run(run())
    assert len(results) >= 1
    assert "Python" in results[0]["title"]
    assert results[0]["url"].startswith("https://")


def test_search_web_handles_failure() -> None:
    """search_web returns empty list on failure."""
    import httpx

    async def run():
        with patch("tools.plugins.information.search._client") as mock_client:
            mock_client.return_value.get = AsyncMock(side_effect=httpx.ConnectError("network error"))
            results = await search_web("test")
        return results

    results = asyncio.run(run())
    assert results == []


def test_read_page_extracts_text() -> None:
    """read_page strips HTML and returns text."""
    html = "<html><head><style>body{}</style></head><body><h1>Hello</h1><p>World</p><script>alert(1)</script></body></html>"

    async def run():
        with patch("tools.plugins.information.search._client") as mock_client:
            mock_resp = Mock()
            mock_resp.text = html
            mock_resp.raise_for_status = lambda: None
            mock_client.return_value.get = AsyncMock(return_value=mock_resp)
            text = await read_page("https://example.com")
        return text

    text = asyncio.run(run())
    assert "Hello" in text
    assert "World" in text
    assert "<script>" not in text
    assert "<style>" not in text


def test_search_places_returns_results() -> None:
    """search_places parses Nominatim results."""
    mock_results = [
        {
            "name": "Apollo Pharmacy",
            "display_name": "Apollo Pharmacy, Connaught Place, New Delhi",
            "lat": "28.6315",
            "lon": "77.2167",
            "type": "amenity",
            "address": {"amenity": "pharmacy", "city": "New Delhi"},
        }
    ]

    async def run():
        with patch("tools.plugins.information.maps._osm") as mock_client:
            mock_resp = Mock()
            mock_resp.json.return_value = mock_results
            mock_resp.raise_for_status = lambda: None
            mock_client.return_value.get = AsyncMock(return_value=mock_resp)
            places = await search_places("pharmacy", near=(28.63, 77.21))
        return places

    places = asyncio.run(run())
    assert len(places) == 1
    assert places[0]["name"] == "Apollo Pharmacy"
    assert places[0]["lat"] == 28.6315


def test_route_duration_returns_result() -> None:
    """route_duration parses OSRM response."""
    mock_response = {
        "routes": [{"duration": 1800, "distance": 15000}]  # 30 min, 15 km
    }

    async def run():
        with patch("tools.plugins.information.maps._osrm") as mock_client:
            mock_resp = Mock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = lambda: None
            mock_client.return_value.get = AsyncMock(return_value=mock_resp)
            result = await route_duration(28.63, 77.21, 28.56, 77.10)
        return result

    result = asyncio.run(run())
    assert result is not None
    assert result["duration_minutes"] == 30
    assert result["distance_km"] == 15.0


def test_route_text_formats_output() -> None:
    """route_text returns human-readable summary."""
    async def run():
        with patch("tools.plugins.information.maps._osrm") as mock_client:
            mock_resp = Mock()
            mock_resp.json.return_value = {"routes": [{"duration": 3600, "distance": 42000}]}
            mock_resp.raise_for_status = lambda: None
            mock_client.return_value.get = AsyncMock(return_value=mock_resp)
            text = await route_text("Home", 28.63, 77.21, "Office", 28.56, 77.10)
        return text

    text = asyncio.run(run())
    assert "Home" in text
    assert "Office" in text
    assert "60 min" in text or "1 h" in text
    assert "42" in text


def test_route_text_handles_no_route() -> None:
    """route_text reports when no route is found."""
    async def run():
        with patch("tools.plugins.information.maps._osrm") as mock_client:
            mock_resp = Mock()
            mock_resp.json.return_value = {"routes": []}
            mock_resp.raise_for_status = lambda: None
            mock_client.return_value.get = AsyncMock(return_value=mock_resp)
            text = await route_text("A", 0, 0, "B", 0, 0)
        return text

    text = asyncio.run(run())
    assert "couldn't find a route" in text


def test_near_uses_device_location() -> None:
    """_near prefers device location over saved home."""
    ctx = PluginContext(
        owner_id="owner",
        memory=object(),
        calendar=object(),
        user_id="admin",
        profile=Mock(),  # regular mock, not async
    )
    ctx.profile.location.return_value = {"lat": 28.63, "lon": 77.21, "age_minutes": 5}
    result = _near(ctx)
    assert result == (28.63, 77.21)
