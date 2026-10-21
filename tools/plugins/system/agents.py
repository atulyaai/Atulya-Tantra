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
    "file_search", "file_stat", "file_copy", "file_move", "file_rename", "file_write", "file_trash",
}
# "voice_loop" is not a job: it lets that device token call the spoken-turn routes as its owner.
ABILITIES = COMMANDS | {"voice_loop"}
_TYPES = {"generic", "android", "pc", "tv", "tablet"}


class AgentHub:
    NAME = r"[A-Za-z0-9][A-Za-z0-9 _'-]{0,39}"

    def __init__(self, data_dir):
        self.path = Path(data_dir) / "agents.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS devices (owner TEXT, name TEXT, abilities TEXT, token_hash TEXT UNIQUE, seen REAL, revoked INTEGER DEFAULT 0, PRIMARY KEY(owner,name))")
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, owner TEXT, device TEXT, kind TEXT, detail TEXT, status TEXT, created REAL, updated REAL, output TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS device_presence (owner TEXT, name TEXT, mode TEXT, PRIMARY KEY(owner,name))")
            db.execute("CREATE TABLE IF NOT EXISTS device_metadata (owner TEXT, name TEXT, device_type TEXT, PRIMARY KEY(owner,name))")

    def pair(self, owner, name, abilities, device_type="generic"):
        device_type = {"phone": "android", "laptop": "pc"}.get(device_type, device_type)
        if device_type not in _TYPES:
            raise ValueError("Unsupported device type")
        name = " ".join(str(name).replace("’", "'").split())
        if not re.fullmatch(self.NAME, name):
            raise ValueError("Use a short device name with letters, numbers, spaces or hyphens")
        if not owner or not abilities or set(abilities) - ABILITIES:
            raise ValueError("Choose supported device abilities")
        token = secrets.token_urlsafe(32)
        with closing(sqlite3.connect(self.path)) as db, db:
            key = re.sub(r"[\s_'-]+", "", name).lower()
            for (existing,) in db.execute("SELECT name FROM devices WHERE owner=? AND revoked=0", (owner,)):
                if re.sub(r"[\s_'-]+", "", existing).lower() == key:
                    raise ValueError(f"'{existing}' is already paired; revoke it before pairing again")
            if db.execute("DELETE FROM devices WHERE owner=? AND name=? AND revoked=1", (owner, name)).rowcount:
                db.execute("UPDATE jobs SET device=? WHERE owner=? AND device=?", (f"{name} (revoked)", owner, name))
            db.execute("INSERT INTO devices VALUES(?,?,?,?,?,0)",
                       (owner, name, json.dumps(sorted(set(abilities))), hashlib.sha256(token.encode()).hexdigest(), 0))
            db.execute("INSERT INTO device_metadata VALUES(?,?,?) ON CONFLICT(owner,name) DO UPDATE SET device_type=excluded.device_type",
                       (owner, name, device_type))
        return {"name": name, "token": token, "abilities": sorted(set(abilities))}

    def authenticate(self, token):
        if not token or len(token) > 200:
            return None
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("SELECT owner,name,abilities FROM devices WHERE token_hash=? AND revoked=0",
                             (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        return {"owner": row[0], "name": row[1], "abilities": json.loads(row[2] or "[]")} if row else None

    def devices(self, owner):
        with closing(sqlite3.connect(self.path)) as db:
            rows = db.execute(
                "SELECT d.name,d.abilities,d.seen,p.mode,m.device_type FROM devices d "
                "LEFT JOIN device_presence p ON p.owner=d.owner AND p.name=d.name "
                "LEFT JOIN device_metadata m ON m.owner=d.owner AND m.name=d.name "
                "WHERE d.owner=? AND d.revoked=0", (owner,)).fetchall()
        return [{"name": r[0], "abilities": json.loads(r[1]), "seen": r[2],
                 "status": "online" if r[2] and time.time() - r[2] < 90 else "offline",
                 "mode": r[3] or "unknown", "device_type": r[4] or "generic"} for r in rows]

    def rename(self, owner, name, new_name):
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
            db.execute("UPDATE device_metadata SET name=? WHERE owner=? AND name=?", (new_name, owner, name))
            db.execute("UPDATE device_presence SET name=? WHERE owner=? AND name=?", (new_name, owner, name))
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
            db.execute("UPDATE jobs SET status='unconfirmed',updated=? WHERE owner=? AND device=? AND status='running' AND updated<?",
                       (time.time(), owner, name, time.time() - 120))
            safe = " AND kind IN ('ping','battery_status')" if passive else ""
            rows = db.execute("SELECT id,kind,detail FROM jobs WHERE owner=? AND device=? AND status='queued'" + safe + " ORDER BY created LIMIT 5", (owner, name)).fetchall()
            for row in rows:
                db.execute("UPDATE jobs SET status='running',updated=? WHERE id=?", (time.time(), row[0]))
        return [{"id": r[0], "kind": r[1], "detail": r[2]} for r in rows]

    def waiting_for_foreground(self, owner, name):
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute(
                "SELECT count(*) FROM jobs WHERE owner=? AND device=? AND status='queued' AND kind NOT IN ('ping','battery_status')",
                (owner, name)).fetchone()[0]

    def complete(self, owner, name, job_id, output, success=True):
        with closing(sqlite3.connect(self.path)) as db, db:
            cursor = db.execute("UPDATE jobs SET status=?,output=?,updated=? WHERE id=? AND owner=? AND device=? AND status IN ('running','unconfirmed')",
                                ("executed" if success else "failed", output[:4000], time.time(), job_id, owner, name))
            if cursor.rowcount == 1:
                return True
            row = db.execute("SELECT status,output FROM jobs WHERE id=? AND owner=? AND device=?",
                             (job_id, owner, name)).fetchone()
            return bool(row and row == ("executed" if success else "failed", output[:4000]))


    def note_executed(self, owner: str, kind: str, detail: str, output: str) -> str | None:
        """Record a receipt for an action the phone already performed. Does not invent one."""
        with closing(sqlite3.connect(self.path)) as db, db:
            chosen = None
            for name, abilities in db.execute(
                    "SELECT name, abilities FROM devices WHERE owner=? AND revoked=0", (owner,)):
                if kind in json.loads(abilities):
                    chosen = name
                    break
            if chosen is None:
                return None
            job_id = secrets.token_urlsafe(16)
            now = time.time()
            db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)",
                       (job_id, owner, chosen, kind, detail[:500], "executed", now, now, output[:4000]))
            return job_id

    def jobs(self, owner):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE jobs SET status='unconfirmed',updated=? WHERE owner=? AND status='running' AND updated<?",
                       (time.time(), owner, time.time() - 120))
            db.row_factory = sqlite3.Row
            rows = db.execute("SELECT id,device,kind,status,created,updated,output FROM jobs WHERE owner=? ORDER BY created DESC LIMIT 50", (owner,)).fetchall()
        return [dict(row) for row in rows]


def _audited(method, describe):
    """Record pairing, revocation, jobs and results. Never log job detail (SMS text or paths)."""
    def wrapper(self, owner, *args, **kwargs):
        from atulya.security_log import record_event

        try:
            result = method(self, owner, *args, **kwargs)
        except ValueError:
            record_event("device", owner, method.__name__, target=describe(args, kwargs, None), outcome="refused")
            raise
        record_event("device", owner, method.__name__, target=describe(args, kwargs, result),
                     outcome="ok" if result is not False else "not found")
        return result
    wrapper.__name__ = method.__name__
    wrapper.__doc__ = method.__doc__
    return wrapper


AgentHub.pair = _audited(AgentHub.pair, lambda a, k, r: f"{a[0]} abilities={','.join(sorted(set(a[1])))}")
AgentHub.revoke = _audited(AgentHub.revoke, lambda a, k, r: str(a[0]))
AgentHub.enqueue = _audited(AgentHub.enqueue, lambda a, k, r: f"{a[0]}: {a[1]}" + (f" job {r['id']}" if r else ""))
AgentHub.complete = _audited(
    AgentHub.complete,
    lambda a, k, r: f"{a[0]}: job {a[1]} " + ("success" if k.get("success", a[3] if len(a) > 3 else True) else "failure"))
