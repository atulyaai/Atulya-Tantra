"""
Atulya Tantra - Basic Architecture Tests
Version: 2.0.0-alpha
Test the new clean architecture implementation
"""

import pytest
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_config_loading():
    """Test that configuration can be loaded"""
    from src.config.settings import get_settings
    
    settings = get_settings()
    assert settings.app_name == "Atulya Tantra"
    assert settings.app_version == "2.5.0"
    assert settings.environment in ["development", "production", "testing"]


def test_task_classifier():
    """Test task classification"""
    from src.core.ai.classifier import TaskClassifier, TaskType, Complexity
    
    classifier = TaskClassifier({})
    
    # Test coding detection
    result = await classifier.classify("Write a Python function to sort a list")
    assert result.task_type == TaskType.CODING
    assert result.complexity == Complexity.MEDIUM
    assert result.confidence > 0.7


def test_sentiment_analyzer():
    """Test sentiment analysis"""
    from src.core.ai.sentiment import SentimentAnalyzer, Sentiment
    
    analyzer = SentimentAnalyzer({})
    
    # Test frustrated detection
    result = await analyzer.analyze("This doesn't work! I'm frustrated!")
    assert result.sentiment == Sentiment.FRUSTRATED
    assert result.confidence > 0.7
    assert "patient" in result.tone_adjustment.lower()


def test_model_router():
    """Test model routing"""
    from src.core.ai.router import ModelRouter
    from src.core.ai.classifier import TaskType, Complexity
    
    router = ModelRouter({"fallback_order": ["ollama", "openai"]})
    
    available_models = {
        "ollama": ["mistral:latest", "gemma2:2b"],
        "openai": ["gpt-4", "gpt-3.5-turbo"]
    }
    
    # Test coding task routing
    selection = await router.select_model(
        TaskType.CODING, 
        Complexity.MEDIUM, 
        available_models
    )
    assert selection.provider in ["ollama", "openai"]
    assert "coding" in selection.reasoning.lower()


def test_ai_service_integration():
    """Test AI service integration"""
    from src.services.ai_service import AIService, AIRequest
    from src.core.ai.classifier import TaskClassifier
    from src.core.ai.sentiment import SentimentAnalyzer
    from src.core.ai.router import ModelRouter
    
    # Create components
    classifier = TaskClassifier({})
    sentiment_analyzer = SentimentAnalyzer({})
    router = ModelRouter({"fallback_order": ["ollama"]})
    
    # Create AI service
    ai_service = AIService(classifier, sentiment_analyzer, router)
    
    # Test request
    request = AIRequest(
        message="Hello, how are you?",
        context=[]
    )
    
    available_models = {"ollama": ["mistral:latest"]}
    
    # This will fail without actual Ollama running, but tests the integration
    try:
        response = await ai_service.generate_response(request, available_models)
        assert response.content is not None
        assert response.model_used is not None
        assert "task_type" in response.metadata
    except Exception as e:
        # Expected if Ollama not running
        assert "ollama" in str(e).lower() or "model" in str(e).lower()


def test_fastapi_app_creation():
    """Test FastAPI app creation"""
    from main import create_app
    
    app = create_app()
    assert app.title == "Atulya Tantra"
    assert app.version == "2.5.0"
    
    # Check that routes are registered
    route_paths = [route.path for route in app.routes]
    assert "/api/chat/" in route_paths
    assert "/health" in route_paths


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
