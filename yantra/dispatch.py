"""Smart dispatch layer for tasks, models, and tools."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tantra.core.task_classifier import TaskClassification, TaskClassifier
from yantra.events import EventBus, default_bus
from yantra.capabilities import ToolRegistry, ToolResult


@dataclass
class DispatchResult:
    classification: TaskClassification
    tool_result: ToolResult | None = None
    model: str = ""
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

    async def dispatch(
        self,
        prompt: str,
        tool_name: str | None = None,
        estimated_tokens: int = 100,
        **tool_kwargs: Any,
    ) -> DispatchResult:
        classification = self.classifier.classify(prompt, estimated_tokens=estimated_tokens)
        await self.events.emit("task_classified", {
            "category": classification.category.value,
            "model": classification.recommended_model,
            "confidence": classification.confidence,
        })

        tool_result = None
        if tool_name:
            tool_result = await self.tools.execute(tool_name, **tool_kwargs)
            await self.events.emit("tool_executed", {
                "tool": tool_name,
                "success": tool_result.success,
                "error": tool_result.error,
            })

        return DispatchResult(
            classification=classification,
            tool_result=tool_result,
            model=classification.recommended_model,
        )
