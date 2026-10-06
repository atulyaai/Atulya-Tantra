"""Tools: tool adapters and the unified registry handed to the brain."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from atulya.skills import Tool, ToolRegistry, ToolResult, create_default_registry


from atulya import brain as _d

# ── tools ────────────────────────────────────────────────────────────
# Setup/admin actions the conversational brain should not trigger on its own:
# downloading multi-GB models and storing mail credentials. Still available via
# the CLI agent and the dashboard settings.
EXCLUDED_FROM_BRAIN = {"download_vision_model", "configure_email"}


class AgentToolAdapter(Tool):
    """Expose an ``atulya.actions`` function tool through ``atulya.skills``'s Tool API."""

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
        from atulya.actions import audit

        audit("tool", name=self.name, args=kwargs)  # every assistant action the brain takes is on the record
        try:
            out = await self._fn(**kwargs)
        except TypeError as exc:  # wrong/missing arguments from the model
            return ToolResult(success=False, error=f"Bad arguments for {self.name}: {exc}")
        except Exception as exc:  # noqa: BLE001 - surface tool failures as results
            return ToolResult(success=False, error=str(exc))
        return ToolResult(success=True, output=str(out) if out is not None else "")


class MCPToolAdapter(Tool):
    """A tool offered by an outside MCP server (``mcp_servers.json``).

    The name is prefixed ``mcp_<server>_`` deliberately: ``ToolRegistry.register``
    overwrites on a duplicate name, so a server offering ``read_file`` would
    otherwise displace Atulya's own path-guarded one and hand the model an
    unchecked route into ``.env`` and ``data/``.
    """

    def __init__(self, server: str, info: dict[str, Any], manager: Any):
        self.name = f"mcp_{server}_{info.get('name') or 'tool'}"
        self.description = str(
            info.get("description") or f"{info.get('name')} from the {server} MCP server"
        )
        # MCP calls its JSON schema inputSchema; the brain reads .parameters.
        self.parameters = info.get("inputSchema") or {"type": "object", "properties": {}}
        self._server = server
        self._tool = str(info.get("name") or "")
        self._manager = manager
        # So the confirmation gate can judge this tool by the name it would
        # have had natively instead of by a name nobody else has ever used.
        _d.MCP_BARE_NAMES[self.name] = self._tool

    async def execute(self, **kwargs: Any) -> ToolResult:
        from atulya.actions import audit

        audit("tool", name=self.name, args=kwargs)  # outside actions are on the record too
        try:
            result = await self._manager.call_tool(self._server, self._tool, kwargs)
        except Exception as exc:  # noqa: BLE001 - a dead server must not take the chat down
            return ToolResult(success=False, error=f"{self._server}: {exc}")
        return ToolResult(
            success=bool(result.get("success")),
            output=str(result.get("output") or ""),
            error=str(result.get("error") or ""),
        )


def build_unified_registry(data_dir: str | Path = ".") -> ToolRegistry:
    """Return the default ``atulya.skills`` registry plus the personal-assistant tools."""
    registry = create_default_registry(data_dir)
    from atulya import actions as agent_tools  # lazy: avoids import cycles

    taken = {t["name"] for t in registry.list_tools()}
    for name, info in agent_tools.TOOL_REGISTRY.items():
        if name in EXCLUDED_FROM_BRAIN or name in taken:
            continue
        registry.register(AgentToolAdapter(name, info))
        taken.add(name)

    # Outside MCP servers. server discovered these tools when it connected the
    # entries enabled in mcp_servers.json; nothing used to hand them over, so
    # enabling a server changed nothing. They join last and are prefixed, so
    # they can never displace a native tool.
    from atulya.mcp import get_manager  # lazy: keeps mcp out of the import graph

    manager = get_manager()
    for info in manager.all_tools():
        adapter = MCPToolAdapter(str(info.get("_server") or ""), info, manager)
        if adapter.name in taken:
            continue
        registry.register(adapter)
        taken.add(adapter.name)
    return registry


