"""
Advanced Sentiment Analysis and Emotional Intelligence for JARVIS
Real-time emotion detection, sentiment analysis, and emotional response generation
"""

import re
import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from enum import Enum
import math

from ..config.settings import settings
from ..config.logging import get_logger
from ..config.exceptions import AgentError
from ..brain import generate_response, get_llm_router

logger = get_logger(__name__)


class EmotionType(str, Enum):
    """Primary emotion types"""
    JOY = "joy"
    SADNESS = "sadness"
    ANGER = "anger"
    FEAR = "fear"
    SURPRISE = "surprise"
    DISGUST = "disgust"
    TRUST = "trust"
    ANTICIPATION = "anticipation"
    NEUTRAL = "neutral"


class SentimentPolarity(str, Enum):
    """Sentiment polarity levels"""
    VERY_NEGATIVE = "very_negative"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    VERY_POSITIVE = "very_positive"


class EmotionalIntensity(str, Enum):
    """Emotional intensity levels"""
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class EmotionalContext:
    """Represents the emotional context of a conversation"""
    
    def __init__(self, user_id: str = None):
        self.user_id = user_id
        self.current_emotion = EmotionType.NEUTRAL
        self.emotion_history = []
        self.sentiment_polarity = SentimentPolarity.NEUTRAL
        self.intensity = EmotionalIntensity.MODERATE
        self.confidence = 0.0
        self.emotional_triggers = []
        self.context_factors = {}
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "user_id": self.user_id,
            "current_emotion": self.current_emotion.value,
            "emotion_history": [e.value for e in self.emotion_history[-10:]],  # Last 10 emotions
            "sentiment_polarity": self.sentiment_polarity.value,
            "intensity": self.intensity.value,
            "confidence": self.confidence,
            "emotional_triggers": self.emotional_triggers,
            "context_factors": self.context_factors,
            "timestamp": self.timestamp.isoformat()
        }


class SentimentAnalyzer:
    """Advanced sentiment analysis with emotional intelligence"""
    
    def __init__(self):
        self.emotion_patterns = self._load_emotion_patterns()
        self.sentiment_lexicon = self._load_sentiment_lexicon()
        self.context_weights = self._load_context_weights()
        self.emotional_memory = {}
        self.conversation_contexts = {}
        
    def _load_emotion_patterns(self) -> Dict[str, List[str]]:
        """Load emotion detection patterns"""
        return {
            EmotionType.JOY: [
                r'\b(?:happy|joy|excited|thrilled|delighted|ecstatic|elated|cheerful|glad|pleased)\b',
                r'\b(?:amazing|wonderful|fantastic|great|awesome|brilliant|excellent|perfect)\b',
                r'\b(?:love|adore|enjoy|like|appreciate|cherish|treasure)\b',
                r'[!]{1,3}',  # Multiple exclamation marks
                r'\b(?:yay|woohoo|hooray|yes|yeah|yep|sure|absolutely|definitely)\b'
            ],
            EmotionType.SADNESS: [
                r'\b(?:sad|depressed|down|blue|melancholy|gloomy|miserable|unhappy|sorrowful)\b',
                r'\b(?:cry|crying|tears|weep|weeping|sob|sobbing)\b',
                r'\b(?:disappointed|let down|heartbroken|devastated|crushed|defeated)\b',
                r'\b(?:lonely|alone|isolated|abandoned|rejected|hurt|pain|ache)\b',
                r'[.]{2,}',  # Multiple periods (ellipsis)
                r'\b(?:no|never|nothing|nowhere|hopeless|helpless|worthless)\b'
            ],
            EmotionType.ANGER: [
                r'\b(?:angry|mad|furious|rage|raging|irritated|annoyed|frustrated|upset)\b',
                r'\b(?:hate|despise|loathe|detest|abhor|disgusted|repulsed)\b',
                r'\b(?:outraged|infuriated|enraged|livid|fuming|seething|boiling)\b',
                r'[!]{2,}',  # Multiple exclamation marks
                r'\b(?:damn|hell|shit|fuck|bitch|asshole|idiot|stupid|dumb)\b',
                r'[A-Z]{3,}',  # ALL CAPS words
                r'\b(?:kill|destroy|smash|break|ruin|waste|trash)\b'
            ],
            EmotionType.FEAR: [
                r'\b(?:scared|afraid|frightened|terrified|petrified|panic|panicking)\b',
                r'\b(?:worried|anxious|nervous|uneasy|concerned|apprehensive|dread)\b',
                r'\b(?:threat|danger|dangerous|risky|hazardous|perilous|unsafe)\b',
                r'\b(?:help|save|protect|rescue|escape|run|hide|avoid)\b',
                r'\b(?:what if|what happens if|suppose|imagine if|in case)\b'
            ],
            EmotionType.SURPRISE: [
                r'\b(?:surprised|shocked|amazed|astonished|stunned|bewildered|confused)\b',
                r'\b(?:wow|whoa|oh|ah|huh|what|really|seriously|no way)\b',
                r'\b(?:unexpected|unbelievable|incredible|remarkable|extraordinary)\b',
                r'[?]{1,3}',  # Multiple question marks
                r'\b(?:wait|hold on|stop|pause|freeze)\b'
            ],
            EmotionType.DISGUST: [
                r'\b(?:disgusted|revolted|repulsed|sickened|nauseated|gross|grossed out)\b',
                r'\b(?:yuck|ew|ugh|bleh|yech|ick|eww|gross|nasty|filthy)\b',
                r'\b(?:vile|repulsive|revolting|disgusting|sickening|nauseating)\b',
                r'\b(?:hate|loathe|despise|detest|abhor|can\'t stand)\b'
            ],
            EmotionType.TRUST: [
                r'\b(?:trust|trusted|trusting|confident|sure|certain|positive)\b',
                r'\b(?:believe|faith|hope|optimistic|reassured|comfortable)\b',
                r'\b(?:reliable|dependable|trustworthy|honest|sincere|genuine)\b',
                r'\b(?:yes|agree|exactly|precisely|absolutely|definitely)\b'
            ],
            EmotionType.ANTICIPATION: [
                r'\b(?:excited|eager|looking forward|can\'t wait|anxious|impatient)\b',
                r'\b(?:hope|hoping|wish|wishing|expect|expecting|anticipate)\b',
                r'\b(?:soon|eventually|finally|at last|about time|coming up)\b',
                r'\b(?:ready|prepared|set|go|let\'s go|bring it on)\b'
            ]
        }
    
    def _load_sentiment_lexicon(self) -> Dict[str, float]:
        """Load sentiment lexicon with polarity scores"""
        return {
            # Very positive words
            "excellent": 1.0, "outstanding": 1.0, "amazing": 1.0, "fantastic": 1.0,
            "wonderful": 1.0, "brilliant": 1.0, "perfect": 1.0, "incredible": 1.0,
            "magnificent": 1.0, "superb": 1.0, "exceptional": 1.0, "marvelous": 1.0,
            
            # Positive words
            "good": 0.7, "great": 0.8, "nice": 0.6, "fine": 0.5, "well": 0.6,
            "better": 0.7, "best": 0.9, "love": 0.9, "like": 0.6, "enjoy": 0.7,
            "happy": 0.8, "pleased": 0.7, "satisfied": 0.6, "content": 0.6,
            
            # Neutral words
            "okay": 0.0, "ok": 0.0, "alright": 0.0, "fine": 0.0, "sure": 0.0,
            "maybe": 0.0, "perhaps": 0.0, "possibly": 0.0, "might": 0.0,
            
            # Negative words
            "bad": -0.7, "terrible": -1.0, "awful": -0.9, "horrible": -0.9,
            "hate": -0.9, "dislike": -0.6, "angry": -0.8, "mad": -0.7,
            "sad": -0.7, "upset": -0.6, "disappointed": -0.6, "frustrated": -0.7,
            
            # Very negative words
            "worst": -1.0, "disgusting": -1.0, "repulsive": -1.0, "hateful": -1.0,
            "despicable": -1.0, "abhorrent": -1.0, "detestable": -1.0, "loathsome": -1.0
        }
    
    def _load_context_weights(self) -> Dict[str, float]:
        """Load context weights for emotional analysis"""
        return {
            "exclamation_marks": 0.3,
            "question_marks": 0.2,
            "all_caps": 0.4,
            "repeated_letters": 0.2,
            "ellipsis": -0.2,
            "question_words": 0.1,
            "negation": -0.3,
            "intensifiers": 0.4
        }
    
    async def analyze_sentiment(self, text: str, context: Optional[Dict[str, Any]] = None) -> EmotionalContext:
        """Analyze sentiment and emotion from text"""
        try:
            if not text or not text.strip():
                return EmotionalContext()
            
            # Clean and preprocess text
            cleaned_text = self._preprocess_text(text)
            
            # Analyze emotion patterns
            emotion_scores = self._analyze_emotion_patterns(cleaned_text)
            
            # Analyze sentiment polarity
            sentiment_score = self._analyze_sentiment_polarity(cleaned_text)
            
            # Analyze context factors
            context_factors = self._analyze_context_factors(cleaned_text)
            
            # Determine primary emotion
            primary_emotion = max(emotion_scores.items(), key=lambda x: x[1])[0]
            emotion_confidence = emotion_scores[primary_emotion]
            
            # Determine sentiment polarity
            if sentiment_score >= 0.6:
                polarity = SentimentPolarity.VERY_POSITIVE
            elif sentiment_score >= 0.2:
                polarity = SentimentPolarity.POSITIVE
            elif sentiment_score <= -0.6:
                polarity = SentimentPolarity.VERY_NEGATIVE
            elif sentiment_score <= -0.2:
                polarity = SentimentPolarity.NEGATIVE
            else:
                polarity = SentimentPolarity.NEUTRAL
            
            # Determine emotional intensity
            intensity = self._determine_intensity(emotion_confidence, sentiment_score, context_factors)
            
            # Create emotional context
            emotional_context = EmotionalContext()
            emotional_context.current_emotion = primary_emotion
            emotional_context.sentiment_polarity = polarity
            emotional_context.intensity = intensity
            emotional_context.confidence = emotion_confidence
            emotional_context.context_factors = context_factors
            emotional_context.emotional_triggers = self._extract_emotional_triggers(cleaned_text)
            
            # Store in memory
            if context and "user_id" in context:
                emotional_context.user_id = context["user_id"]
                self.emotional_memory[context["user_id"]] = emotional_context
            
            return emotional_context
            
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {e}")
            return EmotionalContext()
    
    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for analysis"""
        # Convert to lowercase
        text = text.lower()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Preserve punctuation for context analysis
        return text.strip()
    
    def _analyze_emotion_patterns(self, text: str) -> Dict[EmotionType, float]:
        """Analyze emotion patterns in text"""
        emotion_scores = {emotion: 0.0 for emotion in EmotionType}
        
        for emotion, patterns in self.emotion_patterns.items():
            score = 0.0
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                score += len(matches) * 0.1  # Base score per match
                
                # Boost score for multiple matches
                if len(matches) > 1:
                    score += (len(matches) - 1) * 0.05
            
            # Normalize score
            emotion_scores[emotion] = min(score, 1.0)
        
        return emotion_scores
    
    def _analyze_sentiment_polarity(self, text: str) -> float:
        """Analyze sentiment polarity using lexicon"""
        words = text.split()
        total_score = 0.0
        word_count = 0
        
        for word in words:
            # Clean word (remove punctuation)
            clean_word = re.sub(r'[^\w]', '', word)
            if clean_word in self.sentiment_lexicon:
                total_score += self.sentiment_lexicon[clean_word]
                word_count += 1
        
        if word_count == 0:
            return 0.0
        
        return total_score / word_count
    
    def _analyze_context_factors(self, text: str) -> Dict[str, Any]:
        """Analyze context factors that affect emotion"""
        factors = {}
        
        # Exclamation marks
        exclamation_count = len(re.findall(r'!+', text))
        factors["exclamation_marks"] = exclamation_count
        
        # Question marks
        question_count = len(re.findall(r'\?+', text))
        factors["question_marks"] = question_count
        
        # All caps words
        caps_words = re.findall(r'\b[A-Z]{2,}\b', text)
        factors["all_caps"] = len(caps_words)
        
        # Repeated letters
        repeated_letters = re.findall(r'(\w)\1{2,}', text)
        factors["repeated_letters"] = len(repeated_letters)
        
        # Ellipsis
        ellipsis_count = len(re.findall(r'\.{3,}', text))
        factors["ellipsis"] = ellipsis_count
        
        # Question words
        question_words = len(re.findall(r'\b(what|where|when|why|how|who|which)\b', text))
        factors["question_words"] = question_words
        
        # Negation
        negation_count = len(re.findall(r'\b(no|not|never|nothing|nowhere|none|nobody)\b', text))
        factors["negation"] = negation_count
        
        # Intensifiers
        intensifiers = len(re.findall(r'\b(very|really|so|too|extremely|incredibly|absolutely|totally)\b', text))
        factors["intensifiers"] = intensifiers
        
        return factors
    
    def _determine_intensity(self, emotion_confidence: float, sentiment_score: float, context_factors: Dict[str, Any]) -> EmotionalIntensity:
        """Determine emotional intensity based on various factors"""
        intensity_score = emotion_confidence
        
        # Adjust based on sentiment score
        intensity_score += abs(sentiment_score) * 0.3
        
        # Adjust based on context factors
        if context_factors.get("exclamation_marks", 0) > 0:
            intensity_score += 0.2
        if context_factors.get("all_caps", 0) > 0:
            intensity_score += 0.3
        if context_factors.get("repeated_letters", 0) > 0:
            intensity_score += 0.1
        if context_factors.get("intensifiers", 0) > 0:
            intensity_score += 0.2
        
        # Determine intensity level
        if intensity_score >= 0.8:
            return EmotionalIntensity.VERY_HIGH
        elif intensity_score >= 0.6:
            return EmotionalIntensity.HIGH
        elif intensity_score >= 0.4:
            return EmotionalIntensity.MODERATE
        elif intensity_score >= 0.2:
            return EmotionalIntensity.LOW
        else:
            return EmotionalIntensity.VERY_LOW
    
    def _extract_emotional_triggers(self, text: str) -> List[str]:
        """Extract emotional triggers from text"""
        triggers = []
        
        # Look for emotional keywords
        for emotion, patterns in self.emotion_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                triggers.extend(matches)
        
        # Look for sentiment words
        words = text.split()
        for word in words:
            clean_word = re.sub(r'[^\w]', '', word)
            if clean_word in self.sentiment_lexicon:
                triggers.append(clean_word)
        
        return list(set(triggers))  # Remove duplicates
    
    async def generate_emotional_response(self, emotional_context: EmotionalContext, user_message: str) -> str:
        """Generate emotionally appropriate response"""
        try:
            # Get base response from LLM
            llm_router = get_llm_router()
            base_response = await llm_router.generate_response(
                user_message,
                system_prompt=self._get_emotional_system_prompt(emotional_context)
            )
            
            # Adjust response based on emotion
            adjusted_response = self._adjust_response_for_emotion(base_response, emotional_context)
            
            return adjusted_response
            
        except Exception as e:
            logger.error(f"Error generating emotional response: {e}")
            return "I understand your message, but I'm having trouble processing it right now."
    
    def _get_emotional_system_prompt(self, emotional_context: EmotionalContext) -> str:
        """Get system prompt adjusted for emotional context"""
        base_prompt = """You are JARVIS, an advanced AI assistant with emotional intelligence. 
        Respond naturally and empathetically to the user's message."""
        
        emotion = emotional_context.current_emotion
        intensity = emotional_context.intensity
        polarity = emotional_context.sentiment_polarity
        
        # Adjust tone based on emotion
        if emotion == EmotionType.JOY:
            tone = "enthusiastic and celebratory"
        elif emotion == EmotionType.SADNESS:
            tone = "empathetic and supportive"
        elif emotion == EmotionType.ANGER:
            tone = "calm and understanding"
        elif emotion == EmotionType.FEAR:
            tone = "reassuring and comforting"
        elif emotion == EmotionType.SURPRISE:
            tone = "curious and engaged"
        elif emotion == EmotionType.DISGUST:
            tone = "neutral and professional"
        elif emotion == EmotionType.TRUST:
            tone = "confident and reliable"
        elif emotion == EmotionType.ANTICIPATION:
            tone = "excited and encouraging"
        else:
            tone = "professional and helpful"
        
        # Adjust intensity
        if intensity == EmotionalIntensity.VERY_HIGH:
            intensity_modifier = "very"
        elif intensity == EmotionalIntensity.HIGH:
            intensity_modifier = "quite"
        elif intensity == EmotionalIntensity.LOW:
            intensity_modifier = "slightly"
        else:
            intensity_modifier = ""
        
        return f"{base_prompt} The user seems to be feeling {emotion.value} with {intensity_modifier} {intensity.value} intensity. Respond in a {tone} manner."
    
    def _adjust_response_for_emotion(self, response: str, emotional_context: EmotionalContext) -> str:
        """Adjust response based on emotional context"""
        emotion = emotional_context.current_emotion
        intensity = emotional_context.intensity
        
        # Add emotional markers based on context
        if emotion == EmotionType.JOY and intensity in [EmotionalIntensity.HIGH, EmotionalIntensity.VERY_HIGH]:
            if not response.endswith('!'):
                response += "!"
        elif emotion == EmotionType.SADNESS and intensity in [EmotionalIntensity.HIGH, EmotionalIntensity.VERY_HIGH]:
            # Add empathetic phrases
            empathetic_phrases = ["I understand how you feel.", "I'm here for you.", "That sounds difficult."]
            if not any(phrase in response for phrase in empathetic_phrases):
                response = f"I understand how you feel. {response}"
        elif emotion == EmotionType.ANGER and intensity in [EmotionalIntensity.HIGH, EmotionalIntensity.VERY_HIGH]:
            # Add calming phrases
            calming_phrases = ["I understand your frustration.", "Let's work through this together.", "I'm here to help."]
            if not any(phrase in response for phrase in calming_phrases):
                response = f"I understand your frustration. {response}"
        
        return response
    
    def get_emotional_summary(self, user_id: str) -> Dict[str, Any]:
        """Get emotional summary for a user"""
        if user_id not in self.emotional_memory:
            return {}
        
        context = self.emotional_memory[user_id]
        return context.to_dict()


# Global instances
_sentiment_analyzer = None

def get_sentiment_analyzer() -> SentimentAnalyzer:
    """Get global sentiment analyzer instance"""
    global _sentiment_analyzer
    if _sentiment_analyzer is None:
        _sentiment_analyzer = SentimentAnalyzer()
    return _sentiment_analyzer

async def analyze_user_sentiment(text: str, user_id: str = None) -> EmotionalContext:
    """Analyze sentiment of user text"""
    analyzer = get_sentiment_analyzer()
    context = {"user_id": user_id} if user_id else None
    return await analyzer.analyze_sentiment(text, context)

async def generate_emotional_response(user_message: str, user_id: str = None) -> str:
    """Generate emotionally appropriate response"""
    analyzer = get_sentiment_analyzer()
    emotional_context = await analyze_user_sentiment(user_message, user_id)
    return await analyzer.generate_emotional_response(emotional_context, user_message)

def get_emotional_summary(user_id: str) -> Dict[str, Any]:
    """Get emotional summary for a user"""
    analyzer = get_sentiment_analyzer()
    return analyzer.get_emotional_summary(user_id)
