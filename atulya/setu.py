"""Yantra MCP - Model Context Protocol adapter."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import shutil
import time
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

# ── mcp ────────────────────────────────────────────────────────────
__all__ = ["MCPManifest"]


# ── manifest ────────────────────────────────────────────────────────────
@dataclass
class MCPManifest:
    name: str
    version: str
    tools: list[dict[str, Any]]
    author: str = ""
    description: str = ""
    created_at: float = field(default_factory=time.time)
    signature: str = ""


class MCPManifestSigner:
    def __init__(self, secret: str | None = None):
        if not secret:
            secret = os.environ.get("ATULYA_MCP_SIGNING_SECRET")
        if not secret:
            raise ValueError(
                "MCP signing secret is required. Set ATULYA_MCP_SIGNING_SECRET env var "
                "or pass a secret to MCPManifestSigner()."
            )
        self._secret = secret

    def sign(self, manifest: MCPManifest) -> str:
        """Sign an MCP manifest."""
        payload = json.dumps({
            "name": manifest.name,
            "version": manifest.version,
            "tools": manifest.tools,
            "author": manifest.author,
            "created_at": manifest.created_at,
        }, sort_keys=True)
        signature = hmac.new(self._secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        manifest.signature = signature
        return signature

    def verify(self, manifest: MCPManifest) -> bool:
        """Verify an MCP manifest signature."""
        if not manifest.signature:
            return False
        payload = json.dumps({
            "name": manifest.name,
            "version": manifest.version,
            "tools": manifest.tools,
            "author": manifest.author,
            "created_at": manifest.created_at,
        }, sort_keys=True)
        expected = hmac.new(self._secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, manifest.signature)

    def save_manifest(self, manifest: MCPManifest, path: str | Path):
        """Save signed manifest to file."""
        self.sign(manifest)
        Path(path).write_text(json.dumps(vars(manifest), indent=2))

    def load_manifest(self, path: str | Path) -> MCPManifest | None:
        """Load and verify manifest from file."""
        if not Path(path).exists():
            return None
        data = json.loads(Path(path).read_text())
        manifest = MCPManifest(**data)
        if not self.verify(manifest):
            raise ValueError("Invalid manifest signature")
        return manifest


# ── server ────────────────────────────────────────────────────────────
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

    def __init__(self, data_dir: str | Path = "kosh/mcp"):
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

    async def handle_jsonrpc(self, payload: dict[str, Any]) -> dict[str, Any]:
        method = payload.get("method")
        params = payload.get("params") or {}
        req_id = payload.get("id")
        try:
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": self.get_server_info(),
                    "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                }
            elif method == "tools/list":
                result = {"tools": self.list_tools()}
            elif method == "resources/list":
                result = {"resources": self.list_resources()}
            elif method == "prompts/list":
                result = {"prompts": self.list_prompts()}
            elif method == "tools/call":
                result = await self.call_tool(str(params.get("name") or ""), dict(params.get("arguments") or {}))
                result = {
                    "isError": not result.get("success", False),
                    "content": [{"type": "text", "text": result.get("output") or result.get("error", "")}],
                }
            else:
                raise ValueError(f"Unknown MCP method: {method}")
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        except Exception as exc:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": str(exc)}}


# ── external_client ────────────────────────────────────────────────────────────
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

            # Discover capabilities. Each probe is optional: per the MCP spec a
            # server need only implement what it advertised, and answering
            # "Method not found" for resources/list used to escape as a connect
            # failure that threw away the tools/list results already in hand.
            self._tools = await self._capability("tools/list", "tools")
            self._resources = await self._capability("resources/list", "resources")
            self._prompts = await self._capability("prompts/list", "prompts")

            self.status = MCPServerStatus.CONNECTED
            logger.info(
                "MCP client '%s' connected - %s tools, %s resources",
                self.config.name,
                len(self._tools),
                len(self._resources),
            )
            return True
        except Exception as e:
            logger.error(f"MCP client '{self.config.name}' connect failed: {e}")
            self.status = MCPServerStatus.ERROR
            return False

    async def _capability(self, method: str, key: str) -> list[dict[str, Any]]:
        """Fetch one optional capability, treating its absence as empty."""
        try:
            result = await self._request(method, {})
        except Exception as exc:  # noqa: BLE001 - an unsupported method is normal
            logger.info("MCP '%s': %s unavailable (%s)", self.config.name, method, exc)
            return []
        return list(result.get(key) or [])

    async def _connect_stdio(self):
        """Spawn a process and connect via stdin/stdout."""
        # Windows ships npx as npx.cmd, and create_subprocess_exec does not
        # consult PATHEXT the way cmd.exe does -- so the bare name failed with
        # WinError 2 and every stdio server in setu_servers.json (all six use
        # npx) could never spawn. Resolve through PATH; keep the raw command
        # for an absolute path or one that is not on PATH.
        command = shutil.which(self.config.command) or self.config.command
        self._process = await asyncio.create_subprocess_exec(
            command, *self.config.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, **self.config.env} if self.config.env else None,
        )
        self._reader = self._process.stdout
        self._writer = self._process.stdin

    async def _connect_http(self):
        """HTTP transport uses stdlib requests on a worker thread."""
        self._http_session = True

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
        url = self.config.url.rstrip("/")
        if not url.endswith("/mcp/rpc"):
            url += "/mcp/rpc"

        def post() -> dict[str, Any]:
            payload = json.dumps(request).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                return json.loads(resp.read().decode("utf-8") or "{}")

        response = await asyncio.to_thread(post)
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
            self._http_session = None
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
        self.errors: list[str] = []  # connection failures, surfaced by the doctor and /api/system

    async def add_stdio(
        self,
        name: str,
        command: str,
        args: list[str] = None,
        env: dict[str, str] = None,
        timeout: float = 30.0,
    ) -> MCPClient:
        """Add and connect to a stdio-based MCP server."""
        config = MCPClientConfig(name=name, transport="stdio", command=command, args=args or [], env=env or {}, timeout=timeout)
        client = MCPClient(config)
        success = await client.connect()
        if success:
            self._clients[name] = client
        return client

    async def add_http(self, name: str, url: str, timeout: float = 30.0) -> MCPClient:
        """Add and connect to an HTTP MCP server."""
        config = MCPClientConfig(name=name, transport="http", url=url, timeout=timeout)
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


_manager: MCPClientManager | None = None


def get_manager() -> MCPClientManager:
    """The one manager sevak connects to and the brain reads its tools from.

    Before this existed sevak built its own MCPClientManager, discovered every
    tool the enabled servers offered -- and then discarded the list, because
    nothing else ever held a reference. `enabled` in setu_servers.json now
    reaches the brain.
    """
    global _manager
    if _manager is None:
        _manager = MCPClientManager()
    return _manager

