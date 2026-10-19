"""Owner-visible implementation record; contains engineering state, never credentials."""
import asyncio
import json

from fastapi import HTTPException, Request

from atulya.settings import PROJECT_ROOT


def implementation_status(root=PROJECT_ROOT):
    path = root / "docs" / "implementation-status.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"updated": "", "scope": "Implementation record is unavailable.", "items": []}
    return data


async def implementation_tool(_args, ctx):
    if ctx is None or ctx.user_id != "admin":
        return "Only the owner can inspect implementation progress."
    return json.dumps(await asyncio.to_thread(implementation_status), ensure_ascii=False)


def register_implementation_routes(app, auth_store):
    @app.get("/api/implementation")
    async def status(request: Request):
        if not await asyncio.to_thread(auth_store.is_admin, str(request.state.user_id)):
            raise HTTPException(403, "Implementation progress is for the owner.")
        return await asyncio.to_thread(implementation_status)
