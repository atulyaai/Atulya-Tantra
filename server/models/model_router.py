"""
Model Router - Routes requests to appropriate AI models
Supports multiple models for different tasks
"""

import ollama
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

class ModelRouter:
    """Routes AI requests to appropriate models based on task type"""
    
    def __init__(self):
        self.models = {
            'chat': 'phi3:mini',           # Fast conversations
            'vision': 'llama3.2-vision',   # Image understanding
            'code': 'codellama',           # Programming tasks
            'reasoning': 'mistral',        # Complex analysis
            'fast': 'phi3:mini',           # Quick responses
        }
        
        self.model_configs = {
            'phi3:mini': {
                'context_window': 4096,
                'max_tokens': 60,
                'temperature': 0.7,
                'use_case': 'General conversation'
            },
            'llama3.2-vision': {
                'context_window': 8192,
                'max_tokens': 100,
                'temperature': 0.7,
                'use_case': 'Image analysis, screen reading'
            },
            'codellama': {
                'context_window': 16384,
                'max_tokens': 200,
                'temperature': 0.3,
                'use_case': 'Code generation, debugging'
            },
            'mistral': {
                'context_window': 8192,
                'max_tokens': 150,
                'temperature': 0.7,
                'use_case': 'Complex reasoning, analysis'
            }
        }
    
    def detect_task_type(self, message: str) -> str:
        """Detect task type from message content"""
        message_lower = message.lower()
        
        # Check for code-related keywords
        if any(keyword in message_lower for keyword in ['code', 'function', 'debug', 'program', 'python', 'javascript']):
            return 'code'
        
        # Check for vision-related keywords  
        if any(keyword in message_lower for keyword in ['image', 'picture', 'screenshot', 'see', 'look at']):
            return 'vision'
        
        # Check for complex reasoning
        if any(keyword in message_lower for keyword in ['analyze', 'explain complex', 'reasoning', 'compare']):
            return 'reasoning'
        
        # Default to fast chat
        return 'chat'
    
    def get_model_for_task(self, task_type: str) -> str:
        """Get appropriate model for task type"""
        return self.models.get(task_type, 'phi3:mini')
    
    def route(self, message: str, explicit_model: Optional[str] = None) -> str:
        """Route message to appropriate model"""
        if explicit_model:
            # Use explicitly requested model
            return explicit_model
        
        # Auto-detect task type and select model
        task_type = self.detect_task_type(message)
        model = self.get_model_for_task(task_type)
        
        logger.info(f"Routing to {model} for task type: {task_type}")
        return model
    
    def get_model_config(self, model: str) -> Dict:
        """Get configuration for specific model"""
        return self.model_configs.get(model, self.model_configs['phi3:mini'])
    
    def list_models(self) -> List[Dict]:
        """List all available models with their configs"""
        try:
            # Check which models are actually installed in Ollama
            ollama_models = ollama.list()
            installed = [m['name'] for m in ollama_models.get('models', [])]
            
            available_models = []
            for model_name, config in self.model_configs.items():
                available_models.append({
                    'name': model_name,
                    'installed': any(model_name in installed_model for installed_model in installed),
                    'config': config
                })
            
            return available_models
            
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            # Return just phi3:mini as fallback
            return [{
                'name': 'phi3:mini',
                'installed': True,
                'config': self.model_configs['phi3:mini']
            }]
    
    async def chat(self, model: str, messages: List[Dict], **options) -> str:
        """Send chat request to specified model"""
        try:
            config = self.get_model_config(model)
            
            # Merge config with custom options
            chat_options = {
                'num_predict': config.get('max_tokens', 60),
                'temperature': config.get('temperature', 0.7),
                'num_ctx': config.get('context_window', 4096),
                **options
            }
            
            logger.info(f"Sending to {model} with options: {chat_options}")
            
            response = ollama.chat(
                model=model,
                messages=messages,
                options=chat_options
            )
            
            return response['message']['content']
            
        except Exception as e:
            logger.error(f"Chat error with {model}: {e}")
            raise

