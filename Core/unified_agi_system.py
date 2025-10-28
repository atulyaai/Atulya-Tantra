"""
Unified AGI System for Atulya Tantra
Combines all AGI components into a unified system
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

from .agi_core import AGICore
from .assistant_core import AssistantCore

class UnifiedAGISystem:
    """Unified AGI system combining all components"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.agi_core = AGICore(config)
        self.assistant_core = AssistantCore(config)
        self.system_status = "initialized"
        self.active_sessions = {}
        
    async def initialize(self) -> bool:
        """Initialize the unified AGI system"""
        try:
            self.system_status = "initializing"
            
            # Initialize components
            await self.agi_core.process_input("initialize")
            await self.assistant_core.process_message("system startup", "system")
            
            self.system_status = "ready"
            return True
            
        except Exception as e:
            self.system_status = "error"
            print(f"Initialization error: {e}")
            return False
    
    async def process_user_input(self, message: str, user_id: str = "default") -> Dict[str, Any]:
        """Process user input through the unified system"""
        try:
            # Process through assistant core first
            assistant_response = await self.assistant_core.process_message(message, user_id)
            
            # Process through AGI core for reasoning
            agi_analysis = await self.agi_core.process_input(message)
            
            # Combine responses
            unified_response = {
                'user_id': user_id,
                'message': message,
                'assistant_response': assistant_response,
                'agi_analysis': agi_analysis,
                'timestamp': datetime.now().isoformat(),
                'system_status': self.system_status
            }
            
            return unified_response
            
        except Exception as e:
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat(),
                'system_status': self.system_status
            }
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""
        return {
            'status': self.system_status,
            'active_sessions': len(self.active_sessions),
            'agi_core_ready': self.agi_core is not None,
            'assistant_core_ready': self.assistant_core is not None,
            'timestamp': datetime.now().isoformat()
        }
    
    async def shutdown(self) -> bool:
        """Shutdown the unified system"""
        try:
            self.system_status = "shutting_down"
            
            # Clean up resources
            self.active_sessions.clear()
            
            self.system_status = "shutdown"
            return True
            
        except Exception as e:
            print(f"Shutdown error: {e}")
            return False