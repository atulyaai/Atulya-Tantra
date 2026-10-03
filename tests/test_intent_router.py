"""Tests for the deterministic intent router."""
from __future__ import annotations

import pytest

from atulya.agent.intent_router import route_intent, route_and_execute
from atulya.agent import tools as agent_tools


class TestIntentRouting:
    def test_turn_on_light(self):
        r = route_intent("turn on the living room light")
        assert r is not None
        assert r.tool == "home_control"
        assert r.arguments == {"device_id": "living_room_light", "action": "on"}

    def test_turn_off_kitchen(self):
        r = route_intent("switch off the kitchen light")
        assert r.tool == "home_control"
        assert r.arguments["device_id"] == "kitchen_light"
        assert r.arguments["action"] == "off"

    def test_lock_and_unlock_door(self):
        assert route_intent("lock the front door").arguments["action"] == "lock"
        assert route_intent("unlock the door").arguments["action"] == "unlock"

    def test_set_thermostat(self):
        r = route_intent("set the thermostat to 21 degrees")
        assert r.tool == "home_control"
        assert r.arguments == {"device_id": "thermostat", "action": "set_temperature", "value": "21"}

    def test_reminder(self):
        r = route_intent("remind me to call mom in 10 minutes")
        assert r.tool == "set_reminder"
        assert "call mom" in r.arguments["message"]
        assert "10" in r.arguments["time_str"]

    def test_weather(self):
        r = route_intent("what's the weather in Delhi")
        assert r.tool == "get_weather"
        assert r.arguments["location"].lower() == "delhi"

    def test_forecast(self):
        r = route_intent("give me the forecast for London")
        assert r.tool == "get_forecast"
        assert r.arguments["location"].lower() == "london"

    def test_time(self):
        assert route_intent("what time is it").tool == "current_time"

    def test_check_email(self):
        assert route_intent("check my email").tool == "fetch_emails"

    def test_calendar(self):
        assert route_intent("what's on my calendar").tool == "calendar_list"

    def test_calculate(self):
        r = route_intent("calculate 2 + 2 * 3")
        assert r.tool == "calculate"
        assert "2" in r.arguments["expression"]

    @pytest.mark.parametrize("msg", [
        "hello there",
        "who are you?",
        "tell me a story about a dragon",
        "",
        "what do you think about philosophy",
    ])
    def test_no_match_falls_through(self, msg):
        assert route_intent(msg) is None

    async def test_route_and_execute_runs_tool(self):
        out = await route_and_execute("turn on the kitchen light")
        assert out is not None
        assert "kitchen" in out.lower() and "on" in out.lower()

    async def test_route_and_execute_none_for_chat(self):
        assert await route_and_execute("tell me about the weather on mars generally") is None

    def test_routed_tools_are_registered(self):
        """Every tool the router can emit must exist in the tool registry."""
        registry = set(agent_tools.TOOL_REGISTRY)
        for msg in [
            "turn on the bedroom light",
            "remind me to stretch in 5 minutes",
            "weather in Paris",
            "what time is it",
            "check my inbox",
            "what's my schedule",
            "calculate 5 * 5",
        ]:
            routed = route_intent(msg)
            assert routed is not None, msg
            assert routed.tool in registry, f"{routed.tool} not registered"


class TestWebsites:
    @pytest.mark.parametrize("text,args", [
        ("open youtube", {"site": "youtube"}),
        ("Open YouTube.", {"site": "youtube"}),
        ("hey atulya open gmail please", {"site": "gmail"}),
        ("play lofi music on youtube", {"site": "youtube", "query": "lofi music"}),
        ("search youtube for iron man trailer", {"site": "youtube", "query": "iron man trailer"}),
        ("search for cricket score on google", {"site": "google", "query": "cricket score"}),
        ("google weather in delhi", {"site": "google", "query": "weather in delhi"}),
    ])
    def test_routes_to_open_website(self, text, args):
        r = route_intent(text)
        assert r is not None and r.tool == "open_website"
        assert r.arguments == args
        assert r.tool in agent_tools.TOOL_REGISTRY

    @pytest.mark.parametrize("text", ["open the door", "open notepad", "tell me about youtube"])
    def test_leaves_other_sentences_alone(self, text):
        r = route_intent(text)
        assert r is None or r.tool != "open_website"

    async def test_opens_only_known_sites(self, monkeypatch):
        import webbrowser

        opened = []
        monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url) or True)
        assert await agent_tools.open_website("youtube", "lofi beats") == "Searching YouTube for lofi beats."
        assert opened == ["https://www.youtube.com/results?search_query=lofi+beats"]
        assert "don't know" in await agent_tools.open_website("evil.example")
        assert len(opened) == 1

    async def test_spoken_time(self):
        out = await agent_tools.current_time()
        assert out.startswith("It's ") and ("AM" in out or "PM" in out)
