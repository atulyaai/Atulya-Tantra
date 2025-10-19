"""
Atulya Tantra - AI Service
Version: 2.5.0
Orchestrates AI operations: classification, routing, and generation
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging
from src.core.ai.classifier import TaskClassifier, ClassificationResult
from src.core.ai.sentiment import SentimentAnalyzer, SentimentResult
from src.core.ai.router import ModelRouter, ModelSelection
from src.core.ai.model_clients import ModelClientManager
from src.core.ai.context import ConversationMemory, Message

logger = logging.getLogger(__name__)


@dataclass
class AIRequest:
    """AI request data structure"""
    message: str
    context: List[Dict]
    user_id: Optional[str] = None
    model: str = "ollama"
    attachments: List[Dict] = None


@dataclass
class AIResponse:
    """AI response data structure"""
    content: str
    model_used: str
    metadata: Dict


class AIService:
    """Orchestrates AI operations: classification, routing, and generation"""
    
    def __init__(
        self,
        classifier: TaskClassifier,
        sentiment_analyzer: SentimentAnalyzer,
        router: ModelRouter,
        model_client_manager: ModelClientManager,
        conversation_memory: ConversationMemory
    ):
        self.classifier = classifier
        self.sentiment_analyzer = sentiment_analyzer
        self.router = router
        self.model_client_manager = model_client_manager
        self.conversation_memory = conversation_memory
    
    async def generate_response(
        self,
        request: AIRequest,
        conversation_id: Optional[str] = None
    ) -> AIResponse:
        """Generate AI response with intelligent routing and context management"""
        
        # Step 1: Add user message to conversation memory
        if conversation_id:
            await self.conversation_memory.add_message(
                conversation_id=conversation_id,
                role="user",
                content=request.message,
                user_id=request.user_id,
                metadata={"timestamp": request.timestamp.isoformat() if hasattr(request, 'timestamp') else None}
            )
        
        # Step 2: Classify task
        classification = await self.classifier.classify(request.message)
        
        # Step 3: Analyze sentiment
        sentiment = await self.sentiment_analyzer.analyze(request.message)
        
        # Step 4: Get available models
        available_models = await self.model_client_manager.get_available_models()
        
        # Step 5: Select model (use requested model or intelligent routing)
        if hasattr(request, 'model') and request.model and request.model in ["ollama", "openai", "anthropic"]:
            # Use requested model
            model_selection = ModelSelection(
                provider=request.model,
                model="default",  # Will be determined by client
                reasoning=f"User requested {request.model}"
            )
        else:
            # Use intelligent routing
            model_selection = await self.router.select_model(
                classification.task_type,
                classification.complexity,
                available_models
            )
        
        # Step 6: Build context with relevant conversation history
        context_messages = await self._build_context_messages(
            conversation_id, request.message, classification
        )
        
        # Step 7: Build system prompt with tone adjustment
        system_prompt = self._build_system_prompt(sentiment, classification)
        
        # Step 8: Generate response using model client
        try:
            response_text = await self.model_client_manager.generate(
                provider=model_selection.provider,
                model=model_selection.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *context_messages,
                    {"role": "user", "content": request.message}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            # Step 9: Add AI response to conversation memory
            if conversation_id:
                await self.conversation_memory.add_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=response_text.content,
                    user_id=request.user_id,
                    metadata={
                        "model_used": f"{model_selection.provider}/{model_selection.model}",
                        "task_type": classification.task_type.value,
                        "sentiment": sentiment.sentiment.value,
                        "classification_confidence": classification.confidence,
                        "sentiment_confidence": sentiment.confidence
                    }
                )
            
            # Step 10: Return with metadata
            return AIResponse(
                content=response_text.content,
                model_used=f"{model_selection.provider}/{model_selection.model}",
                metadata={
                    "task_type": classification.task_type.value,
                    "complexity": classification.complexity.value,
                    "sentiment": sentiment.sentiment.value,
                    "classification_confidence": classification.confidence,
                    "sentiment_confidence": sentiment.confidence,
                    "model_reasoning": model_selection.reasoning,
                    "usage": response_text.usage,
                    "response_metadata": response_text.metadata
                }
            )
            
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            # Fallback response when no models available
            return AIResponse(
                content=f"I apologize, but I'm currently unable to process your request. The AI models are not available at the moment. However, I can tell you that your message was classified as a {classification.task_type.value} task with {classification.complexity.value} complexity. Please try again later or check the system configuration.",
                model_used="fallback",
                metadata={
                    "error": str(e),
                    "task_type": classification.task_type.value,
                    "complexity": classification.complexity.value,
                    "sentiment": sentiment.sentiment.value,
                    "classification_confidence": classification.confidence,
                    "sentiment_confidence": sentiment.confidence,
                    "fallback": True
                }
            )
    
    def _build_system_prompt(self, sentiment: SentimentResult, classification: ClassificationResult) -> str:
        """Build system prompt with tone adjustment and task context"""
        base_prompt = "You are Atulya, an intelligent AI assistant powered by Tantra Brain. You provide helpful, accurate, and thoughtful responses."
        
        # Add task-specific context
        task_context = ""
        if classification.task_type.value == "coding":
            task_context = " You are particularly skilled at programming and can help with code generation, debugging, and technical questions."
        elif classification.task_type.value == "research":
            task_context = " You excel at research and can provide detailed, well-sourced information on various topics."
        elif classification.task_type.value == "creative":
            task_context = " You are creative and can help with writing, storytelling, and artistic endeavors."
        
        # Add sentiment-based tone adjustment
        tone_adjustment = ""
        if sentiment.tone_adjustment:
            tone_adjustment = f"\n\n{sentiment.tone_adjustment}"
        
        return f"{base_prompt}{task_context}{tone_adjustment}"
    
    async def _build_context_messages(
        self,
        conversation_id: Optional[str],
        current_message: str,
        classification: ClassificationResult
    ) -> List[Dict[str, str]]:
        """Build context messages from conversation history"""
        
        if not conversation_id:
            return []
        
        try:
            # Get relevant context using semantic search
            relevant_messages = await self.conversation_memory.get_relevant_context(
                conversation_id=conversation_id,
                query=current_message,
                limit=5
            )
            
            # Convert to message format
            context_messages = []
            for msg in relevant_messages:
                context_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # If no relevant context found, get recent messages
            if not context_messages:
                recent_messages = await self.conversation_memory.get_conversation_history(
                    conversation_id=conversation_id,
                    limit=3
                )
                context_messages = [
                    {"role": msg.role, "content": msg.content}
                    for msg in recent_messages[-3:]  # Last 3 messages
                ]
            
            return context_messages
            
        except Exception as e:
            logger.warning(f"Failed to build context messages: {e}")
            return []
    
    async def get_conversation_summary(self, conversation_id: str) -> Optional[str]:
        """Get conversation summary"""
        return await self.conversation_memory.get_conversation_summary(conversation_id)
    
    async def get_conversation_stats(self) -> Dict[str, Any]:
        """Get conversation statistics"""
        return self.conversation_memory.get_conversation_stats()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of all AI components"""
        health_status = {
            "classifier": True,  # Simple components are always healthy
            "sentiment_analyzer": True,
            "router": True,
            "conversation_memory": True,
            "model_clients": await self.model_client_manager.health_check()
        }
        
        return health_status
