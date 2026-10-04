"""Auto brain tier, local vision, lockdown, daily briefing, Piper voice, wake gate, voice commands."""
import asyncio
import datetime as dt
import json

import pytest

from atulya.yantra.agent.intent_router import route_intent


def run(coro):
    return asyncio.run(coro)


# ── brain ────────────────────────────────────────────────────────────────

def test_brain_auto_follows_free_ram(monkeypatch):
    from atulya.buddhi import brain

    monkeypatch.setenv("ATULYA_BRAIN", "auto")
    monkeypatch.setattr(brain, "recommend_tier", lambda: "balanced")
    assert brain.active_brain() == "balanced"


# ── vision ───────────────────────────────────────────────────────────────

class _Resp:
    def __init__(self, payload):
        self._p = payload

    def read(self):
        return json.dumps(self._p).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_local_vision_describes_through_ollama(monkeypatch):
    import urllib.request

    from atulya.drishti import eyes

    seen = {}

    def fake_urlopen(req, timeout=0):
        seen["body"] = json.loads(req.data)
        return _Resp({"response": " A desk with a laptop. "})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert eyes.local_describe(b"\xff\xd8\xff", "what is this?") == "A desk with a laptop."
    assert seen["body"]["model"] == "moondream" and seen["body"]["images"]


def test_describe_scene_prefers_local_then_cloud(monkeypatch):
    from atulya.drishti import eyes

    monkeypatch.setattr(eyes, "local_describe", lambda i, q: "")
    monkeypatch.setattr(eyes, "cloud_describe", lambda i, q: "cloud says hi")
    assert eyes.describe_scene(b"x", "") == "cloud says hi"
    monkeypatch.setattr(eyes, "local_describe", lambda i, q: "local says hi")
    assert eyes.describe_scene(b"x", "") == "local says hi"


# ── lockdown ─────────────────────────────────────────────────────────────

def test_lockdown_forces_localhost_and_no_cors(monkeypatch):
    from atulya.raksha import lockdown

    monkeypatch.setenv("ATULYA_HOST", "0.0.0.0")
    monkeypatch.delenv("ATULYA_CORS_ORIGINS", raising=False)
    monkeypatch.delenv("ATULYA_LOCKDOWN", raising=False)
    assert lockdown.bind_host() == "0.0.0.0" and lockdown.cors_origins() is None
    monkeypatch.setenv("ATULYA_LOCKDOWN", "on")
    assert lockdown.bind_host() == "127.0.0.1" and lockdown.cors_origins() == []
    monkeypatch.setenv("ATULYA_CORS_ORIGINS", "https://me.example")
    assert lockdown.cors_origins() == ["https://me.example"]


# ── daily briefing ───────────────────────────────────────────────────────

def test_briefing_clock_fires_once_per_day():
    from atulya.shruti.listener import BriefingClock

    clock = BriefingClock("08:00")
    day = dt.date(2026, 10, 4)
    assert not clock.due(dt.datetime.combine(day, dt.time(7, 59)))
    assert clock.due(dt.datetime.combine(day, dt.time(8, 1)))
    assert not clock.due(dt.datetime.combine(day, dt.time(9, 0)))
    assert clock.due(dt.datetime.combine(day + dt.timedelta(days=1), dt.time(8, 0)))


def test_engine_speaks_the_briefing():
    from atulya.shruti.listener import AmbientEngine

    class Client:
        sent = []

        async def chat(self, text):
            self.sent.append(text)
            return {"response_text": "Good morning. It is sunny."}

    class Speaker:
        said = []

        def say(self, text):
            self.said.append(text)

    engine = AmbientEngine(Client(), None, Speaker(), briefing_at="07:00", briefing_location="Delhi")
    run(engine.deliver_briefing())
    assert "Delhi" in Client.sent[0] and Speaker.said == ["Good morning. It is sunny."]


# ── voice commands reach the new tools ───────────────────────────────────

@pytest.mark.parametrize("text,tool,args", [
    ("good morning", "morning_briefing", {}),
    ("give me my briefing", "morning_briefing", {}),
    ("pause the music", "media_control", {"action": "play_pause"}),
    ("next song", "media_control", {"action": "next"}),
    ("volume up", "media_control", {"action": "volume_up"}),
    ("play arijit singh", "play_music", {"query": "arijit singh"}),
])
def test_router_maps_media_and_briefing(text, tool, args):
    routed = route_intent(text)
    assert routed is not None and routed.tool == tool and routed.arguments == args


def test_router_still_prefers_websites_for_play_on_site():
    routed = route_intent("play lofi on youtube")
    assert routed.tool == "open_website"


# ── piper voice ──────────────────────────────────────────────────────────

def test_speaker_picks_piper_when_configured(monkeypatch):
    import shutil

    from atulya.shruti.audio import Speaker

    monkeypatch.setenv("ATULYA_PIPER_MODEL", "voice.onnx")
    monkeypatch.setattr(shutil, "which", lambda name: "/bin/piper" if name == "piper" else None)
    assert Speaker().backend == "piper"
    monkeypatch.delenv("ATULYA_PIPER_MODEL")
    assert Speaker().backend != "piper"


# ── wake-word model gate ─────────────────────────────────────────────────

def test_wake_gate_fires_and_expires():
    np = pytest.importorskip("numpy")
    from atulya.shruti.audio import WakeGate

    now = [100.0]

    class Model:
        score = 0.0

        def predict(self, chunk):
            assert chunk.dtype == np.int16 and len(chunk) == WakeGate.CHUNK
            return {"atulya": self.score}

    model = Model()
    gate = WakeGate(model=model, threshold=0.5, window=10, clock=lambda: now[0])
    frame = np.zeros(WakeGate.CHUNK, dtype="float32")
    assert not gate.feed(frame) and not gate.recent()
    model.score = 0.9
    assert gate.feed(frame) and gate.recent()
    now[0] += 11
    assert not gate.recent()


def test_microphone_holds_back_speech_without_wake_word():
    pytest.importorskip("numpy")
    from atulya.shruti.audio import Microphone, WakeGate

    class Never:
        def predict(self, chunk):
            return {"x": 0.0}

    gate = WakeGate(model=Never())
    assert Microphone(gate=gate).gate is gate
    assert not gate.recent()


# ── speech language, local sign-in ───────────────────────────────────────

def test_pick_language_never_returns_arabic():
    from types import SimpleNamespace

    from atulya.vani.pipeline import pick_language

    noisy = SimpleNamespace(language="ar", all_language_probs=[("ar", 0.5), ("hi", 0.3), ("en", 0.1)])
    assert pick_language(noisy) == "hi"
    assert pick_language(SimpleNamespace(language="en", all_language_probs=[])) == "en"
    assert pick_language(SimpleNamespace(language="ar", all_language_probs=None)) in ("en", "hi")


def _client(host="127.0.0.1", headers=None):
    from fastapi.testclient import TestClient

    from atulya.sevak.app import app

    return TestClient(app, client=(host, 5000), headers=headers or {})


def test_local_signin_only_from_this_computer(monkeypatch):
    monkeypatch.delenv("ATULYA_REQUIRE_LOGIN", raising=False)
    assert _client().get("/api/auth/local").json()["token"]
    assert _client(host="192.168.1.20").get("/api/auth/local").status_code == 403
    assert _client(headers={"X-Forwarded-For": "8.8.8.8"}).get("/api/auth/local").status_code == 403
    monkeypatch.setenv("ATULYA_REQUIRE_LOGIN", "on")
    assert _client().get("/api/auth/local").status_code == 403


# ── echo guard ───────────────────────────────────────────────────────────

def test_is_echo_detects_parroting():
    from atulya.buddhi.llm import _echoed_memory, is_echo

    assert is_echo("who are you", "Who are you?")
    assert is_echo("who are you", "who are you")
    assert not is_echo("who are you", "I am Atulya, your assistant.")
    assert not is_echo("what time is it", "It's 10:20 PM.")
    assert _echoed_memory("Q: who are you\nA: Who are you?")
    assert _echoed_memory("Q: \nA: Who are you?")
    assert not _echoed_memory("Q: who are you\nA: I'm Atulya.")


def test_ask_retries_plainly_when_the_model_parrots(monkeypatch):
    from atulya.buddhi.llm import AtulyaLLM

    llm = AtulyaLLM(use_memory=False)
    calls = []

    async def fake_chat(prompt, system_prompt="", preferred_provider="", tools=None):
        calls.append(tools)
        return ("Who are you?" if len(calls) == 1 else "I am Atulya."), "fake"

    monkeypatch.setattr(llm.router, "chat", fake_chat)
    reply = asyncio.run(llm.ask("who are you"))
    assert reply.text == "I am Atulya." and len(calls) == 2 and calls[1] is None


def test_copied_memory_answer_is_detected():
    from atulya.buddhi.llm import copies_memory

    mem = ["Q: who are you\nA: I'm Atulya, an assistant."]
    assert copies_memory("tell me a joke", "I'm Atulya, an assistant.", mem)
    assert not copies_memory("who are you", "I'm Atulya, an assistant.", mem)
    assert not copies_memory("tell me a joke", "Why did the cat sit on the laptop?", mem)


def test_tiny_brain_recalls_only_when_asked_about_the_past(monkeypatch):
    from atulya.buddhi.llm import wants_memory

    monkeypatch.setenv("ATULYA_BRAIN", "tiny")
    assert not wants_memory("tell me a joke")
    assert wants_memory("do you remember what I told you yesterday")
    assert wants_memory("मुझे याद है")
    monkeypatch.setenv("ATULYA_BRAIN", "balanced")
    assert wants_memory("tell me a joke")


def test_clean_history_drops_parroted_and_repeated_replies():
    from atulya.buddhi.llm import AtulyaLLM, clean_history

    history = [
        {"role": "user", "content": "who are you"},
        {"role": "assistant", "content": "Who are you?"},                 # echo: dropped with its question
        {"role": "user", "content": "tell me a joke"},
        {"role": "assistant", "content": "I am Atulya, an assistant."},
        {"role": "user", "content": "what time is it"},
        {"role": "assistant", "content": "I am Atulya, an assistant."},   # repeat of an earlier reply: dropped
        {"role": "user", "content": "capital of France"},
    ]
    cleaned = clean_history(history)
    assert [m["content"] for m in cleaned] == [
        "tell me a joke", "I am Atulya, an assistant.", "capital of France"]
    assert "Who are you?" not in AtulyaLLM._compose_prompt("hi", history)


# ── Claude brain ─────────────────────────────────────────────────────────

def test_claude_leads_the_chain_only_with_a_key(monkeypatch):
    from atulya.buddhi.intelligence import AnthropicProvider, ProviderRouter

    router = ProviderRouter()
    assert isinstance(router.providers[0], AnthropicProvider)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert not router.providers[0].is_available()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert router.providers[0].is_available()


def test_claude_provider_calls_messages_api(monkeypatch):
    import urllib.request

    from atulya.buddhi.intelligence import AnthropicProvider

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    seen = {}

    def fake_urlopen(req, timeout=0):
        seen["url"], seen["headers"], seen["body"] = req.full_url, dict(req.header_items()), json.loads(req.data)
        return _Resp({"content": [{"type": "text", "text": " Hello there. "}]})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    reply = run(AnthropicProvider().chat("hi", "be brief"))
    assert reply == "Hello there."
    assert seen["url"].endswith("/v1/messages")
    assert seen["headers"]["X-api-key"] == "sk-ant-test"
    assert seen["body"]["system"] == "be brief" and seen["body"]["messages"][0]["content"] == "hi"


def test_openrouter_skips_busy_and_empty_free_models(monkeypatch):
    from atulya.buddhi.intelligence import OpenRouterProvider

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("ATULYA_OPENROUTER_MODEL", "a:free,b:free,c:free")
    tried = []

    def fake_ask(self, model, messages):
        tried.append(model)
        if model == "a:free":
            raise RuntimeError("HTTP Error 429")
        if model == "b:free":
            return ""  # a reasoning model that ran out of tokens thinking
        return "Hello."

    monkeypatch.setattr(OpenRouterProvider, "_ask", fake_ask)
    assert run(OpenRouterProvider().chat("hi")) == "Hello."
    assert tried == ["a:free", "b:free", "c:free"]


# ── no emoji in speech ───────────────────────────────────────────────────

def test_emoji_are_never_spoken():
    from atulya.shruti.listener import speakable
    from atulya.textutil import strip_emoji
    from atulya.vani.pipeline import TextToSpeech

    assert strip_emoji("Hello! \U0001F60A How are you? \u2764\ufe0f") == "Hello! How are you?"
    assert strip_emoji("नमस्ते \U0001F44B") == "नमस्ते"
    assert strip_emoji("Plain text, 100% fine.") == "Plain text, 100% fine."
    assert "\U0001F60A" not in speakable("Great job \U0001F60A")
    assert TextToSpeech.strip_ssml("<break time='1s'/>Hi \U0001F600") == "... Hi"


# ── abilities answer and moderation-label guard ──────────────────────────

@pytest.mark.parametrize("text", ["what can you do", "what all you can do", "what are your abilities", "help"])
def test_what_can_you_do_is_answered_by_a_tool_not_a_model(text):
    routed = route_intent(text)
    assert routed is not None and routed.tool == "what_can_you_do"
    from atulya.yantra.agent import tools

    answer = run(tools.execute_tool("what_can_you_do"))
    assert "reminders" in answer and "music" in answer


def test_safety_classifier_labels_are_not_answers():
    from atulya.buddhi.intelligence import _looks_like_safety_label

    assert _looks_like_safety_label("Harassment")
    assert _looks_like_safety_label("safe")
    assert _looks_like_safety_label("Category: violence")
    assert not _looks_like_safety_label("I can help you with reminders and music.")
    assert not _looks_like_safety_label("")


# ── admin-only details ───────────────────────────────────────────────────

@pytest.fixture
def two_users(tmp_path, monkeypatch):
    import atulya.sevak.users as users_mod
    from atulya.sevak import helpers

    monkeypatch.setattr(users_mod, "USERS_FILE", tmp_path / "users.json")
    monkeypatch.setattr(users_mod, "SESSIONS_FILE", tmp_path / "sessions.json")
    users_mod._sessions.clear()
    monkeypatch.setattr(helpers, "ADMIN_TOKEN", "admin-test-token")
    users_mod.create_user("sam", "pw", role="user", display_name="Sam")
    return {"user": users_mod.create_session("sam"), "admin": "admin-test-token"}


ADMIN_ONLY = ["/api/brain", "/api/health", "/api/telemetry", "/api/system", "/api/audit", "/api/agent/tools",
              "/api/agent/status", "/api/devices", "/api/users", "/api/routines", "/api/senses", "/api/triggers"]


@pytest.mark.parametrize("path", ADMIN_ONLY)
def test_normal_users_cannot_read_admin_pages(two_users, path):
    client = _client()
    assert client.get(path, headers={"X-Atulya-Token": two_users["user"]}).status_code == 403
    assert client.get(path, headers={"X-Atulya-Token": two_users["admin"]}).status_code != 403


def test_bootstrap_hides_models_from_normal_users(two_users):
    client = _client()
    normal = client.get("/api/dashboard/bootstrap", headers={"X-Atulya-Token": two_users["user"]}).json()
    assert normal["providers"] == [] and "system" not in normal
    admin = client.get("/api/dashboard/bootstrap", headers={"X-Atulya-Token": two_users["admin"]}).json()
    assert admin["providers"] and "system" in admin


def test_chat_replies_hide_model_details_from_normal_users():
    from atulya.sevak.helpers import redact_for

    reply = {"response": "Hi", "provider": "Claude (haiku)", "model_id": "x", "steps": [{"tool": "t"}],
             "trace": [{"stage": "think"}], "needs_approval": False}
    seen = redact_for({"role": "user"}, dict(reply))
    assert seen["response"] == "Hi" and seen["provider"] == "Atulya" and seen["steps"] == [] and seen["trace"] == []
    assert redact_for({"role": "admin"}, dict(reply)) == reply


def test_models_list_is_admin_only(two_users):
    client = _client()
    assert client.get("/v1/models", headers={"Authorization": f"Bearer {two_users['user']}"}).status_code == 403
    assert client.get("/v1/models", headers={"Authorization": f"Bearer {two_users['admin']}"}).status_code == 200


# ── build helper ─────────────────────────────────────────────────────────

def test_ensure_build_rebuilds_when_source_content_changes(tmp_path, monkeypatch):
    import importlib.util
    import os
    import time
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("web_build", Path(__file__).resolve().parents[1] / "web" / "build.py")
    eb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(eb)

    (tmp_path / "frontend").mkdir()
    src = tmp_path / "frontend" / "main.jsx"
    src.write_text("x")
    dist = tmp_path / "dist" / "index.html"
    dist.parent.mkdir()
    dist.write_text("built")
    monkeypatch.setattr(eb, "DIST", dist)
    monkeypatch.setattr(eb, "STAMP", tmp_path / "dist" / ".source-hash")
    monkeypatch.setattr(eb, "SOURCES", [tmp_path / "frontend"])
    assert eb.needs_build()                      # built, but never stamped: treat as stale
    eb.STAMP.write_text(eb.source_hash())
    assert not eb.needs_build()                  # up to date
    later = time.time() + 100
    os.utime(src, (later, later))
    assert not eb.needs_build()                  # a newer file time alone changes nothing
    src.write_text("y")
    assert eb.needs_build()                      # the content changed
    dist.unlink()
    assert eb.needs_build()                      # no build yet


def test_busy_cloud_message_when_no_brain_answers(monkeypatch):
    from atulya.buddhi.intelligence import CLOUD_BUSY_MESSAGE, NO_BRAIN_MESSAGE, ProviderRouter

    router = ProviderRouter()
    router.providers = []  # nothing answers
    for key in ("ANTHROPIC_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "NVIDIA_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    assert run(router.chat("hi"))[0] == NO_BRAIN_MESSAGE
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    assert run(router.chat("hi"))[0] == CLOUD_BUSY_MESSAGE
