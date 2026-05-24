"""Tests for MCPServer — MCP-compatible tool/resource/prompt serving."""

import pytest
import tempfile


class TestMCPServer:
    """Tests for MCPServer core functionality."""

    def test_register_tool(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            server.register_tool("my_tool", "A test tool", {"type": "object", "properties": {}})
            tools = server.list_tools()
            assert any(t["name"] == "my_tool" for t in tools)

    def test_register_tool_no_schema(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            server.register_tool("simple_tool", "Simple tool", {"type": "object", "properties": {}})
            tools = server.list_tools()
            assert len(tools) == 1

    def test_register_resource(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            server.register_resource(uri="config://model", name="Model Config",
                                     description="Current model configuration")
            resources = server.list_resources()
            assert any("config://model" in str(r) for r in resources)

    def test_register_prompt(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            server.register_prompt("greet", "A greeting prompt", "Hello {{name}}!")
            prompts = server.list_prompts()
            assert any("greet" in str(p) for p in prompts)

    @pytest.mark.asyncio
    async def test_call_tool_with_handler(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            results = []
            def my_handler(arg):
                results.append(arg)
                return f"processed {arg}"
            server.register_tool("process", "Process handler",
                                 {"type": "object", "properties": {"arg": {"type": "string"}}},
                                 handler=my_handler)
            result = await server.call_tool("process", {"arg": "test"})
            assert result is not None
            assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_call_tool_not_found(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            result = await server.call_tool("nonexistent", {})
            assert result.get("success") is False
            assert "not found" in result.get("error", "")

    def test_list_tools_empty(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            assert server.list_tools() == []

    def test_list_resources_empty(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            assert server.list_resources() == []

    def test_list_prompts_empty(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            assert server.list_prompts() == []

    def test_bridge_tool_registry(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            # Mock a tool registry
            class MockRegistry:
                def list_tools(self):
                    return [{"name": "tool_a", "description": "Tool A", "input_schema": {}}]
            server.bridge_tool_registry(MockRegistry())
            tools = server.list_tools()
            assert any("tool_a" in str(t) for t in tools)

    def test_get_server_info(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            info = server.get_server_info()
            assert isinstance(info, dict)
            assert "name" in info or "version" in info

    def test_register_and_list_tools(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            server.register_tool("t1", "First", {"type": "object"})
            server.register_tool("t2", "Second", {"type": "object"})
            tools = server.list_tools()
            assert len(tools) == 2
