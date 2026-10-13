"""Authenticated reminder routes; ownership always comes from the session."""
from datetime import datetime

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool


class ReminderRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    due_at: datetime


def register_reminder_routes(app, store):
    @app.get("/api/reminders")
    async def reminders(request: Request, due_only: bool = False):
        return {"reminders": await run_in_threadpool(store.list, str(request.state.user_id), due_only=due_only),
                "delivery": "Open Atulya page; overdue reminders appear when you return."}

    @app.post("/api/reminders", status_code=201)
    async def add_reminder(body: ReminderRequest, request: Request):
        try:
            return await run_in_threadpool(store.add, str(request.state.user_id), body.message, body.due_at)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/reminders/{reminder_id}/shown")
    async def shown(reminder_id: int, request: Request):
        return {"updated": await run_in_threadpool(store.update, str(request.state.user_id), reminder_id, shown=True)}

    @app.put("/api/reminders/{reminder_id}")
    async def edit(reminder_id: int, body: ReminderRequest, request: Request):
        try:
            changed = await run_in_threadpool(store.edit, str(request.state.user_id), reminder_id, body.message, body.due_at)
            if not changed:
                raise HTTPException(409, "Reminder unavailable or already shown/cancelled")
            return {"updated": True}
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.delete("/api/reminders/{reminder_id}")
    async def cancel(reminder_id: int, request: Request):
        return {"updated": await run_in_threadpool(store.update, str(request.state.user_id), reminder_id)}
