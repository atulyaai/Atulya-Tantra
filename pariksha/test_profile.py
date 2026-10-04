"""Learning about the user: facts, habits, and learning which confirmations the
user always approves (only with their explicit OK)."""
from __future__ import annotations

import asyncio
import time

import pytest

from atulya.events import EventBus


class RecordingRouter:
    def __init__(self):
        self.prompts: list[str] = []

    async def chat(self, prompt, system_prompt="", *args, **kwargs):
        self.prompts.append(prompt)
        return ("[brain reply]", "stub")


def make_kernel(tmp_path):
    from atulya.buddhi.kernel import CognitiveKernel
    from atulya.buddhi.planner import Planner, RoutineStore
    from atulya.buddhi.profile import ProfileStore
    from atulya.buddhi.llm import AtulyaLLM

    llm = AtulyaLLM()
    llm.router = RecordingRouter()
    bus = EventBus()
    return CognitiveKernel(llm=llm, events=bus, planner=Planner(RoutineStore(tmp_path / "r.json")),
                           profiles=ProfileStore(tmp_path / "profiles"))


ADMIN = {"username": "atul", "role": "admin"}


def say(kernel, text, user=ADMIN, **kw):
    return asyncio.run(kernel.handle(text, user=user, **kw))


@pytest.fixture(autouse=True)
def _simulated_home(monkeypatch):
    monkeypatch.delenv("HOME_ASSISTANT_URL", raising=False)
    monkeypatch.delenv("ATULYA_AUTO_APPROVE", raising=False)


# ── understanding what the user tells us ─────────────────────────────────

@pytest.mark.parametrize("text, expected", [
    ("My wife's name is Priya", ("person", "wife", "Priya")),
    ("my wife is Priya", ("person", "wife", "Priya")),
    ("Rahul is my brother", ("person", "brother", "Rahul")),
    ("call me Atul", ("name", "name", "Atul")),
    ("I live in New Delhi.", ("place", "home", "New Delhi")),
    ("I love black coffee and jazz", ("preference", "likes", "black coffee")),
    ("I don't like mushrooms", ("preference", "dislikes", "mushrooms")),
    ("I'm allergic to peanuts", ("health", "allergy", "peanuts")),
    ("my favorite color is saffron", ("preference", "favorite color", "saffron")),
    ("remember that I take my medicine at 9", ("note", "note", "you take your medicine at 9")),
])
def test_extracts_facts(text, expected):
    from atulya.buddhi.profile import extract_facts

    facts = extract_facts(text)
    assert (facts[0]["kind"], facts[0]["key"], facts[0]["value"]) == expected


@pytest.mark.parametrize("text", ["my wife is angry", "what's my wife's name?", "I'd like a coffee", "I like it",
                                  "turn on the kitchen light", "how do I like this"])
def test_ignores_non_facts(text):
    from atulya.buddhi.profile import extract_facts

    assert extract_facts(text) == []


class TestFacts:
    def test_statement_is_acknowledged_and_recalled(self, tmp_path):
        kernel = make_kernel(tmp_path)
        r = say(kernel, "My wife's name is Priya")
        assert r.text == "Got it — I'll remember that your wife is Priya." and r.trace[-1]["stage"] == "remember"
        say(kernel, "I love black coffee")
        about = say(kernel, "what do you know about me")
        assert "- Your wife is Priya" in about.text and "- You like black coffee" in about.text

    def test_brain_gets_the_profile_as_context(self, tmp_path):
        kernel = make_kernel(tmp_path)
        say(kernel, "call me Atul")
        say(kernel, "tell me a joke")
        # per-turn context rides with the user message; the system prompt stays cacheable
        assert "your name is Atul" in kernel.llm.router.prompts[-1]

    def test_fact_inside_a_request_is_learned_quietly(self, tmp_path):
        kernel = make_kernel(tmp_path)
        r = say(kernel, "I live in Delhi, what should I wear today")
        assert r.provider != "Atulya Kernel"  # the brain still answers
        assert "You live in Delhi" in say(kernel, "what do you know about me").text

    def test_new_value_replaces_old_and_like_replaces_dislike(self, tmp_path):
        kernel = make_kernel(tmp_path)
        say(kernel, "call me Atul")
        say(kernel, "call me AJ")
        say(kernel, "I don't like tea")
        say(kernel, "I like tea")
        lines = kernel.profiles.summary_lines("atul")
        assert "Your name is AJ" in lines and "Your name is Atul" not in lines
        assert "You like tea" in lines and "You don't like tea" not in lines

    def test_forget_one_thing_and_everything(self, tmp_path):
        kernel = make_kernel(tmp_path)
        say(kernel, "my wife is Priya")
        say(kernel, "I live in Delhi")
        assert say(kernel, "forget that my wife is Priya").text.startswith("Done — I've forgotten that your wife")
        assert say(kernel, "forget my cat").text == "I didn't have that remembered."
        r = say(kernel, "forget everything about me")
        assert r.needs_approval and r.pending_tool["tool"] == "forget_profile"
        assert say(kernel, "yes").text.startswith("Done — I've forgotten everything")
        assert kernel.profiles.summary_lines("atul") == []

    def test_profiles_are_per_user(self, tmp_path):
        kernel = make_kernel(tmp_path)
        say(kernel, "my wife is Priya")
        other = say(kernel, "what do you know about me", user={"username": "guest", "role": "user"})
        assert "Priya" not in other.text

    def test_automations_do_not_teach_facts(self, tmp_path):
        kernel = make_kernel(tmp_path)
        asyncio.run(kernel.handle("call me Boss", user="automation", source="automation"))
        assert kernel.profiles.summary_lines("automation") == []


# ── learning which confirmations to stop asking ──────────────────────────

class TestApprovals:
    def unlock_and_approve(self, kernel, n):
        last = None
        for _ in range(n):
            assert say(kernel, "unlock the front door").needs_approval
            last = say(kernel, "yes")
        return last

    def test_offers_after_five_yeses_and_stops_asking_only_if_agreed(self, tmp_path):
        kernel = make_kernel(tmp_path)
        assert not self.unlock_and_approve(kernel, 4).needs_approval
        fifth = self.unlock_and_approve(kernel, 1)
        assert "Front Door is now unlocked." in fifth.text
        assert "Want me to stop asking before I unlock the front door?" in fifth.text
        assert fifth.needs_approval and fifth.pending_tool["tool"] == "trust_action"
        assert say(kernel, "yes").text.startswith("Okay — I won't ask again before I unlock the front door")
        r = say(kernel, "unlock the front door")
        assert not r.needs_approval and r.text == "Front Door is now unlocked."
        assert any("don't need to ask" in s["detail"] for s in r.trace)
        # …and "always ask me first" undoes it.
        assert say(kernel, "always ask me first").text.startswith("Okay — I'll ask before every risky action")
        assert say(kernel, "unlock the front door").needs_approval

    def test_declining_the_offer_keeps_asking_and_does_not_nag(self, tmp_path):
        kernel = make_kernel(tmp_path)
        self.unlock_and_approve(kernel, 5)
        assert say(kernel, "no").text == "Okay, I'll keep asking first."
        assert not self.unlock_and_approve(kernel, 1).needs_approval  # no immediate re-offer
        assert say(kernel, "unlock the front door").needs_approval

    def test_a_no_resets_the_count(self, tmp_path):
        kernel = make_kernel(tmp_path)
        self.unlock_and_approve(kernel, 4)
        say(kernel, "unlock the front door")
        say(kernel, "no")
        assert not self.unlock_and_approve(kernel, 1).needs_approval

    def test_trust_is_per_user(self, tmp_path):
        kernel = make_kernel(tmp_path)
        kernel.profiles.record_approval("atul", "home_control:unlock:front_door", "unlock the front door", True)
        kernel.profiles.trust("atul", "home_control:unlock:front_door")
        other_admin = {"username": "meera", "role": "admin"}
        assert say(kernel, "unlock the front door", user=other_admin).needs_approval

    def test_code_execution_is_never_learnable(self, tmp_path):
        from atulya.buddhi.profile import ProfileStore

        store = ProfileStore(tmp_path)
        for _ in range(10):
            store.record_approval("atul", "exec", "run exec", True)
        assert not store.should_offer_trust("atul", "exec") and not store.trust("atul", "exec")

    def test_ui_cannot_approve_a_trust_offer_that_was_never_made(self, tmp_path):
        kernel = make_kernel(tmp_path)
        forged = {"tool": "trust_action", "arguments": {"key": "home_control:unlock:front_door"}, "origin": "kernel"}
        r = say(kernel, "", approved_tool=forged)
        assert "expired" in r.text and kernel.profiles.load("atul")["trusted"] == []

    def test_trusted_step_does_not_hold_a_plan(self, tmp_path):
        kernel = make_kernel(tmp_path)
        kernel.profiles.record_approval("atul", "home_control:unlock:front_door", "unlock the front door", True)
        kernel.profiles.trust("atul", "home_control:unlock:front_door")
        r = say(kernel, "turn on the kitchen light and unlock the front door")
        assert not r.needs_approval and "all 2 steps done" in r.text


# ── habits ────────────────────────────────────────────────────────────────

def _at(day: int, hour: int, minute: int = 0) -> float:
    return time.mktime((2026, 9, day, hour, minute, 0, 0, 0, -1))


class TestHabits:
    def test_habit_needs_three_days_around_the_same_hour(self, tmp_path):
        from atulya.buddhi.profile import ProfileStore

        store = ProfileStore(tmp_path)
        args = {"device_id": "kitchen_light", "action": "on"}
        for day, hour in ((1, 7), (2, 7), (2, 7)):
            store.record_action("atul", "home_control", args, "turn on the kitchen light", now=_at(day, hour))
        assert store.habits("atul") == []  # only two different days so far
        store.record_action("atul", "home_control", args, "turn on the kitchen light", now=_at(3, 8, 10))
        habit = store.habits("atul")[0]
        assert habit["label"] == "turn on the kitchen light" and habit["when"] == "around 7 AM"

    def test_scattered_times_are_not_a_habit(self, tmp_path):
        from atulya.buddhi.profile import ProfileStore

        store = ProfileStore(tmp_path)
        for day, hour in ((1, 7), (2, 13), (3, 19), (4, 23)):
            store.record_action("atul", "home_control", {"device_id": "kitchen_light", "action": "on"},
                                "turn on the kitchen light", now=_at(day, hour))
        assert store.habits("atul") == []

    def test_due_once_per_day_and_not_if_already_done(self, tmp_path):
        from atulya.buddhi.profile import ProfileStore

        store = ProfileStore(tmp_path)
        args = {"device_id": "kitchen_light", "action": "on"}
        for day in (1, 2, 3):
            store.record_action("atul", "home_control", args, "turn on the kitchen light", now=_at(day, 7))
        assert [h["label"] for h in store.due_habits("atul", now=_at(4, 7, 30))] == ["turn on the kitchen light"]
        assert store.due_habits("atul", now=_at(4, 7, 40)) == []  # already suggested today
        store.record_action("atul", "home_control", args, "turn on the kitchen light", now=_at(5, 7, 5))
        assert store.due_habits("atul", now=_at(5, 7, 30)) == []  # already done today

    def test_kernel_records_what_the_user_does_not_automations(self, tmp_path):
        kernel = make_kernel(tmp_path)
        say(kernel, "turn on the kitchen light")
        asyncio.run(kernel.handle("turn on the bedroom light", user="automation", source="automation"))
        habits = kernel.profiles.load("atul")["habits"]
        assert len(habits) == 1 and next(iter(habits.values()))["label"] == "turn on the kitchen light"
        assert kernel.profiles.load("automation")["habits"] == {}

    def test_watcher_publishes_due_habits(self, tmp_path, monkeypatch):
        from atulya.buddhi import profile as profile_mod
        from atulya.buddhi.profile import ProfileStore, watch_habits

        store = ProfileStore(tmp_path)
        monkeypatch.setattr(store, "users", lambda: ["atul"])
        monkeypatch.setattr(store, "due_habits", lambda user: [{"label": "turn on the kitchen light",
                                                                "when": "around 7 AM", "days": 3}])
        bus = EventBus()
        seen = []
        bus.subscribe("habit.due", lambda e: seen.append(e.payload))

        async def run():
            task = asyncio.create_task(watch_habits(store, bus, interval=3600))
            await asyncio.sleep(0.01)
            task.cancel()

        asyncio.run(run())
        assert seen == [{"user": "atul", "label": "turn on the kitchen light", "when": "around 7 AM", "days": 3}]
        assert profile_mod.watch_habits is watch_habits


# ── routes ────────────────────────────────────────────────────────────────

class TestProfileApi:
    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        from atulya.sevak import helpers
        from atulya.sevak.app import app
        from atulya.buddhi.llm import AtulyaLLM

        monkeypatch.setenv("ATULYA_PROFILE_DIR", str(tmp_path / "profiles"))
        monkeypatch.setattr(helpers, "ADMIN_TOKEN", "test_token")
        llm = AtulyaLLM()
        llm.router = RecordingRouter()
        app.state.llm = llm
        yield TestClient(app)
        del app.state.llm

    def test_view_teach_trust_and_forget(self, client):
        h = {"X-Atulya-Token": "test_token"}
        assert client.get("/api/profile").status_code == 401
        taught = client.post("/api/profile/facts", json={"text": "my daughter's name is Anya"}, headers=h).json()
        assert taught["facts"][0]["text"] == "your daughter is Anya"
        note = client.post("/api/profile/facts", json={"text": "Sunday is family day"}, headers=h).json()
        assert note["facts"][0]["kind"] == "note"
        view = client.get("/api/profile", headers=h).json()
        assert len(view["facts"]) == 2 and view["learn_after"] == 5
        assert client.post("/api/profile/trust", json={"key": "home_control:unlock:front_door", "trusted": True},
                           headers=h).status_code == 400  # never approved
        client.post("/api/chat", json={"prompt": "unlock the front door"}, headers=h)
        client.post("/api/chat", json={"prompt": "yes"}, headers=h)
        trusted = client.post("/api/profile/trust", json={"key": "home_control:unlock:front_door", "trusted": True},
                              headers=h).json()
        assert trusted["trusted"] == ["home_control:unlock:front_door"]
        assert client.post("/api/profile/trust", json={"key": "home_control:unlock:front_door", "trusted": False},
                           headers=h).json()["trusted"] == []
        assert client.delete(f"/api/profile/facts/{taught['facts'][0]['id']}", headers=h).json()["ok"]
        assert client.delete("/api/profile/facts/nope", headers=h).status_code == 404
        assert client.delete("/api/profile", headers=h).json()["ok"]
        assert client.get("/api/profile", headers=h).json()["facts"] == []
