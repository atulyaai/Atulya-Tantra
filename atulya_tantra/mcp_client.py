"""
MCP Client - Connects to MCP servers and executes tools
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

class MCPClient:
    """Client for connecting to MCP servers"""
    
    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        # Use current python executable
        import sys
        self.server_configs = {
            "search": {
                "command": sys.executable,
                "args": ["/home/atulya-tantra/mcp_servers/search/server.py"]
            }
        }
    
    async def connect_server(self, server_name: str):
        """Connect to an MCP server"""
        if server_name in self.sessions:
            return  # Already connected
        
        config = self.server_configs.get(server_name)
        if not config:
            raise ValueError(f"Unknown server: {server_name}")
        
        server_params = StdioServerParameters(
            command=config["command"],
            args=config["args"]
        )
        
        logger.info(f"Connecting to MCP server: {server_name}")
        
        # Fixed: Use async context manager properly
        stdio = stdio_client(server_params)
        read, write = await stdio.__aenter__()
        
        session = ClientSession(read, write)
        await session.initialize()
        
        self.sessions[server_name] = session
        logger.info(f"✓ Connected to {server_name} MCP server")
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call a tool on an MCP server"""
        # Connect if not already connected
        if server_name not in self.sessions:
            await self.connect_server(server_name)
        
        session = self.sessions[server_name]
        
        logger.info(f"Calling MCP tool: {server_name}.{tool_name}")
        
        result = await session.call_tool(tool_name, arguments)
        
        # Extract text from result
        if result and result.content:
            texts = [c.text for c in result.content if hasattr(c, 'text')]
            return "\n".join(texts)
        
        return "No result"
    
    async def web_search(self, query: str, max_results: int = 5) -> str:
        """Convenience method for web search"""
        return await self.call_tool(
            "search",
            "web_search",
            {"query": query, "max_results": max_results}
        )
    
    async def news_search(self, topic: str, max_results: int = 5) -> str:
        """Convenience method for news search"""
        return await self.call_tool(
            "search",
            "news_search",
            {"topic": topic, "max_results": max_results}
        )

    async def fact_check(self, claim: str) -> str:
        """Convenience method for fact checking"""
        return await self.call_tool(
            "search",
            "fact_check",
            {"claim": claim}
        )

    async def search_memory(self, query: str, limit: int = 5) -> str:
        """Convenience method for memory search"""
        return await self.call_tool(
            "search",
            "search_memory",
            {"query": query, "limit": limit}
        )
    
    async def close_all(self):
        """Close all server connections"""
        for name, session in self.sessions.items():
            try:
                await session.close()
                logger.info(f"Closed connection to {name}")
            except:
                pass
        self.sessions.clear()

# Global client instance
mcp_client = None

def get_mcp_client() -> MCPClient:
    """Get or create global MCP client"""
    global mcp_client
    if mcp_client is None:
        mcp_client = MCPClient()
    return mcp_client
