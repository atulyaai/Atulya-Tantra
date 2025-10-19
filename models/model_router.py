"""
Atulya Tantra - Smart Model Router
Routes to gemma2:2b for simple tasks, mistral for complex tasks
"""

from typing import Dict, Any
from core.logger import get_logger

logger = get_logger('models.router')


class ModelRouter:
    """Smart router that selects best model for task"""
    
    def __init__(self):
        self.simple_model = "gemma2:2b"      # Fast, brief responses
        self.complex_model = "mistral:latest"  # Better quality, detailed
        logger.info(f"Model router: {self.simple_model} (simple) | {self.complex_model} (complex)")
    
    def select_model(self, message: str) -> str:
        """
        Select appropriate model based on message complexity
        
        Args:
            message: User message
            
        Returns:
            Model name to use
        """
        msg_lower = message.lower()
        
        # Complex task indicators
        complex_indicators = [
            'code', 'program', 'function', 'debug', 'explain', 'analyze',
            'write', 'create', 'build', 'design', 'algorithm', 'solve',
            'research', 'compare', 'detailed', 'complex', 'technical',
            'why', 'how does', 'what is', 'tell me about'
        ]
        
        # Check if complex
        is_complex = any(indicator in msg_lower for indicator in complex_indicators)
        
        # Check length (long questions are usually complex)
        word_count = len(message.split())
        if word_count > 10:
            is_complex = True
        
        selected = self.complex_model if is_complex else self.simple_model
        logger.debug(f"Selected {selected} for: {message[:50]}...")
        
        return selected
    
    def get_model_config(self, model: str) -> Dict[str, Any]:
        """Get configuration for selected model"""
        configs = {
            self.simple_model: {
                'num_predict': 15,      # Very brief
                'temperature': 0.7,
            },
            self.complex_model: {
                'num_predict': 200,     # Detailed
                'temperature': 0.7,
            }
        }
        return configs.get(model, configs[self.simple_model])


# Global instance
_router: ModelRouter = None


def get_model_router() -> ModelRouter:
    """Get global model router instance"""
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router


__all__ = ['ModelRouter', 'get_model_router']

