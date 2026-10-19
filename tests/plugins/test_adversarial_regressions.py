"""Behavioral regressions for tool execution, connections and URL isolation.

Regression cases reproduced during adversarial review.
No production requests, private credentials or real device actions are used.
"""

import asyncio
import json
import socket
import sqlite3
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


import httpx

from tools.plugins.brain import Brain, Message, ToolCall
from tools.plugins.information import google_api, search
from tools.plugins.system import smart_home
from tools.plugins.system.agents import AgentHub

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class Box:
    MAX_ROUNDS = 2
    schemas = [{"type": "function", "function": {"name": "save_note", "parameters": {"type": "object"}}}]

    def __init__(self):
        self.calls = []

    def instructions(self):
        return "Use save_note for note requests."

    async def call(self, name, arguments):
        self.calls.append(name)
        return "Saved note #1"


def test_action_is_not_silently_disabled_for_completion_only_provider():
    class Provider:
        name = model = "test"

        async def complete(self, messages):
            if messages[-1].role == "tool":
                return "Saved."
            return '<tool_call>{"name":"save_note","arguments":{}}</tool_call>'

    box = Box()
    reply = asyncio.run(Brain(Provider()).respond_with_tools([Message(role="user", content="Save a note")], box))
    assert box.calls == ["save_note"], f"No action executed. User received: {reply.text!r}"


def test_final_round_does_not_execute_more_native_actions():
    class Provider:
        name = model = "test"

        async def stream(self, messages, tools=None):
            yield ToolCall("first" if tools else "closed-round", "save_note", "{}")
            if not tools:
                yield "Finished."

    box = Box()
    asyncio.run(Brain(Provider()).respond_with_tools([Message(role="user", content="Save one note")], box))
    assert box.calls == ["save_note"], "A second side effect ran after tools were closed"


def test_calendar_successful_delete_accepts_empty_204(monkeypatch):
    async def token(*args):
        return "test-token"

    monkeypatch.setattr(google_api, "get_access_token", token)
    monkeypatch.setattr(google_api, "_load_tokens", lambda *args: {})
    original = httpx.AsyncClient

    def handler(request):
        assert request.method == "DELETE"
        return httpx.Response(204)

    monkeypatch.setattr(
        google_api.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler))
    )
    assert "Deleted" in asyncio.run(google_api.calendar_delete("alice", "test-event"))


def test_invalid_smart_home_action_must_not_turn_device_off(monkeypatch):
    monkeypatch.setattr(smart_home, "HASS_URL", "https://home.test")
    monkeypatch.setattr(smart_home, "HASS_TOKEN", "test-token")
    original = httpx.AsyncClient
    calls = []

    def handler(request):
        calls.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json=[])

    monkeypatch.setattr(
        smart_home.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler))
    )
    response = asyncio.run(smart_home.execute_smart_home("desk lamp", "unsupported_action"))
    assert calls == [], f"Invalid action sent a real service request: {calls}; reply: {response}"


def test_disconnected_running_job_eventually_becomes_unconfirmed(tmp_path):
    hub = AgentHub(tmp_path)
    hub.pair("alice", "Phone", ["ping"])
    job = hub.enqueue("alice", "Phone", "ping")
    hub.poll("alice", "Phone")
    with sqlite3.connect(hub.path) as db:
        db.execute("UPDATE jobs SET updated=? WHERE id=?", (time.time() - 300, job["id"]))
    assert hub.jobs("alice")[0]["status"] == "unconfirmed", (
        "Offline device never polls again; UI remains running forever"
    )


def test_qualified_entity_and_zero_brightness_are_preserved(monkeypatch):
    monkeypatch.setattr(smart_home, "HASS_URL", "https://home.test")
    monkeypatch.setattr(smart_home, "HASS_TOKEN", "test-token")
    original = httpx.AsyncClient
    sent = []

    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=[])

    monkeypatch.setattr(smart_home.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler)))
    result = asyncio.run(smart_home.execute_smart_home("light.desk_lamp", "on", brightness=0))
    assert sent == [{"entity_id": "light.desk_lamp", "brightness_pct": 0}]
    assert "0%" in result


def test_control_direct_private_url_is_refused():
    assert asyncio.run(search.public_address("http://127.0.0.1/")) is not None


def test_dns_rebinding_cannot_read_loopback_after_public_dns_check(monkeypatch):
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"LOCAL_ONLY_TEST_MARKER")

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    original_resolver = socket.getaddrinfo
    lookups = []

    def rebind(host, port, *args, **kwargs):
        text = host.decode() if isinstance(host, bytes) else host
        if text != "controlled-rebind.invalid":
            return original_resolver(host, port, *args, **kwargs)
        lookups.append(text)
        address = "93.184.216.34" if len(lookups) == 1 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, int(port)))]

    monkeypatch.setattr(socket, "getaddrinfo", rebind)
    original_connect = socket.socket.connect

    def local_only_connection(sock, address):
        if address[0] not in {"127.0.0.1", "::1"}:
            raise OSError("Test blocks all non-loopback connections")
        return original_connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", local_only_connection)

    async def exercise():
        async with httpx.AsyncClient(trust_env=False, timeout=3) as client:
            monkeypatch.setattr(search, "_client", lambda: client)
            return await search.read_page(f"http://controlled-rebind.invalid:{server.server_port}/test-secret")

    try:
        reply = asyncio.run(exercise())
        assert hits == [], f"Private loopback was fetched after DNS changed; lookups={len(lookups)}, result={reply!r}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
