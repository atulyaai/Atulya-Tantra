"""
Atulya Tantra - API Dependencies
Version: 2.5.0
FastAPI dependency injection for services
"""

from functools import lru_cache
from src.services.chat_service import ChatService
from src.services.ai_service import AIService
from src.core.ai.classifier import TaskClassifier
from src.core.ai.sentiment import SentimentAnalyzer
from src.core.ai.router import ModelRouter
from src.core.ai.model_clients import ModelClientManager
from src.core.ai.context import ConversationMemory
from src.core.memory.vector_store import VectorStore
from src.core.memory.knowledge_graph import KnowledgeGraph
from src.config.settings import get_settings


@lru_cache()
def get_settings_service():
    """Get settings service"""
    return get_settings()


@lru_cache()
def get_vector_store() -> VectorStore:
    """Get vector store instance"""
    settings = get_settings()
    return VectorStore()


@lru_cache()
def get_knowledge_graph() -> KnowledgeGraph:
    """Get knowledge graph instance"""
    return KnowledgeGraph()


@lru_cache()
def get_conversation_memory() -> ConversationMemory:
    """Get conversation memory instance"""
    vector_store = get_vector_store()
    knowledge_graph = get_knowledge_graph()
    return ConversationMemory(vector_store, knowledge_graph)


@lru_cache()
def get_model_client_manager() -> ModelClientManager:
    """Get model client manager instance"""
    settings = get_settings()
    return ModelClientManager(settings.ai)


@lru_cache()
def get_task_classifier() -> TaskClassifier:
    """Get task classifier instance"""
    settings = get_settings()
    return TaskClassifier(settings.ai)


@lru_cache()
def get_sentiment_analyzer() -> SentimentAnalyzer:
    """Get sentiment analyzer instance"""
    settings = get_settings()
    return SentimentAnalyzer(settings.ai.get("sentiment", {}))


@lru_cache()
def get_model_router() -> ModelRouter:
    """Get model router instance"""
    settings = get_settings()
    return ModelRouter(settings.ai.get("routing", {}))


@lru_cache()
def get_ai_service() -> AIService:
    """Get AI service instance"""
    classifier = get_task_classifier()
    sentiment_analyzer = get_sentiment_analyzer()
    router = get_model_router()
    model_client_manager = get_model_client_manager()
    conversation_memory = get_conversation_memory()
    
    return AIService(
        classifier=classifier,
        sentiment_analyzer=sentiment_analyzer,
        router=router,
        model_client_manager=model_client_manager,
        conversation_memory=conversation_memory
    )


@lru_cache()
def get_chat_service() -> ChatService:
    """Get chat service instance"""
    ai_service = get_ai_service()
    conversation_memory = get_conversation_memory()
    return ChatService(ai_service, conversation_memory)


def get_current_user():
    """Get current user (placeholder for authentication)"""
    # This will be implemented when authentication is added
    return {"id": "default_user", "name": "Default User"}
