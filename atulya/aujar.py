"""One tool surface for the whole assistant.

Historically Atulya had two tool systems: the ``yantra`` ToolRegistry (files,
web, office, ERP) used by the live chat/voice brain, and the ``atulya.karta``
registry (home control, reminders, weather, email, calendar, time) used only by
the CLI loop and automations. The chat brain could not call the personal-
assistant tools at all, and approvals for them had nowhere to execute.

``build_unified_registry`` merges both into a single ``ToolRegistry`` so every
entry point (chat, voice, automations, triggers) acts through the same hands.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from atulya.kaushal import Tool, ToolRegistry, ToolResult, create_default_registry

# Setup/admin actions the conversational brain should not trigger on its own:
# downloading multi-GB models and storing mail credentials. Still available via
# the CLI agent and the dashboard settings.
EXCLUDED_FROM_BRAIN = {"download_vision_model", "configure_email"}


class AgentToolAdapter(Tool):
    """Expose an ``atulya.karta`` function tool through the yantra Tool API."""

    def __init__(self, name: str, info: dict[str, Any]):
        self.name = name
        self.description = info.get("description", "")
        params = info.get("parameters") or {}
        # tools.py marks every param required=True inline; convert to a JSON
        # schema where only params without a declared default are required.
        self.parameters = {
            "type": "object",
            "properties": {
                pname: {k: v for k, v in pschema.items() if k != "required"}
                for pname, pschema in params.items()
            },
            "required": [p for p, s in params.items() if "default" not in s],
        }
        self._fn = info["fn"]

    async def execute(self, **kwargs: Any) -> ToolResult:
        from atulya.lekha import audit

        audit("tool", name=self.name, args=kwargs)  # every assistant action the brain takes is on the record
        try:
            out = await self._fn(**kwargs)
        except TypeError as exc:  # wrong/missing arguments from the model
            return ToolResult(success=False, error=f"Bad arguments for {self.name}: {exc}")
        except Exception as exc:  # noqa: BLE001 - surface tool failures as results
            return ToolResult(success=False, error=str(exc))
        return ToolResult(success=True, output=str(out) if out is not None else "")


def build_unified_registry(data_dir: str | Path = ".") -> ToolRegistry:
    """Return the yantra default registry plus the personal-assistant tools."""
    registry = create_default_registry(data_dir)
    from atulya import kriya as agent_tools  # lazy: avoids import cycles

    existing = {t["name"] for t in registry.list_tools()}
    for name, info in agent_tools.TOOL_REGISTRY.items():
        if name in EXCLUDED_FROM_BRAIN or name in existing:
            continue
        registry.register(AgentToolAdapter(name, info))
    return registry
