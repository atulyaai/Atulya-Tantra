"""
Atulya Tantra - Hybrid Model Router
Version: 2.2.0
Handles intelligent routing between local and cloud AI models.
"""

import asyncio
import time
import json
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
import openai
import anthropic
import google.generativeai as genai
import ollama
from enum import Enum

class ModelProvider(Enum):
    """Model provider enumeration"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OLLAMA = "ollama"

class ModelStrategy(Enum):
    """Model routing strategy"""
    LOCAL_FIRST = "local_first"
    CLOUD_FIRST = "cloud_first"
    HYBRID = "hybrid"
    COST_OPTIMIZED = "cost_optimized"
    PERFORMANCE_OPTIMIZED = "performance_optimized"

@dataclass
class ModelConfig:
    """Model configuration"""
    provider: ModelProvider
    model_name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 30
    cost_per_token: float = 0.0
    performance_score: float = 1.0
    enabled: bool = True

@dataclass
class ModelResponse:
    """Model response structure"""
    content: str
    model_used: str
    provider: str
    tokens_used: int
    response_time: float
    cost: float
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class ModelMetrics:
    """Model performance metrics"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    total_tokens: int = 0
    total_cost: float = 0.0
    last_used: Optional[datetime] = None

class ModelClient:
    """Base model client"""
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.metrics = ModelMetrics()
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the model client"""
        pass
    
    async def generate_response(self, prompt: str, **kwargs) -> ModelResponse:
        """Generate response from model"""
        raise NotImplementedError("Subclasses must implement generate_response")

class OpenAIClient(ModelClient):
    """OpenAI model client"""
    
    def _initialize_client(self):
        """Initialize OpenAI client"""
        if self.config.api_key:
            openai.api_key = self.config.api_key
        if self.config.base_url:
            openai.api_base = self.config.base_url
    
    async def generate_response(self, prompt: str, **kwargs) -> ModelResponse:
        """Generate response using OpenAI"""
        start_time = time.time()
        
        try:
            response = await openai.ChatCompletion.acreate(
                model=self.config.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                timeout=self.config.timeout
            )
            
            response_time = time.time() - start_time
            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            cost = tokens_used * self.config.cost_per_token
            
            self._update_metrics(True, response_time, tokens_used, cost)
            
            return ModelResponse(
                content=content,
                model_used=self.config.model_name,
                provider=self.config.provider.value,
                tokens_used=tokens_used,
                response_time=response_time,
                cost=cost
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            self._update_metrics(False, response_time, 0, 0)
            raise Exception(f"OpenAI API error: {e}")
    
    def _update_metrics(self, success: bool, response_time: float, tokens: int, cost: float):
        """Update performance metrics"""
        self.metrics.total_requests += 1
        if success:
            self.metrics.successful_requests += 1
        else:
            self.metrics.failed_requests += 1
        
        # Update average response time
        total_time = self.metrics.average_response_time * (self.metrics.total_requests - 1)
        self.metrics.average_response_time = (total_time + response_time) / self.metrics.total_requests
        
        self.metrics.total_tokens += tokens
        self.metrics.total_cost += cost
        self.metrics.last_used = datetime.now()

class AnthropicClient(ModelClient):
    """Anthropic model client"""
    
    def _initialize_client(self):
        """Initialize Anthropic client"""
        if self.config.api_key:
            self.client = anthropic.AsyncAnthropic(api_key=self.config.api_key)
    
    async def generate_response(self, prompt: str, **kwargs) -> ModelResponse:
        """Generate response using Anthropic"""
        start_time = time.time()
        
        try:
            response = await self.client.messages.create(
                model=self.config.model_name,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_time = time.time() - start_time
            content = response.content[0].text
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            cost = tokens_used * self.config.cost_per_token
            
            self._update_metrics(True, response_time, tokens_used, cost)
            
            return ModelResponse(
                content=content,
                model_used=self.config.model_name,
                provider=self.config.provider.value,
                tokens_used=tokens_used,
                response_time=response_time,
                cost=cost
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            self._update_metrics(False, response_time, 0, 0)
            raise Exception(f"Anthropic API error: {e}")
    
    def _update_metrics(self, success: bool, response_time: float, tokens: int, cost: float):
        """Update performance metrics"""
        self.metrics.total_requests += 1
        if success:
            self.metrics.successful_requests += 1
        else:
            self.metrics.failed_requests += 1
        
        total_time = self.metrics.average_response_time * (self.metrics.total_requests - 1)
        self.metrics.average_response_time = (total_time + response_time) / self.metrics.total_requests
        
        self.metrics.total_tokens += tokens
        self.metrics.total_cost += cost
        self.metrics.last_used = datetime.now()

class OllamaClient(ModelClient):
    """Ollama local model client"""
    
    def _initialize_client(self):
        """Initialize Ollama client"""
        self.client = ollama.AsyncClient(host=self.config.base_url or "http://localhost:11434")
    
    async def generate_response(self, prompt: str, **kwargs) -> ModelResponse:
        """Generate response using Ollama"""
        start_time = time.time()
        
        try:
            response = await self.client.generate(
                model=self.config.model_name,
                prompt=prompt,
                options={
                    "temperature": self.config.temperature,
                    "num_predict": self.config.max_tokens
                }
            )
            
            response_time = time.time() - start_time
            content = response['response']
            tokens_used = len(content.split())  # Approximate token count
            cost = 0.0  # Local models are free
            
            self._update_metrics(True, response_time, tokens_used, cost)
            
            return ModelResponse(
                content=content,
                model_used=self.config.model_name,
                provider=self.config.provider.value,
                tokens_used=tokens_used,
                response_time=response_time,
                cost=cost
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            self._update_metrics(False, response_time, 0, 0)
            raise Exception(f"Ollama API error: {e}")
    
    def _update_metrics(self, success: bool, response_time: float, tokens: int, cost: float):
        """Update performance metrics"""
        self.metrics.total_requests += 1
        if success:
            self.metrics.successful_requests += 1
        else:
            self.metrics.failed_requests += 1
        
        total_time = self.metrics.average_response_time * (self.metrics.total_requests - 1)
        self.metrics.average_response_time = (total_time + response_time) / self.metrics.total_requests
        
        self.metrics.total_tokens += tokens
        self.metrics.total_cost += cost
        self.metrics.last_used = datetime.now()

class HybridModelRouter:
    """Main hybrid model router"""
    
    def __init__(self):
        self.models: Dict[str, ModelClient] = {}
        self.strategy = ModelStrategy.HYBRID
        self.cache: Dict[str, ModelResponse] = {}
        self.cache_ttl = 3600  # 1 hour
        
        # Initialize default models
        self._initialize_default_models()
    
    def _initialize_default_models(self):
        """Initialize default model configurations"""
        default_configs = [
            ModelConfig(
                provider=ModelProvider.OLLAMA,
                model_name="llama2",
                base_url="http://localhost:11434",
                cost_per_token=0.0,
                performance_score=0.7
            ),
            ModelConfig(
                provider=ModelProvider.OPENAI,
                model_name="gpt-3.5-turbo",
                cost_per_token=0.0005,
                performance_score=0.9
            ),
            ModelConfig(
                provider=ModelProvider.ANTHROPIC,
                model_name="claude-3-sonnet-20240229",
                cost_per_token=0.003,
                performance_score=0.95
            )
        ]
        
        for config in default_configs:
            self.add_model(config)
    
    def add_model(self, config: ModelConfig):
        """Add a model configuration"""
        model_id = f"{config.provider.value}_{config.model_name}"
        
        if config.provider == ModelProvider.OPENAI:
            client = OpenAIClient(config)
        elif config.provider == ModelProvider.ANTHROPIC:
            client = AnthropicClient(config)
        elif config.provider == ModelProvider.OLLAMA:
            client = OllamaClient(config)
        else:
            raise ValueError(f"Unsupported provider: {config.provider}")
        
        self.models[model_id] = client
    
    def remove_model(self, model_id: str):
        """Remove a model"""
        if model_id in self.models:
            del self.models[model_id]
    
    def set_strategy(self, strategy: ModelStrategy):
        """Set routing strategy"""
        self.strategy = strategy
    
    async def route_request(self, prompt: str, task_type: str = "general", 
                          context: Dict[str, Any] = None, 
                          preferred_model: str = None,
                          max_cost: float = None) -> ModelResponse:
        """Route request to appropriate model"""
        
            # Check cache first
        cache_key = self._generate_cache_key(prompt, task_type)
        if cache_key in self.cache:
            cached_response = self.cache[cache_key]
            if (datetime.now() - cached_response.timestamp).seconds < self.cache_ttl:
                return cached_response
            
            # Select best model
        model_id = await self._select_best_model(prompt, task_type, context, preferred_model, max_cost)
            
        if not model_id:
            raise Exception("No suitable model available")
            
            # Execute request
        try:
            model_client = self.models[model_id]
            response = await model_client.generate_response(prompt)
            
            # Cache response
            self.cache[cache_key] = response
            
            return response
            
        except Exception as e:
            # Try fallback models
            return await self._try_fallback_models(prompt, model_id, max_cost)
    
    async def _select_best_model(self, prompt: str, task_type: str,
                               context: Dict[str, Any], preferred_model: str,
                               max_cost: float) -> Optional[str]:
        """Select the best model for the request"""
        
        available_models = [mid for mid, client in self.models.items() 
                          if client.config.enabled]
        
        if not available_models:
            return None
        
        # Filter by preferred model
        if preferred_model:
            preferred_models = [mid for mid in available_models 
                              if preferred_model in mid]
            if preferred_models:
                available_models = preferred_models
        
        # Filter by cost constraint
        if max_cost is not None:
            affordable_models = []
            for model_id in available_models:
                client = self.models[model_id]
                estimated_cost = len(prompt.split()) * client.config.cost_per_token
                if estimated_cost <= max_cost:
                    affordable_models.append(model_id)
            if affordable_models:
                available_models = affordable_models
        
        # Select based on strategy
        if self.strategy == ModelStrategy.LOCAL_FIRST:
            # Prefer local models (Ollama)
            local_models = [mid for mid in available_models if "ollama" in mid]
            if local_models:
                return local_models[0]
    
        elif self.strategy == ModelStrategy.CLOUD_FIRST:
            # Prefer cloud models
            cloud_models = [mid for mid in available_models if "ollama" not in mid]
            if cloud_models:
                return cloud_models[0]
    
        elif self.strategy == ModelStrategy.COST_OPTIMIZED:
            # Prefer cheapest model
            cheapest_model = min(available_models, 
                               key=lambda mid: self.models[mid].config.cost_per_token)
            return cheapest_model
        
        elif self.strategy == ModelStrategy.PERFORMANCE_OPTIMIZED:
            # Prefer highest performance model
            best_model = max(available_models,
                           key=lambda mid: self.models[mid].config.performance_score)
            return best_model
        
        # Default: return first available model
        return available_models[0]
    
    async def _try_fallback_models(self, prompt: str, failed_model_id: str,
                                 max_cost: float) -> ModelResponse:
        """Try fallback models if primary model fails"""
        
        available_models = [mid for mid, client in self.models.items() 
                          if mid != failed_model_id and client.config.enabled]
        
        for model_id in available_models:
            try:
                model_client = self.models[model_id]
                
                # Check cost constraint
                if max_cost is not None:
                    estimated_cost = len(prompt.split()) * model_client.config.cost_per_token
                    if estimated_cost > max_cost:
                        continue
                
                response = await model_client.generate_response(prompt)
                return response
                
            except Exception as e:
                print(f"Fallback model {model_id} failed: {e}")
                continue
        
        raise Exception("All models failed")
    
    def _generate_cache_key(self, prompt: str, task_type: str) -> str:
        """Generate cache key for prompt"""
        import hashlib
        content = f"{prompt}_{task_type}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get_model_metrics(self) -> Dict[str, ModelMetrics]:
        """Get metrics for all models"""
        return {model_id: client.metrics for model_id, client in self.models.items()}
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system status"""
        total_requests = sum(client.metrics.total_requests for client in self.models.values())
        successful_requests = sum(client.metrics.successful_requests for client in self.models.values())
        
        return {
            "strategy": self.strategy.value,
            "total_models": len(self.models),
            "enabled_models": len([c for c in self.models.values() if c.config.enabled]),
            "total_requests": total_requests,
            "success_rate": successful_requests / total_requests if total_requests > 0 else 0,
            "cache_size": len(self.cache),
            "models": {model_id: {
                "provider": client.config.provider.value,
                "model_name": client.config.model_name,
                "enabled": client.config.enabled,
                "metrics": client.metrics
            } for model_id, client in self.models.items()}
        }

# Global instances
_hybrid_model_router: Optional[HybridModelRouter] = None

def get_hybrid_model_router() -> HybridModelRouter:
    """Get global hybrid model router instance"""
    global _hybrid_model_router
    if _hybrid_model_router is None:
        _hybrid_model_router = HybridModelRouter()
    return _hybrid_model_router

# Alias for compatibility
def get_model_router() -> HybridModelRouter:
    """Get model router (alias for compatibility)"""
    return get_hybrid_model_router()

# Export main classes and functions
__all__ = [
    "ModelProvider",
    "ModelStrategy",
    "ModelConfig",
    "ModelResponse",
    "ModelMetrics",
    "ModelClient",
    "OpenAIClient",
    "AnthropicClient",
    "OllamaClient",
    "HybridModelRouter",
    "get_hybrid_model_router",
    "get_model_router"
]
