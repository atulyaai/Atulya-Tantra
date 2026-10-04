"""Multi-step planning: routines, device groups, compound commands, brain
decomposition, one confirmation per risky plan, and checking each step."""
from __future__ import annotations

import asyncio

import httpx
import pytest

from atulya.ghatna import EventBus


class StubRouter:
    def __init__(self, reply: str = "[brain reply]"):
        self.reply = reply
        self.prompts: list[str] = []

    async def chat(self, prompt, *args, **kwargs):
        self.prompts.append(prompt)
        return (self.reply, "stub")


def make_kernel(tmp_path, reply: str = "[brain reply]"):
    from atulya.buddhi import CognitiveKernel
    from atulya.yojana import Planner, RoutineStore
    from atulya.bhasha import AtulyaLLM

    llm = AtulyaLLM()
    llm.router = StubRouter(reply)
    bus = EventBus()
    seen: list[tuple[str, dict]] = []
    bus.subscribe("*", lambda e: seen.append((e.type, e.payload)))
    kernel = CognitiveKernel(llm=llm, events=bus, planner=Planner(RoutineStore(tmp_path / "routines.json")))
    return kernel, seen


@pytest.fixture(autouse=True)
def _simulated_home(monkeypatch):
    monkeypatch.delenv("HOME_ASSISTANT_URL", raising=False)
    monkeypatch.delenv("HOME_ASSISTANT_TOKEN", raising=False)
    monkeypatch.delenv("ATULYA_AUTO_APPROVE", raising=False)


# ── understanding goals ───────────────────────────────────────────────────

class TestPlanning:
    @pytest.fixture
    def planner(self, tmp_path):
        from atulya.yojana import Planner, RoutineStore

        return Planner(RoutineStore(tmp_path / "routines.json"))

    def test_guests_goal_uses_the_routine(self, planner):
        plan = planner.plan("get the house ready for guests")
        assert plan.source == "routine" and plan.title == "Guests are coming"
        assert [s.arguments.get("device_id") for s in plan.steps] == ["living_room_light", "kitchen_light", "thermostat"]

    def test_routine_phrase_must_be_most_of_the_sentence(self, planner):
        assert planner.plan("good night atulya").title == "Good night"
        assert planner.plan("tell me a good night story") is None
        assert planner.plan("how many guests are coming") is None  # questions never run routines

    def test_explicit_routine_by_name(self, planner):
        assert planner.plan("run the morning routine").title == "Good morning"

    def test_light_group_expands_to_every_light(self, planner):
        plan = planner.plan("turn off all the lights")
        assert plan.source == "group"
        assert {s.arguments["device_id"] for s in plan.steps} == {"living_room_light", "kitchen_light", "bedroom_light"}
        assert all(s.arguments["action"] == "off" for s in plan.steps)

    def test_compound_command_borrows_the_verb(self, planner):
        plan = planner.plan("turn off the kitchen light and the bedroom light, then lock the door")
        assert [(s.arguments["device_id"], s.arguments["action"]) for s in plan.steps] == [
            ("kitchen_light", "off"), ("bedroom_light", "off"), ("front_door", "lock")]

    def test_ambiguous_and_is_not_split(self, planner):
        # "bread and milk" is one reminder, not two commands.
        assert planner.plan("remind me to buy bread and milk in 10 minutes") is None
        assert planner.plan("turn on the kitchen light") is None  # single commands stay single

    def test_brain_steps_are_validated(self):
        from atulya.yojana import parse_brain_steps

        steps = parse_brain_steps("1. Turn on the living room light\n- set the thermostat to 21\n"
                                  "3. summon a pizza\n- turn on the living room light\nNONE")
        assert [(s.tool, s.arguments.get("action")) for s in steps] == [
            ("home_control", "on"), ("home_control", "set_temperature")]

    def test_routine_store_rejects_unclear_steps(self, planner):
        with pytest.raises(ValueError, match="doesn't understand"):
            planner.routines.save({"name": "Party", "steps": ["make it fun"]})
        saved = planner.routines.save({"name": "Movie night", "phrases": "movie night, film time",
                                       "steps": ["turn off the living room light", "set the thermostat to 21"]})
        assert saved["phrases"] == ["movie night", "film time"]
        assert planner.plan("movie night").title == "Movie night"
        assert planner.routines.remove(saved["id"]) and planner.plan("movie night") is None


# ── running plans through the kernel ──────────────────────────────────────

class TestKernelPlans:
    def test_routine_runs_every_step_and_checks_it(self, tmp_path):
        kernel, seen = make_kernel(tmp_path)
        r = asyncio.run(kernel.handle("get the house ready for guests"))
        assert r.text.startswith("Guests are coming — all 3 steps done.")
        assert "Living Room Light turned on." in r.text and "Thermostat set to 22°C." in r.text
        stages = [s["stage"] for s in r.trace]
        assert stages[0] == "plan" and stages.count("act") == 3 and stages.count("check") == 3
        types = [t for t, _ in seen]
        assert types[0] == "plan.started" and types[-1] == "plan.completed"
        assert types.count("action.executed") == 3 and types.count("plan.step") == 3

    def test_failed_step_is_reported_and_others_still_run(self, tmp_path, monkeypatch):
        from atulya import kriya as tools

        kernel, _ = make_kernel(tmp_path)
        monkeypatch.delitem(tools._HOME_DEVICES, "kitchen_light")
        r = asyncio.run(kernel.handle("turn on the kitchen light and the living room light"))
        assert "1 of 2 steps done" in r.text
        assert "Couldn't turn on the kitchen light" in r.text and "Living Room Light turned on." in r.text

    def test_check_catches_a_device_that_did_not_change(self, tmp_path, monkeypatch):
        from atulya import kriya as tools

        kernel, _ = make_kernel(tmp_path)
        real = tools._simulate_home_control

        def stuck(device_id, action, value=""):
            if device_id == "bedroom_light":
                return "Bedroom Light turned on."  # claims success, changes nothing
            return real(device_id, action, value)

        tools._HOME_DEVICES["bedroom_light"]["state"] = "off"
        monkeypatch.setattr(tools, "_simulate_home_control", stuck)
        r = asyncio.run(kernel.handle("turn on the bedroom light and the kitchen light"))
        assert "1 of 2 steps done" in r.text and "when I checked, Bedroom Light is off" in r.text
        assert any(s["title"] == "Check failed" for s in r.trace)

    def test_risky_plan_asks_once_then_runs(self, tmp_path):
        from atulya import kriya as tools

        kernel, _ = make_kernel(tmp_path)
        tools._HOME_DEVICES["front_door"]["state"] = "locked"
        r = asyncio.run(kernel.handle("turn on the kitchen light and unlock the front door"))
        assert r.needs_approval and r.pending_tool["tool"] == "run_plan"
        assert "unlocks a door" in r.text and "Should I go ahead?" in r.text
        assert tools._HOME_DEVICES["front_door"]["state"] == "locked"  # nothing ran yet
        done = asyncio.run(kernel.handle("yes"))
        assert "all 2 steps done" in done.text and tools._HOME_DEVICES["front_door"]["state"] == "unlocked"

    def test_risky_plan_cancelled(self, tmp_path):
        from atulya import kriya as tools

        kernel, _ = make_kernel(tmp_path)
        tools._HOME_DEVICES["front_door"]["state"] = "locked"
        asyncio.run(kernel.handle("turn on the kitchen light and unlock the front door"))
        r = asyncio.run(kernel.handle("no"))
        assert r.text.startswith("Okay, I won't run") and tools._HOME_DEVICES["front_door"]["state"] == "locked"

    def test_ui_approve_runs_the_held_plan_not_a_client_edit(self, tmp_path):
        from atulya import kriya as tools

        kernel, _ = make_kernel(tmp_path)
        tools._HOME_DEVICES["bedroom_light"]["state"] = "off"
        r = asyncio.run(kernel.handle("turn on the kitchen light and unlock the front door"))
        edited = {**r.pending_tool, "arguments": {**r.pending_tool["arguments"],
                                                  "steps": ["turn on the bedroom light"]}}
        done = asyncio.run(kernel.handle("", approved_tool=edited))
        assert "all 2 steps done" in done.text
        assert tools._HOME_DEVICES["bedroom_light"]["state"] == "off"

    def test_guest_user_skips_risky_steps(self, tmp_path):
        from atulya import kriya as tools

        kernel, _ = make_kernel(tmp_path)
        tools._HOME_DEVICES["front_door"]["state"] = "locked"
        guest = {"username": "guest", "role": "user"}
        r = asyncio.run(kernel.handle("turn on the kitchen light and unlock the front door", user=guest))
        assert not r.needs_approval and "1 of 2 steps done" in r.text and "only an admin" in r.text
        assert tools._HOME_DEVICES["front_door"]["state"] == "locked"

    def test_goal_is_planned_by_the_brain(self, tmp_path):
        kernel, _ = make_kernel(tmp_path, reply="turn off the living room light\nset the thermostat to 21\nNONE")
        r = asyncio.run(kernel.handle("set the mood for movie night"))
        assert r.trace[0]["stage"] == "plan" and "(brain)" in r.trace[0]["detail"]
        assert "all 2 steps done" in r.text
        assert "Goal: set the mood for movie night" in kernel.llm.router.prompts[0]

    def test_goal_the_brain_cannot_plan_goes_to_conversation(self, tmp_path):
        kernel, _ = make_kernel(tmp_path, reply="NONE")
        r = asyncio.run(kernel.handle("prepare a speech for my sister's wedding"))
        assert r.provider != "Atulya Kernel"

    def test_trigger_cannot_run_a_risky_step_hidden_in_a_routine(self, tmp_path):
        from atulya.prerak import TriggerEngine
        from atulya.ghatna import Event

        kernel, _ = make_kernel(tmp_path)
        kernel.planner.routines.save({"name": "Open up", "phrases": ["open up"],
                                      "steps": ["turn on the kitchen light", "unlock the front door"]})
        engine = TriggerEngine(rules_file=tmp_path / "t.json", kernel=kernel, events=kernel.events, seed_defaults=False)
        result = asyncio.run(engine.fire({"id": "r", "name": "r", "command": "open up"}, Event("x", {})))
        assert "blocked" in result and "unlock" in result["blocked"]


# ── verifying against Home Assistant ─────────────────────────────────────

class TestVerifyWithHomeAssistant:
    def test_reads_back_real_state(self, monkeypatch):
        from atulya import yojana as planner_mod
        from atulya.yojana import PlanStep, verify_step
        from atulya import upakaran as home_assistant

        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.url.path)
            return httpx.Response(200, json={"entity_id": "light.kitchen", "state": "on", "attributes": {}})

        real = home_assistant.HomeAssistantBridge

        def bridge(*args, **kwargs):
            return real(url="http://ha.local", token="t", transport=httpx.MockTransport(handler))

        monkeypatch.setattr(home_assistant, "HomeAssistantBridge", bridge)
        monkeypatch.setattr(planner_mod, "VERIFY_RETRY_SECONDS", 0)
        ok, detail = asyncio.run(verify_step(PlanStep("x", "home_control", {"device_id": "kitchen_light", "action": "on"})))
        assert ok is True and detail == "light.kitchen is on" and calls == ["/api/states/light.kitchen"]
        ok, _ = asyncio.run(verify_step(PlanStep("x", "home_control", {"device_id": "kitchen_light", "action": "off"})))
        assert ok is False and len(calls) == 4  # retried before reporting a mismatch


# ── routes ────────────────────────────────────────────────────────────────

class TestRoutinesApi:
    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        from atulya import khata as helpers
        from atulya.sevak import app
        from atulya.bhasha import AtulyaLLM

        monkeypatch.setenv("ATULYA_ROUTINES_FILE", str(tmp_path / "routines.json"))
        monkeypatch.setattr(helpers, "ADMIN_TOKEN", "test_token")
        llm = AtulyaLLM()
        llm.router = StubRouter()
        app.state.llm = llm
        yield TestClient(app)
        del app.state.llm

    def test_crud_and_run(self, client):
        h = {"X-Atulya-Token": "test_token"}
        assert client.get("/api/routines").status_code == 401
        listed = client.get("/api/routines", headers=h).json()["routines"]
        assert {r["id"] for r in listed} >= {"rtn_guests", "rtn_goodnight", "rtn_leaving", "rtn_morning"}
        goodnight = next(r for r in listed if r["id"] == "rtn_goodnight")
        assert "turn off the bedroom light" in goodnight["plan"]  # the group is shown expanded
        bad = client.post("/api/routines", json={"name": "x", "steps": ["fly"]}, headers=h)
        assert bad.status_code == 400
        saved = client.post("/api/routines", json={"name": "Lights up", "steps": ["turn on all the lights"]},
                            headers=h).json()["routine"]
        ran = client.post(f"/api/routines/{saved['id']}/run", headers=h).json()
        assert "all 3 steps done" in ran["response"] and ran["trace"][0]["stage"] == "plan"
        assert client.delete(f"/api/routines/{saved['id']}", headers=h).json()["ok"]
        assert client.delete(f"/api/routines/{saved['id']}", headers=h).status_code == 404

    def test_preview(self, client):
        h = {"X-Atulya-Token": "test_token"}
        plan = client.post("/api/plan/preview", json={"text": "lock the door and turn off the lights"},
                           headers=h).json()["plan"]
        assert plan["source"] == "compound" and len(plan["steps"]) == 4
