"""
Data Agent for Atulya Tantra AGI
Specialized agent for data processing and analysis
"""

from typing import Dict, List, Any, Optional
from .base_agent import BaseAgent

class DataAgent(BaseAgent):
    """Agent specialized for data-related tasks"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("DataAgent", config)
        self.capabilities = [
            "data_analysis",
            "data_processing",
            "data_visualization",
            "statistical_analysis"
        ]
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process data-related tasks"""
        task_type = task.get('type', 'unknown')
        
        if task_type == 'analyze_data':
            return await self.analyze_data(task)
        elif task_type == 'process_data':
            return await self.process_data(task)
        else:
            return {
                'status': 'error',
                'message': f'Unknown task type: {task_type}'
            }
    
    async def analyze_data(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze data"""
        data = task.get('data', [])
        
        analysis = {
            'count': len(data),
            'type': type(data).__name__,
            'summary': f'Analyzed {len(data)} items'
        }
        
        return {
            'status': 'success',
            'analysis': analysis
        }
    
    async def process_data(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process data"""
        data = task.get('data', [])
        operation = task.get('operation', 'count')
        
        if operation == 'count':
            result = len(data)
        elif operation == 'sum':
            result = sum(data) if all(isinstance(x, (int, float)) for x in data) else 0
        else:
            result = data
        
        return {
            'status': 'success',
            'result': result,
            'operation': operation
        }