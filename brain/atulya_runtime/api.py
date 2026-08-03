"""Versioned HTTP API for the Atulya Gateway or local clients."""

from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from .config import Settings
from .service import AtulyaService


class RespondRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    user_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1)


class MemoryRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    kind: str = Field(default="note", min_length=1, max_length=64)
    content: str = Field(min_length=1, max_length=12_000)
    confidence: float = Field(default=1.0, ge=0, le=1)


class ActionRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    user_id: str = Field(min_length=1, max_length=128)
    action_type: str = Field(min_length=1, max_length=64)
    payload: dict = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or Settings.from_environment()
    service = AtulyaService(runtime_settings)
    app = FastAPI(title="Atulya Runtime", version="1.0.0")
    app.state.service = service

    def require_api_token(authorization: str | None = Header(default=None)) -> None:
        """Keep local development frictionless, but protect any shared deployment."""
        if runtime_settings.api_token and authorization != f"Bearer {runtime_settings.api_token}":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Valid bearer token required.")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        return {"status": "ready", "database": str(runtime_settings.database_path)}

    @app.post("/v1/respond")
    def respond(body: RespondRequest, request: Request, _: None = Depends(require_api_token)) -> dict:
        try:
            response = request.app.state.service.respond(**body.model_dump())
            return {"trace_id": response.trace_id, "content": response.content, "memory_count": response.memory_count, "model_source": response.model_source}
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error

    @app.post("/v1/memories", status_code=status.HTTP_201_CREATED)
    def remember(body: MemoryRequest, request: Request, _: None = Depends(require_api_token)) -> dict:
        memory_id = request.app.state.service.remember(**body.model_dump())
        return {"id": memory_id}

    @app.get("/v1/users/{user_id}/memories")
    def memories(user_id: str, request: Request, _: None = Depends(require_api_token)) -> dict:
        return {"items": request.app.state.service.store.list_memories(user_id)}

    @app.post("/v1/actions")
    def propose_action(body: ActionRequest, request: Request, _: None = Depends(require_api_token)) -> dict:
        return request.app.state.service.propose_action(**body.model_dump())

    @app.post("/v1/actions/{action_id}/approve")
    def approve_action(action_id: str, body: ApprovalRequest, request: Request, _: None = Depends(require_api_token)) -> dict:
        try:
            return request.app.state.service.approve_action(action_id, user_id=body.user_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except PermissionError as error:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return app
