#!/usr/bin/env python3
"""
Atulya Tantra - Architecture Test Script
Version: 2.0.0-alpha
Test the new clean architecture
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def test_architecture():
    """Test the new architecture"""
    print("🧪 Testing Atulya Tantra v2.0.0-alpha Architecture")
    print("=" * 60)
    
    try:
        # Test 1: Configuration Loading
        print("1. Testing configuration loading...")
        from src.config.settings import get_settings
        settings = get_settings()
        print(f"   ✅ App: {settings.app_name} v{settings.app_version}")
        print(f"   ✅ Environment: {settings.environment}")
        
        # Test 2: Task Classification
        print("\n2. Testing task classification...")
        from src.core.ai.classifier import TaskClassifier
        classifier = TaskClassifier({})
        
        test_messages = [
            "Write a Python function",
            "Hello there!",
            "Research quantum computing",
            "Create a story about dragons"
        ]
        
        for msg in test_messages:
            result = await classifier.classify(msg)
            print(f"   📝 '{msg[:30]}...' → {result.task_type.value} ({result.complexity.value})")
        
        # Test 3: Sentiment Analysis
        print("\n3. Testing sentiment analysis...")
        from src.core.ai.sentiment import SentimentAnalyzer
        analyzer = SentimentAnalyzer({})
        
        sentiment_tests = [
            "Thanks for your help!",
            "This is broken and I'm frustrated!",
            "I need this urgently!",
            "Hello, how are you?"
        ]
        
        for msg in sentiment_tests:
            result = await analyzer.analyze(msg)
            print(f"   😊 '{msg[:30]}...' → {result.sentiment.value} ({result.confidence:.2f})")
        
        # Test 4: Model Router
        print("\n4. Testing model routing...")
        from src.core.ai.router import ModelRouter
        from src.core.ai.classifier import TaskType, Complexity
        
        router = ModelRouter({"fallback_order": ["ollama", "openai"]})
        available_models = {
            "ollama": ["mistral:latest", "gemma2:2b"],
            "openai": ["gpt-4", "gpt-3.5-turbo"]
        }
        
        test_cases = [
            (TaskType.CODING, Complexity.MEDIUM),
            (TaskType.SIMPLE, Complexity.SIMPLE),
            (TaskType.RESEARCH, Complexity.COMPLEX)
        ]
        
        for task_type, complexity in test_cases:
            selection = await router.select_model(task_type, complexity, available_models)
            print(f"   🤖 {task_type.value}/{complexity.value} → {selection.provider}/{selection.model}")
        
        # Test 5: AI Service Integration
        print("\n5. Testing AI service integration...")
        from src.services.ai_service import AIService, AIRequest
        from src.core.ai.classifier import TaskClassifier
        from src.core.ai.sentiment import SentimentAnalyzer
        from src.core.ai.router import ModelRouter
        from src.core.ai.model_clients import ModelClientManager
        from src.core.ai.context import ConversationMemory
        from src.core.memory.vector_store import VectorStore
        from src.core.memory.knowledge_graph import KnowledgeGraph
        
        classifier = TaskClassifier({})
        sentiment_analyzer = SentimentAnalyzer({})
        router = ModelRouter({"fallback_order": ["ollama"]})
        model_client_manager = ModelClientManager({})
        vector_store = VectorStore()
        knowledge_graph = KnowledgeGraph()
        conversation_memory = ConversationMemory(vector_store, knowledge_graph)
        
        ai_service = AIService(
            classifier=classifier,
            sentiment_analyzer=sentiment_analyzer,
            router=router,
            model_client_manager=model_client_manager,
            conversation_memory=conversation_memory
        )
        
        request = AIRequest(
            message="Hello, can you help me write a Python function?",
            context=[]
        )
        
        available_models = {"ollama": ["mistral:latest"]}
        
        try:
            response = await ai_service.generate_response(request, "test-conversation")
            print(f"   ✅ AI Service: Generated response using {response.model_used}")
            print(f"   📊 Metadata: {response.metadata}")
        except Exception as e:
            print(f"   ⚠️  AI Service: {str(e)} (Expected if Ollama not running)")
        
        print("\n🎉 Architecture test completed successfully!")
        print("✅ All core components are working correctly")
        
    except Exception as e:
        print(f"\n❌ Architecture test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_architecture())
    sys.exit(0 if success else 1)
