"""A private server queue; audible playback and receipts come from the client."""
import re
import secrets
import sqlite3
import time
import json
import subprocess
import sys
import importlib.util
from contextlib import closing
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


def search_music(query: str, limit: int = 5) -> list[dict]:
    """Resolve names to video metadata only, with a hard timeout and no media downloads."""
    query = query.strip()
    if not query or len(query) > 150:
        raise ValueError("Enter a song or artist name of 1 to 150 characters")
    if importlib.util.find_spec("yt_dlp") is None:
        raise ValueError("Music search is unavailable: install the project's music extra (yt-dlp) on the server. You can still paste a video URL.")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--ignore-config", "--flat-playlist", "--dump-single-json",
             "--skip-download", "--no-warnings", "--quiet", "--no-cache-dir", "--socket-timeout", "8",
             "--retries", "0", "--extractor-retries", "0", "--", f"ytsearch{max(1, min(limit, 5))}:{query}"],
            capture_output=True, text=True, encoding="utf-8", timeout=25,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        if result.returncode:
            raise ValueError("YouTube search failed. Check server connectivity or paste a video URL.")
        data = json.loads(result.stdout)
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Music search timed out. Try again or paste a video URL.") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Music search could not return usable results. Try a video URL.") from exc
    tracks = []
    for item in data.get("entries", []) or []:
        if not isinstance(item, dict) or not re.fullmatch(r"[A-Za-z0-9_-]{11}", str(item.get("id", ""))):
            continue
        tracks.append({"video_id": item["id"], "url": "https://www.youtube.com/watch?v=" + item["id"],
                       "title": str(item.get("title") or "YouTube video")[:150],
                       "artist": str(item.get("channel") or item.get("uploader") or "")[:150]})
    return tracks[:limit]


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
        return [dict(row) for row in rows]

    def receipt(self, user_id, track_id, state, error=""):
        if state not in {"ready","playing","paused","ended","failed","cancelled"}:
            raise ValueError("Invalid playback state")
        with closing(sqlite3.connect(self.path)) as db, db:
            result=db.execute("UPDATE tracks SET state=?,error=?,updated=? WHERE user_id=? AND id=?",(state,error[:200],time.time(),user_id,track_id))
            return result.rowcount == 1


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
    class Search(BaseModel):
        query: str = Field(min_length=1, max_length=150)
    search_slots = asyncio.Semaphore(2)

    @app.post("/api/music/search")
    async def search(body: Search, request: Request):
        async with search_slots:
            try:
                return {"tracks": await asyncio.to_thread(search_music, body.query)}
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
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
