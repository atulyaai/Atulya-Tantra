import json
import sqlite3
import time
from contextlib import closing
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from atulya.auth import AuthStore, SESSION_COOKIE
from atulya.google_auth import register_google_routes, challenge


def make_app(path):
    auth = AuthStore(path)
    auth.ensure_user("alice", "Alice")
    auth.add_alias("alice@example.com", "alice")
    app = FastAPI()
    def cookie(response, request, token):
        response.set_cookie(SESSION_COOKIE, token, httponly=True, secure=True)
    register_google_routes(app, SimpleNamespace(data_dir=path, public_origin="https://atulya.example"), auth, cookie)
    return app, auth


def test_google_connect_needs_existing_session_and_requests_explicit_scopes(project_temp_dir, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    app, auth = make_app(project_temp_dir)
    with TestClient(app, base_url="https://atulya.example", follow_redirects=False) as client:
        assert client.get("/api/auth/google/start?connect=true").status_code == 401
        client.cookies.set(SESSION_COOKIE, auth.create_session("alice"))
        result = client.get("/api/auth/google/start?connect=true&features=gmail")
        params = parse_qs(urlsplit(result.headers["location"]).query)
        assert "gmail.send" in params["scope"][0]
        assert "calendar.events" not in params["scope"][0]
        assert params["prompt"] == ["consent"]
        assert params["code_challenge_method"] == ["S256"]


def test_google_callback_rejects_wrong_identity_claims(project_temp_dir, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    app, _ = make_app(project_temp_dir)
    original = httpx.AsyncClient
    claims = {"aud": "client", "iss": "https://accounts.google.com", "email_verified": "true",
              "email": "alice@example.com", "exp": str(int(time.time())+600), "nonce": "wrong"}
    def handler(request):
        if request.url.path == "/token":
            return httpx.Response(200, json={"id_token":"opaque"})
        return httpx.Response(200, json=claims)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    with TestClient(app, base_url="https://atulya.example", follow_redirects=False) as client:
        response = client.get("/api/auth/google/start")
        state = parse_qs(urlsplit(response.headers["location"]).query)["state"][0]
        response = client.get("/api/auth/google/callback", params={"state":state,"code":"authcode"})
        assert response.headers["location"] == "/#google=failed"
        assert SESSION_COOKIE not in client.cookies
        assert not (project_temp_dir/"google_tokens.json").exists()


def test_app_login_returns_session_only_to_original_verifier(project_temp_dir, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    app, auth = make_app(project_temp_dir)
    original = httpx.AsyncClient
    claims = {"aud": "client", "iss": "https://accounts.google.com", "email_verified": "true",
              "email":"alice@example.com", "exp":str(int(time.time())+600)}
    def handler(request):
        return httpx.Response(200, json={"id_token":"opaque"} if request.url.path=="/token" else claims)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    verifier = "A" * 43
    with TestClient(app, base_url="https://atulya.example", follow_redirects=False) as client:
        response = client.get("/api/auth/google/start", params={"app_challenge":challenge(verifier)})
        state = parse_qs(urlsplit(response.headers["location"]).query)["state"][0]
        with closing(sqlite3.connect(project_temp_dir/"oauth.sqlite3")) as db:
            payload = json.loads(db.execute("SELECT payload FROM flows WHERE id=?", (state,)).fetchone()[0])
        claims["nonce"] = payload["nonce"]
        client.cookies.clear()
        response = client.get("/api/auth/google/callback", params={"state":state,"code":"authcode"})
        assert response.status_code == 200 and SESSION_COOKIE not in client.cookies
        with closing(sqlite3.connect(project_temp_dir/"oauth.sqlite3")) as db:
            assert db.execute("SELECT user_id FROM handoffs").fetchone()[0] == "alice"
        # Extract the URL-encoded opaque handoff from the generated return link.
        import re
        handoff = re.search(r"handoff=([A-Za-z0-9_-]{43})", response.text).group(1)
        assert client.post("/api/auth/google/app", data={"handoff":handoff,"verifier":"B"*43}).status_code == 401
        response = client.post("/api/auth/google/app", data={"handoff":handoff,"verifier":verifier})
        assert response.status_code == 303
        assert auth.user_for_session(client.cookies.get(SESSION_COOKIE)) == "alice"
        assert client.post("/api/auth/google/app", data={"handoff":handoff,"verifier":verifier}).status_code == 401
