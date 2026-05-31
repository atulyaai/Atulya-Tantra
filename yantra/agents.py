"""Concrete Yantra agent classes backed by the LLM bridge and harness."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from atulya.llm import AtulyaLLM, LLMResponse
from yantra.harness import YantraHarness


@dataclass
class AgentRun:
    agent: str
    prompt: str
    response: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    provider: str = ""


class ChatAgent:
    name = "chat"

    def __init__(self, llm: AtulyaLLM | None = None, max_history: int = 20):
        self.llm = llm or AtulyaLLM()
        self.max_history = max_history
        self.history: list[dict[str, str]] = []

    async def run(self, prompt: str, **kwargs: Any) -> AgentRun:
        response = await self.llm.ask(prompt, history=self.history, tools_enabled=kwargs.get("tools_enabled", True))
        self.history.extend([
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": response.text},
        ])
        del self.history[:-self.max_history]
        return _agent_run(self.name, prompt, response)


class TaskAgent:
    name = "task"

    def __init__(self, llm: AtulyaLLM | None = None, max_steps: int = 5):
        self.llm = llm or AtulyaLLM(max_tool_iterations=max_steps)
        self.max_steps = max_steps

    async def run(self, prompt: str, **kwargs: Any) -> AgentRun:
        response = await self.llm.ask(prompt, history=kwargs.get("history") or [], tools_enabled=True)
        if len(response.tool_steps) > self.max_steps:
            response.tool_steps[:] = response.tool_steps[:self.max_steps]
        return _agent_run(self.name, prompt, response)


class CronAgent:
    name = "cron"

    def __init__(self, harness: YantraHarness | None = None):
        self.harness = harness or YantraHarness()
        self.runs: list[dict[str, Any]] = []

    async def run(self, command: str, prompt: str = "", **kwargs: Any) -> dict[str, Any]:
        result = await self.harness.run(command, prompt=prompt or command, **kwargs)
        record = {
            "agent": self.name,
            "command": command,
            "success": result.tool_result.success,
            "output": result.tool_result.output,
            "error": result.tool_result.error,
            "timestamp": time.time(),
        }
        self.runs.append(record)
        return record


class AgentRouter:
    def __init__(self, chat: ChatAgent | None = None, task: TaskAgent | None = None, cron: CronAgent | None = None):
        self.chat = chat or ChatAgent()
        self.task = task or TaskAgent()
        self.cron = cron or CronAgent()

    async def run(self, prompt: str, mode: str = "chat", **kwargs: Any) -> Any:
        if mode == "cron":
            return await self.cron.run(kwargs.pop("command", prompt), prompt=prompt, **kwargs)
        if mode == "task":
            return await self.task.run(prompt, **kwargs)
        return await self.chat.run(prompt, **kwargs)


def _agent_run(agent: str, prompt: str, response: LLMResponse) -> AgentRun:
    return AgentRun(
        agent=agent,
        prompt=prompt,
        response=response.text,
        steps=response.tool_steps,
        provider=response.provider,
    )
