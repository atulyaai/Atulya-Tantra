"""Owner dashboard APIs for restricted maintenance and MCP connections."""
import asyncio

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field


class ProposalBody(BaseModel):
    path: str
    content: str = Field(max_length=300_000)
    reason: str = Field(max_length=1000)


class ConnectionBody(BaseModel):
    name: str = Field(max_length=60)
    url: str = Field(max_length=1000)


class GrantBody(BaseModel):
    tool: str = Field(max_length=200)
    granted: bool


class ProactiveBody(BaseModel):
    enabled: bool


def register_workspace_routes(app, auth_store, maintenance, connections):
    async def owner(request):
        if not await asyncio.to_thread(auth_store.is_admin, str(request.state.user_id)):
            raise HTTPException(403, "Workspace access is for the owner only.")

    @app.get("/api/maintenance")
    async def status(request: Request):
        await owner(request)
        return {"health": maintenance.last_check,
                "proactive": maintenance.proactive_status(),
                "proposals": await asyncio.to_thread(maintenance.proposals)}

    @app.put("/api/maintenance/proactive")
    async def proactive(body: ProactiveBody, request: Request):
        await owner(request)
        return await asyncio.to_thread(maintenance.set_proactive, body.enabled)

    @app.post("/api/maintenance/check")
    async def check(request: Request):
        await owner(request)
        return await asyncio.to_thread(maintenance.check)

    @app.get("/api/maintenance/file")
    async def read(request: Request, path: str):
        await owner(request)
        try:
            return await asyncio.to_thread(maintenance.read, path)
        except (ValueError, OSError) as exc:
            raise HTTPException(422, "File is protected or unavailable.") from exc

    @app.post("/api/maintenance/proposals", status_code=201)
    async def propose(body: ProposalBody, request: Request):
        await owner(request)
        try:
            return await asyncio.to_thread(maintenance.propose, body.path, body.content, body.reason)
        except (ValueError, OSError) as exc:
            raise HTTPException(422, str(exc) if isinstance(exc, ValueError) else "Proposal could not be saved") from exc

    @app.post("/api/maintenance/proposals/{proposal_id}/{action}")
    async def apply(proposal_id: str, action: str, request: Request):
        await owner(request)
        if action not in {"apply", "rollback"}:
            raise HTTPException(404, "Unknown action")
        try:
            return await asyncio.to_thread(maintenance.apply, proposal_id, rollback=action == "rollback")
        except (ValueError, OSError) as exc:
            raise HTTPException(409, str(exc) if isinstance(exc, ValueError) else "Proposal unavailable") from exc

    @app.post("/api/mcp/connections", status_code=201)
    async def add(body: ConnectionBody, request: Request):
        await owner(request)
        try:
            return await connections.add(body.name, body.url)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/mcp/connections/{connection_id}/test")
    async def test(connection_id: str, request: Request):
        await owner(request)
        try:
            return await connections.discover(connection_id)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/mcp/connections/{connection_id}/grant")
    async def grant(connection_id: str, body: GrantBody, request: Request):
        await owner(request)
        try:
            return await connections.grant(connection_id, body.tool, body.granted)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.delete("/api/mcp/connections/{connection_id}")
    async def remove(connection_id: str, request: Request):
        await owner(request)
        await connections.remove(connection_id)
        return {"removed": True}
