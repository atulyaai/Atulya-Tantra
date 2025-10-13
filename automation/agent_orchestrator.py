"""
Atulya Tantra - Agent Orchestrator
Unified interface to SKYNET Protocol and MCP Server
CONSOLIDATED - No duplicate code, uses protocols/skynet
"""

from typing import Dict, List, Optional, Any
from core.logger import get_logger

logger = get_logger('automation.orchestrator')

# Import from protocols instead of duplicating
from protocols.skynet import SkynetOrchestrator, BaseAgent

# MCP Server implementation
class MCPServer:
    """Model Context Protocol Server for tool integration"""
    
    def __init__(self):
        self.tools = {}
        self.register_default_tools()
        logger.info("MCP Server initialized")
    
    def register_default_tools(self):
        """Register default MCP tools"""
        self.tools = {
            'get_system_info': self.get_system_info,
            'search_files': self.search_files,
            'calculate': self.calculate,
        }
    
    async def get_system_info(self, params: Dict) -> Dict:
        """MCP Tool: Get system information"""
        from core.utils import get_system_info
        return get_system_info()
    
    async def search_files(self, params: Dict) -> Dict:
        """MCP Tool: Search files"""
        import os
        from pathlib import Path
        
        query = params.get('query', '')
        directory = params.get('directory', '.')
        
        results = []
        for root, dirs, files in os.walk(directory):
            for file in files:
                if query.lower() in file.lower():
                    results.append(str(Path(root) / file))
        
        return {'success': True, 'results': results}
    
    async def calculate(self, params: Dict) -> Dict:
        """MCP Tool: Perform calculation"""
        try:
            expression = params.get('expression', '')
            result = eval(expression, {"__builtins__": {}}, {})
            return {'success': True, 'result': result}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def execute_tool(self, tool_name: str, params: Dict) -> Dict:
        """Execute an MCP tool"""
        if tool_name not in self.tools:
            return {'success': False, 'error': f'Tool {tool_name} not found'}
        
        tool_func = self.tools[tool_name]
        return await tool_func(params)
    
    def list_tools(self) -> List[str]:
        """List available MCP tools"""
        return list(self.tools.keys())


# Global instances - USE protocols/skynet, don't duplicate!
orchestrator = SkynetOrchestrator()
mcp_server = MCPServer()

__all__ = ['orchestrator', 'mcp_server', 'MCPServer', 'SkynetOrchestrator', 'BaseAgent']
