from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from datetime import datetime

class LogicNode(BaseModel):
    id: str
    instruction: str
    dependencies: List[str] = Field(default_factory=list)
    status: str = "pending"
    result: Optional[str] = None

class AGIPlan(BaseModel):
    plan_id: str
    goal: str
    nodes: List[LogicNode]
    created_at: datetime = Field(default_factory=datetime.now)

class SystemPulse(BaseModel):
    cpu_load: float
    mem_usage: float
    bus_frequency: float = 20.0
    active_modules: List[str]
    timestamp: datetime = Field(default_factory=datetime.now)
