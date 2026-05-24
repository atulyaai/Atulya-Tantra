"""MCP Client â€” connect to external MCP servers over stdio or HTTP.

    client = MCPClient(name="my-server", transport="stdio", command="node server.js")
    await client.connect()
    tools = await client.list_tools()
    result = await client.call_tool("tool_name", {"arg": "value"})
    await client.close()
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MCPServerStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class MCPClientConfig:
    """Configuration for connecting to an external MCP server."""
    name: str
    transport: str = "stdio"        # "stdio" or "http"
    command: str = ""               # stdio: command to spawn
    url: str = ""                   # http: endpoint URL
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0


class MCPClient:
    """Connect to an external MCP server and interact via JSON-RPC 2.0."""

    def __init__(self, config: MCPClientConfig):
        self.config = config
        self.status = MCPServerStatus.DISCONNECTED
        self._process: asyncio.subprocess.Process | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._http_session = None
        self._req_id = 0
        self._server_info: dict[str, Any] = {}
        self._tools: list[dict[str, Any]] = []
        self._resources: list[dict[str, Any]] = []
        self._prompts: list[dict[str, Any]] = []
        self._connected_at: float = 0.0

    async def connect(self) -> bool:
        """Connect to the MCP server and initialize."""
        self.status = MCPServerStatus.CONNECTING
        try:
            if self.config.transport == "stdio":
                await self._connect_stdio()
            elif self.config.transport == "http":
                await self._connect_http()
            else:
                raise ValueError(f"Unknown transport: {self.config.transport}")

            # Initialize handshake
            init_result = await self._request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "Atulya-MCP-Client", "version": "0.1.0"},
            })
            self._server_info = init_result.get("serverInfo", {})
            self._connected_at = time.time()

            # Discover capabilities
            self._tools = (await self._request("tools/list", {})).get("tools", [])
            self._resources = (await self._request("resources/list", {})).get("resources", [])
            self._prompts = (await self._request("prompts/list", {})).get("prompts", [])

            self.status = MCPServerStatus.CONNECTED
            logger.info(f"MCP client '{self.config.name}' connected â€” {len(self._tools)} tools, {len(self._resources)} resources")
            return True
        except Exception as e:
            logger.error(f"MCP client '{self.config.name}' connect failed: {e}")
            self.status = MCPServerStatus.ERROR
            return False

    async def _connect_stdio(self):
        """Spawn a process and connect via stdin/stdout."""
        self._process = await asyncio.create_subprocess_exec(
            self.config.command, *self.config.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**__import__("os").environ, **self.config.env} if self.config.env else None,
        )
        self._reader = self._process.stdout
        self._writer = self._process.stdin

    async def _connect_http(self):
        """Set up HTTP session (lazy init â€” requests made on demand)."""
        try:
            import aiohttp
            self._http_session = aiohttp.ClientSession()
        except ImportError:
            raise RuntimeError("aiohttp required for HTTP MCP transport: pip install aiohttp")

    async def _request(self, method: str, params: dict[str, Any] = None) -> dict[str, Any]:
        """Send a JSON-RPC 2.0 request and return the result."""
        self._req_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._req_id,
            "method": method,
            "params": params or {},
        }

        if self.config.transport == "stdio":
            return await self._request_stdio(request)
        else:
            return await self._request_http(request)

    async def _request_stdio(self, request: dict) -> dict[str, Any]:
        """Send request over stdio and read response."""
        line = json.dumps(request) + "\n"
        self._writer.write(line.encode())
        await self._writer.drain()

        response_line = await asyncio.wait_for(
            self._reader.readline(),
            timeout=self.config.timeout,
        )
        response = json.loads(response_line.decode().strip())

        err = response.get("error")
        if err is not None:
            raise RuntimeError(f"MCP error: {err.get('message', 'unknown') if isinstance(err, dict) else err}")

        return response.get("result", {})

    async def _request_http(self, request: dict) -> dict[str, Any]:
        """Send request over HTTP POST."""
        if not self._http_session:
            raise RuntimeError("Not connected")
        url = self.config.url.rstrip("/") + "/mcp/rpc"
        async with self._http_session.post(url, json=request, timeout=self.config.timeout) as resp:
            response = await resp.json()
            err = response.get("error")
            if err is not None:
                raise RuntimeError(f"MCP error: {err.get('message', 'unknown') if isinstance(err, dict) else err}")
            return response.get("result", {})

    async def list_tools(self) -> list[dict[str, Any]]:
        return self._tools.copy()

    async def list_resources(self) -> list[dict[str, Any]]:
        return self._resources.copy()

    async def list_prompts(self) -> list[dict[str, Any]]:
        return self._prompts.copy()

    async def call_tool(self, name: str, arguments: dict[str, Any] = None) -> dict[str, Any]:
        """Call a tool on the remote MCP server."""
        result = await self._request("tools/call", {"name": name, "arguments": arguments or {}})
        content = result.get("content", [])
        texts = [c.get("text", "") for c in content if c.get("type") == "text"]
        return {
            "success": not result.get("isError", False),
            "output": "\n".join(texts),
            "error": "",
        }

    async def close(self):
        """Disconnect from the MCP server."""
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()
        if self._http_session:
            await self._http_session.close()
        self.status = MCPServerStatus.DISCONNECTED

    def get_info(self) -> dict[str, Any]:
        return {
            "name": self.config.name,
            "transport": self.config.transport,
            "status": self.status.value,
            "server": self._server_info,
            "tools": len(self._tools),
            "resources": len(self._resources),
            "prompts": len(self._prompts),
            "connected_at": self._connected_at,
        }


class MCPClientManager:
    """Manages multiple external MCP server connections."""

    def __init__(self):
        self._clients: dict[str, MCPClient] = {}

    async def add_stdio(self, name: str, command: str, args: list[str] = None, env: dict[str, str] = None) -> MCPClient:
        """Add and connect to a stdio-based MCP server."""
        config = MCPClientConfig(name=name, transport="stdio", command=command, args=args or [], env=env or {})
        client = MCPClient(config)
        success = await client.connect()
        if success:
            self._clients[name] = client
        return client

    async def add_http(self, name: str, url: str) -> MCPClient:
        """Add and connect to an HTTP MCP server."""
        config = MCPClientConfig(name=name, transport="http", url=url)
        client = MCPClient(config)
        success = await client.connect()
        if success:
            self._clients[name] = client
        return client

    async def remove(self, name: str):
        """Disconnect and remove a client."""
        client = self._clients.pop(name, None)
        if client:
            await client.close()

    def get(self, name: str) -> MCPClient | None:
        return self._clients.get(name)

    def list(self) -> list[dict[str, Any]]:
        return [c.get_info() for c in self._clients.values()]

    def all_tools(self) -> list[dict[str, Any]]:
        """Aggregate tools from all connected servers."""
        tools = []
        for name, client in self._clients.items():
            for t in client._tools:
                tools.append({**t, "_server": name})
        return tools

    def all_resources(self) -> list[dict[str, Any]]:
        resources = []
        for name, client in self._clients.items():
            for r in client._resources:
                resources.append({**r, "_server": name})
        return resources

    async def call_tool(self, server: str, name: str, arguments: dict[str, Any] = None) -> dict[str, Any]:
        client = self._clients.get(server)
        if not client:
            return {"success": False, "error": f"Server not found: {server}"}
        return await client.call_tool(name, arguments)

    async def shutdown_all(self):
        """Disconnect all clients."""
        for name in list(self._clients.keys()):
            await self.remove(name)

