"""
Agent Orchestrator - MCP Server Integration & Multi-Agent System
Coordinates multiple AI agents and tools for complex tasks
"""

import logging
from typing import Dict, List, Optional, Any
import asyncio

logger = logging.getLogger(__name__)

class Agent:
    """Base agent class for specific tasks"""
    
    def __init__(self, name: str, model: str, system_prompt: str):
        self.name = name
        self.model = model
        self.system_prompt = system_prompt
    
    async def execute(self, task: str, context: Optional[Dict] = None) -> str:
        """Execute agent task"""
        import ollama
        
        messages = [
            {'role': 'system', 'content': self.system_prompt},
            {'role': 'user', 'content': task}
        ]
        
        if context:
            # Add context from previous agents
            for key, value in context.items():
                messages.insert(1, {'role': 'user', 'content': f"Context - {key}: {value}"})
        
        response = ollama.chat(model=self.model, messages=messages, options={'num_predict': 100})
        return response['message']['content']

class AgentOrchestrator:
    """Orchestrates multiple specialized agents for complex tasks"""
    
    def __init__(self):
        # Specialized agents for different tasks
        self.agents = {
            'conversation': Agent(
                name='Conversation Agent',
                model='phi3:mini',
                system_prompt='You are Atulya, a warm conversational AI. Keep responses brief (1 sentence for simple, 2 for complex). Be friendly and helpful. English only, no emojis.'
            ),
            
            'code': Agent(
                name='Code Agent',
                model='phi3:mini',  # Will use codellama if available
                system_prompt='You are a programming expert. Provide clear, concise code solutions. Explain briefly.'
            ),
            
            'task_planner': Agent(
                name='Task Planner',
                model='phi3:mini',
                system_prompt='You are a task planning agent. Break down requests into actionable steps. Be concise.'
            ),
            
            'researcher': Agent(
                name='Research Agent',
                model='phi3:mini',
                system_prompt='You are a research assistant. Provide accurate, concise information. Cite sources when possible.'
            ),
        }
    
    def detect_agent_type(self, message: str) -> str:
        """Detect which agent should handle the message"""
        msg_lower = message.lower()
        
        # Code-related
        if any(word in msg_lower for word in ['code', 'function', 'debug', 'program', 'script']):
            return 'code'
        
        # Research/factual
        if any(word in msg_lower for word in ['what is', 'who is', 'explain', 'research', 'find out']):
            return 'researcher'
        
        # Task planning
        if any(word in msg_lower for word in ['plan', 'steps', 'how to', 'guide']):
            return 'task_planner'
        
        # Default to conversation
        return 'conversation'
    
    async def process(self, message: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Process message through appropriate agent(s)
        
        Returns:
            {
                'response': str,
                'agent_used': str,
                'execution_time': float
            }
        """
        import time
        start_time = time.time()
        
        # Detect appropriate agent
        agent_type = self.detect_agent_type(message)
        agent = self.agents.get(agent_type)
        
        logger.info(f"Routing to {agent_type} agent")
        
        # Execute agent
        response = await agent.execute(message, context)
        
        execution_time = time.time() - start_time
        
        return {
            'response': response,
            'agent_used': agent_type,
            'model': agent.model,
            'execution_time': execution_time
        }

class MCPServer:
    """Model Context Protocol Server for tool integration"""
    
    def __init__(self):
        self.tools = {}
        self.register_default_tools()
    
    def register_default_tools(self):
        """Register default MCP tools"""
        self.tools = {
            'get_system_info': self.get_system_info,
            'search_files': self.search_files,
            'open_application': self.open_app,
            'web_search': self.web_search,
            'calculate': self.calculate,
        }
    
    async def get_system_info(self, params: Dict) -> Dict:
        """MCP Tool: Get system information"""
        from services.task_service import task_service
        return await task_service.get_system_info()
    
    async def search_files(self, params: Dict) -> Dict:
        """MCP Tool: Search files"""
        from services.task_service import task_service
        return await task_service.search_files(
            params.get('query', ''),
            params.get('directory', '.')
        )
    
    async def open_app(self, params: Dict) -> Dict:
        """MCP Tool: Open application"""
        from services.task_service import task_service
        return await task_service.open_application(params.get('app_name', ''))
    
    async def web_search(self, params: Dict) -> Dict:
        """MCP Tool: Web search"""
        from services.task_service import task_service
        return await task_service.web_search(params.get('query', ''))
    
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

# Global instances
orchestrator = AgentOrchestrator()
mcp_server = MCPServer()

