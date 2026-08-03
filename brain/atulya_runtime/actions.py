"""Policy-controlled, workspace-confined action execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


READ_ONLY_ACTIONS = {"list_files", "read_file"}
WRITE_ACTIONS = {"write_file"}
SUPPORTED_ACTIONS = READ_ONLY_ACTIONS | WRITE_ACTIONS


class ActionError(ValueError):
    pass


@dataclass(frozen=True)
class PolicyDecision:
    status: str
    reason: str


class ActionPolicy:
    """A model may propose actions, but it never grants itself authority."""

    def evaluate(self, action_type: str, payload: dict[str, Any]) -> PolicyDecision:
        if action_type not in SUPPORTED_ACTIONS:
            return PolicyDecision("rejected", "This action type is not enabled.")
        if action_type in READ_ONLY_ACTIONS:
            return PolicyDecision("approved", "Read-only action.")
        if not isinstance(payload.get("path"), str) or not isinstance(payload.get("content"), str):
            return PolicyDecision("rejected", "write_file requires string path and content.")
        return PolicyDecision("pending_approval", "Writing files requires explicit user approval.")


class WorkspaceExecutor:
    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir.resolve()

    def _path(self, raw_path: str) -> Path:
        if not raw_path or Path(raw_path).is_absolute():
            raise ActionError("Path must be a non-empty relative path.")
        candidate = (self.workspace_dir / raw_path).resolve()
        try:
            candidate.relative_to(self.workspace_dir)
        except ValueError as error:
            raise ActionError("Path escapes the configured workspace.") from error
        return candidate

    def execute(self, action_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        path = self._path(str(payload.get("path", "")))
        if action_type == "list_files":
            if not path.is_dir():
                raise ActionError("Requested directory does not exist.")
            entries = sorted(item.name for item in path.iterdir())[:200]
            return {"path": str(path.relative_to(self.workspace_dir)), "entries": entries}
        if action_type == "read_file":
            if not path.is_file():
                raise ActionError("Requested file does not exist.")
            if path.stat().st_size > 1_000_000:
                raise ActionError("Requested file is too large.")
            return {"path": str(path.relative_to(self.workspace_dir)), "content": path.read_text(encoding="utf-8", errors="replace")}
        if action_type == "write_file":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(payload["content"]), encoding="utf-8")
            return {"path": str(path.relative_to(self.workspace_dir)), "bytes_written": path.stat().st_size}
        raise ActionError("Unsupported action type.")
