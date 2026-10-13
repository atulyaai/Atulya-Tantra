"""Google Gmail and Calendar helpers using stored OAuth refresh token."""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

DATA_DIR = Path(os.environ.get("ATULYA_DATA_DIR", "data"))
TOKEN_FILE = DATA_DIR / "google_tokens.json"

GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"


def _load_tokens() -> dict:
    if not TOKEN_FILE.exists():
        return {}
    try:
        return json.loads(TOKEN_FILE.read_text())
    except Exception:
        return {}


def save_refresh_token(user_id: str, refresh_token: str, email: str = "") -> None:
    tokens = _load_tokens()
    tokens[user_id] = {"refresh_token": refresh_token, "email": email}
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(tokens))
    TOKEN_FILE.chmod(0o600)


def get_refresh_token(user_id: str) -> str | None:
    return (_load_tokens().get(user_id) or {}).get("refresh_token")


async def get_access_token(user_id: str) -> str | None:
    refresh = get_refresh_token(user_id)
    if not refresh:
        return None
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return None
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh,
                "grant_type": "refresh_token",
            },
        )
        if resp.status_code != 200:
            return None
        return resp.json().get("access_token")


async def gmail_search(user_id: str, query: str, limit: int = 5) -> str:
    token = await get_access_token(user_id)
    if not token:
        return "NEEDS_GOOGLE_AUTH: sign in with Google again (Gmail scope required)."
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{GMAIL_API}/messages",
            params={"q": query, "maxResults": limit},
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            return f"Gmail error: {resp.status_code}"
        messages = resp.json().get("messages") or []
        if not messages:
            return f"No Gmail messages matching {query!r}."
        lines = [f"Gmail results for {query!r}:"]
        for msg in messages[:limit]:
            detail = await client.get(
                f"{GMAIL_API}/messages/{msg['id']}",
                params={"format": "metadata", "metadataHeaders": "Subject,From,Date"},
                headers={"Authorization": f"Bearer {token}"},
            )
            if detail.status_code != 200:
                continue
            headers = {h["name"]: h["value"] for h in detail.json().get("payload", {}).get("headers", [])}
            lines.append(f"- {headers.get('Date', '')} | {headers.get('From', '')} | {headers.get('Subject', '(no subject)')}")
        return "\n".join(lines)


async def gmail_drafts(user_id: str) -> str:
    token = await get_access_token(user_id)
    if not token:
        return "NEEDS_GOOGLE_AUTH: sign in with Google again (Gmail scope required)."
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{GMAIL_API}/drafts",
            params={"maxResults": 10},
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            return f"Gmail drafts error: {resp.status_code}"
        drafts = resp.json().get("drafts") or []
        if not drafts:
            return "No Gmail drafts."
        return f"{len(drafts)} draft(s) found."


async def calendar_search(user_id: str, query: str) -> str:
    token = await get_access_token(user_id)
    if not token:
        return "NEEDS_GOOGLE_AUTH: sign in with Google again (Calendar scope required)."
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{CALENDAR_API}/calendars/primary/events",
            params={"q": query, "maxResults": 10, "singleEvents": True, "orderBy": "startTime"},
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            return f"Calendar error: {resp.status_code}"
        items = resp.json().get("items") or []
        if not items:
            return f"No calendar events matching {query!r}."
        lines = [f"Calendar events for {query!r}:"]
        for item in items:
            start = (item.get("start") or {}).get("dateTime") or (item.get("start") or {}).get("date") or ""
            lines.append(f"- {start} | {item.get('summary', '(no title)')}")
        return "\n".join(lines)
