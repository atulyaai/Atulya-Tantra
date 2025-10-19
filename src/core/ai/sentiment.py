"""
Atulya Tantra - Sentiment Analysis System
Version: 2.5.0
Analyzes user sentiment and provides tone adjustments
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class Sentiment(Enum):
    """Sentiment enumeration"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    FRUSTRATED = "frustrated"
    EXCITED = "excited"
    URGENT = "urgent"


@dataclass
class SentimentResult:
    """Sentiment analysis result"""
    sentiment: Sentiment
    confidence: float
    tone_adjustment: str


class SentimentAnalyzer:
    """Analyzes user sentiment and provides tone adjustments"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.frustrated_keywords = [
            "error", "broken", "doesn't work", "failed",
            "help!", "frustrated", "stuck", "not working",
            "problem", "issue", "bug", "crash", "hang"
        ]
        self.positive_keywords = [
            "thanks", "great", "awesome", "perfect",
            "love", "excellent", "amazing", "wonderful",
            "fantastic", "brilliant", "outstanding"
        ]
        self.urgent_keywords = [
            "urgent", "asap", "quickly", "now",
            "emergency", "immediately", "critical",
            "rush", "hurry", "fast", "priority"
        ]
        self.negative_keywords = [
            "bad", "terrible", "awful", "hate",
            "disappointed", "angry", "upset",
            "wrong", "incorrect", "mistake"
        ]
    
    async def analyze(self, message: str) -> SentimentResult:
        """Analyze message sentiment"""
        message_lower = message.lower()
        
        # Detect sentiment
        sentiment = self._detect_sentiment(message_lower, message)
        
        # Calculate confidence
        confidence = self._calculate_confidence(message_lower, sentiment)
        
        # Get tone adjustment
        tone_adjustment = self._get_tone_adjustment(sentiment)
        
        logger.info(f"Sentiment: {sentiment.value}, confidence: {confidence:.2f}")
        
        return SentimentResult(
            sentiment=sentiment,
            confidence=confidence,
            tone_adjustment=tone_adjustment
        )
    
    def _detect_sentiment(self, message_lower: str, original: str) -> Sentiment:
        """Detect sentiment from message"""
        # Check urgent first (highest priority)
        if any(kw in message_lower for kw in self.urgent_keywords):
            return Sentiment.URGENT
        
        # Check frustrated
        if any(kw in message_lower for kw in self.frustrated_keywords):
            return Sentiment.FRUSTRATED
        
        # Check negative
        if any(kw in message_lower for kw in self.negative_keywords):
            return Sentiment.NEGATIVE
        
        # Check positive
        if any(kw in message_lower for kw in self.positive_keywords):
            return Sentiment.POSITIVE
        
        # Check excited (exclamation marks, caps)
        if original.count("!") > 2 or (len(original) > 10 and original.isupper()):
            return Sentiment.EXCITED
        
        return Sentiment.NEUTRAL
    
    def _calculate_confidence(self, message: str, sentiment: Sentiment) -> float:
        """Calculate sentiment detection confidence"""
        if sentiment == Sentiment.FRUSTRATED:
            count = sum(1 for kw in self.frustrated_keywords if kw in message)
            return min(0.6 + (count * 0.1), 0.95)
        
        elif sentiment == Sentiment.URGENT:
            count = sum(1 for kw in self.urgent_keywords if kw in message)
            return min(0.7 + (count * 0.1), 0.95)
        
        elif sentiment == Sentiment.POSITIVE:
            count = sum(1 for kw in self.positive_keywords if kw in message)
            return min(0.65 + (count * 0.1), 0.95)
        
        elif sentiment == Sentiment.NEGATIVE:
            count = sum(1 for kw in self.negative_keywords if kw in message)
            return min(0.65 + (count * 0.1), 0.95)
        
        return 0.75  # Default confidence for neutral/excited
    
    def _get_tone_adjustment(self, sentiment: Sentiment) -> str:
        """Get system prompt tone adjustment"""
        adjustments = {
            Sentiment.FRUSTRATED: "The user seems frustrated. Be extra patient, empathetic, and thorough. Break down steps clearly and offer additional help.",
            Sentiment.URGENT: "The user needs help urgently. Provide clear, actionable steps immediately. Be concise but complete.",
            Sentiment.EXCITED: "The user is enthusiastic! Match their energy with positive, encouraging responses.",
            Sentiment.POSITIVE: "The user is happy. Continue with a friendly, helpful tone.",
            Sentiment.NEGATIVE: "The user seems disappointed. Be understanding, acknowledge their concerns, and focus on solutions.",
            Sentiment.NEUTRAL: "Maintain a professional, informative tone."
        }
        return adjustments.get(sentiment, "")
