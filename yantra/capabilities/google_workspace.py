"""Google sign-in for Gmail and Google Calendar.

One click in the web UI ("Connect Google") signs a user in with Google's OAuth
consent screen; after that "check my email", "what's on my calendar" and
"schedule a call with Rahul tomorrow at 3pm" use their real Gmail and Calendar.

* Each Atulya user connects their own Google account — nobody reads anyone
  else's mail. Scheduled automations use ``ATULYA_GOOGLE_DEFAULT_USER``'s
  account, or the only connected one.
* Standard OAuth 2.0 authorization-code flow with PKCE and a single-use,
  10-minute ``state`` bound to the user who started it.
* Tokens stay on this machine (``ATULYA_GOOGLE_DIR``, owner-only files) and
  are refreshed automatically; "Disconnect" revokes them at Google.
* Sending mail and deleting events still ask for confirmation (safety policy).

Setup (once): create an OAuth client in Google Cloud Console, enable the Gmail
and Google Calendar APIs, add the redirect URI shown in the UI, and paste the
client ID and secret into the UI (or set GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET).
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
CALENDAR_API = "https://www.googleapis.com/calendar/v3/calendars/primary"
SCOPES = [
    "openid",
    "email",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
]
STATE_TTL_SECONDS = 600
AUTOMATION_USERS = {"", "default", "automation", "trigger"}


class GoogleError(RuntimeError):
    pass


class GoogleNotConnected(GoogleError):
    pass


def _dir() -> Path:
    return Path(os.environ.get("ATULYA_GOOGLE_DIR", "assets/agent/google"))


def _safe(user: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", user or "default")[:64]


def _write_private(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        tmp.chmod(0o600)
    except OSError:
        pass
    tmp.replace(path)


# ── the OAuth client (the app's identity at Google) ───────────────────────
def client_config() -> dict[str, str]:
    """Client ID/secret from the environment, else from the UI-saved file."""
    cid, secret = os.environ.get("GOOGLE_CLIENT_ID", ""), os.environ.get("GOOGLE_CLIENT_SECRET", "")
    if cid and secret:
        return {"client_id": cid, "client_secret": secret, "source": "environment"}
    try:
        saved = json.loads((_dir() / "client.json").read_text(encoding="utf-8"))
        if saved.get("client_id") and saved.get("client_secret"):
            return {"client_id": saved["client_id"], "client_secret": saved["client_secret"], "source": "settings"}
    except (OSError, json.JSONDecodeError):
        pass
    return {"client_id": "", "client_secret": "", "source": ""}


def save_client_config(client_id: str, client_secret: str) -> None:
    client_id, client_secret = client_id.strip(), client_secret.strip()
    if not client_id.endswith(".apps.googleusercontent.com") or not client_secret:
        raise GoogleError("that doesn't look like a Google OAuth client ID and secret")
    _write_private(_dir() / "client.json", {"client_id": client_id, "client_secret": client_secret})


# ── sign-in (authorization code + PKCE) ───────────────────────────────────
_PENDING: dict[str, dict[str, Any]] = {}
_PENDING_LOCK = threading.Lock()


def begin_sign_in(user: str, redirect_uri: str) -> str:
    """The Google consent URL to send this user to."""
    cfg = client_config()
    if not cfg["client_id"]:
        raise GoogleError("Google isn't set up yet — add an OAuth client ID and secret first")
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(32)
    now = time.time()
    with _PENDING_LOCK:
        for key in [k for k, v in _PENDING.items() if now - v["created"] > STATE_TTL_SECONDS]:
            _PENDING.pop(key, None)
        _PENDING[state] = {"user": user, "verifier": verifier, "redirect_uri": redirect_uri, "created": now}
    return AUTH_URL + "?" + urlencode({
        "client_id": cfg["client_id"], "redirect_uri": redirect_uri, "response_type": "code",
        "scope": " ".join(SCOPES), "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
        "access_type": "offline", "prompt": "consent", "include_granted_scopes": "true",
    })


async def finish_sign_in(state: str, code: str, transport: Any = None) -> tuple[str, str]:
    """Exchange the code; returns (atulya user, google email). The state is single-use."""
    with _PENDING_LOCK:
        pending = _PENDING.pop(state or "", None)
    if pending is None or time.time() - pending["created"] > STATE_TTL_SECONDS:
        raise GoogleError("this sign-in link has expired or was already used — please try again")
    cfg = client_config()
    async with httpx.AsyncClient(timeout=20, transport=transport) as client:
        resp = await client.post(TOKEN_URL, data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": pending["redirect_uri"],
            "client_id": cfg["client_id"], "client_secret": cfg["client_secret"],
            "code_verifier": pending["verifier"],
        })
        if resp.status_code != 200:
            raise GoogleError(f"Google didn't accept the sign-in ({resp.status_code})")
        tokens = resp.json()
        info = await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {tokens['access_token']}"})
    email = info.json().get("email", "") if info.status_code == 200 else ""
    if not tokens.get("refresh_token"):
        raise GoogleError("Google didn't grant offline access — remove Atulya's access in your Google account and retry")
    account = GoogleAccount(pending["user"], transport=transport)
    account._save({"refresh_token": tokens["refresh_token"], "access_token": tokens.get("access_token", ""),
                   "expires_at": time.time() + int(tokens.get("expires_in", 3600)) - 60,
                   "scope": tokens.get("scope", ""), "email": email, "connected_at": time.time()})
    return pending["user"], email


# ── one user's Google account ─────────────────────────────────────────────
class GoogleAccount:
    def __init__(self, user: str, transport: Any = None):
        self.user = user
        self._transport = transport
        self.path = _dir() / f"{_safe(user)}.json"

    @classmethod
    def for_current_user(cls, transport: Any = None) -> "GoogleAccount":
        """The account of whoever the current request is for (see yantra.identity)."""
        from yantra.identity import current_user

        user = current_user.get()
        if user in AUTOMATION_USERS:
            user = os.environ.get("ATULYA_GOOGLE_DEFAULT_USER", "") or cls._only_connected() or user
        return cls(user, transport=transport)

    @staticmethod
    def _only_connected() -> str:
        accounts = [p.stem for p in _dir().glob("*.json") if p.stem != "client"] if _dir().exists() else []
        return accounts[0] if len(accounts) == 1 else ""

    def _load(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self, data: dict[str, Any]) -> None:
        _write_private(self.path, data)

    @property
    def connected(self) -> bool:
        return bool(self._load().get("refresh_token"))

    def status(self) -> dict[str, Any]:
        data = self._load()
        return {"connected": bool(data.get("refresh_token")), "email": data.get("email", ""),
                "scopes": (data.get("scope") or "").split(), "connected_at": data.get("connected_at")}

    async def disconnect(self) -> bool:
        data = self._load()
        if not data:
            return False
        try:
            async with httpx.AsyncClient(timeout=10, transport=self._transport) as client:
                await client.post(REVOKE_URL, data={"token": data.get("refresh_token", "")})
        except httpx.HTTPError as exc:  # revoke is best-effort; the local copy is removed regardless
            logger.info("google revoke failed: %s", exc)
        self.path.unlink(missing_ok=True)
        return True

    async def _access_token(self) -> str:
        data = self._load()
        if not data.get("refresh_token"):
            raise GoogleNotConnected("Google isn't connected — connect it under Settings → Accounts")
        if data.get("access_token") and time.time() < float(data.get("expires_at", 0)):
            return str(data["access_token"])
        cfg = client_config()
        async with httpx.AsyncClient(timeout=20, transport=self._transport) as client:
            resp = await client.post(TOKEN_URL, data={
                "grant_type": "refresh_token", "refresh_token": data["refresh_token"],
                "client_id": cfg["client_id"], "client_secret": cfg["client_secret"],
            })
        if resp.status_code != 200:
            if "invalid_grant" in resp.text:  # revoked or expired at Google
                self.path.unlink(missing_ok=True)
                raise GoogleNotConnected("Google access was revoked — please connect Google again")
            raise GoogleError(f"couldn't refresh Google access ({resp.status_code})")
        fresh = resp.json()
        data.update(access_token=fresh["access_token"],
                    expires_at=time.time() + int(fresh.get("expires_in", 3600)) - 60)
        self._save(data)
        return str(data["access_token"])

    async def _api(self, method: str, url: str, **kwargs: Any) -> Any:
        token = await self._access_token()
        async with httpx.AsyncClient(timeout=20, transport=self._transport) as client:
            resp = await client.request(method, url, headers={"Authorization": f"Bearer {token}"}, **kwargs)
        if resp.status_code == 401:
            raise GoogleNotConnected("Google rejected Atulya's access — please connect Google again")
        if resp.status_code >= 400:
            raise GoogleError(f"Google returned {resp.status_code}: {resp.text[:160]}")
        return resp.json() if resp.content else {}

    # ── Gmail ──────────────────────────────────────────────────────────────
    async def list_messages(self, query: str = "in:inbox", limit: int = 5) -> list[dict[str, str]]:
        found = await self._api("GET", f"{GMAIL_API}/messages", params={"q": query, "maxResults": max(1, min(limit, 20))})
        messages = []
        for item in found.get("messages") or []:
            msg = await self._api("GET", f"{GMAIL_API}/messages/{item['id']}", params=[
                ("format", "metadata"), ("metadataHeaders", "From"), ("metadataHeaders", "Subject"),
                ("metadataHeaders", "Date")])
            headers = {h["name"].lower(): h["value"] for h in (msg.get("payload") or {}).get("headers") or []}
            messages.append({"id": item["id"], "from": headers.get("from", ""), "subject": headers.get("subject", ""),
                             "date": headers.get("date", ""), "snippet": msg.get("snippet", ""),
                             "unread": "UNREAD" in (msg.get("labelIds") or [])})
        return messages

    async def send_message(self, to: str, subject: str, body: str) -> str:
        msg = EmailMessage()
        sender = self._load().get("email")
        if sender:
            msg["From"] = sender
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        sent = await self._api("POST", f"{GMAIL_API}/messages/send", json={"raw": raw})
        return str(sent.get("id", ""))

    # ── Calendar ───────────────────────────────────────────────────────────
    async def list_events(self, days: int = 7, now: datetime | None = None) -> list[dict[str, str]]:
        start = now or datetime.now(timezone.utc)
        data = await self._api("GET", f"{CALENDAR_API}/events", params={
            "timeMin": start.isoformat(), "timeMax": (start + timedelta(days=max(1, days))).isoformat(),
            "singleEvents": "true", "orderBy": "startTime", "maxResults": 25})
        events = []
        for e in data.get("items") or []:
            when = (e.get("start") or {}).get("dateTime") or (e.get("start") or {}).get("date") or ""
            events.append({"id": e.get("id", ""), "title": e.get("summary") or "(no title)", "start": when,
                           "location": e.get("location", "")})
        return events

    async def create_event(self, title: str, start_ts: float, minutes: int = 60, description: str = "") -> dict:
        start = datetime.fromtimestamp(start_ts).astimezone()
        end = start + timedelta(minutes=max(5, minutes))
        return await self._api("POST", f"{CALENDAR_API}/events", json={
            "summary": title, "description": description,
            "start": {"dateTime": start.isoformat()}, "end": {"dateTime": end.isoformat()}})

    async def delete_event(self, event_id: str) -> None:
        await self._api("DELETE", f"{CALENDAR_API}/events/{event_id}")


def friendly_time(value: str) -> str:
    """'2026-09-28T10:00:00+05:30' -> 'Mon 28 Sep 10:00'; all-day dates as 'Mon 28 Sep'."""
    try:
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().strftime("%a %d %b %H:%M")
        return datetime.fromisoformat(value).strftime("%a %d %b")
    except ValueError:
        return value
