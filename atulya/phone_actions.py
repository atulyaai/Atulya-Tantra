"""Pending phone composers/dialers; these never silently send an SMS or call."""
import re
import secrets
import sqlite3
import time
from contextlib import closing
from pathlib import Path


class PhoneActions:
    def __init__(self, data_dir):
        self.path=Path(data_dir)/"phone_actions.sqlite3"
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute("CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY,user_id TEXT,kind TEXT,number TEXT,body TEXT,state TEXT,created REAL)")

    def add(self,user_id,kind,number,body=""):
        if kind not in {"compose_sms","dial"} or not re.fullmatch(r"\+?[0-9]{3,15}",number) or len(body)>2000:
            raise ValueError("Provide a valid phone number and a short SMS body")
        item={"id":secrets.token_urlsafe(12),"kind":kind,"number":number,"body":body,"state":"queued"}
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute("UPDATE requests SET state='expired' WHERE user_id=? AND state='queued' AND created<?",(user_id,time.time()-600))
            if db.execute("SELECT count(*) FROM requests WHERE user_id=? AND state='queued'",(user_id,)).fetchone()[0]>=10:
                raise ValueError("Open Phone actions and handle pending requests first")
            db.execute("INSERT INTO requests VALUES(?,?,?,?,?,?,?)",(item["id"],user_id,kind,number,body,"queued",time.time()))
        return item

    def pending(self,user_id):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory=sqlite3.Row
            rows=db.execute("SELECT id,kind,number,body,state FROM requests WHERE user_id=? AND state='queued' AND created>? ORDER BY created",(user_id,time.time()-600)).fetchall()
        return [dict(row) for row in rows]

    def receipt(self,user_id,request_id,state):
        if state not in {"composer_opened","dialer_opened","failed","cancelled"}:
            raise ValueError("Invalid phone receipt")
        with closing(sqlite3.connect(self.path)) as db,db:
            return db.execute("UPDATE requests SET state=? WHERE user_id=? AND id=? AND state='queued' AND created>?",(state,user_id,request_id,time.time()-600)).rowcount==1


def register_phone_routes(app,data_dir):
    import asyncio
    from fastapi import Request,HTTPException
    from pydantic import BaseModel
    store=PhoneActions(data_dir)
    class Receipt(BaseModel):
        state: str
    @app.get("/api/phone/actions")
    async def pending(request: Request):
        return {"requests":await asyncio.to_thread(store.pending,str(request.state.user_id))}
    @app.post("/api/phone/actions/{request_id}/receipt")
    async def receipt(request_id: str,body: Receipt,request: Request):
        try:
            ok=await asyncio.to_thread(store.receipt,str(request.state.user_id),request_id,body.state)
        except ValueError as exc:
            raise HTTPException(422,str(exc)) from exc
        if not ok:
            raise HTTPException(404,"Phone action expired or unavailable")
        return {"updated":True}
