"""Regression tests for outbound action safety and Home Assistant inputs."""
from __future__ import annotations

import asyncio

from atulya import actions
from atulya.brain import assess


def test_twilio_say_text_cannot_inject_xml_verbs():
    twiml = actions._twilio_say_twiml("hello</Say><Redirect>https://evil.test</Redirect>")
    assert twiml == "<Response><Say>hello&lt;/Say&gt;&lt;Redirect&gt;https://evil.test&lt;/Redirect&gt;</Say></Response>"


def test_external_actions_require_confirmation():
    for name in ("twilio_sms", "twilio_call", "ha_call_service"):
        assert assess(name, {}).needs_confirmation, name


def test_home_assistant_rejects_invalid_entity_ids_before_network(monkeypatch):
    monkeypatch.setenv("HOME_ASSISTANT_URL", "https://ha.example")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "secret")
    result = asyncio.run(actions.ha_state("../api/config"))
    assert result.startswith("Entity ID must look like")


def test_home_assistant_service_keeps_target_entity_authoritative(monkeypatch):
    monkeypatch.setenv("HOME_ASSISTANT_URL", "https://ha.example")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "secret")
    calls = []

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

    class Client:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return None

        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return Response()

    monkeypatch.setattr(actions.httpx, "AsyncClient", Client)
    result = asyncio.run(actions.ha_call_service(
        "light", "turn_on", "light.kitchen", {"entity_id": "lock.front_door", "brightness": 50}
    ))
    assert "called on light.kitchen" in result
    assert calls[0][0] == "https://ha.example/api/services/light/turn_on"
    assert calls[0][1]["json"] == {"entity_id": "light.kitchen", "brightness": 50}


def test_home_assistant_rejects_pathlike_service_names(monkeypatch):
    monkeypatch.setenv("HOME_ASSISTANT_URL", "https://ha.example")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "secret")
    result = asyncio.run(actions.ha_call_service("light/../api", "turn_on", "light.kitchen"))
    assert "domain and service" in result
