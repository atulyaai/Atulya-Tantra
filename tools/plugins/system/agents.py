"""Owner-scoped paired devices and durable, acknowledged jobs."""
import hashlib
import json
import re
import secrets
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit

COMMANDS = {
    "ping", "say", "open_url", "open_app",
    "list_files", "read_file",
    "take_photo", "list_photos",
    "media_control", "send_sms", "place_call",
    "display_message", "battery_status",
}


class AgentHub:
    def __init__(self, data_dir):
        self.path = Path(data_dir) / "agents.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS devices (owner TEXT, name TEXT, abilities TEXT, token_hash TEXT UNIQUE, seen REAL, revoked INTEGER DEFAULT 0, PRIMARY KEY(owner,name))")
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, owner TEXT, device TEXT, kind TEXT, detail TEXT, status TEXT, created REAL, updated REAL, output TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS device_presence (owner TEXT, name TEXT, mode TEXT, PRIMARY KEY(owner,name))")
            db.execute("CREATE TABLE IF NOT EXISTS device_metadata (owner TEXT, name TEXT, device_type TEXT, PRIMARY KEY(owner,name))")

    NAME = r"[A-Za-z0-9][A-Za-z0-9 _'-]{0,39}"  # e.g. "Atul's Phone"; always shown as plain text

    def pair(self, owner, name, abilities, device_type="generic"):
        device_type = {"phone": "android", "laptop": "pc"}.get(device_type, device_type)
        if device_type not in {"generic", "android", "pc", "tv", "tablet"}:
            raise ValueError("Unsupported device type")
        if not re.fullmatch(self.NAME, name):
            raise ValueError("Use a short device name with letters, numbers, spaces or hyphens")
        if not owner or not abilities or set(abilities) - COMMANDS:
            raise ValueError("Choose supported device abilities")
        token = secrets.token_urlsafe(32)
        with closing(sqlite3.connect(self.path)) as db, db:
            if db.execute("SELECT 1 FROM devices WHERE owner=? AND name=? AND revoked=0", (owner, name)).fetchone():
                raise ValueError("Device name already paired; revoke it before pairing again")
            db.execute("DELETE FROM devices WHERE owner=? AND name=? AND revoked=1", (owner, name))
            db.execute("INSERT INTO devices VALUES(?,?,?,?,?,0)",
                       (owner, name, json.dumps(sorted(set(abilities))), hashlib.sha256(token.encode()).hexdigest(), 0))
            db.execute("INSERT INTO device_metadata VALUES(?,?,?) ON CONFLICT(owner,name) DO UPDATE SET device_type=excluded.device_type", (owner, name, device_type))
        return {"name": name, "token": token, "abilities": sorted(set(abilities))}

    def authenticate(self, token):
        if not token or len(token) > 200:
            return None
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("SELECT owner,name FROM devices WHERE token_hash=? AND revoked=0",
                             (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        return {"owner": row[0], "name": row[1]} if row else None

    def devices(self, owner):
        with closing(sqlite3.connect(self.path)) as db:
            rows = db.execute("SELECT d.name,d.abilities,d.seen,p.mode,m.device_type FROM devices d LEFT JOIN device_presence p ON p.owner=d.owner AND p.name=d.name LEFT JOIN device_metadata m ON m.owner=d.owner AND m.name=d.name WHERE d.owner=? AND d.revoked=0", (owner,)).fetchall()
        return [{"name": r[0], "abilities": json.loads(r[1]), "seen": r[2],
                 "status": "online" if r[2] and time.time() - r[2] < 90 else "offline", "mode": r[3] or "unknown", "device_type": r[4] or "generic"} for r in rows]

    def rename(self, owner, name, new_name):
        """Give a paired device a friendlier name; its credential and job history stay attached."""
        new_name = " ".join(str(new_name).replace("’", "'").split())
        if not re.fullmatch(self.NAME, new_name):
            raise ValueError("Use a short name with letters, numbers, spaces, hyphens or ' (up to 40)")
        with closing(sqlite3.connect(self.path)) as db, db:
            if not db.execute("SELECT 1 FROM devices WHERE owner=? AND name=? AND revoked=0", (owner, name)).fetchone():
                raise ValueError(f"No paired device called '{name}'")
            if new_name == name:
                return {"name": name}
            if db.execute("SELECT 1 FROM devices WHERE owner=? AND name=? AND revoked=0", (owner, new_name)).fetchone():
                raise ValueError(f"You already have a device called '{new_name}'")
            db.execute("DELETE FROM devices WHERE owner=? AND name=? AND revoked=1", (owner, new_name))
            db.execute("UPDATE devices SET name=? WHERE owner=? AND name=?", (new_name, owner, name))
            db.execute("UPDATE jobs SET device=? WHERE owner=? AND device=?", (new_name, owner, name))
        return {"name": new_name}

    def revoke(self, owner, name):
        with closing(sqlite3.connect(self.path)) as db, db:
            cursor = db.execute("UPDATE devices SET revoked=1 WHERE owner=? AND name=? AND revoked=0", (owner, name))
            db.execute("UPDATE jobs SET status='cancelled',updated=? WHERE owner=? AND device=? AND status='queued'", (time.time(), owner, name))
            return cursor.rowcount == 1

    def enqueue(self, owner, device, kind, detail=""):
        if kind not in COMMANDS or len(detail) > 2000:
            raise ValueError("Unsupported device command")
        if kind == "open_url":
            url = urlsplit(detail)
            if url.scheme != "https" or not url.hostname or url.username:
                raise ValueError("Device links must use HTTPS")
        with closing(sqlite3.connect(self.path)) as db, db:
            row = db.execute("SELECT abilities FROM devices WHERE owner=? AND name=? AND revoked=0", (owner, device)).fetchone()
            if not row or kind not in json.loads(row[0]):
                raise ValueError("Device is not paired to you or lacks this ability")
            if db.execute("SELECT count(*) FROM jobs WHERE owner=? AND device=? AND status='queued'", (owner, device)).fetchone()[0] >= 20:
                raise ValueError("Device queue is full; connect the device first")
            job = {"id": secrets.token_urlsafe(16), "device": device, "kind": kind, "detail": detail, "status": "queued"}
            db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)", (job["id"], owner, device, kind, detail, "queued", time.time(), time.time(), ""))
        return job

    def poll(self, owner, name, passive=False):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute("UPDATE devices SET seen=? WHERE owner=? AND name=? AND revoked=0", (time.time(), owner, name))
            if not cursor.rowcount:
                raise ValueError("Device unavailable")
            db.execute("INSERT INTO device_presence VALUES(?,?,?) ON CONFLICT(owner,name) DO UPDATE SET mode=excluded.mode",
                       (owner, name, "background" if passive else "foreground"))
            # Never replay a side effect after an uncertain disconnect.
            db.execute("UPDATE jobs SET status='unconfirmed',updated=? WHERE owner=? AND device=? AND status='running' AND updated<?",
                       (time.time(), owner, name, time.time() - 120))
            safe_filter = " AND kind IN ('ping','battery_status')" if passive else ""
            rows = db.execute("SELECT id,kind,detail FROM jobs WHERE owner=? AND device=? AND status='queued'" + safe_filter + " ORDER BY created LIMIT 5", (owner, name)).fetchall()
            for row in rows:
                db.execute("UPDATE jobs SET status='running',updated=? WHERE id=?", (time.time(), row[0]))
        return [{"id": r[0], "kind": r[1], "detail": r[2]} for r in rows]

    def waiting_for_foreground(self, owner, name):
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute("SELECT count(*) FROM jobs WHERE owner=? AND device=? AND status='queued' AND kind NOT IN ('ping','battery_status')", (owner, name)).fetchone()[0]

    def complete(self, owner, name, job_id, output, success=True):
        with closing(sqlite3.connect(self.path)) as db, db:
            cursor = db.execute("UPDATE jobs SET status=?,output=?,updated=? WHERE id=? AND owner=? AND device=? AND status IN ('running','unconfirmed')",
                                ("executed" if success else "failed", output[:4000], time.time(), job_id, owner, name))
            if cursor.rowcount == 1:
                return True
            row = db.execute("SELECT status,output FROM jobs WHERE id=? AND owner=? AND device=?",
                             (job_id, owner, name)).fetchone()
            return bool(row and row == ("executed" if success else "failed", output[:4000]))

    def jobs(self, owner):
        with closing(sqlite3.connect(self.path)) as db, db:
            # Status must settle even when a disconnected device never polls again.
            db.execute("UPDATE jobs SET status='unconfirmed',updated=? WHERE owner=? AND status='running' AND updated<?",
                       (time.time(), owner, time.time() - 120))
            db.row_factory = sqlite3.Row
            rows = db.execute("SELECT id,device,kind,status,created,updated,output FROM jobs WHERE owner=? ORDER BY created DESC LIMIT 50", (owner,)).fetchall()
        return [dict(row) for row in rows]
