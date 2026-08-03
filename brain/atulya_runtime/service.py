"""The application service that owns Atulya sessions, memory, and actions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from .actions import ActionError, ActionPolicy, WorkspaceExecutor
from .config import Settings
from .models import ModelProvider, OpenAICompatibleProvider
from .store import AtulyaStore


@dataclass(frozen=True)
class Response:
    trace_id: str
    content: str
    memory_count: int
    model_source: str


class AtulyaService:
    def __init__(self, settings: Settings, provider: ModelProvider | None = None):
        self.settings = settings
        self.store = AtulyaStore(settings.database_path)
        self.policy = ActionPolicy()
        self.executor = WorkspaceExecutor(settings.workspace_dir)
        self.provider = provider if provider is not None else OpenAICompatibleProvider.from_settings(settings)

    def respond(self, *, session_id: str, user_id: str, message: str) -> Response:
        message = message.strip()
        if not message:
            raise ValueError("Message cannot be empty.")
        if len(message) > self.settings.max_message_chars:
            raise ValueError(f"Message exceeds {self.settings.max_message_chars} characters.")
        trace_id = f"atl-{uuid.uuid4().hex}"
        self.store.add_message(session_id=session_id, user_id=user_id, role="user", content=message, trace_id=trace_id)
        context = self.store.recent_messages(session_id)
        reply, model_source = self._compose_reply(message, context)
        self.store.add_message(session_id=session_id, user_id=user_id, role="assistant", content=reply, trace_id=trace_id)
        return Response(trace_id=trace_id, content=reply, memory_count=len(self.store.list_memories(user_id, limit=50)), model_source=model_source)

    def _compose_reply(self, message: str, context: list[dict[str, str]]) -> tuple[str, str]:
        if self.provider is not None:
            messages = [
                {
                    "role": "system",
                    "content": "You are Atulya, a helpful local assistant. Return text only. Never claim to have executed an action; actions require a separate approved request.",
                },
                *context,
            ]
            try:
                return self.provider.complete(messages), self.provider.name
            except RuntimeError as error:
                return f"Atulya could not reach its configured model. {error}", "model-unavailable"
        # A safe baseline is more valuable than a hidden fake model.
        previous_turns = max(0, (len(context) - 1) // 2)
        return (
            f"Atulya received your request. Session context contains {previous_turns} prior turn(s). Model reasoning is not configured yet: {message}",
            "deterministic-fallback",
        )

    def remember(self, *, user_id: str, kind: str, content: str, source: str = "user", confidence: float = 1.0) -> int:
        if not content.strip():
            raise ValueError("Memory content cannot be empty.")
        if not 0 <= confidence <= 1:
            raise ValueError("Confidence must be between 0 and 1.")
        return self.store.add_memory(user_id=user_id, kind=kind, content=content.strip(), source=source, confidence=confidence)

    def propose_action(self, *, session_id: str, user_id: str, action_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        trace_id, action_id = f"atl-{uuid.uuid4().hex}", uuid.uuid4().hex
        decision = self.policy.evaluate(action_type, payload)
        self.store.create_action(action_id=action_id, session_id=session_id, user_id=user_id, trace_id=trace_id, action_type=action_type, payload=payload, status=decision.status)
        if decision.status == "approved":
            return self._execute(action_id)
        return {"id": action_id, "trace_id": trace_id, "status": decision.status, "reason": decision.reason}

    def approve_action(self, action_id: str, *, user_id: str) -> dict[str, Any]:
        action = self.store.get_action(action_id)
        if action is None:
            raise KeyError("Action not found.")
        if action["user_id"] != user_id:
            raise PermissionError("Action belongs to another user.")
        if action["status"] != "pending_approval":
            raise ValueError(f"Action cannot be approved from status {action['status']}.")
        return self._execute(action_id)

    def _execute(self, action_id: str) -> dict[str, Any]:
        action = self.store.get_action(action_id)
        assert action is not None
        try:
            result = self.executor.execute(action["action_type"], action["payload"])
        except ActionError as error:
            result = {"error": str(error)}
            self.store.update_action(action_id, status="failed", result=result)
            return {"id": action_id, "trace_id": action["trace_id"], "status": "failed", "result": result}
        self.store.update_action(action_id, status="completed", result=result)
        return {"id": action_id, "trace_id": action["trace_id"], "status": "completed", "result": result}

    def close(self) -> None:
        self.store.close()
