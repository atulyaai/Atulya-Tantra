"""
Unit tests for JARVIS agent modules
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from typing import Dict, Any

# Import the conversational AI agents
from src.core.agents.conversational_personality import PersonalityEngine, PersonalityTrait, EmotionalState
from src.core.agents.conversational_memory import ConversationalMemory, PersonalDetail, RelationshipContext
from src.core.agents.conversational_nlu import NaturalLanguageUnderstanding, IntentType, ContextType
from src.core.agents.conversational_assistant import TaskAssistant, TaskComplexity, TaskStatus
from src.core.agents.conversational_knowledge import KnowledgeManager, KnowledgeItem
from src.core.agents.conversational_voice import ConversationalVoiceInterface, VoiceCommand, VoiceStatus


class TestPersonalityEngine:
    """Test JARVIS Personality Engine"""
    
    @pytest.fixture
    def personality_engine(self):
        config = {"voice_enabled": False}
        return PersonalityEngine(config)
    
    @pytest.mark.asyncio
    async def test_personality_initialization(self, personality_engine):
        """Test personality engine initialization"""
        assert personality_engine.base_personality is not None
        assert PersonalityTrait.PROFESSIONAL in personality_engine.base_personality.traits
        assert personality_engine.base_personality.emotional_state == EmotionalState.NEUTRAL
    
    @pytest.mark.asyncio
    async def test_get_personality_for_context(self, personality_engine):
        """Test getting personality for context"""
        personality = await personality_engine.get_personality_for_context(
            "conv_1", "user_1", "Hello JARVIS", "positive", "simple"
        )
        assert personality is not None
        assert personality.emotional_state == EmotionalState.POSITIVE
    
    @pytest.mark.asyncio
    async def test_adjust_for_sentiment(self, personality_engine):
        """Test personality adjustment for sentiment"""
        base_personality = personality_engine.base_personality
        adjusted = personality_engine._adjust_for_sentiment(base_personality, "frustrated")
        assert adjusted.emotional_state == EmotionalState.SUPPORTIVE
        assert adjusted.traits[PersonalityTrait.PATIENT] > base_personality.traits[PersonalityTrait.PATIENT]
    
    @pytest.mark.asyncio
    async def test_generate_personality_prompt(self, personality_engine):
        """Test personality prompt generation"""
        prompt = await personality_engine.generate_personality_prompt(
            personality_engine.base_personality, "John"
        )
        assert "JARVIS" in prompt
        assert "John" in prompt
        assert isinstance(prompt, str)
    
    @pytest.mark.asyncio
    async def test_update_user_preferences(self, personality_engine):
        """Test updating user preferences"""
        await personality_engine.update_user_preferences(
            "user_1", 
            preferred_name="Alice",
            communication_style="casual"
        )
        assert "user_1" in personality_engine.user_preferences
        assert personality_engine.user_preferences["user_1"].preferred_name == "Alice"


class TestConversationalMemory:
    """Test JARVIS Conversational Memory"""
    
    @pytest.fixture
    def conversational_memory(self):
        config = {}
        return ConversationalMemory(config)
    
    @pytest.mark.asyncio
    async def test_memory_initialization(self, conversational_memory):
        """Test conversational memory initialization"""
        assert conversational_memory.relationship_contexts == {}
        assert conversational_memory.personal_details is not None
        assert conversational_memory.memory_decay_factor == 0.95
    
    @pytest.mark.asyncio
    async def test_update_relationship_context(self, conversational_memory):
        """Test updating relationship context"""
        await conversational_memory.update_relationship_context(
            "user_1", "conv_1", "chat", "positive", ["AI", "technology"]
        )
        assert "user_1" in conversational_memory.relationship_contexts
        context = conversational_memory.relationship_contexts["user_1"]
        assert context.interaction_count == 1
        assert context.trust_level > 0.5
    
    @pytest.mark.asyncio
    async def test_store_personal_detail(self, conversational_memory):
        """Test storing personal details"""
        await conversational_memory.store_personal_detail(
            "user_1", "name", "John Doe", 0.9, "explicit", "conv_1"
        )
        assert "user_1" in conversational_memory.personal_details
        details = conversational_memory.personal_details["user_1"]
        assert len(details) == 1
        assert details[0].key == "name"
        assert details[0].value == "John Doe"
    
    @pytest.mark.asyncio
    async def test_extract_personal_details(self, conversational_memory):
        """Test extracting personal details from message"""
        details = await conversational_memory.extract_personal_details(
            "user_1", "My name is Alice", "conv_1"
        )
        assert len(details) == 1
        assert details[0].key == "name"
        assert details[0].value == "Alice"
    
    @pytest.mark.asyncio
    async def test_get_user_context(self, conversational_memory):
        """Test getting user context"""
        # First add some data
        await conversational_memory.update_relationship_context(
            "user_1", "conv_1", "chat", "positive", ["AI"]
        )
        await conversational_memory.store_personal_detail(
            "user_1", "location", "New York", 0.8, "inferred", "conv_1"
        )
        
        context = await conversational_memory.get_user_context("user_1", "conv_1")
        assert context["user_id"] == "user_1"
        assert context["relationship_stage"] == "new"
        assert "location" in context["personal_details"]


class TestNaturalLanguageUnderstanding:
    """Test JARVIS NLU System"""
    
    @pytest.fixture
    def nlu_system(self):
        config = {}
        return NaturalLanguageUnderstanding(config)
    
    @pytest.mark.asyncio
    async def test_nlu_initialization(self, nlu_system):
        """Test NLU system initialization"""
        assert nlu_system.intent_patterns is not None
        assert IntentType.QUESTION in nlu_system.intent_patterns
        assert nlu_system.context_patterns is not None
    
    @pytest.mark.asyncio
    async def test_recognize_intent(self, nlu_system):
        """Test intent recognition"""
        result = await nlu_system.recognize_intent("What is the weather?", "conv_1")
        assert result.intent == IntentType.QUESTION
        assert result.confidence > 0
        assert "?" in result.context_clues[0] if result.context_clues else True
    
    @pytest.mark.asyncio
    async def test_analyze_context(self, nlu_system):
        """Test context analysis"""
        intent_result = await nlu_system.recognize_intent("I need help with coding", "conv_1")
        context_result = await nlu_system.analyze_context("I need help with coding", "conv_1", intent_result)
        assert context_result.context_type == ContextType.TECHNICAL
        assert "coding" in context_result.topics
    
    @pytest.mark.asyncio
    async def test_detect_ambiguity(self, nlu_system):
        """Test ambiguity detection"""
        intent_result = await nlu_system.recognize_intent("What is it?", "conv_1")
        context_result = await nlu_system.analyze_context("What is it?", "conv_1", intent_result)
        ambiguity_result = await nlu_system.detect_ambiguity("What is it?", "conv_1", intent_result, context_result)
        assert ambiguity_result.is_ambiguous
        assert "pronoun_reference" in ambiguity_result.ambiguity_types


class TestTaskAssistant:
    """Test JARVIS Task Assistant"""
    
    @pytest.fixture
    def task_assistant(self):
        config = {}
        return TaskAssistant(config)
    
    @pytest.mark.asyncio
    async def test_task_assistant_initialization(self, task_assistant):
        """Test task assistant initialization"""
        assert task_assistant.active_tasks == {}
        assert task_assistant.task_templates is not None
        assert "coding" in task_assistant.task_templates
    
    @pytest.mark.asyncio
    async def test_create_task(self, task_assistant):
        """Test creating a task"""
        task = await task_assistant.create_task(
            "user_1", "conv_1", "Write a Python function", "Create a simple Python function", "coding"
        )
        assert task is not None
        assert task.title == "Write a Python function"
        assert task.complexity in [TaskComplexity.SIMPLE, TaskComplexity.MODERATE, TaskComplexity.COMPLEX]
        assert len(task.steps) > 0
    
    @pytest.mark.asyncio
    async def test_get_recommendations(self, task_assistant):
        """Test getting recommendations"""
        recommendations = await task_assistant.get_recommendations("user_1", "coding", ["Python", "functions"])
        assert isinstance(recommendations, list)
        if recommendations:
            assert recommendations[0].type in ["next_action", "best_practice", "efficiency_tip", "resource"]


class TestKnowledgeManager:
    """Test JARVIS Knowledge Manager"""
    
    @pytest.fixture
    def knowledge_manager(self):
        config = {}
        return KnowledgeManager(config)
    
    @pytest.mark.asyncio
    async def test_knowledge_manager_initialization(self, knowledge_manager):
        """Test knowledge manager initialization"""
        assert knowledge_manager.knowledge_items == {}
        assert knowledge_manager.user_knowledge is not None
        assert knowledge_manager.documents == {}
    
    @pytest.mark.asyncio
    async def test_store_knowledge(self, knowledge_manager):
        """Test storing knowledge"""
        item_id = await knowledge_manager.store_knowledge(
            "user_1", "Python Basics", "Python is a programming language", "programming", ["python", "coding"]
        )
        assert item_id is not None
        assert item_id in knowledge_manager.knowledge_items
        assert "user_1" in knowledge_manager.user_knowledge
    
    @pytest.mark.asyncio
    async def test_search_knowledge(self, knowledge_manager):
        """Test searching knowledge"""
        # First store some knowledge
        await knowledge_manager.store_knowledge(
            "user_1", "Python Basics", "Python is a programming language", "programming", ["python"]
        )
        
        results = await knowledge_manager.search_knowledge("user_1", "python")
        assert len(results) > 0
        assert results[0].title == "Python Basics"


class TestJARVISVoiceInterface:
    """Test JARVIS Voice Interface"""
    
    @pytest.fixture
    def voice_interface(self):
        config = {"voice_enabled": True, "wake_word": "hey jarvis"}
        return JARVISVoiceInterface(config)
    
    @pytest.mark.asyncio
    async def test_voice_interface_initialization(self, voice_interface):
        """Test voice interface initialization"""
        assert voice_interface.voice_enabled == True
        assert voice_interface.wake_word == "hey jarvis"
        assert voice_interface.voice_sessions == {}
    
    @pytest.mark.asyncio
    async def test_start_voice_session(self, voice_interface):
        """Test starting voice session"""
        session_id = await voice_interface.start_voice_session("user_1")
        assert session_id is not None
        assert session_id in voice_interface.voice_sessions
        session = voice_interface.voice_sessions[session_id]
        assert session.user_id == "user_1"
        assert session.status == VoiceStatus.IDLE
    
    @pytest.mark.asyncio
    async def test_process_voice_input(self, voice_interface):
        """Test processing voice input"""
        session_id = await voice_interface.start_voice_session("user_1")
        result = await voice_interface.process_voice_input(session_id, b"fake_audio_data")
        assert result is not None
        assert "transcribed_text" in result or "error" in result


@pytest.mark.asyncio
async def test_jarvis_health_checks():
    """Test health checks for all JARVIS components"""
    config = {}
    
    personality_engine = PersonalityEngine(config)
    conversational_memory = ConversationalMemory(config)
    nlu_system = NaturalLanguageUnderstanding(config)
    task_assistant = TaskAssistant(config)
    knowledge_manager = KnowledgeManager(config)
    voice_interface = JARVISVoiceInterface(config)
    
    # Test health checks
    personality_health = await personality_engine.health_check()
    memory_health = await conversational_memory.health_check()
    nlu_health = await nlu_system.health_check()
    
    assert personality_health["personality_engine"] == True
    assert memory_health["conversational_memory"] == True
    assert nlu_health["nlu_system"] == True
