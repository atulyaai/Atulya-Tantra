"""Full MCP Server — bridge ALL tools to external agents."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable | None = None


@dataclass
class MCPResource:
    uri: str
    name: str
    description: str
    mime_type: str = "text/plain"


@dataclass
class MCPPrompt:
    name: str
    description: str
    template: str


class MCPServer:
    """Full MCP server bridging all tools to external agents."""

    def __init__(self, data_dir: str | Path = "data/mcp"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._tools: dict[str, MCPTool] = {}
        self._resources: dict[str, MCPResource] = {}
        self._prompts: dict[str, MCPPrompt] = {}
        self._tool_registry = None
        self._load()

    def _load(self):
        state_file = self.data_dir / "mcp_state.json"
        if state_file.exists():
            data = json.loads(state_file.read_text())
            for t in data.get("tools", []):
                self._tools[t["name"]] = MCPTool(name=t["name"], description=t["description"], input_schema=t.get("input_schema", {}))
            for r in data.get("resources", []):
                self._resources[r["uri"]] = MCPResource(**r)
            for p in data.get("prompts", []):
                self._prompts[p["name"]] = MCPPrompt(**p)

    def _save(self):
        state_file = self.data_dir / "mcp_state.json"
        data = {
            "tools": [{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in self._tools.values()],
            "resources": [vars(r) for r in self._resources.values()],
            "prompts": [vars(p) for p in self._prompts.values()],
        }
        state_file.write_text(json.dumps(data, indent=2))

    def register_tool(self, name: str, description: str, input_schema: dict[str, Any], handler: Callable | None = None):
        """Register a tool with the MCP server."""
        self._tools[name] = MCPTool(name=name, description=description, input_schema=input_schema, handler=handler)
        self._save()

    def register_resource(self, uri: str, name: str, description: str, mime_type: str = "text/plain"):
        """Register a resource."""
        self._resources[uri] = MCPResource(uri=uri, name=name, description=description, mime_type=mime_type)
        self._save()

    def register_prompt(self, name: str, description: str, template: str):
        """Register a prompt template."""
        self._prompts[name] = MCPPrompt(name=name, description=description, template=template)
        self._save()

    def bridge_tool_registry(self, tool_registry):
        """Bridge entire tool registry to MCP."""
        self._tool_registry = tool_registry
        for tool_info in tool_registry.list_tools():
            self.register_tool(
                name=tool_info["name"],
                description=tool_info["description"],
                input_schema={"type": "object", "properties": {}},
            )

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call an MCP tool."""
        tool = self._tools.get(name)
        if not tool:
            return {"success": False, "error": f"Tool not found: {name}"}

        # Try tool registry first
        if self._tool_registry:
            try:
                result = await self._tool_registry.execute(name, **arguments)
                return {"success": result.success, "output": result.output, "error": result.error}
            except Exception as e:
                return {"success": False, "error": str(e)}

        # Fallback to direct handler
        if tool.handler:
            try:
                result = tool.handler(**arguments)
                return {"success": True, "output": result}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "No handler available"}

    def list_tools(self) -> list[dict[str, Any]]:
        return [{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in self._tools.values()]

    def list_resources(self) -> list[dict[str, Any]]:
        return [vars(r) for r in self._resources.values()]

    def list_prompts(self) -> list[dict[str, Any]]:
        return [vars(p) for p in self._prompts.values()]

    def get_server_info(self) -> dict[str, Any]:
        return {
            "name": "Atulya Tantra MCP Server",
            "version": "0.2.0",
            "tools": len(self._tools),
            "resources": len(self._resources),
            "prompts": len(self._prompts),
        }
