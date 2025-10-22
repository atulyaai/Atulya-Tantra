"""
Comprehensive Test Suite for JARVIS-Skynet AGI System
Tests all components including sentiment analysis, voice interface, AGI core, and integration
"""

import asyncio
import pytest
import json
import time
from datetime import datetime
from typing import Dict, List, Any

# Import all components
from Core.jarvis.sentiment_analyzer import (
    get_sentiment_analyzer, analyze_user_sentiment, 
    EmotionType, SentimentPolarity, EmotionalIntensity
)
from Core.jarvis.enhanced_voice_interface import (
    get_enhanced_voice_interface, VoiceState, ConversationMode
)
from Core.agi_core import (
    get_agi_core, process_agi_request, 
    ReasoningType, DecisionPriority, GoalStatus
)
from Core.skynet import get_task_scheduler, get_system_monitor, get_auto_healer
from Core.agents import get_orchestrator


class TestSentimentAnalysis:
    """Test sentiment analysis and emotional intelligence"""
    
    @pytest.mark.asyncio
    async def test_emotion_detection(self):
        """Test emotion detection from text"""
        analyzer = get_sentiment_analyzer()
        
        # Test joy detection
        joy_text = "I'm so happy and excited about this amazing opportunity!"
        context = await analyze_user_sentiment(joy_text, "test_user")
        assert context.current_emotion == EmotionType.JOY
        assert context.sentiment_polarity == SentimentPolarity.POSITIVE
        assert context.intensity in [EmotionalIntensity.HIGH, EmotionalIntensity.VERY_HIGH]
        
        # Test sadness detection
        sad_text = "I'm feeling really down and disappointed about what happened."
        context = await analyze_user_sentiment(sad_text, "test_user")
        assert context.current_emotion == EmotionType.SADNESS
        assert context.sentiment_polarity == SentimentPolarity.NEGATIVE
        
        # Test anger detection
        angry_text = "I'm absolutely furious about this situation! This is terrible!"
        context = await analyze_user_sentiment(angry_text, "test_user")
        assert context.current_emotion == EmotionType.ANGER
        assert context.sentiment_polarity == SentimentPolarity.VERY_NEGATIVE
    
    @pytest.mark.asyncio
    async def test_emotional_response_generation(self):
        """Test emotional response generation"""
        analyzer = get_sentiment_analyzer()
        
        # Test empathetic response for sadness
        sad_message = "I'm feeling really sad today."
        response = await analyzer.generate_emotional_response(
            await analyze_user_sentiment(sad_message, "test_user"),
            sad_message
        )
        assert "understand" in response.lower() or "feel" in response.lower()
        
        # Test enthusiastic response for joy
        joy_message = "I'm so excited about this project!"
        response = await analyzer.generate_emotional_response(
            await analyze_user_sentiment(joy_message, "test_user"),
            joy_message
        )
        assert len(response) > 0
    
    def test_emotion_patterns(self):
        """Test emotion pattern matching"""
        analyzer = get_sentiment_analyzer()
        
        # Test joy patterns
        joy_patterns = analyzer.emotion_patterns[EmotionType.JOY]
        assert len(joy_patterns) > 0
        
        # Test sentiment lexicon
        assert "happy" in analyzer.sentiment_lexicon
        assert analyzer.sentiment_lexicon["happy"] > 0
        assert "sad" in analyzer.sentiment_lexicon
        assert analyzer.sentiment_lexicon["sad"] < 0


class TestVoiceInterface:
    """Test enhanced voice interface"""
    
    def test_voice_interface_initialization(self):
        """Test voice interface initialization"""
        interface = get_enhanced_voice_interface()
        assert interface is not None
        assert interface.state == VoiceState.IDLE
        assert interface.conversation_mode == ConversationMode.WAKE_WORD
    
    def test_voice_settings(self):
        """Test voice settings configuration"""
        interface = get_enhanced_voice_interface()
        
        # Test setting voice parameters
        new_settings = {
            "rate": 250,
            "volume": 0.9,
            "pitch": 0.7
        }
        interface.set_voice_settings(new_settings)
        
        assert interface.voice_settings["rate"] == 250
        assert interface.voice_settings["volume"] == 0.9
        assert interface.voice_settings["pitch"] == 0.7
    
    def test_speech_settings(self):
        """Test speech recognition settings"""
        interface = get_enhanced_voice_interface()
        
        new_speech_settings = {
            "language": "en-GB",
            "timeout": 10,
            "wake_word": "assistant"
        }
        interface.set_speech_settings(new_speech_settings)
        
        assert interface.speech_settings["language"] == "en-GB"
        assert interface.speech_settings["timeout"] == 10
        assert interface.speech_settings["wake_word"] == "assistant"
    
    def test_text_cleaning(self):
        """Test text cleaning for speech synthesis"""
        interface = get_enhanced_voice_interface()
        
        # Test markdown removal
        text_with_markdown = "This is **bold** and *italic* text with `code`."
        cleaned = interface._clean_text_for_speech(text_with_markdown)
        assert "**" not in cleaned
        assert "*" not in cleaned
        assert "`" not in cleaned
        
        # Test URL removal
        text_with_url = "Check out https://example.com for more info."
        cleaned = interface._clean_text_for_speech(text_with_url)
        assert "https://example.com" not in cleaned
    
    def test_conversation_state_management(self):
        """Test conversation state management"""
        interface = get_enhanced_voice_interface()
        
        # Test state changes
        interface._change_state(VoiceState.LISTENING)
        assert interface.state == VoiceState.LISTENING
        
        interface._change_state(VoiceState.PROCESSING)
        assert interface.state == VoiceState.PROCESSING
        
        # Test conversation history
        interface.clear_conversation_history()
        assert len(interface.get_conversation_history()) == 0


class TestAGICore:
    """Test AGI core reasoning and decision making"""
    
    @pytest.mark.asyncio
    async def test_agi_request_processing(self):
        """Test AGI request processing"""
        agi_core = get_agi_core()
        
        # Test simple request
        request = "Help me organize my tasks for today"
        result = await agi_core.process_request(request, "test_user")
        
        assert result["success"] is True
        assert "analysis" in result
        assert "reasoning_chain" in result
        assert "decision" in result
        assert "action_plan" in result
        assert "results" in result
    
    @pytest.mark.asyncio
    async def test_reasoning_context_creation(self):
        """Test reasoning context creation"""
        agi_core = get_agi_core()
        
        context_data = {
            "preferences": {"style": "formal"},
            "constraints": ["time_limited"],
            "resources": ["computer", "internet"]
        }
        
        context = agi_core._create_reasoning_context("test_user", context_data)
        
        assert context.user_id == "test_user"
        assert context.preferences["style"] == "formal"
        assert "time_limited" in context.constraints
        assert "computer" in context.available_resources
    
    @pytest.mark.asyncio
    async def test_request_analysis(self):
        """Test request analysis"""
        agi_core = get_agi_core()
        context = agi_core._create_reasoning_context("test_user")
        
        request = "Create a presentation about AI trends"
        analysis = await agi_core._analyze_request(request, context)
        
        assert "intent" in analysis
        assert "entities" in analysis
        assert "goals" in analysis
        assert "priority" in analysis
        assert "complexity" in analysis
    
    def test_reasoning_type_determination(self):
        """Test reasoning type determination"""
        agi_core = get_agi_core()
        context = agi_core._create_reasoning_context("test_user")
        
        # Test deductive reasoning
        analysis = {"intent": "prove that X is true", "complexity": "medium"}
        reasoning_type = agi_core._determine_reasoning_type(analysis, context)
        assert reasoning_type == ReasoningType.DEDUCTIVE
        
        # Test inductive reasoning
        analysis = {"intent": "predict future trends", "complexity": "high"}
        reasoning_type = agi_core._determine_reasoning_type(analysis, context)
        assert reasoning_type == ReasoningType.INDUCTIVE
        
        # Test causal reasoning
        analysis = {"intent": "find the cause of the problem", "complexity": "medium"}
        reasoning_type = agi_core._determine_reasoning_type(analysis, context)
        assert reasoning_type == ReasoningType.CAUSAL
    
    def test_goal_creation(self):
        """Test AGI goal creation"""
        from Core.agi_core import AGIGoal, DecisionPriority, GoalStatus
        
        goal = AGIGoal("test_goal", "Complete the test", DecisionPriority.HIGH)
        
        assert goal.goal_id == "test_goal"
        assert goal.description == "Complete the test"
        assert goal.priority == DecisionPriority.HIGH
        assert goal.status == GoalStatus.PENDING
        assert goal.progress == 0.0
    
    def test_agi_status(self):
        """Test AGI status reporting"""
        status = get_agi_status()
        
        assert "active_goals" in status
        assert "reasoning_contexts" in status
        assert "decisions_made" in status
        assert "learning_entries" in status
        
        # All should be non-negative integers
        for key, value in status.items():
            assert isinstance(value, int)
            assert value >= 0


class TestSkynetIntegration:
    """Test Skynet integration and autonomous operations"""
    
    @pytest.mark.asyncio
    async def test_system_monitoring(self):
        """Test system monitoring capabilities"""
        monitor = get_system_monitor()
        
        # Test system health check
        health = await monitor.get_system_health()
        assert "status" in health
        assert "timestamp" in health
        
        # Test system metrics
        metrics = await monitor.get_system_metrics()
        assert isinstance(metrics, list)
    
    @pytest.mark.asyncio
    async def test_task_scheduling(self):
        """Test task scheduling capabilities"""
        scheduler = get_task_scheduler()
        
        # Test task creation
        task_id = await scheduler.schedule_task(
            "test_task",
            "Test task description",
            priority="normal"
        )
        assert task_id is not None
        
        # Test task status
        status = await scheduler.get_task_status(task_id)
        assert "status" in status
    
    @pytest.mark.asyncio
    async def test_auto_healing(self):
        """Test auto-healing capabilities"""
        healer = get_auto_healer()
        
        # Test healing status
        status = await healer.get_healing_status()
        assert "active_sessions" in status
        assert "healing_rules" in status


class TestAgentOrchestration:
    """Test multi-agent orchestration"""
    
    @pytest.mark.asyncio
    async def test_agent_orchestration(self):
        """Test agent orchestration"""
        orchestrator = get_orchestrator()
        
        # Test agent status
        status = await orchestrator.get_system_status()
        assert "agents" in status
        assert "active_tasks" in status
    
    @pytest.mark.asyncio
    async def test_task_submission(self):
        """Test task submission to agents"""
        orchestrator = get_orchestrator()
        
        # Test task submission
        task_id = await orchestrator.submit_task(
            "test_task",
            "Test task description",
            priority="normal"
        )
        assert task_id is not None


class TestIntegration:
    """Test integration between components"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_conversation(self):
        """Test end-to-end conversation flow"""
        # This would test the complete flow from voice input to response
        # For now, we'll test the components individually
        
        # Test sentiment analysis
        analyzer = get_sentiment_analyzer()
        emotional_context = await analyze_user_sentiment("Hello, how are you?", "test_user")
        assert emotional_context is not None
        
        # Test AGI processing
        agi_core = get_agi_core()
        result = await agi_core.process_request("Hello, how are you?", "test_user")
        assert result["success"] is True
        
        # Test voice interface
        voice_interface = get_enhanced_voice_interface()
        assert voice_interface is not None
    
    @pytest.mark.asyncio
    async def test_emotional_agi_integration(self):
        """Test integration between sentiment analysis and AGI core"""
        agi_core = get_agi_core()
        
        # Test with emotional context
        context = {
            "emotional_state": {
                "current_emotion": "joy",
                "intensity": "high",
                "sentiment_polarity": "positive"
            }
        }
        
        result = await agi_core.process_request("I'm excited about this project!", "test_user", context)
        assert result["success"] is True
        assert "analysis" in result
    
    def test_component_initialization(self):
        """Test that all components can be initialized"""
        # Test sentiment analyzer
        analyzer = get_sentiment_analyzer()
        assert analyzer is not None
        
        # Test voice interface
        voice_interface = get_enhanced_voice_interface()
        assert voice_interface is not None
        
        # Test AGI core
        agi_core = get_agi_core()
        assert agi_core is not None
        
        # Test Skynet components
        scheduler = get_task_scheduler()
        assert scheduler is not None
        
        monitor = get_system_monitor()
        assert monitor is not None
        
        healer = get_auto_healer()
        assert healer is not None


class TestPerformance:
    """Test performance and scalability"""
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test handling multiple concurrent requests"""
        agi_core = get_agi_core()
        
        # Create multiple concurrent requests
        requests = [
            "Help me with task 1",
            "Help me with task 2", 
            "Help me with task 3"
        ]
        
        # Execute concurrently
        tasks = [agi_core.process_request(req, f"user_{i}") for i, req in enumerate(requests)]
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        for result in results:
            assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_sentiment_analysis_performance(self):
        """Test sentiment analysis performance"""
        analyzer = get_sentiment_analyzer()
        
        # Test with multiple texts
        texts = [
            "I'm so happy today!",
            "This is terrible and awful.",
            "I'm feeling neutral about this.",
            "I'm excited and thrilled!",
            "I'm sad and disappointed."
        ]
        
        start_time = time.time()
        
        # Process all texts
        tasks = [analyze_user_sentiment(text, f"user_{i}") for i, text in enumerate(texts)]
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should process all texts in reasonable time
        assert processing_time < 5.0  # Less than 5 seconds
        assert len(results) == len(texts)
        
        # All results should be valid
        for result in results:
            assert result is not None
            assert hasattr(result, 'current_emotion')


class TestErrorHandling:
    """Test error handling and recovery"""
    
    @pytest.mark.asyncio
    async def test_invalid_input_handling(self):
        """Test handling of invalid inputs"""
        agi_core = get_agi_core()
        
        # Test with empty request
        result = await agi_core.process_request("", "test_user")
        assert result["success"] is False or "error" in result
        
        # Test with None request
        result = await agi_core.process_request(None, "test_user")
        assert result["success"] is False or "error" in result
    
    @pytest.mark.asyncio
    async def test_sentiment_analysis_error_handling(self):
        """Test sentiment analysis error handling"""
        analyzer = get_sentiment_analyzer()
        
        # Test with empty text
        result = await analyze_user_sentiment("", "test_user")
        assert result is not None
        
        # Test with None text
        result = await analyze_user_sentiment(None, "test_user")
        assert result is not None
    
    def test_voice_interface_error_handling(self):
        """Test voice interface error handling"""
        interface = get_enhanced_voice_interface()
        
        # Test with invalid settings
        try:
            interface.set_voice_settings({"invalid_key": "invalid_value"})
            # Should not raise exception
        except Exception as e:
            pytest.fail(f"Voice interface should handle invalid settings gracefully: {e}")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
