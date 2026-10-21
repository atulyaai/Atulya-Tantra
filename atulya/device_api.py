"""Per-device bearer credentials; no shared server token impersonation."""
import asyncio

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

from tools.plugins.system.agents import AgentHub


class PairRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    abilities: list[str] = Field(min_length=1, max_length=32)
    device_type: str = Field(default="generic", max_length=32)


class ResultRequest(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    output: str = Field(default="", max_length=4000)
    success: bool = True


def register_device_routes(app, data_dir):
    hub = AgentHub(data_dir)

    async def device(request):
        header = request.headers.get("authorization", "")
        token = header[7:].strip() if header.lower().startswith("bearer ") else ""
        identity = await asyncio.to_thread(hub.authenticate, token)
        if identity is None:
            raise HTTPException(401, "Pair this device in Atulya Devices first.")
        return identity

    @app.get("/api/devices")
    async def devices(request: Request):
        owner = str(request.state.user_id)
        return {"devices": await asyncio.to_thread(hub.devices, owner), "jobs": await asyncio.to_thread(hub.jobs, owner)}

    async def own_device(request, name):
        """404, never 403, for a device of another account: its existence is not revealed (PLAN M12-3)."""
        owner = str(request.state.user_id)
        names = {row["name"] for row in await asyncio.to_thread(hub.devices, owner)}
        if name not in names:
            raise HTTPException(404, "No such device.")
        return owner

    @app.post("/api/devices/pair", status_code=201)
    async def pair(body: PairRequest, request: Request):
        if "voice_loop" in body.abilities and not await asyncio.to_thread(
                request.app.state.auth_store.is_admin, str(request.state.user_id)):
            # The voice-loop token speaks to /api/chat as its owner: admins only (PLAN M12).
            raise HTTPException(403, "Only the administrator can pair a voice-loop device.")
        try:
            return await asyncio.to_thread(hub.pair, str(request.state.user_id), body.name, body.abilities)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.delete("/api/devices/{name}")
    async def revoke(name: str, request: Request):
        owner = await own_device(request, name)
        return {"revoked": await asyncio.to_thread(hub.revoke, owner, name)}

    @app.post("/api/devices/{name}/test", status_code=202)
    async def test_device(name: str, request: Request):
        owner = await own_device(request, name)
        try:
            job = await asyncio.to_thread(hub.enqueue, owner, name, "ping")
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"job": job, "message": "Ping queued. Connection is verified only after an executed receipt."}

    @app.post("/api/agents/register")
    async def register(request: Request):
        identity = await device(request)
        return {"name": identity["name"], "registered": True}

    @app.post("/api/agents/poll")
    async def poll(request: Request):
        identity = await device(request)
        return {"jobs": await asyncio.to_thread(hub.poll, identity["owner"], identity["name"])}

    @app.post("/api/agents/result")
    async def result(body: ResultRequest, request: Request):
        identity = await device(request)
        return {"ok": await asyncio.to_thread(hub.complete, identity["owner"], identity["name"], body.id, body.output, body.success)}
