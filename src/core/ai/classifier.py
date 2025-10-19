"""
Atulya Tantra - Task Classification System
Version: 2.5.0
Intelligent task classification for optimal model routing
"""

from enum import Enum
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Task type enumeration"""
    CODING = "coding"
    GENERAL = "general"
    CREATIVE = "creative"
    RESEARCH = "research"
    SIMPLE = "simple"


class Complexity(Enum):
    """Complexity level enumeration"""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


@dataclass
class ClassificationResult:
    """Task classification result"""
    task_type: TaskType
    complexity: Complexity
    confidence: float
    reasoning: str


class TaskClassifier:
    """Classifies user messages into task types and complexity levels"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.coding_keywords = [
            "code", "function", "debug", "error", "program",
            "python", "javascript", "java", "c++", "sql",
            "implement", "algorithm", "class", "method",
            "variable", "loop", "condition", "api", "database"
        ]
        self.simple_patterns = [
            "hello", "hi", "thanks", "yes", "no", "ok", "bye",
            "good morning", "good afternoon", "good evening"
        ]
        self.research_keywords = [
            "research", "find", "search", "learn about", "what is",
            "explain", "tell me about", "information", "facts"
        ]
        self.creative_keywords = [
            "write", "create", "story", "poem", "article", "essay",
            "creative", "imagine", "design", "art", "music"
        ]
    
    async def classify(self, message: str) -> ClassificationResult:
        """Classify message into task type and complexity"""
        message_lower = message.lower()
        word_count = len(message.split())
        
        # Determine task type
        task_type = self._classify_task_type(message_lower)
        
        # Determine complexity
        complexity = self._classify_complexity(message, word_count)
        
        # Calculate confidence
        confidence = self._calculate_confidence(message, task_type, complexity)
        
        logger.info(f"Classification: {task_type.value}, {complexity.value}, {confidence:.2f}")
        
        return ClassificationResult(
            task_type=task_type,
            complexity=complexity,
            confidence=confidence,
            reasoning=f"Detected {task_type.value} task with {complexity.value} complexity"
        )
    
    def _classify_task_type(self, message: str) -> TaskType:
        """Classify into task type"""
        # Coding detection
        coding_score = sum(1 for kw in self.coding_keywords if kw in message)
        if coding_score >= 2:
            return TaskType.CODING
        
        # Simple detection
        if any(pattern in message for pattern in self.simple_patterns):
            return TaskType.SIMPLE
        
        # Research detection
        if any(kw in message for kw in self.research_keywords):
            return TaskType.RESEARCH
        
        # Creative detection
        if any(kw in message for kw in self.creative_keywords):
            return TaskType.CREATIVE
        
        return TaskType.GENERAL
    
    def _classify_complexity(self, message: str, word_count: int) -> Complexity:
        """Classify complexity level"""
        # Simple heuristics for complexity
        if word_count < 10:
            return Complexity.SIMPLE
        elif word_count < 50:
            return Complexity.MEDIUM
        else:
            return Complexity.COMPLEX
    
    def _calculate_confidence(self, message: str, task_type: TaskType, complexity: Complexity) -> float:
        """Calculate classification confidence"""
        base_confidence = 0.7
        
        # Increase confidence if strong indicators present
        message_lower = message.lower()
        
        if task_type == TaskType.CODING:
            coding_score = sum(1 for kw in self.coding_keywords if kw in message_lower)
            base_confidence += min(coding_score * 0.1, 0.2)
        
        elif task_type == TaskType.RESEARCH:
            research_score = sum(1 for kw in self.research_keywords if kw in message_lower)
            base_confidence += min(research_score * 0.1, 0.2)
        
        elif task_type == TaskType.CREATIVE:
            creative_score = sum(1 for kw in self.creative_keywords if kw in message_lower)
            base_confidence += min(creative_score * 0.1, 0.2)
        
        return min(base_confidence, 1.0)
