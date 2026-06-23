"""SubAgent Orchestrator — decomposes complex tasks into sub-tasks,
dispatches to parallel agents, aggregates results."""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class AgentSpec:
    name: str
    description: str
    handler: Callable
    max_concurrent: int = 3
    timeout: float = 60.0


@dataclass
class AgentTask:
    id: str
    agent: str
    prompt: str
    context: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    created_at: float = field(default_factory=time.time)
    dependencies: list[str] = field(default_factory=list)


@dataclass
class AgentResult:
    task_id: str
    agent: str
    success: bool
    output: str
    duration: float
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class SubAgentOrchestrator:
    """Decomposes complex tasks into sub-tasks, dispatches to
    parallel sub-agents, and aggregates results."""

    def __init__(self, data_dir: str | Path = "assets/orchestrator"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._agents: dict[str, AgentSpec] = {}
        self._results: dict[str, AgentResult] = {}
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    def register_agent(self, spec: AgentSpec):
        self._agents[spec.name] = spec
        self._semaphores[spec.name] = asyncio.Semaphore(spec.max_concurrent)

    def get_agents(self) -> dict[str, AgentSpec]:
        return dict(self._agents)

    # ── task decomposition ───────────────────────────────────

    def decompose_task(self, objective: str) -> list[AgentTask]:
        """Decompose a complex objective into sub-tasks for different agents."""
        tasks = []
        # Generate sub-tasks based on objective keywords
        lines = objective.split("\n")
        deps: list[str] = []

        for line in lines:
            if not line.strip():
                continue
            best_agent = self._find_best_agent(line)
            if best_agent:
                task = AgentTask(
                    id=str(uuid.uuid4())[:8],
                    agent=best_agent.name,
                    prompt=line.strip(),
                    dependencies=list(deps),
                )
                tasks.append(task)
                deps.append(task.id)

        # If no task decomposition produced anything useful,
        # create a single generic task
        if not tasks and self._agents:
            first_agent = list(self._agents.values())[0]
            tasks.append(AgentTask(
                id=str(uuid.uuid4())[:8],
                agent=first_agent.name,
                prompt=objective,
            ))

        return tasks

    def _find_best_agent(self, text: str) -> AgentSpec | None:
        """Route a task to the best-matching agent by description."""
        if not self._agents:
            return None
        text_lower = text.lower()
        best_score = -1
        best_agent = None

        for agent in self._agents.values():
            desc_tokens = set(re.findall(r"[a-z]+", agent.description.lower()))
            text_tokens = set(re.findall(r"[a-z]+", text_lower))
            overlap = desc_tokens & text_tokens
            if overlap:
                score = len(overlap) / max(len(desc_tokens | text_tokens), 1)
                if score > best_score:
                    best_score = score
                    best_agent = agent

        return best_agent or list(self._agents.values())[0]

    # ── execution ────────────────────────────────────────────

    async def _execute_single(self, task: AgentTask) -> AgentResult:
        """Execute a single sub-task."""
        agent = self._agents.get(task.agent)
        if not agent:
            return AgentResult(
                task_id=task.id, agent=task.agent, success=False,
                output="", duration=0, error=f"Unknown agent: {task.agent}",
            )

        sem = self._semaphores.get(task.agent)
        if sem:
            async with sem:
                return await self._run_with_timeout(agent, task)
        return await self._run_with_timeout(agent, task)

    async def _run_with_timeout(self, agent: AgentSpec, task: AgentTask) -> AgentResult:
        start = time.time()
        try:
            result = await asyncio.wait_for(
                agent.handler(prompt=task.prompt, context=task.context),
                timeout=agent.timeout,
            )
            duration = time.time() - start
            if isinstance(result, str):
                return AgentResult(
                    task_id=task.id, agent=agent.name,
                    success=True, output=result, duration=duration,
                )
            if isinstance(result, dict):
                return AgentResult(
                    task_id=task.id, agent=agent.name,
                    success=result.get("success", True),
                    output=result.get("output", str(result)),
                    duration=duration,
                    metadata=result.get("metadata", {}),
                )
            return AgentResult(
                task_id=task.id, agent=agent.name,
                success=True, output=str(result), duration=duration,
            )
        except asyncio.TimeoutError:
            duration = time.time() - start
            return AgentResult(
                task_id=task.id, agent=agent.name, success=False,
                output="", duration=duration,
                error=f"Timeout after {agent.timeout}s",
            )
        except Exception as e:
            duration = time.time() - start
            return AgentResult(
                task_id=task.id, agent=agent.name, success=False,
                output="", duration=duration, error=str(e),
            )

    async def execute(self, tasks: list[AgentTask]) -> list[AgentResult]:
        """Execute tasks respecting dependency order."""
        completed: set[str] = set()
        results: list[AgentResult] = []
        remaining = list(tasks)

        while remaining:
            batch = []
            still_remaining = []
            for task in remaining:
                if all(dep in completed for dep in task.dependencies):
                    batch.append(task)
                else:
                    still_remaining.append(task)

            if not batch:
                # Dependency deadlock — run remaining anyway
                batch = still_remaining
                still_remaining = []

            coros = [self._execute_single(task) for task in batch]
            batch_results = await asyncio.gather(*coros)
            for result in batch_results:
                results.append(result)
                completed.add(result.task_id)

            remaining = still_remaining

        self._save_results(results)
        return results

    async def execute_parallel(self, tasks: list[AgentTask]) -> list[AgentResult]:
        """Execute all tasks in parallel (no dependency waiting)."""
        coros = [self._execute_single(task) for task in tasks]
        results = await asyncio.gather(*coros)
        self._save_results(results)
        return results

    async def run_objective(self, objective: str) -> dict[str, Any]:
        """High-level: decompose objective → execute → aggregate."""
        start = time.time()
        tasks = self.decompose_task(objective)
        if not tasks:
            return {"success": False, "error": "No tasks generated", "duration": 0}
        results = await self.execute(tasks)
        duration = time.time() - start

        return {
            "success": all(r.success for r in results),
            "objective": objective,
            "tasks": len(tasks),
            "completed": sum(1 for r in results if r.success),
            "failed": sum(1 for r in results if not r.success),
            "duration": round(duration, 2),
            "results": [vars(r) for r in results],
        }

    # ── aggregation ──────────────────────────────────────────

    def aggregate(self, results: list[AgentResult]) -> str:
        """Aggregate results into a single coherent output."""
        if not results:
            return "No results."

        parts = []
        for r in results:
            status = "✓" if r.success else "✗"
            header = f"## {r.agent} [{status}] ({r.duration:.1f}s)"
            parts.append(header)
            if r.success:
                parts.append(r.output[:2000])
            else:
                parts.append(f"Error: {r.error}")
            parts.append("")

        return "\n".join(parts)

    def _save_results(self, results: list[AgentResult]):
        f = self.data_dir / f"run_{int(time.time())}.json"
        f.write_text(json.dumps([vars(r) for r in results], indent=2))

    # ── stats ────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        history = sorted(self.data_dir.glob("run_*.json"))
        total_runs = len(history)
        total_tasks = 0
        total_success = 0
        total_duration = 0.0

        for h in history:
            try:
                data = json.loads(h.read_text())
                for r in data:
                    total_tasks += 1
                    if r.get("success"):
                        total_success += 1
                    total_duration += r.get("duration", 0)
            except Exception:
                pass

        return {
            "agents": len(self._agents),
            "total_runs": total_runs,
            "total_tasks": total_tasks,
            "success_rate": round(total_success / max(total_tasks, 1) * 100, 1),
            "avg_duration": round(total_duration / max(total_tasks, 1), 2),
        }
