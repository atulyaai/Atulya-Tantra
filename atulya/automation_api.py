"""Owner controls for recurring Telegram schedules and reminders."""
import asyncio

from fastapi import HTTPException, Request
from pydantic import BaseModel

from tools.plugins.productivity.routines import RoutineStore


class EnabledRequest(BaseModel):
    enabled: bool


def register_automation_routes(app, auth, data_dir, telegram_ids, reminders, web_reminders):
    store = RoutineStore(data_dir)

    async def owner(request):
        if not await asyncio.to_thread(auth.is_admin, str(request.state.user_id)):
            raise HTTPException(403, "Scheduled Telegram updates belong to the owner.")

    @app.get("/api/automations")
    async def list_automations(request: Request):
        await owner(request)
        return {"routines": await asyncio.to_thread(store.list_items),
                "types": {"message": "Recurring reminder", "briefing": "Morning briefing", "rain": "Rain alert",
                          "weather": "Weather update", "calendar": "Upcoming meetings"},
                "delivery": "Telegram acceptance does not verify phone sound or vibration."}

    @app.put("/api/automations/{routine_id}")
    async def toggle(routine_id: str, body: EnabledRequest, request: Request):
        await owner(request)
        changed = await asyncio.to_thread(store.set_enabled, routine_id, body.enabled)
        if not changed:
            raise HTTPException(404, "Schedule not found")
        return {"updated": True}

    @app.delete("/api/automations/{routine_id}")
    async def remove(routine_id: str, request: Request):
        await owner(request)
        try:
            await asyncio.to_thread(store.remove, routine_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        return {"removed": True}

    @app.post("/api/reminders/cancel-all")
    async def cancel_all(request: Request):
        await owner(request)
        web_count = await asyncio.to_thread(web_reminders.cancel_all, str(request.state.user_id))
        telegram_count = 0
        for telegram_id in telegram_ids:
            telegram_count += await asyncio.to_thread(reminders.cancel_all, telegram_id)
        routine_count = 0
        for item in await asyncio.to_thread(store.list_items):
            if item.get("action") == "message" and item.get("enabled"):
                await asyncio.to_thread(store.set_enabled, item["id"], False)
                routine_count += 1
        return {"web_cancelled": web_count, "telegram_cancelled": telegram_count,
                "recurring_reminders_disabled": routine_count,
                "note": "Briefings and weather subscriptions remain separately controllable. A send already in flight may arrive."}
