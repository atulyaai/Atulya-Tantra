"""
Natural Conversation API Endpoints
REST API for human-like conversations without hardcoded responses
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio

from ..conversation.natural_conversation import get_natural_conversation_engine
from ..config.logging import get_logger

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/conversation", tags=["conversation"])


class ChatMessage(BaseModel):
    """Chat message model"""
    message: str = Field(..., description="User message", min_length=1, max_length=2000)
    user_id: str = Field(..., description="User identifier")
    session_id: Optional[str] = Field(None, description="Session identifier")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class ChatResponse(BaseModel):
    """Chat response model"""
    response: str = Field(..., description="AI response")
    session_id: str = Field(..., description="Session identifier")
    timestamp: datetime = Field(..., description="Response timestamp")
    context: Dict[str, Any] = Field(..., description="Response context")
    emotional_tone: str = Field(..., description="Detected emotional tone")
    topics: List[str] = Field(..., description="Identified topics")
    follow_up_needed: bool = Field(..., description="Whether follow-up is needed")


class ConversationHistory(BaseModel):
    """Conversation history model"""
    conversations: List[Dict[str, Any]] = Field(..., description="Conversation history")
    total_count: int = Field(..., description="Total conversation count")


class ConversationInsights(BaseModel):
    """Conversation insights model"""
    total_conversations: int = Field(..., description="Total conversations")
    most_common_context: str = Field(..., description="Most common conversation context")
    most_common_emotional_tone: str = Field(..., description="Most common emotional tone")
    top_topics: List[tuple] = Field(..., description="Top topics discussed")
    conversation_frequency: float = Field(..., description="Conversations per day")


class ConversationStats(BaseModel):
    """Conversation statistics model"""
    total_users: int = Field(..., description="Total users")
    total_conversations: int = Field(..., description="Total conversations")
    active_sessions: int = Field(..., description="Active sessions")
    average_conversations_per_user: float = Field(..., description="Average conversations per user")


@router.post("/chat", response_model=ChatResponse)
async def chat_with_ai(
    message: ChatMessage,
    background_tasks: BackgroundTasks
) -> ChatResponse:
    """
    Chat with the AI using natural conversation
    
    This endpoint provides human-like conversations without hardcoded responses.
    The AI analyzes the message context, emotional tone, and generates appropriate responses.
    """
    try:
        engine = get_natural_conversation_engine()
        
        # Process the message
        response = await engine.process_message(
            user_id=message.user_id,
            message=message.message,
            session_id=message.session_id
        )
        
        # Get conversation state for additional context
        state_key = f"{message.user_id}_{message.session_id or 'default'}"
        state = engine.conversation_states.get(state_key)
        
        # Get recent conversation memory for context
        recent_memories = engine.conversation_memories.get(message.user_id, [])
        last_memory = recent_memories[-1] if recent_memories else None
        
        # Build response context
        response_context = {
            "user_id": message.user_id,
            "session_id": message.session_id or "default",
            "message_length": len(message.message),
            "response_length": len(response),
            "conversation_depth": state.conversation_depth if state else 1,
            "style": state.style.value if state else "adaptive",
            "mood": state.mood if state else "neutral"
        }
        
        # Add additional context if provided
        if message.context:
            response_context.update(message.context)
        
        # Determine emotional tone and topics from last memory
        emotional_tone = last_memory.emotional_tone if last_memory else "neutral"
        topics = last_memory.topics if last_memory else []
        follow_up_needed = last_memory.follow_up_needed if last_memory else False
        
        # Log the conversation
        logger.info(f"Conversation: User {message.user_id} -> AI: {message.message[:50]}...")
        
        return ChatResponse(
            response=response,
            session_id=message.session_id or "default",
            timestamp=datetime.utcnow(),
            context=response_context,
            emotional_tone=emotional_tone,
            topics=topics,
            follow_up_needed=follow_up_needed
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")


@router.get("/history/{user_id}", response_model=ConversationHistory)
async def get_conversation_history(
    user_id: str,
    limit: int = 10,
    session_id: Optional[str] = None
) -> ConversationHistory:
    """
    Get conversation history for a user
    
    Returns the recent conversation history with context and emotional analysis.
    """
    try:
        engine = get_natural_conversation_engine()
        
        # Get conversation history
        history = await engine.get_conversation_history(user_id, limit)
        
        return ConversationHistory(
            conversations=history,
            total_count=len(history)
        )
        
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get conversation history: {str(e)}")


@router.get("/insights/{user_id}", response_model=ConversationInsights)
async def get_conversation_insights(user_id: str) -> ConversationInsights:
    """
    Get conversation insights for a user
    
    Provides analysis of conversation patterns, topics, and emotional trends.
    """
    try:
        engine = get_natural_conversation_engine()
        
        # Get conversation insights
        insights = await engine.get_conversation_insights(user_id)
        
        return ConversationInsights(
            total_conversations=insights.get("total_conversations", 0),
            most_common_context=insights.get("most_common_context", "unknown"),
            most_common_emotional_tone=insights.get("most_common_emotional_tone", "neutral"),
            top_topics=insights.get("top_topics", []),
            conversation_frequency=insights.get("conversation_frequency", 0.0)
        )
        
    except Exception as e:
        logger.error(f"Error getting conversation insights: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get conversation insights: {str(e)}")


@router.get("/stats", response_model=ConversationStats)
async def get_conversation_statistics() -> ConversationStats:
    """
    Get overall conversation statistics
    
    Returns system-wide conversation statistics and metrics.
    """
    try:
        engine = get_natural_conversation_engine()
        
        # Get conversation statistics
        stats = engine.get_conversation_statistics()
        
        return ConversationStats(
            total_users=stats.get("total_users", 0),
            total_conversations=stats.get("total_conversations", 0),
            active_sessions=stats.get("active_sessions", 0),
            average_conversations_per_user=stats.get("average_conversations_per_user", 0.0)
        )
        
    except Exception as e:
        logger.error(f"Error getting conversation statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get conversation statistics: {str(e)}")


@router.post("/reset/{user_id}")
async def reset_conversation(user_id: str, session_id: Optional[str] = None):
    """
    Reset conversation state for a user
    
    Clears conversation history and resets the conversation state.
    """
    try:
        engine = get_natural_conversation_engine()
        
        # Clear conversation memory
        if user_id in engine.conversation_memories:
            del engine.conversation_memories[user_id]
        
        # Clear conversation state
        state_key = f"{user_id}_{session_id or 'default'}"
        if state_key in engine.conversation_states:
            del engine.conversation_states[state_key]
        
        logger.info(f"Reset conversation for user {user_id}")
        
        return {"message": f"Conversation reset for user {user_id}", "success": True}
        
    except Exception as e:
        logger.error(f"Error resetting conversation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset conversation: {str(e)}")


@router.get("/health")
async def conversation_health_check():
    """
    Health check for conversation system
    
    Verifies that the conversation engine is working properly.
    """
    try:
        engine = get_natural_conversation_engine()
        
        # Test basic functionality
        test_response = await engine.process_message(
            user_id="health_check",
            message="Hello",
            session_id="health_check"
        )
        
        return {
            "status": "healthy",
            "message": "Conversation system is working",
            "test_response_length": len(test_response),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Conversation health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": f"Conversation system error: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }


# WebSocket endpoint for real-time conversations
@router.websocket("/ws/{user_id}")
async def websocket_conversation(websocket, user_id: str):
    """
    WebSocket endpoint for real-time conversations
    
    Provides real-time, bidirectional communication for natural conversations.
    """
    try:
        await websocket.accept()
        engine = get_natural_conversation_engine()
        session_id = f"ws_{int(datetime.utcnow().timestamp())}"
        
        logger.info(f"WebSocket connection established for user {user_id}")
        
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_json()
                message = data.get("message", "")
                
                if not message:
                    continue
                
                # Process message
                response = await engine.process_message(
                    user_id=user_id,
                    message=message,
                    session_id=session_id
                )
                
                # Send response back to client
                await websocket.send_json({
                    "type": "response",
                    "message": response,
                    "timestamp": datetime.utcnow().isoformat(),
                    "user_id": user_id,
                    "session_id": session_id
                })
                
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Error processing message: {str(e)}"
                })
                
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        logger.info(f"WebSocket connection closed for user {user_id}")


# Example usage and testing endpoints
@router.get("/examples")
async def get_conversation_examples():
    """
    Get example conversation starters
    
    Provides example messages to test the conversation system.
    """
    examples = [
        {
            "category": "Greetings",
            "examples": [
                "Hello! How are you today?",
                "Hi there! What's new?",
                "Good morning! How can you help me?"
            ]
        },
        {
            "category": "Questions",
            "examples": [
                "What can you do to help me?",
                "How does this system work?",
                "Can you explain artificial intelligence?"
            ]
        },
        {
            "category": "Emotional Support",
            "examples": [
                "I'm feeling stressed about work.",
                "I'm excited about my new project!",
                "I'm confused about this problem."
            ]
        },
        {
            "category": "Creative Tasks",
            "examples": [
                "Write me a poem about the ocean.",
                "Help me brainstorm ideas for my presentation.",
                "Create a story about a robot and a human."
            ]
        },
        {
            "category": "Problem Solving",
            "examples": [
                "I need help debugging my code.",
                "How can I improve my productivity?",
                "What's the best way to learn a new skill?"
            ]
        }
    ]
    
    return {
        "examples": examples,
        "total_categories": len(examples),
        "total_examples": sum(len(cat["examples"]) for cat in examples)
    }