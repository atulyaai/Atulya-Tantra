"""Google login and explicit Gmail/Calendar connection, with proof-bound Android handoff."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import json
import os
import re
import secrets
import sqlite3
import time
from contextlib import closing
from urllib.parse import parse_qs, urlencode

import httpx
from fastapi import HTTPException, Request
from starlette.responses import HTMLResponse, RedirectResponse

from .auth import SESSION_COOKIE

IDENTITY = {"openid", "email", "profile"}
GMAIL = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_SEND = "https://www.googleapis.com/auth/gmail.send"
CALENDAR = "https://www.googleapis.com/auth/calendar.events"
COOKIE = "atulya_oauth_state"


def challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")


class OAuthFlows:
    def __init__(self, data_dir):
        self.path = data_dir / "oauth.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS flows (id TEXT PRIMARY KEY, payload TEXT, expires INTEGER)")
            db.execute("CREATE TABLE IF NOT EXISTS handoffs (id TEXT PRIMARY KEY, user_id TEXT, proof TEXT, expires INTEGER)")

    def start(self, payload):
        state = secrets.token_urlsafe(32)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM flows WHERE expires<?", (int(time.time()),))
            db.execute("INSERT INTO flows VALUES(?,?,?)", (state, json.dumps(payload), int(time.time()) + 600))
        return state

    def consume(self, state):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM flows WHERE id=? AND expires>?", (state, int(time.time()))).fetchone()
            db.execute("DELETE FROM flows WHERE id=?", (state,))
        return json.loads(row[0]) if row else None

    def handoff(self, user_id, proof):
        code = secrets.token_urlsafe(32)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM handoffs WHERE expires<?", (int(time.time()),))
            db.execute("INSERT INTO handoffs VALUES(?,?,?,?)", (hashlib.sha256(code.encode()).hexdigest(), user_id,
                                                               proof, int(time.time()) + 120))
        return code

    def exchange(self, code, verifier):
        if not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", verifier) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", code):
            return None
        digest = hashlib.sha256(code.encode()).hexdigest()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT user_id,proof FROM handoffs WHERE id=? AND expires>?", (digest, int(time.time()))).fetchone()
            if row is None or not secrets.compare_digest(row[1], challenge(verifier)):
                return None
            db.execute("DELETE FROM handoffs WHERE id=?", (digest,))
            return row[0]


def register_google_routes(app, config, auth_store, set_cookie):
    flows = OAuthFlows(config.data_dir)

    def origin(request):
        return config.public_origin or f"{request.url.scheme}://{request.headers['host']}"

    @app.get("/api/auth/google/start")
    async def start(request: Request, connect: bool = False, app_challenge: str = "", features: str = "all"):
        client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
        if not client_id or not os.environ.get("GOOGLE_CLIENT_SECRET", "").strip():
            raise HTTPException(503, "Google connection is not configured on this server.")
        if app_challenge and not re.fullmatch(r"[A-Za-z0-9_-]{43}", app_challenge):
            raise HTTPException(422, "Invalid app proof")
        user_id = await asyncio.to_thread(auth_store.user_for_session, request.cookies.get(SESSION_COOKIE))
        if connect and not user_id:
            raise HTTPException(401, "Sign in to Atulya before connecting Google services.")
        scopes = set(IDENTITY)
        if connect:
            if features not in {"gmail", "calendar", "all"}:
                raise HTTPException(422, "Choose Gmail, Calendar or both")
            if features in {"gmail", "all"}:
                scopes.update({GMAIL, GMAIL_SEND})
            if features in {"calendar", "all"}:
                scopes.add(CALENDAR)
        payload = {"connect_user": user_id if connect else None, "app_proof": app_challenge,
                   "verifier": secrets.token_urlsafe(48), "nonce": secrets.token_urlsafe(24),
                   "redirect": origin(request) + "/api/auth/google/callback", "requested": sorted(scopes)}
        state = await asyncio.to_thread(flows.start, payload)
        params = {"client_id": client_id, "redirect_uri": payload["redirect"], "response_type": "code",
                  "scope": " ".join(sorted(scopes)), "state": state, "nonce": payload["nonce"],
                  "code_challenge": challenge(payload["verifier"]), "code_challenge_method": "S256"}
        if connect:
            params.update(access_type="offline", include_granted_scopes="true", prompt="consent")
        response = RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))
        response.set_cookie(COOKIE, state, httponly=True, secure=origin(request).startswith("https://"),
                            samesite="lax", max_age=600, path="/api/auth/google")
        return response

    @app.get("/api/auth/google/callback")
    async def callback(request: Request, code: str = "", state: str = "", error: str = ""):
        flow = await asyncio.to_thread(flows.consume, state)
        if not flow or error or not code:
            return RedirectResponse("/#google=failed")
        if not flow["app_proof"] and not secrets.compare_digest(request.cookies.get(COOKIE, ""), state):
            return RedirectResponse("/#google=failed")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                result = await client.post("https://oauth2.googleapis.com/token", data={
                    "code": code, "client_id": os.environ["GOOGLE_CLIENT_ID"],
                    "client_secret": os.environ["GOOGLE_CLIENT_SECRET"], "redirect_uri": flow["redirect"],
                    "grant_type": "authorization_code", "code_verifier": flow["verifier"]})
                result.raise_for_status()
                tokens = result.json()
                verified = await client.get("https://oauth2.googleapis.com/tokeninfo", params={"id_token": tokens.get("id_token", "")})
                verified.raise_for_status()
                info = verified.json()
            if (info.get("aud") != os.environ["GOOGLE_CLIENT_ID"] or info.get("iss") not in
                    {"accounts.google.com", "https://accounts.google.com"} or
                    info.get("email_verified") not in {True, "true"} or info.get("nonce") != flow["nonce"] or
                    int(info.get("exp", 0)) <= time.time()):
                raise ValueError("Identity verification failed")
            email = str(info.get("email", "")).lower()
            if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                raise ValueError("Invalid email")
            user_id = flow["connect_user"] or await asyncio.to_thread(auth_store.resolve_login, email)
            account = await asyncio.to_thread(auth_store.user, user_id)
            if account is None:
                try:
                    await asyncio.to_thread(auth_store.create_signup, str(info.get("name", email)), email, None, "google")
                except ValueError:
                    pass
                return RedirectResponse("/#google=pending")
            if account["disabled_at"] is not None:
                raise ValueError("Account unavailable")
            if flow["connect_user"]:
                from tools.plugins.information.google_api import save_connection
                await asyncio.to_thread(save_connection, user_id, tokens, email, config.data_dir)
                resolved = await asyncio.to_thread(auth_store.resolve_login, email)
                if resolved in {email, user_id}:
                    await asyncio.to_thread(auth_store.add_alias, email, user_id)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return RedirectResponse("/#google=failed")
        response = RedirectResponse("/#google=ok")
        response.delete_cookie(COOKIE, path="/api/auth/google")
        if flow["app_proof"]:
            handoff = await asyncio.to_thread(flows.handoff, user_id, flow["app_proof"])
            link = origin(request) + "/api/auth/google/finish?handoff=" + handoff
            intent = "intent://" + link.split("://", 1)[1] + "#Intent;scheme=https;package=com.atulvij.atulya;end"
            response = HTMLResponse("<!doctype html><html><meta name='viewport' content='width=device-width'>"
                                    "<title>Return to Atulya</title><body style='font:20px system-ui;padding:30px'>"
                                    "<h1>Google connection completed</h1><p>Return to the app to finish signing in.</p>"
                                    f"<p><a href='{html.escape(intent, quote=True)}'>Open Atulya app</a></p>"
                                    f"<p><a href='{html.escape(link, quote=True)}'>Use verified app link</a></p>"
                                    "<p>This link expires in two minutes.</p></body></html>")
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
        else:
            set_cookie(response, request, await asyncio.to_thread(auth_store.create_session, user_id))
        return response

    @app.get("/api/auth/google/finish")
    async def finish():
        return HTMLResponse("<p>Open this link in the Atulya app that started Google sign-in. "
                            "A link alone cannot sign another device in. If it expired, start again in the app.</p>")

    @app.post("/api/auth/google/app")
    async def app_exchange(request: Request):
        raw = await request.body()
        if len(raw) > 1000:
            raise HTTPException(422, "Invalid handoff")
        body = parse_qs(raw.decode("ascii", errors="replace"))
        user_id = await asyncio.to_thread(flows.exchange, body.get("handoff", [""])[0], body.get("verifier", [""])[0])
        account = await asyncio.to_thread(auth_store.user, user_id) if user_id else None
        if account is None or account["disabled_at"] is not None:
            raise HTTPException(401, "App sign-in expired or belongs to another device. Start Google sign-in again.")
        response = RedirectResponse("/", status_code=303)
        set_cookie(response, request, await asyncio.to_thread(auth_store.create_session, user_id))
        return response

    @app.get("/api/google/status")
    async def status(request: Request):
        from tools.plugins.information.google_api import connection_status
        return await asyncio.to_thread(connection_status, str(request.state.user_id), config.data_dir)

    @app.post("/api/google/test")
    async def test(request: Request):
        from tools.plugins.information.google_api import test_connection
        return await test_connection(str(request.state.user_id), config.data_dir)

    @app.delete("/api/google/connection")
    async def disconnect(request: Request):
        from tools.plugins.information.google_api import remove_connection
        await asyncio.to_thread(remove_connection, str(request.state.user_id), config.data_dir)
        return {"disconnected": True}
