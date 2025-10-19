"""
Atulya Tantra - Model Router
Version: 2.5.0
Intelligent model routing based on task classification
"""

from typing import List, Optional, Dict
from dataclasses import dataclass
import logging
from .classifier import TaskType, Complexity

logger = logging.getLogger(__name__)


@dataclass
class ModelSelection:
    """Model selection result"""
    provider: str  # "ollama", "openai", "anthropic"
    model: str
    reasoning: str


class ModelRouter:
    """Routes requests to optimal AI model based on task classification"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.fallback_order = config.get('fallback_order', ['ollama', 'openai', 'anthropic'])
    
    async def select_model(
        self,
        task_type: TaskType,
        complexity: Complexity,
        available_models: Dict[str, List[str]]
    ) -> ModelSelection:
        """Select best model for task"""
        
        # Define model preferences
        preferences = self._get_model_preferences(task_type, complexity)
        
        # Find first available preferred model
        for provider, model in preferences:
            if provider in available_models and model in available_models[provider]:
                logger.info(f"Selected {provider}/{model} for {task_type.value} task")
                return ModelSelection(
                    provider=provider,
                    model=model,
                    reasoning=f"Best match for {task_type.value} task with {complexity.value} complexity"
                )
        
        # Fallback to first available
        for provider in self.fallback_order:
            if provider in available_models and available_models[provider]:
                model = available_models[provider][0]
                logger.warning(f"Using fallback model {provider}/{model}")
                return ModelSelection(
                    provider=provider,
                    model=model,
                    reasoning="Fallback to available model"
                )
        
        raise RuntimeError("No AI models available")
    
    def _get_model_preferences(self, task_type: TaskType, complexity: Complexity) -> List[tuple]:
        """Get ordered list of preferred models"""
        # Coding tasks - prefer coding-specialized models
        if task_type == TaskType.CODING:
            return [
                ("ollama", "qwen2.5-coder:7b"),
                ("ollama", "codellama:latest"),
                ("openai", "gpt-4"),
                ("anthropic", "claude-3-sonnet-20240229")
            ]
        
        # Simple tasks - use fast, efficient models
        if complexity == Complexity.SIMPLE:
            return [
                ("ollama", "gemma2:2b"),
                ("ollama", "gemma:latest"),
                ("openai", "gpt-3.5-turbo"),
                ("anthropic", "claude-3-haiku-20240307")
            ]
        
        # Complex tasks - use most capable models
        if complexity == Complexity.COMPLEX:
            return [
                ("anthropic", "claude-3-sonnet-20240229"),
                ("openai", "gpt-4"),
                ("ollama", "mistral:latest"),
                ("ollama", "llama2:latest")
            ]
        
        # Research tasks - prefer models good at reasoning
        if task_type == TaskType.RESEARCH:
            return [
                ("anthropic", "claude-3-sonnet-20240229"),
                ("openai", "gpt-4"),
                ("ollama", "mistral:latest")
            ]
        
        # Creative tasks - prefer models good at creative writing
        if task_type == TaskType.CREATIVE:
            return [
                ("openai", "gpt-4"),
                ("anthropic", "claude-3-sonnet-20240229"),
                ("ollama", "mistral:latest")
            ]
        
        # Default - balanced approach
        return [
            ("ollama", "mistral:latest"),
            ("ollama", "gemma2:2b"),
            ("openai", "gpt-3.5-turbo"),
            ("anthropic", "claude-3-haiku-20240307")
        ]
