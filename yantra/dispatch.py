"""Smart dispatch layer for tasks, models, and tools."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tantra.core.task_classifier import TaskClassification, TaskClassifier
from yantra.events import EventBus, default_bus
from yantra.capabilities import ToolRegistry, ToolResult


# Conservative intent -> canonical tool routing. When a prompt is classified
# into one of these categories and no explicit tool_name was supplied, the
# Dispatcher offers the matching tool (only if it is actually registered).
# Only clearly-intent-aligned tools are listed here to avoid surprising side
# effects (e.g. we never auto-execute `exec` or `file_write`).
CATEGORY_TOOLS = {
    "coding": ["code_execute"],
    "analysis": ["csv_analyze", "grep"],
    "creative": ["email", "create_output"],
    "vision": ["web_fetch", "web_search"],
    "fast": ["todo_create", "todo_list"],
    "reasoning": ["memory_search"],
}


@dataclass
class DispatchResult:
    classification: TaskClassification
    tool_result: ToolResult | None = None
    model: str = ""
    tool_used: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Dispatcher:
    def __init__(
        self,
        classifier: TaskClassifier | None = None,
        tools: ToolRegistry | None = None,
        events: EventBus | None = None,
    ):
        self.classifier = classifier or TaskClassifier()
        self.tools = tools or ToolRegistry()
        self.events = events or default_bus
        self._registered = {t["name"] for t in self.tools.list_tools()}

    def _tool_for_category(self, category: str) -> str | None:
        """Return the first registered canonical tool for an intent category."""
        for name in CATEGORY_TOOLS.get(category, []):
            if name in self._registered:
                return name
        return None

    async def dispatch(
        self,
        prompt: str,
        tool_name: str | None = None,
        estimated_tokens: int = 100,
        auto_route: bool = True,
        **tool_kwargs: Any,
    ) -> DispatchResult:
        classification = self.classifier.classify(prompt, estimated_tokens=estimated_tokens)
        await self.events.emit("task_classified", {
            "category": classification.category.value,
            "model": classification.recommended_model,
            "confidence": classification.confidence,
        })

        tool_result = None
        used: str | None = None

        # No explicit tool was given: route to a tool by detected intent.
        if not tool_name and auto_route:
            routed = self._tool_for_category(classification.category.value)
            if routed:
                tool_name = routed
                await self.events.emit("tool_routed", {
                    "category": classification.category.value,
                    "tool": routed,
                    "confidence": classification.confidence,
                })

        if tool_name:
            tool_result = await self.tools.execute(tool_name, **tool_kwargs)
            used = tool_name
            await self.events.emit("tool_executed", {
                "tool": tool_name,
                "success": tool_result.success,
                "error": tool_result.error,
            })

        return DispatchResult(
            classification=classification,
            tool_result=tool_result,
            model=classification.recommended_model,
            tool_used=used,
        )
