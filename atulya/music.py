"""A private server queue; audible playback and receipts come from the client."""
import re
import secrets
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


def youtube_id(url):
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or parsed.username or parsed.port not in {None, 443}:
        raise ValueError("Use a normal HTTPS YouTube video link")
    if host == "youtu.be":
        video = parsed.path.strip("/")
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        video = parse_qs(parsed.query).get("v", [""])[0] if parsed.path == "/watch" else parsed.path.split("/")[-1] if parsed.path.startswith(("/shorts/", "/embed/")) else ""
    else:
        video = ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video):
        raise ValueError("Provide one YouTube video link, not a search or playlist")
    return video


async def find_youtube(query, limit=5):
    """The top YouTube result for a request ("play Kesariya") that YouTube allows inside other apps.

    Returns {"video_id", "title"} or None. Uses YouTube's public results page and oEmbed (no API key);
    oEmbed answers 401 for videos whose owners block embedding, so the in-app player never gets one of those.
    """
    import httpx

    query = " ".join(str(query).split())[:150]
    if not query:
        return None
    # Desktop page: the mobile one (m.youtube.com) carries results in a different, script-built form.
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
               "Accept-Language": "en-IN,en;q=0.8"}
    async with httpx.AsyncClient(timeout=httpx.Timeout(10, connect=5), headers=headers, follow_redirects=True) as client:
        try:
            page = await client.get("https://www.youtube.com/results", params={"search_query": query})
            page.raise_for_status()
        except httpx.HTTPError:
            return None
        candidates = list(dict.fromkeys(re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', page.text)))[:limit]
        for video in candidates:
            try:
                check = await client.get("https://www.youtube.com/oembed",
                                         params={"url": f"https://www.youtube.com/watch?v={video}", "format": "json"})
            except httpx.HTTPError:
                continue
            if check.status_code == 200:
                return {"video_id": video, "title": str(check.json().get("title") or query)[:150]}
    return None


class MusicStore:
    def __init__(self, data_dir):
        self.path = Path(data_dir) / "music.sqlite3"
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS tracks(id TEXT PRIMARY KEY,user_id TEXT,video_id TEXT,title TEXT,state TEXT,created REAL,updated REAL,error TEXT)")

    def add(self, user_id, url, title=""):
        video = youtube_id(url)
        track = {"id":secrets.token_urlsafe(12), "video_id":video, "title":title[:150] or "YouTube video", "state":"queued"}
        with closing(sqlite3.connect(self.path)) as db, db:
            if db.execute("SELECT count(*) FROM tracks WHERE user_id=? AND state IN ('queued','ready','playing','paused')", (user_id,)).fetchone()[0] >= 30:
                raise ValueError("Music queue is full")
            db.execute("INSERT INTO tracks VALUES(?,?,?,?,?,?,?,?)", (track["id"],user_id,video,track["title"],"queued",time.time(),time.time(),""))
        return track

    def list(self, user_id):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory=sqlite3.Row
            rows=db.execute("SELECT id,video_id,title,state,updated,error FROM tracks WHERE user_id=? ORDER BY created DESC LIMIT 30", (user_id,)).fetchall()
        tracks = [dict(row) for row in rows]
        for track in tracks:
            track["receipt_age_seconds"] = max(0, int(time.time() - track["updated"]))
            track["verification"] = "Client-reported player state; audible output is not verified."
            if track["state"] == "playing" and track["receipt_age_seconds"] > 45:
                track["state"] = "unconfirmed"
                track["verification"] = "Player heartbeat is stale; current playback is unconfirmed."
        return tracks

    def receipt(self, user_id, track_id, state, error=""):
        if state not in {"ready","playing","paused","ended","failed","cancelled"}:
            raise ValueError("Invalid playback state")
        with closing(sqlite3.connect(self.path)) as db, db:
            if state == "cancelled":
                condition = ""
            else:
                condition = " AND state!='cancelled'"
            result=db.execute("UPDATE tracks SET state=?,error=?,updated=? WHERE user_id=? AND id=?" + condition,(state,error[:200],time.time(),user_id,track_id))
            return result.rowcount == 1


async def music_status_tool(_args, ctx):
    if ctx is None:
        return "Sign in to inspect your music queue."
    import asyncio
    import json
    from atulya.settings import Settings
    tracks = await asyncio.to_thread(MusicStore(Settings.from_environment().data_dir).list, ctx.user_id)
    return json.dumps({"tracks": tracks, "limits": "Client player receipts are not proof of audible sound. Stale playing receipts are unconfirmed."})


def register_music_routes(app, data_dir):
    from fastapi import HTTPException, Request
    from pydantic import BaseModel, Field
    import asyncio
    store=MusicStore(data_dir)
    class Add(BaseModel):
        url: str = Field(max_length=500)
        title: str = Field(default="",max_length=150)
    class Receipt(BaseModel):
        state: str
        error: str = Field(default="",max_length=200)
    @app.get("/api/music")
    async def queue(request: Request):
        return {"tracks":await asyncio.to_thread(store.list,str(request.state.user_id)),
                "delivery":"Playback requires an open Atulya player on your device; queued is not playing."}
    @app.post("/api/music",status_code=201)
    async def add(body: Add,request: Request):
        try:
            return await asyncio.to_thread(store.add,str(request.state.user_id),body.url,body.title)
        except ValueError as exc:
            raise HTTPException(422,str(exc)) from exc
    @app.post("/api/music/{track_id}/receipt")
    async def receipt(track_id: str,body: Receipt,request: Request):
        try:
            ok=await asyncio.to_thread(store.receipt,str(request.state.user_id),track_id,body.state,body.error)
        except ValueError as exc:
            raise HTTPException(422,str(exc)) from exc
        if not ok:
            raise HTTPException(404,"Track not found")
        return {"updated":True}
