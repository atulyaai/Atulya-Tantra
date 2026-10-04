"""Tests for the cognition layer: toolbelt, safety, kernel, triggers, brain
tiers, heartbeat events, Home Assistant bridge, and the routes that use them."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from atulya.events import EventBus


class StubRouter:
    """Stands in for the provider router so no real model/network is used."""

    async def chat(self, *args, **kwargs):
        return ("[brain reply]", "stub")


def make_llm():
    from atulya.llm import AtulyaLLM

    llm = AtulyaLLM()
    llm.router = StubRouter()
    return llm


def make_kernel():
    from atulya.cognition.kernel import CognitiveKernel

    bus = EventBus()
    seen: list[str] = []
    bus.subscribe("*", lambda e: seen.append(e.type))
    return CognitiveKernel(llm=make_llm(), events=bus), seen


# ── toolbelt ────────────────────────────────────────────────────────────────

class TestToolbelt:
    def test_unified_registry_has_assistant_tools(self):
        from atulya.cognition.toolbelt import build_unified_registry

        names = {t["name"] for t in build_unified_registry().list_tools()}
        assert {"home_control", "set_reminder", "get_weather", "web_search", "file_read"} <= names
        assert "download_vision_model" not in names and "configure_email" not in names

    def test_adapter_schema_requires_only_params_without_default(self):
        from atulya.cognition.toolbelt import build_unified_registry

        schema = build_unified_registry().get("home_control").parameters
        assert set(schema["properties"]) == {"device_id", "action", "value"}
        assert schema["required"] == ["device_id", "action"]

    def test_live_brain_advertises_assistant_tools_first(self):
        schemas = make_llm()._build_tool_schemas()
        names = [s["function"]["name"] for s in schemas]
        assert names[0] == "home_control"
        assert schemas[0]["function"]["parameters"]["properties"]
        assert len(names) == 14

    def test_live_brain_executes_assistant_tool(self):
        step = asyncio.run(make_llm().run_tool(
            {"tool": "home_control", "arguments": {"device_id": "kitchen_light", "action": "on"}}))
        assert step["success"] and "Kitchen Light turned on" in step["output"]

    def test_exec_permission_cannot_be_supplied_by_caller(self):
        """allow_exec / allow_list are server policy, not call arguments."""
        from atulya.llm import AtulyaLLM
        from atulya.capabilities import Tool, ToolRegistry, ToolResult

        received = {}

        class Exec(Tool):
            name = "exec"
            description = "exec"

            async def execute(self, **kwargs):
                received.update(kwargs)
                return ToolResult(success=True, output="ran")

        reg = ToolRegistry()
        reg.register(Exec())
        llm = AtulyaLLM(tools=reg, allow_exec=False)
        asyncio.run(llm.run_tool({"tool": "exec", "arguments": {
            "command": "rm -rf /", "allow_exec": True, "allow_list": ["rm"]}}))
        assert received["allow_exec"] is False
        assert "allow_list" not in received


# ── safety ──────────────────────────────────────────────────────────────────

class TestSafety:
    @pytest.mark.parametrize("tool,args,level", [
        ("home_control", {"action": "unlock"}, "confirm"),
        ("home_control", {"action": "lock"}, "allow"),
        ("home_control", {"action": "on"}, "allow"),
        ("send_email", {}, "confirm"),
        ("calendar_remove", {}, "confirm"),
        ("exec", {}, "confirm"),
        ("get_weather", {}, "allow"),
    ])
    def test_policy(self, tool, args, level):
        from atulya.cognition.safety import assess

        assert assess(tool, args).level == level

    def test_auto_approve_override(self, monkeypatch):
        from atulya.cognition.safety import assess

        monkeypatch.setenv("ATULYA_AUTO_APPROVE", "home_control:unlock, send_email")
        assert assess("home_control", {"action": "unlock"}).level == "allow"
        assert assess("send_email", {}).level == "allow"
        assert assess("calendar_remove", {}).level == "confirm"

    def test_describe_action(self):
        from atulya.cognition.safety import describe_action

        assert describe_action("home_control", {"device_id": "front_door", "action": "unlock"}) == "unlock the front door"
        assert describe_action("home_control", {"device_id": "kitchen_light", "action": "on"}) == "turn on the kitchen light"


# ── kernel ──────────────────────────────────────────────────────────────────

class TestKernel:
    def test_confirmation_intent(self):
        from atulya.cognition.kernel import confirmation_intent

        assert confirmation_intent("yes please") == "affirm"
        assert confirmation_intent("go ahead") == "affirm"
        assert confirmation_intent("no thanks") == "deny"
        assert confirmation_intent("don't do it") == "deny"
        assert confirmation_intent("stop the music") is None  # a new command, not a cancel
        assert confirmation_intent("ha ha") is None           # laughter never confirms
        assert confirmation_intent("") is None

    def test_safe_action_runs_immediately(self):
        kernel, seen = make_kernel()
        r = asyncio.run(kernel.handle("turn on the bedroom light", user="u"))
        assert r.text == "Bedroom Light turned on." and r.provider == "Atulya Kernel"
        assert not r.needs_approval and "action.executed" in seen

    def test_risky_action_held_then_confirmed(self):
        kernel, seen = make_kernel()

        async def run():
            held = await kernel.handle("unlock the front door", user="u")
            assert held.needs_approval and held.pending_tool["origin"] == "kernel"
            assert "Just to confirm" in held.text
            done = await kernel.handle("yes", user="u")
            assert done.text == "Front Door is now unlocked."
            assert kernel.pending_action("u") is None

        asyncio.run(run())
        assert seen.count("action.pending") == 1 and "action.executed" in seen

    def test_deny_cancels(self):
        kernel, seen = make_kernel()

        async def run():
            await kernel.handle("unlock the front door", user="u")
            r = await kernel.handle("no", user="u")
            assert r.text == "Okay, I won't unlock the front door."

        asyncio.run(run())
        assert "action.cancelled" in seen

    def test_unrelated_message_drops_hold_so_stray_yes_cannot_release(self):
        kernel, _ = make_kernel()

        async def run():
            await kernel.handle("unlock the front door", user="u")
            await kernel.handle("ha ha", user="u")          # conversation moved on
            assert kernel.pending_action("u") is None
            r = await kernel.handle("yes", user="u")        # goes to the brain, unlocks nothing
            assert r.text == "[brain reply]"

        asyncio.run(run())

    def test_holds_are_per_user(self):
        kernel, _ = make_kernel()

        async def run():
            await kernel.handle("unlock the front door", user="alice")
            r = await kernel.handle("yes", user="mallory")
            assert r.text == "[brain reply]"
            assert kernel.pending_action("alice") is not None

        asyncio.run(run())

    def test_ui_approval_round_trip(self):
        kernel, _ = make_kernel()

        admin = {"username": "u", "role": "admin"}

        async def run():
            held = await kernel.handle("unlock the front door", user=admin)
            r = await kernel.handle("", user=admin, approved_tool=held.pending_tool)
            assert r.text == "Front Door is now unlocked."

        asyncio.run(run())

    def test_non_admin_can_do_everyday_actions_but_not_risky_ones(self):
        kernel, seen = make_kernel()
        guest = {"username": "guest", "role": "user"}
        admin = {"username": "owner", "role": "admin"}

        async def run():
            lights = await kernel.handle("turn on the kitchen light", user=guest)
            assert lights.text == "Kitchen Light turned on."
            denied = await kernel.handle("unlock the front door", user=guest)
            assert denied.text.startswith("Sorry — only an admin can unlock the front door")
            assert not denied.needs_approval and kernel.pending_action(guest) is None
            held = await kernel.handle("unlock the front door", user=admin)
            assert held.needs_approval

        asyncio.run(run())
        assert "action.denied" in seen

    def test_non_admin_cannot_approve_risky_actions(self):
        kernel, _ = make_kernel()
        guest = {"username": "guest", "role": "user"}
        forged = {"tool": "home_control", "arguments": {"device_id": "front_door", "action": "unlock"},
                  "origin": "kernel"}
        llm_origin = {"tool": "send_email", "arguments": {"to": "x@y.z", "subject": "s", "body": "b"}}

        async def run():
            r1 = await kernel.handle("", user=guest, approved_tool=forged)
            r2 = await kernel.handle("", user=guest, approved_tool=llm_origin)
            assert r1.text.startswith("Sorry — only an admin")
            assert r2.text.startswith("Sorry — only an admin can send an email")

        asyncio.run(run())

    def test_automation_source_is_pre_authorized(self):
        kernel, _ = make_kernel()
        r = asyncio.run(kernel.handle("unlock the front door", user="automation", source="automation"))
        assert r.text == "Front Door is now unlocked." and not r.needs_approval

    def test_open_conversation_goes_to_brain(self):
        kernel, _ = make_kernel()
        r = asyncio.run(kernel.handle("tell me a joke", user="u"))
        assert r.text == "[brain reply]" and r.provider == "stub"

    def test_stream_renders_kernel_actions_as_events(self):
        kernel, _ = make_kernel()

        async def run():
            return [e async for e in kernel.stream("unlock the front door", user="u")]

        events = asyncio.run(run())
        assert "".join(e.content for e in events if e.type == "token").startswith("Just to confirm")
        done = events[-1]
        assert done.type == "done" and done.metadata["needs_approval"] is True

    def test_tools_the_brain_runs_natively_are_published(self):
        from atulya.cognition.kernel import CognitiveKernel
        from atulya.llm import LLMResponse

        class ToolUsingBrain:
            async def ask(self, prompt, **kwargs):
                return LLMResponse(text="done", provider="b", tool_steps=[
                    {"tool": "get_weather", "arguments": {"location": "Pune"}, "success": True, "output": "sunny"}])

        bus = EventBus()
        seen = []
        bus.subscribe("action.executed", lambda e: seen.append(e.payload))
        asyncio.run(CognitiveKernel(llm=ToolUsingBrain(), events=bus).handle("how's the sky", user="u"))
        assert seen and seen[0]["tool"] == "get_weather" and seen[0]["via"] == "brain"

    def test_trace_records_real_stages(self):
        kernel, _ = make_kernel()
        admin = {"username": "a", "role": "admin"}
        guest = {"username": "g", "role": "user"}

        async def run():
            direct = await kernel.handle("turn on the kitchen light", user=admin)
            held = await kernel.handle("unlock the front door", user=admin)
            confirmed = await kernel.handle("yes", user=admin)
            refused = await kernel.handle("unlock the front door", user=guest)
            chat = await kernel.handle("tell me a joke", user=admin)
            return direct, held, confirmed, refused, chat

        direct, held, confirmed, refused, chat = asyncio.run(run())
        stages = lambda r: [s["stage"] for s in r.trace]  # noqa: E731
        assert stages(direct) == ["understand", "decide", "act"]
        assert direct.trace[0]["detail"].startswith("home_control(")
        assert direct.trace[1]["title"] == "Allowed"
        assert stages(held) == ["understand", "decide"] and held.trace[1]["title"] == "Needs confirmation"
        assert confirmed.trace[0]["title"] == "Confirmed" and stages(confirmed)[-1] == "act"
        assert refused.trace[-1]["title"] == "Refused"
        assert stages(chat) == ["understand", "think"] and chat.trace[0]["title"] == "Conversation"

    def test_stream_done_event_carries_trace(self):
        kernel, _ = make_kernel()

        async def run():
            direct = [e async for e in kernel.stream("what time is it", user="u")]
            brain = [e async for e in kernel.stream("tell me a joke", user="u")]
            return direct[-1], brain[-1]

        direct_done, brain_done = asyncio.run(run())
        assert [s["stage"] for s in direct_done.metadata["trace"]] == ["understand", "decide", "act"]
        assert brain_done.metadata["trace"][-1]["stage"] == "think"

    def test_works_with_brains_that_have_narrow_ask(self):
        from atulya.cognition.kernel import CognitiveKernel

        class NarrowLLM:
            async def ask(self, prompt):
                from atulya.llm import LLMResponse
                return LLMResponse(text=f"ok:{prompt}", provider="narrow")

        k = CognitiveKernel(llm=NarrowLLM(), events=EventBus())
        assert asyncio.run(k.handle("hello")).text == "ok:hello"
        assert asyncio.run(k.handle("turn off the kitchen light")).text == "Kitchen Light turned off."


# ── triggers ────────────────────────────────────────────────────────────────

class TestTriggers:
    def make(self, tmp_path):
        from atulya.cognition.kernel import CognitiveKernel
        from atulya.cognition.triggers import TriggerEngine

        bus = EventBus()
        notes: list[str] = []
        bus.subscribe("notification", lambda e: notes.append(e.payload["message"]))
        kernel = CognitiveKernel(llm=make_llm(), events=bus)
        engine = TriggerEngine(rules_file=tmp_path / "triggers.json", kernel=kernel, events=bus)
        engine.start()
        return engine, bus, notes

    def test_defaults_seeded(self, tmp_path):
        engine, _, _ = self.make(tmp_path)
        assert {r["id"] for r in engine.list_rules()} == {
            "trg_reminder_alert", "trg_health_alert", "trg_automation_failed", "trg_habit_nudge",
            "trg_someone_at_door", "trg_calendar_soon"}

    def test_new_defaults_top_up_old_rule_files_once(self, tmp_path):
        """An older rules file gets new built-ins, but a deleted built-in never returns."""
        from atulya.cognition.triggers import TriggerEngine

        rules_file = tmp_path / "old.json"
        rules_file.write_text(json.dumps([{"id": "trg_reminder_alert", "event": "reminder.due", "notify": "x"}]))
        engine = TriggerEngine(rules_file=rules_file, events=EventBus())
        ids = {r["id"] for r in engine.list_rules()}
        assert "trg_habit_nudge" in ids and "trg_health_alert" not in ids  # the user had deleted it
        engine.remove_rule("trg_habit_nudge")
        again = TriggerEngine(rules_file=rules_file, events=EventBus())
        assert "trg_habit_nudge" not in {r["id"] for r in again.list_rules()}

    def test_reminder_alert_and_command_rule(self, tmp_path):
        from atulya.agent.tools import _HOME_DEVICES

        engine, bus, notes = self.make(tmp_path)
        engine.add_rule({"event": "reminder.due", "match": {"message": "dusk"},
                         "command": "turn on the living room light", "cooldown_seconds": 0})
        _HOME_DEVICES["living_room_light"]["state"] = "off"

        async def run():
            await bus.emit("reminder.due", {"message": "it is dusk"})
            await engine.drain()

        asyncio.run(run())
        assert "Reminder: it is dusk" in notes
        assert _HOME_DEVICES["living_room_light"]["state"] == "on"

    def test_risky_command_blocked_unless_allowed(self, tmp_path):
        from atulya.agent.tools import _HOME_DEVICES

        engine, bus, notes = self.make(tmp_path)
        engine.add_rule({"id": "r1", "event": "custom.ping", "command": "unlock the front door", "cooldown_seconds": 0})
        _HOME_DEVICES["front_door"]["state"] = "locked"

        async def fire():
            await bus.emit("custom.ping", {})
            await engine.drain()

        asyncio.run(fire())
        assert _HOME_DEVICES["front_door"]["state"] == "locked"
        assert any("allow_risky" in n for n in notes)

        engine.add_rule({"id": "r1", "event": "custom.ping", "command": "unlock the front door",
                         "allow_risky": True, "cooldown_seconds": 0})
        asyncio.run(fire())
        assert _HOME_DEVICES["front_door"]["state"] == "unlocked"

    def test_payload_never_injected_into_commands(self, tmp_path):
        from atulya.cognition.triggers import render

        assert render("Reminder: {message}", {"message": "hi"}) == "Reminder: hi"
        assert render("{missing}!", {}) == "!"
        assert render("{0.__class__}", {}) == "{0.__class__}"  # no attribute traversal

    def test_loop_guard_and_cooldown(self, tmp_path):
        engine, bus, notes = self.make(tmp_path)
        engine.add_rule({"event": "action.executed", "notify": "ran {tool}", "cooldown_seconds": 3600})

        async def run():
            await bus.emit("action.executed", {"tool": "x", "source": "trigger"})  # caused by a trigger
            await bus.emit("action.executed", {"tool": "y", "source": "chat"})
            await bus.emit("action.executed", {"tool": "z", "source": "chat"})     # in cooldown
            await engine.drain()

        asyncio.run(run())
        assert notes == ["ran y"]

    def test_rule_validation_and_removal(self, tmp_path):
        engine, _, _ = self.make(tmp_path)
        with pytest.raises(ValueError):
            engine.add_rule({"event": "x"})
        with pytest.raises(ValueError):
            engine.add_rule({"notify": "hi"})
        rule = engine.add_rule({"event": "x", "notify": "hi"})
        assert engine.remove_rule(rule["id"]) and not engine.remove_rule(rule["id"])

    def test_editing_a_rule_keeps_its_history(self, tmp_path):
        engine, bus, _ = self.make(tmp_path)
        rule = engine.add_rule({"id": "r", "event": "custom.x", "notify": "hi", "cooldown_seconds": 0})

        async def run():
            await bus.emit("custom.x", {})
            await engine.drain()

        asyncio.run(run())
        engine.add_rule({**rule, "enabled": False})  # e.g. Pause in the UI
        saved = next(r for r in engine.list_rules() if r["id"] == "r")
        assert saved["enabled"] is False and saved["fire_count"] == 1 and saved["last_fired"]

    def test_stop_unsubscribes(self, tmp_path):
        engine, bus, notes = self.make(tmp_path)
        engine.stop()
        asyncio.run(bus.emit("reminder.due", {"message": "x"}))
        assert notes == []


# ── heartbeat, reminders ────────────────────────────────────────────────────

class TestSensors:
    def test_heartbeat_events_are_edge_triggered(self, tmp_path):
        from atulya.heartbeat import HealthCheck, HeartbeatSystem

        bus = EventBus()
        seen: list[tuple[str, str]] = []
        bus.subscribe("*", lambda e: seen.append((e.type, e.payload.get("check"))))
        hb = HeartbeatSystem(data_dir=tmp_path, events=bus)

        async def run():
            for status in ("warning", "warning", "ok"):
                hb._checks = [HealthCheck("disk", "ok", ""), HealthCheck("memory", status, "")]
                await hb._publish_changes()

        asyncio.run(run())
        assert seen == [("health.warning", "memory"), ("health.ok", "memory")]

    def test_reminder_confirmation_shows_time_not_module(self):
        from atulya.agent.tools import set_reminder

        out = asyncio.run(set_reminder("stretch", "in 10 minutes"))
        assert "module" not in out and "Reminder set: 'stretch' at " in out


# ── brain tiers ─────────────────────────────────────────────────────────────

class TestBrainTiers:
    def test_tier_selection_and_fallback(self, tmp_path, monkeypatch):
        import atulya.local_provider as lp

        (tmp_path / "Qwen3-0.6B-Q4_K_M.gguf").write_bytes(b"x")
        monkeypatch.setenv("ATULYA_MODEL_DIR", str(tmp_path))
        monkeypatch.delenv("ATULYA_GGUF_PATH", raising=False)
        monkeypatch.setattr(lp, "_PORTABLE_MODEL_DIR", tmp_path / "none")
        monkeypatch.setattr(lp, "_LEGACY_MODEL_DIR", tmp_path / "none")

        monkeypatch.setenv("ATULYA_BRAIN", "power")
        assert lp._resolve_model_path().name == "Qwen3-0.6B-Q4_K_M.gguf"  # falls back down
        (tmp_path / "Qwen3-4B-Q4_K_M.gguf").write_bytes(b"x")
        assert lp._resolve_model_path().name == "Qwen3-4B-Q4_K_M.gguf"
        assert lp.LocalGGUFProvider(lp._resolve_model_path()).name() == "Local Brain (Qwen3-4B)"

        monkeypatch.setenv("ATULYA_BRAIN", "tiny")
        assert lp._resolve_model_path().name == "Qwen3-0.6B-Q4_K_M.gguf"  # never falls up

        custom = tmp_path / "mine.gguf"
        custom.write_bytes(b"x")
        monkeypatch.setenv("ATULYA_GGUF_PATH", str(custom))
        assert lp._resolve_model_path() == custom  # explicit file wins

    def test_unknown_tier_defaults_to_tiny(self, monkeypatch):
        from atulya.cognition.brain import active_brain

        monkeypatch.setenv("ATULYA_BRAIN", "galaxy-brain")
        assert active_brain() == "tiny"

    def test_cloud_tier_routes_cloud_first(self, monkeypatch):
        from atulya.intelligence import LocalGGUFProvider, OpenCodeProvider, ProviderRouter

        monkeypatch.setenv("ATULYA_BRAIN", "cloud")
        providers = ProviderRouter().providers
        assert not isinstance(providers[0], LocalGGUFProvider)
        assert isinstance(providers[-1], OpenCodeProvider)
        local_index = next(i for i, p in enumerate(providers) if isinstance(p, LocalGGUFProvider))
        assert local_index > 0


# ── Home Assistant ──────────────────────────────────────────────────────────

class TestHomeAssistant:
    def test_service_calls(self):
        from atulya.capabilities.home_assistant import HomeAssistantBridge

        calls = []

        def handler(req):
            calls.append((req.url.path, req.headers["authorization"], json.loads(req.read())))
            return httpx.Response(200, json=[])

        bridge = HomeAssistantBridge(url="http://ha:8123", token="tok", entities={},
                                     transport=httpx.MockTransport(handler))

        async def run():
            assert await bridge.control("living_room_light", "on") == "light.living_room turned on (via Home Assistant)."
            await bridge.control("front_door", "unlock")
            await bridge.control("thermostat", "set_temperature", "21")

        asyncio.run(run())
        assert calls == [
            ("/api/services/light/turn_on", "Bearer tok", {"entity_id": "light.living_room"}),
            ("/api/services/lock/unlock", "Bearer tok", {"entity_id": "lock.front_door"}),
            ("/api/services/climate/set_temperature", "Bearer tok",
             {"entity_id": "climate.thermostat", "temperature": 21.0}),
        ]

    def test_errors_are_reported_not_faked(self):
        from atulya.capabilities.home_assistant import HomeAssistantBridge, HomeAssistantError

        bridge = HomeAssistantBridge(url="http://ha", token="t", entities={},
                                     transport=httpx.MockTransport(lambda r: httpx.Response(401, text="no")))
        with pytest.raises(HomeAssistantError, match="401"):
            asyncio.run(bridge.control("kitchen_light", "on"))
        with pytest.raises(HomeAssistantError, match="no Home Assistant entity"):
            asyncio.run(bridge.control("garage", "on"))

    def test_home_control_uses_simulation_when_unconfigured(self, monkeypatch):
        from atulya.agent.tools import home_control

        monkeypatch.delenv("HOME_ASSISTANT_URL", raising=False)
        monkeypatch.delenv("HOME_ASSISTANT_TOKEN", raising=False)
        assert asyncio.run(home_control("kitchen_light", "on")) == "Kitchen Light turned on."


# ── routes ──────────────────────────────────────────────────────────────────

class TestRoutes:
    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        from atulya.server import helpers
        from atulya.server.app import app
        from atulya.cognition.triggers import TriggerEngine

        monkeypatch.setattr(helpers, "ADMIN_TOKEN", "test_token")
        app.state.llm = make_llm()
        app.state.triggers = TriggerEngine(rules_file=tmp_path / "t.json", events=EventBus())
        yield TestClient(app)
        del app.state.llm
        del app.state.triggers

    def test_chat_goes_through_kernel(self, client):
        h = {"X-Atulya-Token": "test_token"}
        r = client.post("/api/chat", json={"prompt": "unlock the front door"}, headers=h).json()
        assert r["needs_approval"] and r["provider"] == "Atulya Kernel"
        r = client.post("/api/chat", json={"prompt": "", "approved_tool": r["pending_tool"]}, headers=h).json()
        assert r["response"] == "Front Door is now unlocked."

    def test_chat_returns_trace(self, client):
        r = client.post("/api/chat", json={"prompt": "turn off the kitchen light"},
                        headers={"X-Atulya-Token": "test_token"}).json()
        assert [s["stage"] for s in r["trace"]] == ["understand", "decide", "act"]

    def test_websocket_replays_history_flagged_as_replay(self, client):
        from atulya.server.routes import ws as ws_mod

        ws_mod._broadcast_history.append({"type": "event", "data": {"title": "old"}, "timestamp": 1.0})
        try:
            with client.websocket_connect("/api/ws?token=test_token") as sock:
                assert sock.receive_json()["type"] == "welcome"
                replayed = sock.receive_json()
                while replayed.get("data", {}).get("title") != "old":
                    replayed = sock.receive_json()
                assert replayed["replay"] is True
            # Stored history itself is unchanged.
            assert "replay" not in ws_mod._broadcast_history[-1]
        finally:
            ws_mod._broadcast_history.pop()

    def test_triggers_api_is_admin_only(self, client):
        assert client.get("/api/triggers").status_code == 401
        h = {"X-Atulya-Token": "test_token"}
        created = client.post("/api/triggers", json={"event": "x", "notify": "hi"}, headers=h).json()
        assert created["ok"]
        assert client.post("/api/triggers", json={"event": "x"}, headers=h).status_code == 400
        assert client.delete(f"/api/triggers/{created['trigger']['id']}", headers=h).json()["ok"]

    def test_brain_endpoint(self, client, monkeypatch):
        monkeypatch.setenv("ATULYA_BRAIN", "balanced")
        data = client.get("/api/brain", headers={"X-Atulya-Token": "test_token"}).json()
        assert data["tier"] == "balanced" and data["local_model"]["label"] == "Qwen3-1.7B"
        assert set(data["tiers"]) == {"tiny", "balanced", "power", "cloud"}


class TestNoBrain:
    async def test_last_fallback_says_no_brain_instead_of_canned_reply(self):
        from atulya.intelligence import NO_BRAIN_MESSAGE, OpenCodeProvider

        reply = await OpenCodeProvider().chat("what is the capital of france")
        assert reply == NO_BRAIN_MESSAGE
        assert "At your service" not in reply


def test_voice_for_reply_keeps_gender_and_follows_language():
    from atulya.server.routes.voice import voice_for_reply

    assert voice_for_reply("Hello there.", "en_female") == "en_female"
    assert voice_for_reply("नमस्ते, मैं अतुल्य हूँ।", "en_female") == "hi_female"
    assert voice_for_reply("Good evening.", "hi_male") == "en_male"
    assert voice_for_reply("नमस्ते", "sa_male") == "sa_male"


def test_recommend_tier_by_free_ram():
    from atulya.cognition.brain import recommend_tier

    assert recommend_tier(2) == "tiny"
    assert recommend_tier(5) == "balanced"
    assert recommend_tier(16) == "power"


def test_cloud_key_leads_unless_a_local_brain_is_chosen(monkeypatch):
    from atulya.intelligence import LocalGGUFProvider, OpenRouterProvider, ProviderRouter

    for key in ("ANTHROPIC_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "NVIDIA_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    monkeypatch.delenv("ATULYA_BRAIN", raising=False)
    names = [type(p) for p in ProviderRouter().providers]
    assert names.index(OpenRouterProvider) < names.index(LocalGGUFProvider)
    monkeypatch.setenv("ATULYA_BRAIN", "tiny")
    names = [type(p) for p in ProviderRouter().providers]
    assert names.index(LocalGGUFProvider) < names.index(OpenRouterProvider)


def test_router_prefers_the_fastest_working_brain(monkeypatch):
    import asyncio

    from atulya import intelligence as ai

    class Fake(ai.IntelligenceProvider):
        def __init__(self, label, delay=0.0, fail=False):
            self.label, self.delay, self.fail = label, delay, fail

        def name(self):
            return self.label

        def is_available(self):
            return True

        async def chat(self, prompt, system_prompt=""):
            await asyncio.sleep(self.delay)
            if self.fail:
                raise RuntimeError("down")
            return "ok"

    monkeypatch.delenv("ATULYA_BRAIN", raising=False)
    monkeypatch.setattr(ai, "_SPEED", {})
    router = ai.ProviderRouter()
    slow, fast, broken = Fake("slow", 0.05), Fake("fast", 0.0), Fake("broken", fail=True)
    router.providers = [broken, slow, fast]

    async def ask():
        return (await router.chat("hi"))[1]

    assert asyncio.run(ask()) == "slow"      # first try follows the configured order; broken is skipped
    assert asyncio.run(ask()) == "slow"      # still the only one measured; broken is in its cooldown
    ai._SPEED["fast"] = {"avg": 0.001}
    assert asyncio.run(ask()) == "fast"      # measured faster, so it now leads
    monkeypatch.setenv("ATULYA_BRAIN", "tiny")
    assert [p.name() for p in router._ordered(router.providers)] == ["broken", "slow", "fast"]  # pinned: no reordering
