"""
NLP Engine for understanding and processing natural language
"""

import re
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class NLPEngine:
    """Natural Language Processing Engine"""

    def __init__(self):
        """Initialize NLP Engine"""
        self.intent_patterns = {
            "information": [r"what is", r"tell me", r"explain", r"how to"],
            "execution": [r"execute", r"run", r"perform", r"do"],
            "analysis": [r"analyze", r"examine", r"review", r"check"],
            "learning": [r"learn", r"study", r"understand", r"research"]
        }
        self.entities = {}
        logger.info("NLP Engine initialized")

    def parse_task(self, task_description: str) -> Dict[str, Any]:
        """
        Parse task description into structured format
        
        Args:
            task_description: Natural language task description
            
        Returns:
            Parsed task structure
        """
        intent = self._detect_intent(task_description)
        entities = self._extract_entities(task_description)
        keywords = self._extract_keywords(task_description)
        
        parsed = {
            "original": task_description,
            "intent": intent,
            "entities": entities,
            "keywords": keywords,
            "priority": self._estimate_priority(task_description),
            "complexity": self._estimate_complexity(task_description)
        }
        
        return parsed

    def _detect_intent(self, text: str) -> str:
        """Detect task intent from text"""
        text_lower = text.lower()
        
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return intent
        
        return "general"

    def _extract_entities(self, text: str) -> List[Dict]:
        """Extract named entities from text"""
        entities = []
        
        # Simple entity extraction patterns
        patterns = {
            "location": r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b",
            "number": r"\b\d+(?:\.\d+)?\b",
            "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "url": r"https?://\S+"
        }
        
        for entity_type, pattern in patterns.items():
            matches = re.finditer(pattern, text)
            for match in matches:
                entities.append({
                    "type": entity_type,
                    "value": match.group(),
                    "position": match.span()
                })
        
        return entities

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract important keywords"""
        # Remove common stop words
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at",
            "to", "for", "of", "with", "is", "are", "be", "was", "were"
        }
        
        words = text.lower().split()
        keywords = [w.strip(".,!?") for w in words 
                   if w.lower() not in stop_words and len(w) > 2]
        
        return keywords

    def _estimate_priority(self, text: str) -> str:
        """Estimate task priority"""
        high_priority_keywords = ["urgent", "immediately", "critical", "important"]
        low_priority_keywords = ["later", "when possible", "no rush"]
        
        text_lower = text.lower()
        
        for keyword in high_priority_keywords:
            if keyword in text_lower:
                return "high"
        
        for keyword in low_priority_keywords:
            if keyword in text_lower:
                return "low"
        
        return "medium"

    def _estimate_complexity(self, text: str) -> str:
        """Estimate task complexity"""
        word_count = len(text.split())
        
        if word_count > 50:
            return "high"
        elif word_count > 20:
            return "medium"
        else:
            return "low"

    def sentiment_analysis(self, text: str) -> Dict[str, float]:
        """
        Analyze sentiment of text
        
        Args:
            text: Text to analyze
            
        Returns:
            Sentiment scores
        """
        positive_words = {"good", "great", "excellent", "happy", "love", "amazing"}
        negative_words = {"bad", "terrible", "sad", "hate", "awful", "horrible"}
        
        words = set(text.lower().split())
        
        positive_count = len(words & positive_words)
        negative_count = len(words & negative_words)
        total = len(words)
        
        return {
            "positive": positive_count / total if total > 0 else 0,
            "negative": negative_count / total if total > 0 else 0,
            "neutral": 1 - (positive_count + negative_count) / total if total > 0 else 1
        }
