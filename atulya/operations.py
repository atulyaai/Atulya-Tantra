"""Durable, owner-approved operations. Fixed operations only; no model-supplied shell."""
import asyncio
import json
import secrets
import sqlite3
import time
from contextlib import closing

from fastapi import HTTPException, Request
from atulya.settings import Settings

SERVICES = {"atulya": "atulya.service", "atulya.service": "atulya.service"}


class Operations:
    def __init__(self, data_dir):
        self.path = data_dir / "operations.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS worker (id INTEGER PRIMARY KEY, seen REAL)")
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, owner TEXT, kind TEXT, target TEXT, status TEXT, created REAL, updated REAL, result TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS signals (name TEXT PRIMARY KEY, active INTEGER, updated REAL)")
            db.execute("CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY, message TEXT, status TEXT, created REAL, attempted REAL DEFAULT 0)")
            db.execute("CREATE TABLE IF NOT EXISTS policy (id INTEGER PRIMARY KEY, enabled INTEGER)")

    def heartbeat(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO worker VALUES(1,?) ON CONFLICT(id) DO UPDATE SET seen=excluded.seen", (time.time(),))

    def ready(self):
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("SELECT seen FROM worker WHERE id=1").fetchone()
        return bool(row and time.time() - row[0] < 45)

    def enqueue_restart(self, owner, service):
        if owner != "admin":
            raise ValueError("Only the owner may request server operations")
        target = SERVICES.get(service)
        if target is None:
            raise ValueError("Only the Atulya service is allowlisted")
        if not self.ready():
            raise ValueError("The operations worker is not connected; nothing was queued")
        now = time.time()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM jobs WHERE kind='restart' AND created>?", (now - 60,)).fetchone():
                raise ValueError("A restart was already requested within the last minute; inspect its result first")
            job = secrets.token_urlsafe(16)
            db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)", (job, owner, "restart", target, "queued", now, now, ""))
        return job

    def claim(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE jobs SET status='expired',updated=? WHERE status='queued' AND created<?", (time.time(), time.time() - 300))
            db.execute("UPDATE jobs SET status='unconfirmed',updated=? WHERE status='running' AND updated<?", (time.time(), time.time() - 120))
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if row is None:
                return None
            db.execute("UPDATE jobs SET status='running',updated=? WHERE id=?", (time.time(), row["id"]))
            return dict(row)

    def finish(self, job, ok, result):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE jobs SET status=?,updated=?,result=? WHERE id=? AND status='running'",
                       ("unconfirmed" if ok is None else "executed" if ok else "failed", time.time(), result[:800], job["id"]))

    def observe(self, name, active, message):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT active FROM signals WHERE name=?", (name,)).fetchone()
            db.execute("INSERT INTO signals VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET active=excluded.active,updated=excluded.updated", (name, int(active), time.time()))
            if (old is None and active) or (old and bool(old[0]) != active):
                policy = db.execute("SELECT enabled FROM policy WHERE id=1").fetchone()
                state = "pending" if policy is None or policy[0] else "muted"
                db.execute("INSERT INTO alerts(message,status,created) VALUES(?,?,?)", (message[:500], state, time.time()))
            db.execute("DELETE FROM alerts WHERE id NOT IN (SELECT id FROM alerts ORDER BY id DESC LIMIT 100)")

    def alerts_enabled(self):
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("SELECT enabled FROM policy WHERE id=1").fetchone()
        return row is None or bool(row[0])

    def set_alerts(self, enabled):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO policy VALUES(1,?) ON CONFLICT(id) DO UPDATE SET enabled=excluded.enabled", (int(enabled),))
            if not enabled:
                db.execute("UPDATE alerts SET status='muted' WHERE status='pending'")

    def pending_alerts(self):
        if not self.alerts_enabled():
            return []
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE alerts SET status='expired' WHERE status='pending' AND created<?", (time.time() - 86400,))
            db.row_factory = sqlite3.Row
            rows = [dict(r) for r in db.execute("SELECT * FROM alerts WHERE status='pending' AND attempted<? ORDER BY created LIMIT 5", (time.time() - 60,))]
            for row in rows:
                db.execute("UPDATE alerts SET attempted=? WHERE id=?", (time.time(), row["id"]))
        return rows

    def acknowledge_alert(self, identifier):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE alerts SET status='provider_accepted' WHERE id=?", (identifier,))

    def status(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE jobs SET status='unconfirmed',updated=? WHERE status='running' AND updated<?", (time.time(), time.time() - 120))
            db.row_factory = sqlite3.Row
            jobs = [dict(r) for r in db.execute("SELECT id,kind,target,status,created,updated,result FROM jobs ORDER BY created DESC LIMIT 20")]
            alerts = [dict(r) for r in db.execute("SELECT id,message,status,created FROM alerts ORDER BY created DESC LIMIT 20")]
        return {"worker_connected": self.ready(), "allowed_services": ["atulya.service"], "jobs": jobs, "alerts": alerts, "alerts_enabled": self.alerts_enabled(),
                "limits": "Owner approval required. No arbitrary shell, sudo commands, file edits or automatic replay after uncertain execution."}


def store():
    return Operations(Settings.from_environment().data_dir)


async def restart_tool(args, ctx):
    if ctx is None or ctx.user_id != "admin":
        return "Service restart is unavailable: only the owner may request it. No approval was queued and no service was changed."
    job = await asyncio.to_thread(store().enqueue_restart, ctx.user_id, str(args.get("service", "")))
    return f"Queued approved restart job {job}. Execution is not confirmed; use operations_status for its receipt."


async def status_tool(_args, ctx):
    if ctx is None or ctx.user_id != "admin":
        return "Only the owner may inspect server operations."
    return json.dumps(await asyncio.to_thread(store().status))


def register_operations_routes(app, auth):
    @app.get("/api/operations")
    async def status(request: Request):
        if not await asyncio.to_thread(auth.is_admin, str(request.state.user_id)):
            raise HTTPException(403, "Server operations belong to the owner.")
        return await asyncio.to_thread(store().status)

    @app.put("/api/operations/alerts/{enabled}")
    async def configure_alerts(enabled: bool, request: Request):
        if not await asyncio.to_thread(auth.is_admin, str(request.state.user_id)):
            raise HTTPException(403, "Server alerts belong to the owner.")
        await asyncio.to_thread(store().set_alerts, enabled)
        return {"alerts_enabled": enabled}


async def deliver_alerts(ops, notifier):
    for alert in await asyncio.to_thread(ops.pending_alerts):
        try:
            accepted = await notifier(alert["message"])
            if accepted:
                await asyncio.to_thread(ops.acknowledge_alert, alert["id"])
        except Exception:
            pass  # Preserve for retry; provider acceptance is not device delivery.
