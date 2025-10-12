"""
Sentiment Analyzer - Simple rule-based sentiment detection
Lightweight, no extra models needed
"""

import logging
import re

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    """Lightweight sentiment analysis without external models"""
    
    def __init__(self):
        # Emotion keywords
        self.emotion_patterns = {
            'happy': ['happy', 'great', 'awesome', 'wonderful', 'excited', 'love', 'joy', 'amazing'],
            'sad': ['sad', 'unhappy', 'depressed', 'down', 'miserable', 'awful', 'terrible'],
            'angry': ['angry', 'mad', 'furious', 'annoyed', 'frustrated', 'irritated'],
            'anxious': ['worried', 'anxious', 'nervous', 'stressed', 'scared', 'afraid'],
            'curious': ['curious', 'wondering', 'interested', 'want to know', 'tell me', 'explain'],
            'confused': ['confused', 'don\'t understand', 'unclear', 'lost', 'puzzled'],
            'grateful': ['thank', 'thanks', 'appreciate', 'grateful'],
        }
        
        # Sentiment response tones
        self.response_tones = {
            'happy': 'Match their enthusiasm! Be cheerful and supportive.',
            'sad': 'Be empathetic and comforting. Offer support.',
            'angry': 'Be calm and patient. Show understanding.',
            'anxious': 'Be reassuring and calm. Help them feel safe.',
            'curious': 'Be informative and encouraging. Feed their curiosity.',
            'confused': 'Be clear and patient. Break things down simply.',
            'grateful': 'Be humble and warm. You\'re happy to help.',
            'neutral': 'Be friendly and helpful.'
        }
    
    def detect_emotion(self, text: str) -> str:
        """
        Detect primary emotion from text
        
        Args:
            text: Input text to analyze
        
        Returns:
            Detected emotion ('happy', 'sad', etc.)
        """
        text_lower = text.lower()
        
        # Count matches for each emotion
        emotion_scores = {}
        for emotion, keywords in self.emotion_patterns.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                emotion_scores[emotion] = score
        
        # Return emotion with highest score
        if emotion_scores:
            detected_emotion = max(emotion_scores, key=emotion_scores.get)
            logger.info(f"Detected emotion: {detected_emotion} from: {text[:50]}")
            return detected_emotion
        
        return 'neutral'
    
    def get_tone_guidance(self, emotion: str) -> str:
        """Get response tone guidance based on detected emotion"""
        return self.response_tones.get(emotion, self.response_tones['neutral'])
    
    def analyze(self, text: str) -> dict:
        """
        Full sentiment analysis
        
        Returns:
            {
                'emotion': str,
                'tone_guidance': str,
                'sentiment_score': float (-1 to 1)
            }
        """
        emotion = self.detect_emotion(text)
        tone = self.get_tone_guidance(emotion)
        
        # Simple sentiment score
        positive_words = ['good', 'great', 'love', 'happy', 'yes', 'thanks']
        negative_words = ['bad', 'hate', 'sad', 'no', 'angry', 'terrible']
        
        text_lower = text.lower()
        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)
        
        # Normalized sentiment score
        total = pos_count + neg_count
        if total > 0:
            sentiment_score = (pos_count - neg_count) / total
        else:
            sentiment_score = 0.0
        
        return {
            'emotion': emotion,
            'tone_guidance': tone,
            'sentiment_score': sentiment_score
        }

# Singleton
sentiment_analyzer = SentimentAnalyzer()

