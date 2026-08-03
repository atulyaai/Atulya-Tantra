from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from enum import Enum

class ModelProvider(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    VLLM = "vllm"

class TantraMessage(BaseModel):
    role: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TantraRequest(BaseModel):
    messages: List[TantraMessage]
    model: str
    provider: Optional[ModelProvider] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False
    context_id: Optional[str] = None # Interlinking with Smriti
    trace_id: Optional[str] = None   # Interlinking with Trace
    budget_limit: Optional[float] = None # Interlinking with Kosha

class TantraResponse(BaseModel):
    content: str
    model: str
    provider: ModelProvider
    usage: Dict[str, int] = Field(default_factory=dict)
    cost: float = 0.0
    trace_id: str
    entropy_score: Optional[float] = None
    confidence_level: Optional[str] = None
