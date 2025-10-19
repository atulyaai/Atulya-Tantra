"""
Atulya Tantra - Model Router
Version: 2.5.0
Intelligent model routing for Ollama models only
"""

from typing import List, Optional, Dict
from dataclasses import dataclass
import logging
from .classifier import TaskType, Complexity

logger = logging.getLogger(__name__)


@dataclass
class ModelSelection:
    provider: str  # "ollama"
    model: str
    reasoning: str


class ModelRouter:
    """Routes requests to optimal Ollama model based on task classification"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.fallback_order = ["ollama"]  # Only Ollama
    
    async def select_model(
        self,
        task_type: TaskType,
        complexity: Complexity,
        available_models: Dict[str, List[str]]
    ) -> ModelSelection:
        """Select best Ollama model for task"""
        
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
        
        # Fallback to first available Ollama model
        if "ollama" in available_models and available_models["ollama"]:
            model = available_models["ollama"][0]
            logger.warning(f"Using fallback model ollama/{model}")
            return ModelSelection(
                provider="ollama",
                model=model,
                reasoning="Fallback to available Ollama model"
            )
        
        # If no models available, return a default
        logger.warning("No Ollama models available, using default fallback")
        return ModelSelection(
            provider="ollama",
            model="gemma2:2b",
            reasoning="Default fallback - no models configured"
        )
    
    def _get_model_preferences(self, task_type: TaskType, complexity: Complexity) -> List[tuple]:
        """Get ordered list of preferred Ollama models"""
        # Coding tasks - use coder model
        if task_type == TaskType.CODING:
            return [
                ("ollama", "qwen2.5-coder:7b"),
                ("ollama", "codellama:latest"),
                ("ollama", "mistral:latest")
            ]
        
        # Simple tasks - use gemma2 for conversation
        if complexity == Complexity.SIMPLE:
            return [
                ("ollama", "gemma2:2b"),
                ("ollama", "gemma:latest"),
                ("ollama", "mistral:latest")
            ]
        
        # Complex tasks - use mistral
        if complexity == Complexity.COMPLEX:
            return [
                ("ollama", "mistral:latest"),
                ("ollama", "gemma2:2b"),
                ("ollama", "qwen2.5-coder:7b")
            ]
        
        # Research tasks - use mistral for reasoning
        if task_type == TaskType.RESEARCH:
            return [
                ("ollama", "mistral:latest"),
                ("ollama", "gemma2:2b"),
                ("ollama", "qwen2.5-coder:7b")
            ]
        
        # Creative tasks - use mistral for creativity
        if task_type == TaskType.CREATIVE:
            return [
                ("ollama", "mistral:latest"),
                ("ollama", "gemma2:2b"),
                ("ollama", "qwen2.5-coder:7b")
            ]
        
        # Default - use gemma2 for general conversation
        return [
            ("ollama", "gemma2:2b"),
            ("ollama", "mistral:latest"),
            ("ollama", "qwen2.5-coder:7b")
        ]