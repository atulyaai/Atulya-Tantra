"""
Unified AGI System for Atulya Tantra
Integrates JARVIS, Skynet, and all AGI components into a cohesive system
"""

import asyncio
import json
import time
import threading
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import queue

from .config.settings import settings
from .config.logging import get_logger
from .config.exceptions import AgentError

# Import all components
from .jarvis.sentiment_analyzer import get_sentiment_analyzer, analyze_user_sentiment
from .jarvis.enhanced_voice_interface import get_enhanced_voice_interface, VoiceState, ConversationMode
from .jarvis.personality_engine import get_conversational_ai
from .agi_core import get_agi_core, process_agi_request
from .skynet import get_task_scheduler, get_system_monitor, get_auto_healer
from .agents import get_orchestrator
from .memory.conversation_memory import ConversationMemory

logger = get_logger(__name__)


class SystemMode(str, Enum):
    """System operation modes"""
    CONVERSATIONAL = "conversational"  # Human-like conversation
    AUTONOMOUS = "autonomous"  # Self-directed operation
    ASSISTIVE = "assistive"  # Task assistance
    MONITORING = "monitoring"  # System monitoring only
    LEARNING = "learning"  # Learning mode


class AGISystem:
    """Unified AGI system integrating all components"""
    
    def __init__(self):
        self.system_mode = SystemMode.CONVERSATIONAL
        self.is_active = False
        self.is_initialized = False
        
        # Core components
        self.sentiment_analyzer = get_sentiment_analyzer()
        self.voice_interface = get_enhanced_voice_interface()
        self.conversational_ai = get_conversational_ai()
        self.agi_core = get_agi_core()
        self.task_scheduler = get_task_scheduler()
        self.system_monitor = get_system_monitor()
        self.auto_healer = get_auto_healer()
        self.orchestrator = get_orchestrator()
        self.memory = ConversationMemory()
        
        # System state
        self.active_sessions = {}
        self.system_health = {}
        self.learning_data = {}
        self.performance_metrics = {}
        
        # Background processing
        self.processing_queue = queue.Queue()
        self.monitoring_queue = queue.Queue()
        self.learning_queue = queue.Queue()
        
        # Callbacks
        self.on_user_input = None
        self.on_system_response = None
        self.on_system_state_change = None
        self.on_error = None
        
        # Initialize system
        self._initialize_system()
    
    def _initialize_system(self):
        """Initialize the unified AGI system"""
        try:
            logger.info("Initializing unified AGI system...")
            
            # Set up voice interface callbacks
            self.voice_interface.on_command_received = self._handle_voice_command
            self.voice_interface.on_response_ready = self._handle_voice_response
            self.voice_interface.on_state_changed = self._handle_voice_state_change
            
            # Start background threads
            self._start_background_threads()
            
            # Initialize system health monitoring
            asyncio.create_task(self._monitor_system_health())
            
            self.is_initialized = True
            logger.info("Unified AGI system initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing AGI system: {e}")
            self.is_initialized = False
    
    def _start_background_threads(self):
        """Start background processing threads"""
        threading.Thread(target=self._process_requests, daemon=True).start()
        threading.Thread(target=self._monitor_system, daemon=True).start()
        threading.Thread(target=self._learn_from_interactions, daemon=True).start()
        threading.Thread(target=self._maintain_system, daemon=True).start()
    
    async def start_system(self, mode: SystemMode = SystemMode.CONVERSATIONAL):
        """Start the AGI system"""
        try:
            if not self.is_initialized:
                raise AgentError("System not initialized")
            
            self.system_mode = mode
            self.is_active = True
            
            # Start voice interface if in conversational mode
            if mode in [SystemMode.CONVERSATIONAL, SystemMode.ASSISTIVE]:
                await self.voice_interface.start_conversation(
                    user_id="system_user",
                    mode=ConversationMode.WAKE_WORD
                )
            
            # Start autonomous operations if in autonomous mode
            if mode == SystemMode.AUTONOMOUS:
                await self._start_autonomous_operations()
            
            # Start monitoring if in monitoring mode
            if mode == SystemMode.MONITORING:
                await self._start_monitoring_mode()
            
            logger.info(f"AGI system started in {mode.value} mode")
            
        except Exception as e:
            logger.error(f"Error starting AGI system: {e}")
            if self.on_error:
                self.on_error(e)
    
    async def stop_system(self):
        """Stop the AGI system"""
        try:
            self.is_active = False
            
            # Stop voice interface
            await self.voice_interface.stop_conversation()
            
            # Stop autonomous operations
            await self._stop_autonomous_operations()
            
            logger.info("AGI system stopped")
            
        except Exception as e:
            logger.error(f"Error stopping AGI system: {e}")
    
    async def process_user_input(self, input_text: str, user_id: str = None, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process user input through the complete AGI pipeline"""
        try:
            if not self.is_active:
                raise AgentError("System not active")
            
            user_id = user_id or "default_user"
            session_id = f"{user_id}_{int(time.time())}"
            
            # Create processing context
            processing_context = {
                "user_id": user_id,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "system_mode": self.system_mode.value,
                "context": context or {}
            }
            
            # Step 1: Analyze sentiment and emotion
            emotional_context = await analyze_user_sentiment(input_text, user_id)
            processing_context["emotional_context"] = emotional_context.to_dict()
            
            # Step 2: Process with conversational AI
            conversational_response = await self.conversational_ai.process_message(
                input_text, user_id=user_id
            )
            processing_context["conversational_response"] = conversational_response
            
            # Step 3: Process with AGI core for reasoning
            agi_result = await process_agi_request(input_text, user_id, processing_context)
            processing_context["agi_result"] = agi_result
            
            # Step 4: Generate final response
            final_response = await self._generate_final_response(
                input_text, emotional_context, conversational_response, agi_result, processing_context
            )
            
            # Step 5: Store in memory
            await self.memory.store_conversation(
                user_id=user_id,
                input_text=input_text,
                response=final_response,
                context=processing_context
            )
            
            # Step 6: Execute any actions from AGI result
            if agi_result.get("success") and agi_result.get("results", {}).get("actions"):
                await self._execute_actions(agi_result["results"]["actions"], processing_context)
            
            # Callback
            if self.on_user_input:
                self.on_user_input(input_text, processing_context)
            
            return {
                "success": True,
                "response": final_response,
                "emotional_context": emotional_context.to_dict(),
                "agi_analysis": agi_result,
                "processing_context": processing_context
            }
            
        except Exception as e:
            logger.error(f"Error processing user input: {e}")
            if self.on_error:
                self.on_error(e)
            return {
                "success": False,
                "error": str(e),
                "response": "I'm sorry, I encountered an error processing your request."
            }
    
    async def _generate_final_response(self, input_text: str, emotional_context, conversational_response: str, agi_result: Dict[str, Any], processing_context: Dict[str, Any]) -> str:
        """Generate the final response combining all components"""
        try:
            # Start with conversational response
            response = conversational_response
            
            # Enhance with emotional intelligence
            if emotional_context.current_emotion != "neutral":
                response = await self.sentiment_analyzer.generate_emotional_response(
                    emotional_context, response
                )
            
            # Add AGI insights if available
            if agi_result.get("success") and agi_result.get("decision", {}).get("decision") == "proceed":
                agi_insights = agi_result.get("decision", {}).get("alternative", {})
                if agi_insights.get("approach"):
                    response += f"\n\nBased on my analysis, I recommend: {agi_insights['approach']}"
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating final response: {e}")
            return conversational_response
    
    async def _execute_actions(self, actions: List[Dict[str, Any]], context: Dict[str, Any]):
        """Execute actions from AGI processing"""
        try:
            for action in actions:
                action_type = action.get("type", "unknown")
                
                if action_type == "schedule_task":
                    await self.task_scheduler.schedule_task(
                        action.get("task_name", "Unknown Task"),
                        action.get("description", ""),
                        priority=action.get("priority", "normal")
                    )
                elif action_type == "monitor_system":
                    await self.system_monitor.get_system_health()
                elif action_type == "heal_system":
                    await self.auto_healer.trigger_manual_healing()
                elif action_type == "submit_to_agent":
                    await self.orchestrator.submit_task(
                        action.get("task_name", "Unknown Task"),
                        action.get("description", ""),
                        priority=action.get("priority", "normal")
                    )
                
                logger.info(f"Executed action: {action_type}")
                
        except Exception as e:
            logger.error(f"Error executing actions: {e}")
    
    def _handle_voice_command(self, command):
        """Handle voice command from voice interface"""
        try:
            if self.on_user_input:
                self.on_user_input(command.text, {"source": "voice"})
            
            # Process voice command
            asyncio.create_task(self.process_user_input(
                command.text,
                user_id=command.emotional_context.user_id if command.emotional_context else None
            ))
            
        except Exception as e:
            logger.error(f"Error handling voice command: {e}")
    
    def _handle_voice_response(self, response: str):
        """Handle voice response ready"""
        try:
            if self.on_system_response:
                self.on_system_response(response, {"source": "voice"})
                
        except Exception as e:
            logger.error(f"Error handling voice response: {e}")
    
    def _handle_voice_state_change(self, old_state: VoiceState, new_state: VoiceState):
        """Handle voice interface state change"""
        try:
            if self.on_system_state_change:
                self.on_system_state_change("voice_interface", old_state.value, new_state.value)
                
        except Exception as e:
            logger.error(f"Error handling voice state change: {e}")
    
    async def _start_autonomous_operations(self):
        """Start autonomous operations"""
        try:
            # Schedule autonomous tasks
            await self.task_scheduler.schedule_task(
                "system_health_check",
                "Regular system health monitoring",
                priority="high"
            )
            
            await self.task_scheduler.schedule_task(
                "learning_optimization",
                "Continuous learning and optimization",
                priority="normal"
            )
            
            logger.info("Autonomous operations started")
            
        except Exception as e:
            logger.error(f"Error starting autonomous operations: {e}")
    
    async def _stop_autonomous_operations(self):
        """Stop autonomous operations"""
        try:
            # Cancel autonomous tasks
            # Implementation would cancel scheduled tasks
            
            logger.info("Autonomous operations stopped")
            
        except Exception as e:
            logger.error(f"Error stopping autonomous operations: {e}")
    
    async def _start_monitoring_mode(self):
        """Start monitoring mode"""
        try:
            # Start intensive monitoring
            await self.system_monitor.get_system_health()
            
            logger.info("Monitoring mode started")
            
        except Exception as e:
            logger.error(f"Error starting monitoring mode: {e}")
    
    async def _monitor_system_health(self):
        """Monitor system health"""
        while self.is_active:
            try:
                # Get system health
                health = await self.system_monitor.get_system_health()
                self.system_health = health
                
                # Check for issues and trigger healing if needed
                if health.get("status") == "degraded":
                    await self.auto_healer.trigger_manual_healing()
                
                # Update performance metrics
                self.performance_metrics = {
                    "timestamp": datetime.now().isoformat(),
                    "system_health": health,
                    "active_sessions": len(self.active_sessions),
                    "memory_usage": self._get_memory_usage(),
                    "processing_queue_size": self.processing_queue.qsize()
                }
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring system health: {e}")
                await asyncio.sleep(60)
    
    def _process_requests(self):
        """Process requests in background thread"""
        while True:
            try:
                if not self.processing_queue.empty():
                    request = self.processing_queue.get()
                    # Process request
                    asyncio.create_task(self._process_background_request(request))
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error processing requests: {e}")
                time.sleep(1)
    
    def _monitor_system(self):
        """Monitor system in background thread"""
        while True:
            try:
                if not self.monitoring_queue.empty():
                    monitoring_task = self.monitoring_queue.get()
                    # Process monitoring task
                    pass
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error in system monitoring: {e}")
                time.sleep(5)
    
    def _learn_from_interactions(self):
        """Learn from interactions in background thread"""
        while True:
            try:
                if not self.learning_queue.empty():
                    learning_data = self.learning_queue.get()
                    # Process learning data
                    self.learning_data[time.time()] = learning_data
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error in learning: {e}")
                time.sleep(5)
    
    def _maintain_system(self):
        """Maintain system in background thread"""
        while True:
            try:
                # Clean up old data
                self._cleanup_old_data()
                
                # Optimize performance
                self._optimize_performance()
                
                time.sleep(300)  # Run every 5 minutes
            except Exception as e:
                logger.error(f"Error in system maintenance: {e}")
                time.sleep(600)
    
    async def _process_background_request(self, request: Dict[str, Any]):
        """Process background request"""
        try:
            # Process request based on type
            request_type = request.get("type", "unknown")
            
            if request_type == "user_input":
                await self.process_user_input(
                    request.get("input_text", ""),
                    request.get("user_id"),
                    request.get("context")
                )
            
        except Exception as e:
            logger.error(f"Error processing background request: {e}")
    
    def _cleanup_old_data(self):
        """Clean up old data"""
        try:
            # Clean up old learning data
            current_time = time.time()
            cutoff_time = current_time - (24 * 60 * 60)  # 24 hours ago
            
            old_keys = [k for k in self.learning_data.keys() if k < cutoff_time]
            for key in old_keys:
                del self.learning_data[key]
            
            # Clean up old sessions
            # Implementation would clean up old sessions
            
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
    
    def _optimize_performance(self):
        """Optimize system performance"""
        try:
            # Optimize memory usage
            # Implementation would optimize memory
            
            # Optimize processing queues
            # Implementation would optimize queues
            
        except Exception as e:
            logger.error(f"Error optimizing performance: {e}")
    
    def _get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage information"""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                "rss": memory_info.rss,
                "vms": memory_info.vms,
                "percent": process.memory_percent()
            }
        except ImportError:
            return {"error": "psutil not available"}
        except Exception as e:
            return {"error": str(e)}
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            "is_active": self.is_active,
            "is_initialized": self.is_initialized,
            "system_mode": self.system_mode.value,
            "system_health": self.system_health,
            "performance_metrics": self.performance_metrics,
            "active_sessions": len(self.active_sessions),
            "learning_entries": len(self.learning_data),
            "voice_state": self.voice_interface.get_current_state(),
            "agi_status": self.agi_core.get_agi_status() if hasattr(self.agi_core, 'get_agi_status') else {}
        }
    
    def set_callbacks(self, on_user_input=None, on_system_response=None, on_system_state_change=None, on_error=None):
        """Set system callbacks"""
        self.on_user_input = on_user_input
        self.on_system_response = on_system_response
        self.on_system_state_change = on_system_state_change
        self.on_error = on_error


# Global instance
_agi_system = None

def get_agi_system() -> AGISystem:
    """Get global AGI system instance"""
    global _agi_system
    if _agi_system is None:
        _agi_system = AGISystem()
    return _agi_system

async def start_agi_system(mode: SystemMode = SystemMode.CONVERSATIONAL):
    """Start the AGI system"""
    system = get_agi_system()
    await system.start_system(mode)

async def stop_agi_system():
    """Stop the AGI system"""
    system = get_agi_system()
    await system.stop_system()

async def process_with_agi(input_text: str, user_id: str = None, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Process input with the AGI system"""
    system = get_agi_system()
    return await system.process_user_input(input_text, user_id, context)

def get_agi_system_status() -> Dict[str, Any]:
    """Get AGI system status"""
    system = get_agi_system()
    return system.get_system_status()
