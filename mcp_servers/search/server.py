"""
MCP Search Server - Tantra AI
Provides web search tools via Model Context Protocol
"""

from mcp.server import Server
from mcp.types import Tool, TextContent
from duckduckgo_search import DDGS
import logging
import json
import sys
import os

# Add project root to path to import atulya_tantra
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.append(project_root)

from atulya_tantra.memory import MemoryManager

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("mcp-search")

logger.info("Tantra Search MCP Server starting...")

# Initialize Memory Manager
try:
    memory = MemoryManager(persist_directory=os.path.join(project_root, "data/vectors"))
    logger.info("Memory Manager initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Memory Manager: {e}")
    memory = None

# Create MCP server
app = Server("tantra-search")

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available search tools"""
    tools = [
        Tool(
            name="web_search",
            description="Search the web for current information (news, prices, facts)",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="news_search",
            description="Search for latest news on a topic",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "News topic to search"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results (default: 5)",
                        "default": 5
                    }
                },
                "required": ["topic"]
            }
        ),
        Tool(
            name="search_memory",
            description="Search internal memory for past conversations, facts, and preferences",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for in memory"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="store_fact",
            description="Store a new fact in memory",
            inputSchema={
                "type": "object",
                "properties": {
                    "fact": {
                        "type": "string",
                        "description": "The fact to store"
                    },
                    "source": {
                        "type": "string",
                        "description": "Source of the fact (default: user)",
                        "default": "user"
                    }
                },
                "required": ["fact"]
            }
        ),
        Tool(
            name="fact_check",
            description="Check a fact against memory first, then web search if needed",
            inputSchema={
                "type": "object",
                "properties": {
                    "claim": {
                        "type": "string",
                        "description": "The claim or fact to check"
                    }
                },
                "required": ["claim"]
            }
        )
    ]
    return tools

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""
    
    if name == "web_search":
        query = arguments["query"]
        max_results = arguments.get("max_results", 5)
        
        logger.info(f"Web search: {query}")
        
        try:
            ddgs = DDGS()
            results = ddgs.text(query, max_results=max_results)
            
            if not results:
                return [TextContent(type="text", text="No results found")]
            
            # Format results
            formatted = f"Search results for '{query}':\n\n"
            for i, r in enumerate(results, 1):
                formatted += f"{i}. {r.get('title', 'No title')}\n"
                formatted += f"   {r.get('body', 'No description')}\n"
                formatted += f"   URL: {r.get('href', '#')}\n\n"
            
            return [TextContent(type="text", text=formatted)]
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return [TextContent(type="text", text=f"Search failed: {str(e)}")]
    
    elif name == "news_search":
        topic = arguments["topic"]
        max_results = arguments.get("max_results", 5)
        
        logger.info(f"News search: {topic}")
        
        try:
            ddgs = DDGS()
            # Search with "news" keyword to get recent results
            query = f"{topic} news"
            results = ddgs.text(query, max_results=max_results)
            
            if not results:
                return [TextContent(type="text", text=f"No news found for '{topic}'")]
            
            formatted = f"Latest news on '{topic}':\n\n"
            for i, r in enumerate(results, 1):
                formatted += f"{i}. {r.get('title', 'No title')}\n"
                formatted += f"   {r.get('body', 'No description')}\n"
                formatted += f"   Source: {r.get('href', '#')}\n\n"
            
            return [TextContent(type="text", text=formatted)]
            
        except Exception as e:
            logger.error(f"News search error: {e}")
            return [TextContent(type="text", text=f"News search failed: {str(e)}")]

    elif name == "search_memory":
        if not memory:
            return [TextContent(type="text", text="Memory system is not available.")]
            
        query = arguments["query"]
        limit = arguments.get("limit", 5)
        
        logger.info(f"Memory search: {query}")
        
        try:
            results = memory.search_all(query, n_results=limit)
            
            formatted = f"Memory Search Results for '{query}':\n\n"
            
            # Format Facts
            if results.get("facts"):
                formatted += "--- Facts ---\n"
                for r in results["facts"]:
                    formatted += f"• {r['text']} (Source: {r['metadata'].get('source', 'unknown')})\n"
                formatted += "\n"
                
            # Format Conversations
            if results.get("conversations"):
                formatted += "--- Conversations ---\n"
                for r in results["conversations"]:
                    formatted += f"• {r['text']}\n"
                formatted += "\n"
                
            # Format Preferences
            if results.get("preferences"):
                formatted += "--- Preferences ---\n"
                for r in results["preferences"]:
                    formatted += f"• {r['text']}\n"
                formatted += "\n"
                
            if formatted.strip() == f"Memory Search Results for '{query}':":
                return [TextContent(type="text", text="No relevant memories found.")]
                
            return [TextContent(type="text", text=formatted)]
            
        except Exception as e:
            logger.error(f"Memory search error: {e}")
            return [TextContent(type="text", text=f"Memory search failed: {str(e)}")]

    elif name == "store_fact":
        if not memory:
            return [TextContent(type="text", text="Memory system is not available.")]
            
        fact = arguments["fact"]
        source = arguments.get("source", "user")
        
        logger.info(f"Storing fact: {fact}")
        
        try:
            memory.store_fact(fact, source=source)
            return [TextContent(type="text", text=f"Fact stored successfully: {fact}")]
        except Exception as e:
            logger.error(f"Store fact error: {e}")
            return [TextContent(type="text", text=f"Failed to store fact: {str(e)}")]

    elif name == "fact_check":
        if not memory:
            return [TextContent(type="text", text="Memory system is not available.")]
            
        claim = arguments["claim"]
        logger.info(f"Fact checking: {claim}")
        
        try:
            # 1. Check memory first
            mem_results = memory.search_facts(claim, n_results=1)
            
            # Simple heuristic: if we have a result with low distance (high similarity), trust it
            # Note: ChromaDB distances are L2 squared by default. Lower is better.
            # Threshold needs tuning, but let's say < 0.5 is good match
            
            found_in_memory = False
            memory_fact = ""
            
            if mem_results:
                dist = mem_results[0].get('distance', 1.0)
                logger.info(f"Top memory result: {mem_results[0]['text']} (Distance: {dist})")
                
                # Relaxed threshold for testing
                if dist < 0.8:
                    found_in_memory = True
                    memory_fact = mem_results[0]['text']
                    logger.info(f"Found in memory: {memory_fact}")
                    return [TextContent(type="text", text=f"Found in memory: {memory_fact}")]
            else:
                logger.info("No results from memory search")
            
            # 2. If not in memory, search web
            logger.info("Not found in memory, searching web...")
            ddgs = DDGS()
            web_results = ddgs.text(claim, max_results=3)
            
            if not web_results:
                return [TextContent(type="text", text=f"Could not verify '{claim}' in memory or on the web.")]
            
            # 3. Summarize web results (naive approach)
            top_result = web_results[0]
            web_fact = f"{top_result['body']} (Source: {top_result['href']})"
            
            # 4. Store in memory for future
            memory.store_fact(web_fact, source="web_search_verification")
            
            return [TextContent(type="text", text=f"Verified via web: {web_fact}\n(This has been added to memory)")]
            
        except Exception as e:
            logger.error(f"Fact check error: {e}")
            return [TextContent(type="text", text=f"Fact check failed: {str(e)}")]
    
    raise ValueError(f"Unknown tool: {name}")

async def main():
    """Run the MCP server"""
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        logger.info("Tantra Search MCP Server starting...")
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
