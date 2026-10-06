"""Google sign-in (OAuth + PKCE), token refresh, Gmail and Calendar, and the
email/calendar tools acting for the right user — against a fake Google."""
from __future__ import annotations

import asyncio
import base64
import email
import hashlib
import json
import os
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

CLIENT_ID = "123-abc.apps.googleusercontent.com"


class FakeGoogle:
    def __init__(self):
        self.challenge = ""
        self.sent: list[dict] = []
        self.created: list[dict] = []
        self.deleted: list[str] = []
        self.refreshes = 0
        self.revoke_refresh = False
        self.revoked: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        path = request.url.path
        if url.startswith("https://oauth2.googleapis.com/token"):
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            if form["grant_type"] == "authorization_code":
                digest = base64.urlsafe_b64encode(hashlib.sha256(form["code_verifier"].encode()).digest())
                if digest.rstrip(b"=").decode() != self.challenge or form["code"] != "good-code":
                    return httpx.Response(400, json={"error": "invalid_grant"})
                return httpx.Response(200, json={"access_token": "at1", "expires_in": 3600,
                                                  "refresh_token": "rt1", "scope": "email gmail"})
            self.refreshes += 1
            if self.revoke_refresh:
                return httpx.Response(400, json={"error": "invalid_grant"})
            return httpx.Response(200, json={"access_token": f"at{self.refreshes + 1}", "expires_in": 3600})
        if url.startswith("https://oauth2.googleapis.com/revoke"):
            self.revoked.append(parse_qs(request.content.decode())["token"][0])
            return httpx.Response(200)
        if url.startswith("https://openidconnect.googleapis.com/v1/userinfo"):
            return httpx.Response(200, json={"email": "atul@gmail.com"})
        assert request.headers["Authorization"].startswith("Bearer at")
        if path.endswith("/messages") and request.method == "GET":
            return httpx.Response(200, json={"messages": [{"id": "m1"}, {"id": "m2"}]})
        if path.endswith("/messages/send"):
            self.sent.append(json.loads(request.content))
            return httpx.Response(200, json={"id": "s1"})
        if "/messages/" in path:
            mid = path.rsplit("/", 1)[-1]
            headers = [{"name": "From", "value": "Rahul Sharma <rahul@example.com>" if mid == "m1" else "bank@x.com"},
                       {"name": "Subject", "value": "Lunch tomorrow?" if mid == "m1" else "Statement"}]
            return httpx.Response(200, json={"snippet": "hi", "labelIds": ["UNREAD"] if mid == "m1" else [],
                                             "payload": {"headers": headers}})
        if path.endswith("/events") and request.method == "GET":
            return httpx.Response(200, json={"items": [
                {"id": "e1", "summary": "Standup", "start": {"dateTime": "2026-09-28T10:00:00+00:00"}}]})
        if path.endswith("/events") and request.method == "POST":
            self.created.append(json.loads(request.content))
            return httpx.Response(200, json={"id": "e2"})
        if "/events/" in path and request.method == "DELETE":
            self.deleted.append(path.rsplit("/", 1)[-1])
            return httpx.Response(204)
        return httpx.Response(404)


@pytest.fixture
def google(tmp_path, monkeypatch):
    """A fake Google behind every httpx client, and a clean token directory."""
    from atulya import web as google_workspace

    fake = FakeGoogle()
    transport = httpx.MockTransport(fake)
    real = httpx.AsyncClient

    class Routed(real):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(google_workspace.httpx, "AsyncClient", Routed)
    monkeypatch.setenv("ATULYA_GOOGLE_DIR", str(tmp_path / "google"))
    monkeypatch.setenv("GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "shh")
    monkeypatch.delenv("ATULYA_GOOGLE_DEFAULT_USER", raising=False)
    google_workspace._PENDING.clear()
    return fake


def connect(fake: FakeGoogle, user: str = "atul") -> str:
    from atulya.web import begin_sign_in, finish_sign_in

    url = begin_sign_in(user, "http://localhost:8000/api/google/callback")
    params = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    fake.challenge = params["code_challenge"]
    asyncio.run(finish_sign_in(params["state"], "good-code"))
    return params["state"]


# ── sign-in ───────────────────────────────────────────────────────────────

class TestSignIn:
    def test_consent_url(self, google):
        from atulya.web import begin_sign_in

        url = begin_sign_in("atul", "http://localhost:8000/api/google/callback")
        q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
        assert q["client_id"] == CLIENT_ID and q["code_challenge_method"] == "S256" and q["access_type"] == "offline"
        assert "https://www.googleapis.com/auth/gmail.send" in q["scope"].split()
        assert "https://www.googleapis.com/auth/calendar.events" in q["scope"].split()

    def test_full_flow_stores_private_tokens(self, google, tmp_path):
        from atulya.web import GoogleAccount

        connect(google)
        account = GoogleAccount("atul")
        assert account.status()["connected"] and account.status()["email"] == "atul@gmail.com"
        if os.name == "posix":
            assert oct(account.path.stat().st_mode & 0o777) == "0o600"
        assert not GoogleAccount("meera").connected  # per user

    def test_state_is_single_use_and_bound(self, google):
        from atulya.web import GoogleError, finish_sign_in

        state = connect(google)
        with pytest.raises(GoogleError, match="expired or was already used"):
            asyncio.run(finish_sign_in(state, "good-code"))
        with pytest.raises(GoogleError):
            asyncio.run(finish_sign_in("made-up", "good-code"))

    def test_expired_state(self, google, monkeypatch):
        from atulya import web as google_workspace
        from atulya.web import GoogleError, begin_sign_in, finish_sign_in

        url = begin_sign_in("atul", "http://x/cb")
        state = parse_qs(urlparse(url).query)["state"][0]
        google_workspace._PENDING[state]["created"] -= google_workspace.STATE_TTL_SECONDS + 1
        with pytest.raises(GoogleError):
            asyncio.run(finish_sign_in(state, "good-code"))

    def test_needs_a_client_first(self, tmp_path, monkeypatch):
        from atulya.web import GoogleError, begin_sign_in, client_config, save_client_config

        monkeypatch.setenv("ATULYA_GOOGLE_DIR", str(tmp_path))
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
        with pytest.raises(GoogleError, match="isn't set up"):
            begin_sign_in("atul", "http://x/cb")
        with pytest.raises(GoogleError):
            save_client_config("not-a-client-id", "s")
        save_client_config(CLIENT_ID, "secret")
        assert client_config()["source"] == "settings"
        if os.name == "posix":
            assert oct((tmp_path / "client.json").stat().st_mode & 0o777) == "0o600"


# ── tokens ────────────────────────────────────────────────────────────────

class TestTokens:
    def test_refresh_when_expired(self, google):
        from atulya.web import GoogleAccount

        connect(google)
        account = GoogleAccount("atul")
        data = account._load()
        data["expires_at"] = 0
        account._save(data)
        asyncio.run(account.list_events())
        assert google.refreshes == 1 and account._load()["access_token"] == "at2"
        asyncio.run(account.list_events())
        assert google.refreshes == 1  # reused until it expires

    def test_revoked_at_google_disconnects(self, google):
        from atulya.web import GoogleAccount, GoogleNotConnected

        connect(google)
        account = GoogleAccount("atul")
        data = account._load()
        data["expires_at"] = 0
        account._save(data)
        google.revoke_refresh = True
        with pytest.raises(GoogleNotConnected, match="connect Google again"):
            asyncio.run(account.list_events())
        assert not account.connected

    def test_disconnect_revokes(self, google):
        from atulya.web import GoogleAccount

        connect(google)
        assert asyncio.run(GoogleAccount("atul").disconnect())
        assert google.revoked == ["rt1"] and not GoogleAccount("atul").connected


# ── the tools, acting for the right person ────────────────────────────────

class TestTools:
    def test_email_and_calendar_use_the_users_google(self, google):
        from atulya import actions as tools
        from atulya.persona import acting_as

        connect(google)

        async def run():
            with acting_as("atul"):
                inbox = await tools.fetch_emails(limit=2)
                sent = await tools.send_email("priya@example.com", "Dinner", "At 8?")
                agenda = await tools.calendar_list(days=3)
                added = await tools.calendar_add("Call with Rahul", "tomorrow at 3pm", 30)
                removed = await tools.calendar_remove("e1")
            return inbox, sent, agenda, added, removed

        inbox, sent, agenda, added, removed = asyncio.run(run())
        assert inbox.splitlines()[1:] == ["1. Rahul Sharma — Lunch tomorrow? (unread)", "2. bank@x.com — Statement"]
        assert sent == "Email sent to priya@example.com: 'Dinner' (Gmail)"
        mime = email.message_from_bytes(base64.urlsafe_b64decode(google.sent[0]["raw"]))
        assert (mime["To"], mime["Subject"], mime["From"]) == ("priya@example.com", "Dinner", "atul@gmail.com")
        assert agenda.startswith("1. Standup — ") and "(id: e1)" in agenda
        assert added.startswith("Added to Google Calendar: 'Call with Rahul'")
        event = google.created[0]
        assert event["summary"] == "Call with Rahul" and event["start"]["dateTime"][11:16] == "15:00"
        assert removed == "Event removed from Google Calendar." and google.deleted == ["e1"]

    def test_someone_else_does_not_get_your_mail(self, google):
        from atulya import actions as tools
        from atulya.persona import acting_as

        connect(google, user="atul")

        async def run():
            with acting_as("guest"):
                return await tools.fetch_emails()

        assert "Rahul" not in asyncio.run(run())

    def test_automations_use_the_only_connected_account(self, google):
        from atulya import actions as tools
        from atulya.persona import acting_as

        connect(google, user="atul")

        async def run():
            with acting_as("automation"):
                return await tools.fetch_emails()

        assert "Rahul Sharma" in asyncio.run(run())

    def test_kernel_acts_for_the_requesting_user(self, google, tmp_path):
        from atulya.settings import EventBus
        from atulya.pipeline import CognitiveKernel, Planner, ProfileStore, RoutineStore

        connect(google, user="atul")
        kernel = CognitiveKernel(llm=object(), events=EventBus(), planner=Planner(RoutineStore(tmp_path / "r.json")),
                                 profiles=ProfileStore(tmp_path / "p"))
        mine = asyncio.run(kernel.handle("check my email", user={"username": "atul", "role": "admin"}))
        theirs = asyncio.run(kernel.handle("check my email", user={"username": "meera", "role": "admin"}))
        assert "Rahul Sharma" in mine.text and "Rahul" not in theirs.text
        scheduled = asyncio.run(kernel.handle("schedule a call with Rahul tomorrow at 3pm",
                                              user={"username": "atul", "role": "admin"}))
        assert scheduled.text.startswith("Added to Google Calendar: 'Call with Rahul'")


def test_schedule_intents():
    from atulya.actions import route_intent

    r = route_intent("schedule lunch with Priya next monday at 1pm for 90 minutes")
    assert r.tool == "calendar_add"
    assert r.arguments == {"title": "Lunch with Priya", "date": "next monday at 1pm", "duration_minutes": 90}
    assert route_intent("add dentist appointment on friday at 10am to my calendar").arguments == {
        "title": "Dentist appointment", "date": "on friday at 10am"}
    assert route_intent("book a table") is None  # no time: the brain asks
    assert route_intent("what's on my calendar today").arguments == {"days": 1}


def test_reminder_at_a_clock_time_now_works():
    from atulya.actions import _parse_time

    assert _parse_time("at 5pm") is not None and _parse_time("today at 6pm") is not None


# ── routes ────────────────────────────────────────────────────────────────

class TestGoogleApi:
    @pytest.fixture
    def client(self, google, monkeypatch):
        from fastapi.testclient import TestClient

        from atulya import api as helpers
        from atulya.server import app

        monkeypatch.setattr(helpers, "ADMIN_TOKEN", "test_token")
        monkeypatch.delenv("ATULYA_PUBLIC_URL", raising=False)
        return TestClient(app)

    def test_connect_callback_disconnect(self, client, google):
        h = {"X-Atulya-Token": "test_token"}
        status = client.get("/api/google/status", headers=h).json()
        assert status["configured"] and not status["account"]["connected"]
        assert status["redirect_uri"] == "http://testserver/api/google/callback"
        url = client.post("/api/google/connect", headers=h).json()["url"]
        q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        google.challenge = q["code_challenge"]
        page = client.get(f"/api/google/callback?state={q['state']}&code=good-code")
        assert page.status_code == 200 and "atul@gmail.com" in page.text
        assert client.get(f"/api/google/callback?state={q['state']}&code=good-code").status_code == 400
        assert "cancelled" in client.get("/api/google/callback?error=access_denied").text
        assert client.get("/api/google/status", headers=h).json()["account"]["email"] == "atul@gmail.com"
        assert client.post("/api/google/disconnect", headers=h).json()["ok"]
        assert not client.get("/api/google/status", headers=h).json()["account"]["connected"]

    def test_client_setup_is_admin_only(self, client):
        assert client.post("/api/google/client", json={"client_id": CLIENT_ID, "client_secret": "s"}).status_code == 401
        h = {"X-Atulya-Token": "test_token"}
        assert client.post("/api/google/client", json={"client_id": "x", "client_secret": "s"},
                           headers=h).status_code == 400
        assert client.post("/api/google/client", json={"client_id": CLIENT_ID, "client_secret": "s"},
                           headers=h).json()["ok"]
