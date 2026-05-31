"""Workflow Engine — Kanban-based super-mind tool orchestration."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class TaskStatus(Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class WorkflowTask:
    id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee: str = ""
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    dependencies: list[str] = field(default_factory=list)
    subtasks: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


def _task_to_dict(t: WorkflowTask) -> dict[str, Any]:
    """Serialize a WorkflowTask to a JSON-compatible dict."""
    d = {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "status": t.status.value,
        "priority": t.priority.value,
        "assignee": t.assignee,
        "tool_name": t.tool_name,
        "tool_args": t.tool_args,
        "dependencies": t.dependencies,
        "subtasks": t.subtasks,
        "created_at": t.created_at,
        "completed_at": t.completed_at,
        "metadata": t.metadata,
    }
    if t.result is not None:
        try:
            json.dumps(t.result)
            d["result"] = t.result
        except (TypeError, ValueError):
            d["result"] = str(t.result)
    return d


class WorkflowEngine:
    """Super-mind tool orchestration engine."""

    def __init__(self, data_dir: str | Path = "assets/workflows"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._tasks: dict[str, WorkflowTask] = {}
        self._workflows: dict[str, list[str]] = {}
        self._tool_registry = None
        self._load()

    def set_tool_registry(self, registry):
        self._tool_registry = registry

    def _load(self):
        state_file = self.data_dir / "workflow_state.json"
        if state_file.exists():
            data = json.loads(state_file.read_text())
            for t in data.get("tasks", []):
                # Convert string values back to Enums
                if isinstance(t.get("status"), str):
                    t["status"] = TaskStatus(t["status"])
                if isinstance(t.get("priority"), str):
                    t["priority"] = TaskPriority(t["priority"])
                task = WorkflowTask(**t)
                self._tasks[task.id] = task
            self._workflows = data.get("workflows", {})

    def _save(self):
        state_file = self.data_dir / "workflow_state.json"
        data = {
            "tasks": [_task_to_dict(t) for t in self._tasks.values()],
            "workflows": self._workflows,
        }
        state_file.write_text(json.dumps(data, indent=2))

    def get_task(self, task_id: str) -> WorkflowTask | None:
        return self._tasks.get(task_id)

    def get_workflow(self, workflow_id: str) -> list[str] | None:
        return self._workflows.get(workflow_id)

    def create_task(self, title: str, tool_name: str = "", tool_args: dict | None = None,
                   priority: TaskPriority = TaskPriority.MEDIUM, dependencies: list[str] | None = None) -> str:
        task_id = str(uuid.uuid4())[:8]
        task = WorkflowTask(
            id=task_id, title=title, tool_name=tool_name, tool_args=tool_args or {},
            priority=priority, dependencies=dependencies or [],
        )
        self._tasks[task_id] = task
        self._save()
        return task_id

    def create_workflow(self, name: str, task_ids: list[str]) -> str:
        workflow_id = str(uuid.uuid4())[:8]
        self._workflows[workflow_id] = task_ids
        self._save()
        return workflow_id

    async def execute_task(self, task_id: str) -> WorkflowTask:
        """Execute a single task."""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        # Check dependencies
        for dep_id in task.dependencies:
            dep = self._tasks.get(dep_id)
            if dep is None:
                raise ValueError(f"Dependency not found: {dep_id}")
            if dep.status != TaskStatus.DONE:
                task.status = TaskStatus.BLOCKED
                self._save()
                return task

        task.status = TaskStatus.IN_PROGRESS
        self._save()

        # Execute tool if registered
        if self._tool_registry and task.tool_name:
            try:
                result = await self._tool_registry.execute(task.tool_name, **task.tool_args)
                task.result = result.output if result.success else result.error
                task.status = TaskStatus.DONE if result.success else TaskStatus.BLOCKED
            except Exception as e:
                task.result = str(e)
                task.status = TaskStatus.BLOCKED
        else:
            task.status = TaskStatus.DONE

        task.completed_at = time.time()
        self._save()
        return task

    async def execute_workflow(self, workflow_id: str) -> list[WorkflowTask]:
        """Execute entire workflow in dependency order."""
        task_ids = self._workflows.get(workflow_id, [])
        results = []
        for task_id in task_ids:
            result = await self.execute_task(task_id)
            results.append(result)
            if result.status == TaskStatus.BLOCKED:
                break
        return results

    def get_blocked_tasks(self) -> list[WorkflowTask]:
        return [t for t in self._tasks.values() if t.status == TaskStatus.BLOCKED]

    def get_pending_tasks(self) -> list[WorkflowTask]:
        return [t for t in self._tasks.values() if t.status in (TaskStatus.TODO, TaskStatus.IN_PROGRESS)]

    def get_stats(self) -> dict[str, Any]:
        by_status = {}
        for t in self._tasks.values():
            by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
        return {"total_tasks": len(self._tasks), "by_status": by_status, "workflows": len(self._workflows)}
