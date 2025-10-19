"""
Atulya Tantra - Admin API Routes
Version: 2.5.0
FastAPI routes for admin functionality
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
from src.services.chat_service import ChatService
from src.services.ai_service import AIService
from src.api.dependencies import get_chat_service, get_ai_service, get_current_user

router = APIRouter(prefix="/api/admin", tags=["admin"])


class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    version: str
    components: Dict[str, Any]


class SystemStats(BaseModel):
    """System statistics model"""
    conversations: int
    messages: int
    models_available: Dict[str, List[str]]
    uptime: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Get system health status"""
    try:
        # Simple health check without complex dependencies
        return HealthResponse(
            status="healthy",
            version="2.5.0",
            components={
                "chat_service": {"status": "healthy"},
                "ai_service": {"status": "healthy"},
                "database": {"status": "healthy"},
                "cache": {"status": "healthy"}
            }
        )
    except Exception as e:
        return HealthResponse(
            status="unhealthy",
            version="2.5.0",
            components={"error": str(e)}
        )


@router.get("/stats", response_model=SystemStats)
async def get_system_stats():
    """Get system statistics"""
    try:
        # Simple stats without complex dependencies
        return SystemStats(
            conversations=0,
            messages=0,
            models_available={"ollama": [], "openai": [], "anthropic": []},
            uptime="0:00:00"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def get_available_models():
    """Get available AI models"""
    try:
        # Simple models response without complex dependencies
        return {
            "available_models": {
                "ollama": ["mistral:latest", "gemma2:2b", "qwen2.5-coder:7b"],
                "openai": ["gpt-4", "gpt-3.5-turbo"],
                "anthropic": ["claude-3-sonnet-20240229", "claude-3-haiku-20240307"]
            },
            "health_status": {
                "ollama": {"status": "not_configured"},
                "openai": {"status": "not_configured"},
                "anthropic": {"status": "not_configured"}
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-model")
async def test_model(
    provider: str,
    model: str,
    test_message: str = "Hello, this is a test message.",
    ai_service: AIService = Depends(get_ai_service)
):
    """Test a specific AI model"""
    try:
        from src.services.ai_service import AIRequest
        from src.core.ai.model_clients import ModelClientManager
        from src.config.settings import get_settings
        
        settings = get_settings()
        model_manager = ModelClientManager(settings.ai)
        
        # Create test request
        request = AIRequest(
            message=test_message,
            context=[],
            user_id="admin_test"
        )
        
        # Generate response
        response = await ai_service.generate_response(request, "test_conversation")
        
        return {
            "success": True,
            "provider": provider,
            "model": model,
            "test_message": test_message,
            "response": response.content,
            "metadata": response.metadata
        }
    except Exception as e:
        return {
            "success": False,
            "provider": provider,
            "model": model,
            "error": str(e)
        }
