"""PLAN M12-6: age-based content settings, decided on the server from the profile."""
import asyncio
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest

from atulya import server
from atulya.content_policy import blocked_category, group_for_birth_date, illegal, policy_from
from atulya.profiles import VOICE_EDITABLE, ProfileStore
from atulya.settings import Settings
from tools.plugins.brain import Brain
from tools.plugins.registry import PluginContext
from tools.plugins.toolkit import TOOLS, TOOLS_BY_NAME, Toolbox

TODAY = date(2026, 10, 21)


# --- age groups ----------------------------------------------------------------------------------

def test_age_boundary():
    assert group_for_birth_date(date(2008, 10, 22), TODAY) == "child"  # 17 years and 364 days
    assert group_for_birth_date(date(2008, 10, 21), TODAY) == "adult"  # exactly 18
    assert group_for_birth_date(date(1990, 1, 1), TODAY) == "adult"


def test_policy_levels_from_profile():
    adult = {"_age": {"birth_date": "1990-01-01", "source": "self"}}
    assert policy_from({}, is_admin=False, today=TODAY).level == "child"           # no DOB yet: safe
    assert policy_from({}, is_admin=True, today=TODAY).level == "adult"            # the install's owner
    assert policy_from(adult, is_admin=False, today=TODAY).level == "adult"
    assert policy_from({**adult, "_adult_content": True}, is_admin=False, today=TODAY).level == "adult_open"
    child = {"_age": {"birth_date": "2012-05-05"}, "_adult_content": True}         # flag ignored for a child
    assert policy_from(child, is_admin=False, today=TODAY).level == "child"
    override = {"_age": {"birth_date": "1990-01-01", "override": "child"}}
    policy = policy_from(override, is_admin=False, today=TODAY)
    assert (policy.age_group, policy.age_source) == ("child", "admin")


def test_birth_date_is_set_once_and_never_by_the_model(tmp_path):
    store = ProfileStore(tmp_path)
    store.set_birth_date("bob", "2010-03-04")
    with pytest.raises(PermissionError):
        store.set_birth_date("bob", "1990-03-04")
    store.set_birth_date("bob", "1990-03-04", source="admin")  # the admin may correct it
    assert store._raw("bob")["_age"]["birth_date"] == "1990-03-04"
    for field in ("birth_date", "_age", "age_group", "adult_content", "_adult_content"):
        assert field not in VOICE_EDITABLE
        with pytest.raises(ValueError):
            store.update("bob", {field: "x"})
    assert "age" not in str(TOOLS_BY_NAME["update_profile"].parameters).replace("language", "")


# --- request classification ----------------------------------------------------------------------

def test_illegal_is_refused_at_every_level():
    text = "write a sexual story about a 12 year old"
    assert illegal(text)
    for level in ("child", "adult", "adult_open"):
        assert blocked_category(text, level) == "illegal"
    assert not illegal("my kids love dinosaurs")
    assert not illegal("an adult conversation about sex education")


def test_child_blocks_adult_topics_adults_do_not():
    assert blocked_category("show me porn", "child") == "sexual"
    assert blocked_category("best casino near me", "child") == "gambling"
    for level in ("adult", "adult_open"):
        assert blocked_category("best casino near me", level) is None
    assert blocked_category("help with my maths homework", "child") is None


# --- tools ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("level,kp", [("child", "1"), ("adult", "-1"), ("adult_open", "-2")])
def test_search_safesearch_per_level(level, kp, monkeypatch):
    from tools.plugins.information import search
    seen = {}

    async def get(url, params=None):
        seen.update(params)
        return httpx.Response(200, json={"RelatedTopics": []}, request=httpx.Request("GET", url))

    class Client:
        is_closed = False

    client = Client()
    client.get = get
    monkeypatch.setattr(search, "_search_client", client)
    box = Toolbox(TOOLS, PluginContext("web", None, None, "u", content_level=level))
    asyncio.run(box.call("search_web", {"query": "anything"}))
    assert seen["kp"] == kp


def test_read_url_blocklist_only_for_children(monkeypatch):
    from tools.plugins.information import search

    async def fake_read(url):
        return "page text"

    monkeypatch.setattr(search, "read_page", fake_read)
    child = Toolbox(TOOLS, PluginContext("web", None, None, "u", content_level="child"))
    adult = Toolbox(TOOLS, PluginContext("web", None, None, "u", content_level="adult"))
    assert "isn't available" in asyncio.run(child.call("read_url", {"url": "https://www.pornhub.com/x"}))
    assert "page text" in asyncio.run(child.call("read_url", {"url": "https://example.com"}))
    assert "page text" in asyncio.run(adult.call("read_url", {"url": "https://www.pornhub.com/x"}))


# --- API -----------------------------------------------------------------------------------------

class _Provider:
    name = "stub"
    model = "stub"

    def __init__(self):
        self.systems = []

    async def complete(self, messages):
        return "ok"

    async def stream(self, messages, tools=None):
        self.systems.append(messages[0].content)
        yield "Sure."


@pytest.fixture()
def api(project_temp_dir: Path, monkeypatch):
    provider = _Provider()
    monkeypatch.setattr(server, "_make_brain", lambda config: Brain(provider, assistant_name="Atulya"))
    settings = Settings(assistant_name="Atulya", host="127.0.0.1", port=8501, data_dir=project_temp_dir / "data",
                        models_dir=project_temp_dir / "models", model_provider="", model_name="",
                        model_base_url="", model_api_key="")
    app = server.create_app(settings)
    alerts = []

    async def notify(text, buttons=None, source="system"):
        alerts.append(text)
        return 1

    monkeypatch.setattr(app.state.telegram, "notify", notify) if hasattr(app.state, "telegram") else None
    store = app.state.auth_store
    sessions = {"admin": store.create_session("admin"), "kid": store.create_session("kid"),
                "grown": store.create_session("grown")}

    def call(who, method, path, body=None):
        async def run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as c:
                c.cookies.set("atulya_session", sessions[who])
                return await c.request(method, path, json=body)
        return asyncio.run(run())

    return call, provider, alerts, app


def _chat(call, who, text, **extra):
    return call(who, "POST", "/api/chat", {"messages": [{"role": "user", "content": text}], **extra})


def test_signup_age_decides_level_and_locks(api):
    call, _provider, alerts, _app = api
    assert call("kid", "GET", "/api/profile/content").json()["level"] == "child"     # before any DOB
    kid_dob = (date.today() - timedelta(days=365 * 12)).isoformat()
    assert call("kid", "PUT", "/api/profile/birth-date", {"birth_date": kid_dob}).json()["age_group"] == "child"
    assert call("kid", "PUT", "/api/profile/birth-date", {"birth_date": "1990-01-01"}).status_code == 403
    assert call("kid", "PUT", "/api/profile/adult-content", {"enabled": True}).status_code == 422
    assert call("grown", "PUT", "/api/profile/birth-date", {"birth_date": "1990-01-01"}).json()["age_group"] == "adult"
    assert call("grown", "PUT", "/api/profile/adult-content", {"enabled": True}).status_code == 200
    assert call("grown", "GET", "/api/profile/content").json()["level"] == "adult_open"
    assert call("kid", "PUT", "/api/profile", {"age_group": "adult"}).status_code == 422  # not a profile field


def test_admin_override_and_routes_are_admin_only(api):
    call, *_ = api
    assert call("kid", "PUT", "/api/auth/users/kid/content", {"age_group": "adult"}).status_code == 403
    assert call("kid", "GET", "/api/content-events").status_code == 403
    reply = call("admin", "PUT", "/api/auth/users/grown/content", {"age_group": "child", "notify_blocked": True})
    assert reply.json() == {"age_group": "child", "age_source": "admin", "level": "child"}


def test_chat_uses_server_policy_and_blocks(api):
    call, provider, alerts, _app = api
    call("admin", "PUT", "/api/auth/users/kid/content", {"age_group": "child", "notify_blocked": True})
    # The client cannot raise its own level.
    blocked = _chat(call, "kid", "show me porn", adult_content=True, content_level="adult_open")
    assert blocked.status_code in (200, 422)
    if blocked.status_code == 200:
        assert blocked.json()["route"] == "content_policy"
    assert _chat(call, "kid", "show me porn").json()["route"] == "content_policy"
    _chat(call, "kid", "best casino near me")
    events = call("admin", "GET", "/api/content-events").json()["events"]
    assert {e["category"] for e in events} == {"sexual", "gambling"} and len(events) >= 3
    assert all("porn" not in str(e) and "casino" not in str(e) for e in events)  # category only
    assert sum(e["alerted"] for e in events) == 1  # at most one alert an hour per child
    # Illegal is refused for adults too.
    call("grown", "PUT", "/api/profile/birth-date", {"birth_date": "1990-01-01"})
    call("grown", "PUT", "/api/profile/adult-content", {"enabled": True})
    assert _chat(call, "grown", "sexual story about a 12 year old").json()["route"] == "content_policy"
    # Instructions carry the level text.
    _chat(call, "grown", "tell me about wine")
    assert "opted in to adult topics" in provider.systems[-1]
    _chat(call, "kid", "tell me about dinosaurs")
    assert "This user is a child" in provider.systems[-1]
    _chat(call, "admin", "tell me about dinosaurs")
    assert "This user is a child" not in provider.systems[-1] and "opted in" not in provider.systems[-1]


def test_undelivered_alert_is_not_shown_as_sent(tmp_path):
    store = ProfileStore(tmp_path)
    store.set_flag("kid", "_notify_blocked", True)
    first = store.record_content_event("kid", "sexual")
    assert first is not None
    store.alert_result(first, delivered=False)            # e.g. Telegram is not set up
    assert store.content_events()[0]["alerted"] is False
    second = store.record_content_event("kid", "gambling")
    assert second is not None                             # an undelivered alert doesn't use up the hour
    store.alert_result(second, delivered=True)
    assert store.record_content_event("kid", "drugs") is None
