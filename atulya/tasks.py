"""Durable bounded diagnostic plans; no arbitrary model code or side effects."""
import asyncio
import json
import secrets
import sqlite3
import time
from contextlib import closing

from fastapi import HTTPException, Request

CHECKS = frozenset({"server_health", "devices", "google_connection"})


class TaskStore:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.path = data_dir / "tasks.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, owner TEXT, plan TEXT, status TEXT, checkpoint INTEGER, results TEXT, attempts INTEGER, created REAL, updated REAL)")

    def create(self, owner, checks):
        if not owner or not checks or len(checks) > 3 or len(set(checks)) != len(checks) or set(checks) - CHECKS:
            raise ValueError("Choose one to three distinct supported diagnostic checks")
        if "server_health" in checks and owner != "admin":
            raise ValueError("Primary server diagnostics require the owner account")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT count(*) FROM tasks WHERE owner=? AND status IN ('queued','running')", (owner,)).fetchone()[0] >= 3:
                raise ValueError("Three tasks are already pending; wait or cancel one")
            identifier = secrets.token_urlsafe(16)
            now = time.time()
            db.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?)", (identifier, owner, json.dumps(checks), "queued", 0, "[]", 0, now, now))
        return identifier

    def list(self, owner):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            rows = [dict(r) for r in db.execute("SELECT id,plan,status,checkpoint,results,attempts,created,updated FROM tasks WHERE owner=? ORDER BY created DESC LIMIT 30", (owner,))]
        for row in rows:
            row["plan"] = json.loads(row["plan"])
            row["results"] = json.loads(row["results"])
        return rows

    def cancel(self, owner, identifier):
        with closing(sqlite3.connect(self.path)) as db, db:
            return db.execute("UPDATE tasks SET status='cancelled',updated=? WHERE owner=? AND id=? AND status IN ('queued','running')", (time.time(), owner, identifier)).rowcount == 1

    def claim(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            # Repeating these fixed read-only checks is safe; effectful jobs use a different queue.
            db.execute("UPDATE tasks SET status='queued' WHERE status='running' AND updated<? AND attempts<3", (time.time() - 180,))
            db.execute("UPDATE tasks SET status='failed',updated=? WHERE status IN ('queued','running') AND ((status='queued' AND attempts>=3) OR (status='running' AND attempts>=3 AND updated<?) OR created<?)", (time.time(), time.time() - 180, time.time() - 86400))
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM tasks WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if row is None:
                return None
            db.execute("UPDATE tasks SET status='running',attempts=attempts+1,updated=? WHERE id=?", (time.time(), row["id"]))
            return dict(row)

    def save_checkpoint(self, job, results, final=False):
        with closing(sqlite3.connect(self.path)) as db, db:
            return db.execute("UPDATE tasks SET checkpoint=?,results=?,status=?,updated=? WHERE id=? AND owner=? AND status='running'", (len(results), json.dumps(results), "completed" if final else "running", time.time(), job["id"], job["owner"])).rowcount == 1

    def is_running(self, identifier):
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("SELECT status FROM tasks WHERE id=?", (identifier,)).fetchone()
        return bool(row and row[0] == "running")


async def diagnostic(check, owner, data_dir):
    if check == "server_health":
        if owner != "admin":
            return {"check": check, "status": "denied"}
        from tools.plugins.toolkit import _server_status
        from tools.plugins.registry import PluginContext
        result = await _server_status({}, PluginContext("web", None, None, owner))
        return {"check": check, "status": "checked", "result": result[:2000]}
    if check == "devices":
        from tools.plugins.system.agents import AgentHub
        devices = await asyncio.to_thread(AgentHub(data_dir).devices, owner)
        return {"check": check, "status": "checked", "result": [{k: d.get(k) for k in ["name", "status", "mode", "abilities"]} for d in devices], "limit": "A heartbeat is not execution verification."}
    if check == "google_connection":
        from tools.plugins.information.google_api import connection_status
        state = await asyncio.to_thread(connection_status, owner, data_dir)
        return {"check": check, "status": "checked", "result": {k: state.get(k) for k in ["configured", "connected", "gmail_read", "gmail_send", "calendar_write"]}, "limit": "Authorization flags only; no email content read, send, or calendar write."}
    raise ValueError("Unsupported diagnostic")


async def run_one(store, executor=diagnostic):
    job = await asyncio.to_thread(store.claim)
    if job is None:
        return False
    plan, results = json.loads(job["plan"]), json.loads(job["results"])
    for check in plan[len(results):]:
        if not await asyncio.to_thread(store.is_running, job["id"]):
            return True
        try:
            result = await asyncio.wait_for(executor(check, job["owner"], store.data_dir), timeout=35)
        except Exception as exc:
            result = {"check": check, "status": "failed", "error": type(exc).__name__}
        results.append(result)
        if not await asyncio.to_thread(store.save_checkpoint, job, results, len(results) == len(plan)):
            return True
    return True


def register_task_routes(app, data_dir):
    store = TaskStore(data_dir)
    @app.get("/api/tasks")
    async def list_tasks(request: Request):
        return {"tasks": await asyncio.to_thread(store.list, str(request.state.user_id)), "limits": "Fixed read-only diagnostic plans only. Completed means checks finished; inspect each check result."}

    @app.post("/api/tasks", status_code=202)
    async def create(request: Request):
        try:
            body = await request.json()
        except ValueError as exc:
            raise HTTPException(422, "Provide a JSON diagnostic plan") from exc
        checks = body.get("checks") if isinstance(body, dict) else None
        if not isinstance(checks, list) or not all(isinstance(c, str) for c in checks):
            raise HTTPException(422, "Provide a list of supported checks")
        try:
            identifier = await asyncio.to_thread(store.create, str(request.state.user_id), checks)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"id": identifier, "status": "queued"}

    @app.delete("/api/tasks/{identifier}")
    async def cancel(identifier: str, request: Request):
        return {"cancelled": await asyncio.to_thread(store.cancel, str(request.state.user_id), identifier)}

    async def worker():
        while True:
            try:
                worked = await run_one(store)
            except Exception:
                worked = False
            await asyncio.sleep(.1 if worked else 2)

    async def start():
        app.state.diagnostic_task_worker = asyncio.create_task(worker())
    async def stop():
        task = getattr(app.state, "diagnostic_task_worker", None)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    app.router.add_event_handler("startup", start)
    app.router.add_event_handler("shutdown", stop)


async def start_tool(args, ctx):
    if ctx is None:
        return "Sign in before starting a diagnostic task."
    from atulya.settings import Settings
    identifier = await asyncio.to_thread(TaskStore(Settings.from_environment().data_dir).create, ctx.user_id, args.get("checks"))
    return f"Queued diagnostic task {identifier}. Use task_status for checkpoints and results; it has not completed yet."


async def status_tool(_args, ctx):
    if ctx is None:
        return "Sign in to inspect your tasks."
    from atulya.settings import Settings
    return json.dumps(await asyncio.to_thread(TaskStore(Settings.from_environment().data_dir).list, ctx.user_id))


async def cancel_tool(args, ctx):
    if ctx is None:
        return "Sign in to cancel your diagnostic task."
    from atulya.settings import Settings
    cancelled = await asyncio.to_thread(TaskStore(Settings.from_environment().data_dir).cancel, ctx.user_id, str(args.get("id", "")))
    return "Task cancelled; no further checks will start." if cancelled else "No pending task with that ID belongs to you; nothing was cancelled."
