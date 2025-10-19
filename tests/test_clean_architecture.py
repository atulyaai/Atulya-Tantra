#!/usr/bin/env python3
"""
Atulya Tantra - Clean Architecture Test
Version: 2.5.0
Test the clean architecture implementation
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def test_clean_architecture():
    """Test the clean architecture implementation"""
    print("🧪 Testing Atulya Tantra v2.5.0 Clean Architecture")
    print("=" * 60)
    
    try:
        # Test 1: Configuration Loading
        print("1. Testing configuration loading...")
        from src.config.settings import get_settings
        settings = get_settings()
        print(f"   ✅ App: {settings.app_name} v{settings.app_version}")
        print(f"   ✅ Environment: {settings.environment}")
        assert settings.app_name == "Atulya Tantra"
        assert settings.app_version == "2.5.0"
        print("   ✅ Configuration loaded successfully")
        
        # Test 2: Task Classification
        print("\n2. Testing task classification...")
        from src.core.ai.classifier import TaskClassifier, TaskType, Complexity
        classifier = TaskClassifier({})
        
        result = await classifier.classify("Write a Python function to sort a list")
        print(f"   📝 Coding task → {result.task_type.value} ({result.complexity.value})")
        assert result.task_type == TaskType.CODING
        assert result.complexity == Complexity.SIMPLE
        print("   ✅ Task classification works")
        
        # Test 3: Sentiment Analysis
        print("\n3. Testing sentiment analysis...")
        from src.core.ai.sentiment import SentimentAnalyzer, Sentiment
        analyzer = SentimentAnalyzer({})
        
        result = await analyzer.analyze("This is broken and I'm frustrated!")
        print(f"   😊 Frustrated message → {result.sentiment.value}")
        assert result.sentiment == Sentiment.FRUSTRATED
        print("   ✅ Sentiment analysis works")
        
        # Test 4: Model Router
        print("\n4. Testing model routing...")
        from src.core.ai.router import ModelRouter
        router = ModelRouter({"fallback_order": ["ollama", "openai"]})
        
        available_models = {
            "ollama": ["mistral:latest", "gemma2:2b"],
            "openai": ["gpt-4", "gpt-3.5-turbo"]
        }
        
        selection = await router.select_model(TaskType.CODING, Complexity.SIMPLE, available_models)
        print(f"   🤖 Coding task → {selection.provider}/{selection.model}")
        assert selection.provider in ["ollama", "openai"]
        print("   ✅ Model routing works")
        
        # Test 5: FastAPI App Creation
        print("\n5. Testing FastAPI app creation...")
        from main import create_app
        app = create_app()
        assert app is not None
        print("   ✅ FastAPI app created successfully")
        
        print("\n🎉 Clean architecture test completed successfully!")
        print("✅ All core components are working correctly")
        print("✅ Clean modular architecture is functional")
        print("✅ Ready for production deployment")
        
    except Exception as e:
        print(f"\n❌ Architecture test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_clean_architecture())
    sys.exit(0 if success else 1)
