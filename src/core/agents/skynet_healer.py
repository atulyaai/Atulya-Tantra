"""
Atulya Tantra - Skynet Auto-Healing System
Version: 2.5.0
Automatic error detection, recovery, and system healing
"""

import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import json
import asyncio
import subprocess
import psutil
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class HealingAction(Enum):
    """Types of healing actions"""
    RESTART_SERVICE = "restart_service"
    CLEAR_CACHE = "clear_cache"
    RETRY_CONNECTION = "retry_connection"
    FALLBACK_MODE = "fallback_mode"
    SCALE_RESOURCES = "scale_resources"
    ROLLBACK_CHANGES = "rollback_changes"
    NOTIFY_ADMIN = "notify_admin"


class HealingStatus(Enum):
    """Healing action status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class HealingRule:
    """Healing rule definition"""
    rule_id: str
    name: str
    description: str
    condition: str  # Error pattern or condition
    actions: List[HealingAction]
    priority: int
    cooldown_seconds: int
    max_attempts: int
    enabled: bool
    metadata: Dict[str, Any]


@dataclass
class HealingAction:
    """Healing action execution"""
    action_id: str
    rule_id: str
    action_type: HealingAction
    target: str
    parameters: Dict[str, Any]
    status: HealingStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    result: Any


class AutoHealer:
    """Automatic system healing and recovery"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.healing_enabled = config.get("healing_enabled", False)
        self.safety_mode = config.get("safety_mode", True)
        self.healing_rules = {}  # rule_id -> HealingRule
        self.healing_history = deque(maxlen=1000)  # Keep last 1000 healing actions
        self.cooldowns = {}  # rule_id -> last_execution_time
        self.action_handlers = {}  # action_type -> handler_function
        
        # Initialize default healing rules
        self._initialize_default_rules()
        
        # Initialize action handlers
        self._initialize_action_handlers()
        
        logger.info("AutoHealer initialized")
    
    def _initialize_default_rules(self):
        """Initialize default healing rules"""
        
        # High memory usage rule
        self.add_healing_rule(
            name="High Memory Usage",
            description="Clear caches when memory usage is high",
            condition="memory_usage > 90",
            actions=[HealingAction.CLEAR_CACHE, HealingAction.NOTIFY_ADMIN],
            priority=10,
            cooldown_seconds=300,
            max_attempts=3
        )
        
        # API timeout rule
        self.add_healing_rule(
            name="API Timeout",
            description="Restart API service on repeated timeouts",
            condition="api_timeout_count > 5",
            actions=[HealingAction.RESTART_SERVICE],
            priority=8,
            cooldown_seconds=600,
            max_attempts=2
        )
        
        # Database connection failure rule
        self.add_healing_rule(
            name="Database Connection Failure",
            description="Retry database connections and restart if needed",
            condition="db_connection_failed",
            actions=[HealingAction.RETRY_CONNECTION, HealingAction.RESTART_SERVICE],
            priority=9,
            cooldown_seconds=180,
            max_attempts=3
        )
        
        # AI model unavailability rule
        self.add_healing_rule(
            name="AI Model Unavailable",
            description="Switch to fallback models when primary models fail",
            condition="ai_model_unavailable",
            actions=[HealingAction.FALLBACK_MODE, HealingAction.RETRY_CONNECTION],
            priority=7,
            cooldown_seconds=120,
            max_attempts=2
        )
    
    def _initialize_action_handlers(self):
        """Initialize healing action handlers"""
        
        self.action_handlers = {
            HealingAction.RESTART_SERVICE: self._restart_service,
            HealingAction.CLEAR_CACHE: self._clear_cache,
            HealingAction.RETRY_CONNECTION: self._retry_connection,
            HealingAction.FALLBACK_MODE: self._enable_fallback_mode,
            HealingAction.SCALE_RESOURCES: self._scale_resources,
            HealingAction.ROLLBACK_CHANGES: self._rollback_changes,
            HealingAction.NOTIFY_ADMIN: self._notify_admin
        }
    
    async def add_healing_rule(
        self,
        name: str,
        description: str,
        condition: str,
        actions: List[HealingAction],
        priority: int = 5,
        cooldown_seconds: int = 300,
        max_attempts: int = 3,
        enabled: bool = True,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Add a new healing rule"""
        
        rule_id = f"rule_{int(datetime.now().timestamp())}_{len(self.healing_rules)}"
        
        rule = HealingRule(
            rule_id=rule_id,
            name=name,
            description=description,
            condition=condition,
            actions=actions,
            priority=priority,
            cooldown_seconds=cooldown_seconds,
            max_attempts=max_attempts,
            enabled=enabled,
            metadata=metadata or {}
        )
        
        self.healing_rules[rule_id] = rule
        
        logger.info(f"Added healing rule: {name} ({rule_id})")
        return rule_id
    
    async def evaluate_conditions(self, system_state: Dict[str, Any]) -> List[str]:
        """Evaluate healing rules against current system state"""
        
        if not self.healing_enabled:
            return []
        
        triggered_rules = []
        
        for rule_id, rule in self.healing_rules.items():
            if not rule.enabled:
                continue
            
            # Check cooldown
            if rule_id in self.cooldowns:
                last_execution = self.cooldowns[rule_id]
                if datetime.now() - last_execution < timedelta(seconds=rule.cooldown_seconds):
                    continue
            
            # Evaluate condition
            if await self._evaluate_condition(rule.condition, system_state):
                triggered_rules.append(rule_id)
        
        return triggered_rules
    
    async def execute_healing_actions(
        self,
        rule_id: str,
        system_state: Dict[str, Any]
    ) -> List[HealingAction]:
        """Execute healing actions for a rule"""
        
        if rule_id not in self.healing_rules:
            return []
        
        rule = self.healing_rules[rule_id]
        executed_actions = []
        
        # Update cooldown
        self.cooldowns[rule_id] = datetime.now()
        
        for action_type in rule.actions:
            action_id = f"action_{int(datetime.now().timestamp())}_{len(self.healing_history)}"
            
            action = HealingAction(
                action_id=action_id,
                rule_id=rule_id,
                action_type=action_type,
                target=rule.metadata.get("target", "system"),
                parameters=rule.metadata.get("parameters", {}),
                status=HealingStatus.PENDING,
                started_at=None,
                completed_at=None,
                error_message=None,
                result=None
            )
            
            try:
                # Execute action
                action.status = HealingStatus.IN_PROGRESS
                action.started_at = datetime.now()
                
                result = await self._execute_action(action, system_state)
                
                action.status = HealingStatus.SUCCESS
                action.completed_at = datetime.now()
                action.result = result
                
                logger.info(f"Healing action completed: {action_type.value} for rule {rule_id}")
                
            except Exception as e:
                action.status = HealingStatus.FAILED
                action.completed_at = datetime.now()
                action.error_message = str(e)
                
                logger.error(f"Healing action failed: {action_type.value} for rule {rule_id} - {e}")
            
            executed_actions.append(action)
            self.healing_history.append(action)
        
        return executed_actions
    
    async def get_healing_status(self) -> Dict[str, Any]:
        """Get current healing system status"""
        
        recent_actions = list(self.healing_history)[-10:]
        
        return {
            "healing_enabled": self.healing_enabled,
            "safety_mode": self.safety_mode,
            "total_rules": len(self.healing_rules),
            "enabled_rules": len([r for r in self.healing_rules.values() if r.enabled]),
            "recent_actions": [
                {
                    "action_id": action.action_id,
                    "rule_id": action.rule_id,
                    "action_type": action.action_type.value,
                    "status": action.status.value,
                    "started_at": action.started_at.isoformat() if action.started_at else None,
                    "completed_at": action.completed_at.isoformat() if action.completed_at else None,
                    "error_message": action.error_message
                }
                for action in recent_actions
            ],
            "active_cooldowns": len(self.cooldowns),
            "total_actions_executed": len(self.healing_history)
        }
    
    async def get_healing_history(
        self,
        rule_id: Optional[str] = None,
        action_type: Optional[HealingAction] = None,
        status: Optional[HealingStatus] = None,
        limit: int = 100
    ) -> List[HealingAction]:
        """Get healing action history with filters"""
        
        history = list(self.healing_history)
        
        # Apply filters
        if rule_id:
            history = [a for a in history if a.rule_id == rule_id]
        
        if action_type:
            history = [a for a in history if a.action_type == action_type]
        
        if status:
            history = [a for a in history if a.status == status]
        
        # Sort by timestamp (newest first)
        history.sort(key=lambda x: x.started_at or datetime.min, reverse=True)
        
        return history[:limit]
    
    async def _evaluate_condition(self, condition: str, system_state: Dict[str, Any]) -> bool:
        """Evaluate a healing condition against system state"""
        
        try:
            # Simple condition evaluation
            # In production, you'd use a proper expression evaluator
            
            if "life" in condition:
                return False  # Skip dangerous conditions in safety mode
            
            if "memory_usage >" in condition:
                threshold = float(condition.split(">")[1].strip())
                return system_state.get("memory_usage", 0) > threshold
            
            elif "cpu_usage >" in condition:
                threshold = float(condition.split(">")[1].strip())
                return system_state.get("cpu_usage", 0) > threshold
            
            elif "api_timeout_count >" in condition:
                threshold = int(condition.split(">")[1].strip())
                return system_state.get("api_timeout_count", 0) > threshold
            
            elif "db_connection_failed" in condition:
                return system_state.get("db_connection_failed", False)
            
            elif "ai_model_unavailable" in condition:
                return system_state.get("ai_model_unavailable", False)
            
            # Default to False for unknown conditions
            return False
            
        except Exception as e:
            logger.error(f"Error evaluating condition '{condition}': {e}")
            return False
    
    async def _execute_action(self, action: HealingAction, system_state: Dict[str, Any]) -> Any:
        """Execute a healing action"""
        
        if action.action_type not in self.action_handlers:
            raise ValueError(f"No handler for action type: {action.action_type}")
        
        handler = self.action_handlers[action.action_type]
        return await handler(action, system_state)
    
    async def _restart_service(self, action: HealingAction, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Restart a service"""
        
        if self.safety_mode and action.target in ["database", "system"]:
            raise Exception(f"Cannot restart {action.target} in safety mode")
        
        service_name = action.target
        
        try:
            # Simulate service restart
            # In production, this would use actual service management
            logger.info(f"Restarting service: {service_name}")
            
            # Simulate restart delay
            await asyncio.sleep(2)
            
            return {
                "service": service_name,
                "status": "restarted",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to restart service {service_name}: {e}")
            raise
    
    async def _clear_cache(self, action: HealingAction, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Clear system caches"""
        
        try:
            # Simulate cache clearing
            logger.info("Clearing system caches")
            
            # In production, this would clear actual caches
            await asyncio.sleep(1)
            
            return {
                "cache_cleared": True,
                "timestamp": datetime.now().isoformat(),
                "memory_freed": "estimated"
            }
            
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            raise
    
    async def _retry_connection(self, action: HealingAction, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Retry failed connections"""
        
        target = action.target
        
        try:
            # Simulate connection retry
            logger.info(f"Retrying connection to: {target}")
            
            await asyncio.sleep(1)
            
            # Simulate connection success
            return {
                "target": target,
                "status": "connected",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to retry connection to {target}: {e}")
            raise
    
    async def _enable_fallback_mode(self, action: HealingAction, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Enable fallback mode for services"""
        
        try:
            # Simulate enabling fallback mode
            logger.info("Enabling fallback mode")
            
            return {
                "fallback_enabled": True,
                "timestamp": datetime.now().isoformat(),
                "affected_services": action.parameters.get("services", ["ai_models"])
            }
            
        except Exception as e:
            logger.error(f"Failed to enable fallback mode: {e}")
            raise
    
    async def _scale_resources(self, action: HealingAction, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Scale system resources"""
        
        if self.safety_mode:
            raise Exception("Resource scaling disabled in safety mode")
        
        try:
            # Simulate resource scaling
            logger.info("Scaling system resources")
            
            return {
                "scaling_completed": True,
                "timestamp": datetime.now().isoformat(),
                "scaled_resources": action.parameters.get("resources", ["cpu", "memory"])
            }
            
        except Exception as e:
            logger.error(f"Failed to scale resources: {e}")
            raise
    
    async def _rollback_changes(self, action: HealingAction, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Rollback recent changes"""
        
        if self.safety_mode:
            raise Exception("Rollback disabled in safety mode")
        
        try:
            # Simulate rollback
            logger.info("Rolling back recent changes")
            
            return {
                "rollback_completed": True,
                "timestamp": datetime.now().isoformat(),
                "rolled_back_changes": action.parameters.get("changes", ["recent"])
            }
            
        except Exception as e:
            logger.error(f"Failed to rollback changes: {e}")
            raise
    
    async def _notify_admin(self, action: HealingAction, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Send notification to administrator"""
        
        try:
            # Simulate admin notification
            logger.info("Sending notification to administrator")
            
            # In production, this would send actual notifications
            return {
                "notification_sent": True,
                "timestamp": datetime.now().isoformat(),
                "recipients": action.parameters.get("recipients", ["admin"])
            }
            
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of auto-healer"""
        return {
            "auto_healer": True,
            "healing_enabled": self.healing_enabled,
            "safety_mode": self.safety_mode,
            "total_rules": len(self.healing_rules),
            "action_handlers": len(self.action_handlers),
            "healing_history": len(self.healing_history),
            "active_cooldowns": len(self.cooldowns)
        }
