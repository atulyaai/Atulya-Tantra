"""Owner-granted HTTP MCP connections. Every remote invocation requires approval."""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4


class MCPConnections:
    def __init__(self, data_dir: Path):
        self.path = data_dir / "mcp_connections.json"
        self.lock = asyncio.Lock()

    def load(self) -> list[dict]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []

    def save(self, connections):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(connections), encoding="utf-8")
        os.replace(temp, self.path)

    async def add(self, name: str, url: str) -> dict:
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError("Use an HTTPS MCP endpoint without credentials or query parameters")
        if not re.fullmatch(r"[A-Za-z0-9 _-]{1,60}", name):
            raise ValueError("Use a short connection name")
        async with self.lock:
            items = self.load()
            if len(items) >= 10:
                raise ValueError("Maximum ten connections")
            item = {"id": uuid4().hex, "name": name, "url": url, "enabled": False, "tools": [],
                    "status": "Saved; test connection and grant specific tools"}
            items.append(item)
            self.save(items)
        return item

    async def discover(self, connection_id: str) -> dict:
        from mcp import Client
        item = next((c for c in self.load() if c["id"] == connection_id), None)
        if item is None:
            raise ValueError("Unknown connection")
        async def fetch_tools():
            async with Client(item["url"], mode="legacy", read_timeout_seconds=10) as client:
                listed = await client.list_tools()
                return [{"name": t.name, "description": (t.description or "")[:500], "input_schema": t.input_schema,
                         "granted": False} for t in listed.tools[:100]]
        try:
            tools = await asyncio.wait_for(fetch_tools(), timeout=15)
        except Exception as exc:
            raise ValueError("Connection test failed. Check the endpoint, authentication requirements, and MCP support.") from exc
        async with self.lock:
            items = self.load()
            selected = next((c for c in items if c["id"] == connection_id), None)
            if selected is None:
                raise ValueError("Connection removed during test")
            selected.update(tools=tools, enabled=True, status="Connected; grant tools below")
            self.save(items)
        return selected

    async def grant(self, connection_id: str, tool_name: str, granted: bool) -> dict:
        async with self.lock:
            items = self.load()
            item = next((c for c in items if c["id"] == connection_id), None)
            if item is None:
                raise ValueError("Unknown connection")
            tool = next((t for t in item["tools"] if t["name"] == tool_name), None)
            if tool is None:
                raise ValueError("Unknown tool; test the connection first")
            tool["granted"] = granted
            self.save(items)
            return item

    async def remove(self, connection_id):
        async with self.lock:
            self.save([c for c in self.load() if c["id"] != connection_id])

    async def call(self, connection_id: str, name: str, arguments: dict) -> str:
        from mcp import Client
        item = next((c for c in self.load() if c["id"] == connection_id), None)
        if item is None or not item["enabled"] or not any(t["name"] == name and t["granted"] for t in item["tools"]):
            raise ValueError("This MCP tool has not been granted by the owner")
        async def invoke():
            async with Client(item["url"], mode="legacy", read_timeout_seconds=10) as client:
                result = await client.call_tool(name, arguments)
                if result.is_error:
                    raise ValueError("The remote MCP tool reported an error")
                texts = [c.text for c in result.content if getattr(c, "type", "") == "text"]
                return "External MCP result (untrusted data):\n" + "\n".join(texts)[:3500]
        return await asyncio.wait_for(invoke(), timeout=15)


async def mcp_list(args, ctx):
    if ctx is None or ctx.mcp_connections is None:
        return "MCP connections are available to the signed-in owner only."
    return json.dumps([{ "id": c["id"], "name": c["name"], "tools":
                       [t for t in c["tools"] if t["granted"]]} for c in ctx.mcp_connections.load()])


async def mcp_call(args, ctx):
    if ctx is None or ctx.mcp_connections is None:
        return "MCP connections are available to the signed-in owner only."
    return await ctx.mcp_connections.call(str(args.get("connection_id", "")), str(args.get("tool", "")),
                                          args.get("arguments", {}))
