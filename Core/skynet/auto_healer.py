"""
Auto-Healer for Atulya Tantra AGI
Automatically detects and resolves system issues
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from ..config.logging import get_logger
from ..config.exceptions import SystemError, ValidationError
from ..monitoring.system_monitor import SystemMonitor
from ..monitoring.alerting import AlertManager

logger = get_logger(__name__)


class HealAction(Enum):
    """Healing action types"""
    RESTART_SERVICE = "restart_service"
    CLEAR_CACHE = "clear_cache"
    SCALE_RESOURCES = "scale_resources"
    ROLLBACK_CHANGES = "rollback_changes"
    ISOLATE_COMPONENT = "isolate_component"
    NOTIFY_ADMIN = "notify_admin"
    CUSTOM_ACTION = "custom_action"


@dataclass
class HealRule:
    """Healing rule definition"""
    id: str
    name: str
    condition: str
    action: HealAction
    parameters: Dict[str, Any]
    enabled: bool
    priority: int
    cooldown_seconds: int
    max_attempts: int
    created_at: str
    updated_at: str


@dataclass
class HealAttempt:
    """Healing attempt record"""
    id: str
    rule_id: str
    component: str
    action: HealAction
    status: str
    message: str
    timestamp: str
    duration_seconds: float
    parameters: Dict[str, Any]


class AutoHealer:
    """Auto-healer for system issues"""
    
    def __init__(
        self,
        system_monitor: SystemMonitor = None,
        alert_manager: AlertManager = None
    ):
        self.system_monitor = system_monitor
        self.alert_manager = alert_manager
        
        # Healing rules
        self.heal_rules: Dict[str, HealRule] = {}
        
        # Healing attempts
        self.heal_attempts: List[HealAttempt] = []
        
        # Component status
        self.component_status: Dict[str, Dict[str, Any]] = {}
        
        # Custom actions
        self.custom_actions: Dict[str, Callable] = {}
        
        # Initialize default rules
        self._initialize_default_rules()
        
        logger.info("Initialized Auto-Healer")
    
    def _initialize_default_rules(self):
        """Initialize default healing rules"""
        try:
            # High CPU usage rule
            self.add_heal_rule(
                id="high_cpu_usage",
                name="High CPU Usage",
                condition="cpu_usage > 80",
                action=HealAction.SCALE_RESOURCES,
                parameters={"cpu_limit": 2.0, "memory_limit": "4Gi"},
                priority=1,
                cooldown_seconds=300
            )
            
            # High memory usage rule
            self.add_heal_rule(
                id="high_memory_usage",
                name="High Memory Usage",
                condition="memory_usage > 85",
                action=HealAction.SCALE_RESOURCES,
                parameters={"memory_limit": "8Gi", "cpu_limit": 1.5},
                priority=1,
                cooldown_seconds=300
            )
            
            # Service down rule
            self.add_heal_rule(
                id="service_down",
                name="Service Down",
                condition="service_status == 'down'",
                action=HealAction.RESTART_SERVICE,
                parameters={"service_name": "auto_detect"},
                priority=0,
                cooldown_seconds=60
            )
            
            # Cache issues rule
            self.add_heal_rule(
                id="cache_issues",
                name="Cache Issues",
                condition="cache_hit_rate < 0.7",
                action=HealAction.CLEAR_CACHE,
                parameters={"cache_type": "all"},
                priority=2,
                cooldown_seconds=600
            )
            
            # Error rate rule
            self.add_heal_rule(
                id="high_error_rate",
                name="High Error Rate",
                condition="error_rate > 0.05",
                action=HealAction.ISOLATE_COMPONENT,
                parameters={"isolation_level": "partial"},
                priority=0,
                cooldown_seconds=120
            )
            
            logger.info("Initialized default healing rules")
            
        except Exception as e:
            logger.error(f"Error initializing default rules: {e}")
    
    def add_heal_rule(
        self,
        id: str,
        name: str,
        condition: str,
        action: HealAction,
        parameters: Dict[str, Any] = None,
        priority: int = 5,
        cooldown_seconds: int = 300,
        max_attempts: int = 3,
        enabled: bool = True
    ) -> bool:
        """Add a healing rule"""
        try:
            rule = HealRule(
                id=id,
                name=name,
                condition=condition,
                action=action,
                parameters=parameters or {},
                enabled=enabled,
                priority=priority,
                cooldown_seconds=cooldown_seconds,
                max_attempts=max_attempts,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
            
            self.heal_rules[id] = rule
            logger.info(f"Added healing rule: {id}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding healing rule: {e}")
            return False
    
    def update_heal_rule(
        self,
        id: str,
        **kwargs
    ) -> bool:
        """Update a healing rule"""
        try:
            if id not in self.heal_rules:
                return False
            
            rule = self.heal_rules[id]
            
            # Update allowed fields
            allowed_fields = [
                "name", "condition", "action", "parameters", "enabled",
                "priority", "cooldown_seconds", "max_attempts"
            ]
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    setattr(rule, field, value)
            
            rule.updated_at = datetime.now().isoformat()
            
            logger.info(f"Updated healing rule: {id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating healing rule: {e}")
            return False
    
    def remove_heal_rule(self, id: str) -> bool:
        """Remove a healing rule"""
        try:
            if id in self.heal_rules:
                del self.heal_rules[id]
                logger.info(f"Removed healing rule: {id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error removing healing rule: {e}")
            return False
    
    def add_custom_action(self, name: str, action_func: Callable) -> bool:
        """Add a custom healing action"""
        try:
            self.custom_actions[name] = action_func
            logger.info(f"Added custom action: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding custom action: {e}")
            return False
    
    async def check_and_heal(self) -> List[HealAttempt]:
        """Check system and perform healing actions"""
        try:
            if not self.system_monitor:
                logger.warning("No system monitor available for healing")
                return []
            
            # Get system metrics
            metrics = await self.system_monitor.get_system_metrics()
            
            # Check each rule
            heal_attempts = []
            for rule in self.heal_rules.values():
                if not rule.enabled:
                    continue
                
                # Check if rule should be triggered
                if await self._should_trigger_rule(rule, metrics):
                    # Check cooldown
                    if self._is_in_cooldown(rule):
                        continue
                    
                    # Check max attempts
                    if self._has_exceeded_max_attempts(rule):
                        continue
                    
                    # Perform healing action
                    attempt = await self._perform_heal_action(rule, metrics)
                    if attempt:
                        heal_attempts.append(attempt)
            
            return heal_attempts
            
        except Exception as e:
            logger.error(f"Error checking and healing: {e}")
            return []
    
    async def _should_trigger_rule(self, rule: HealRule, metrics: Dict[str, Any]) -> bool:
        """Check if a rule should be triggered"""
        try:
            # Simple condition evaluation
            # In a real implementation, this would use a proper expression evaluator
            condition = rule.condition.lower()
            
            # Parse condition
            if "cpu_usage" in condition:
                cpu_usage = metrics.get("cpu_usage", 0)
                if ">" in condition:
                    threshold = float(condition.split(">")[1].strip())
                    return cpu_usage > threshold
            
            elif "memory_usage" in condition:
                memory_usage = metrics.get("memory_usage", 0)
                if ">" in condition:
                    threshold = float(condition.split(">")[1].strip())
                    return memory_usage > threshold
            
            elif "service_status" in condition:
                service_status = metrics.get("service_status", "unknown")
                if "==" in condition:
                    expected_status = condition.split("==")[1].strip().strip("'\"")
                    return service_status == expected_status
            
            elif "cache_hit_rate" in condition:
                cache_hit_rate = metrics.get("cache_hit_rate", 1.0)
                if "<" in condition:
                    threshold = float(condition.split("<")[1].strip())
                    return cache_hit_rate < threshold
            
            elif "error_rate" in condition:
                error_rate = metrics.get("error_rate", 0.0)
                if ">" in condition:
                    threshold = float(condition.split(">")[1].strip())
                    return error_rate > threshold
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking rule condition: {e}")
            return False
    
    def _is_in_cooldown(self, rule: HealRule) -> bool:
        """Check if rule is in cooldown period"""
        try:
            # Find recent attempts for this rule
            recent_attempts = [
                attempt for attempt in self.heal_attempts
                if attempt.rule_id == rule.id
                and datetime.fromisoformat(attempt.timestamp) > 
                   datetime.now() - timedelta(seconds=rule.cooldown_seconds)
            ]
            
            return len(recent_attempts) > 0
            
        except Exception as e:
            logger.error(f"Error checking cooldown: {e}")
            return False
    
    def _has_exceeded_max_attempts(self, rule: HealRule) -> bool:
        """Check if rule has exceeded max attempts"""
        try:
            # Count recent attempts
            recent_attempts = [
                attempt for attempt in self.heal_attempts
                if attempt.rule_id == rule.id
                and datetime.fromisoformat(attempt.timestamp) > 
                   datetime.now() - timedelta(hours=1)
            ]
            
            return len(recent_attempts) >= rule.max_attempts
            
        except Exception as e:
            logger.error(f"Error checking max attempts: {e}")
            return False
    
    async def _perform_heal_action(
        self,
        rule: HealRule,
        metrics: Dict[str, Any]
    ) -> Optional[HealAttempt]:
        """Perform a healing action"""
        try:
            start_time = datetime.now()
            
            # Create heal attempt record
            attempt = HealAttempt(
                id=f"heal_{int(start_time.timestamp())}",
                rule_id=rule.id,
                component=rule.parameters.get("service_name", "system"),
                action=rule.action,
                status="running",
                message="Starting healing action",
                timestamp=start_time.isoformat(),
                duration_seconds=0.0,
                parameters=rule.parameters
            )
            
            # Perform the action
            success = await self._execute_heal_action(rule, metrics)
            
            # Update attempt record
            end_time = datetime.now()
            attempt.duration_seconds = (end_time - start_time).total_seconds()
            attempt.status = "success" if success else "failed"
            attempt.message = "Healing action completed" if success else "Healing action failed"
            
            # Store attempt
            self.heal_attempts.append(attempt)
            
            # Send alert if failed
            if not success and self.alert_manager:
                await self.alert_manager.send_alert(
                    level="warning",
                    message=f"Healing action failed for rule: {rule.name}",
                    component=attempt.component,
                    metadata={
                        "rule_id": rule.id,
                        "action": rule.action.value,
                        "attempt_id": attempt.id
                    }
                )
            
            logger.info(f"Healing action {'succeeded' if success else 'failed'}: {rule.name}")
            return attempt
            
        except Exception as e:
            logger.error(f"Error performing heal action: {e}")
            return None
    
    async def _execute_heal_action(
        self,
        rule: HealRule,
        metrics: Dict[str, Any]
    ) -> bool:
        """Execute the actual healing action"""
        try:
            action = rule.action
            parameters = rule.parameters
            
            if action == HealAction.RESTART_SERVICE:
                return await self._restart_service(parameters)
            
            elif action == HealAction.CLEAR_CACHE:
                return await self._clear_cache(parameters)
            
            elif action == HealAction.SCALE_RESOURCES:
                return await self._scale_resources(parameters)
            
            elif action == HealAction.ROLLBACK_CHANGES:
                return await self._rollback_changes(parameters)
            
            elif action == HealAction.ISOLATE_COMPONENT:
                return await self._isolate_component(parameters)
            
            elif action == HealAction.NOTIFY_ADMIN:
                return await self._notify_admin(parameters)
            
            elif action == HealAction.CUSTOM_ACTION:
                return await self._execute_custom_action(parameters)
            
            else:
                logger.warning(f"Unknown healing action: {action}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing heal action: {e}")
            return False
    
    async def _restart_service(self, parameters: Dict[str, Any]) -> bool:
        """Restart a service"""
        try:
            service_name = parameters.get("service_name", "auto_detect")
            
            # Mock service restart
            logger.info(f"Restarting service: {service_name}")
            
            # Simulate restart delay
            await asyncio.sleep(1)
            
            # Update component status
            self.component_status[service_name] = {
                "status": "running",
                "last_restart": datetime.now().isoformat(),
                "restart_count": self.component_status.get(service_name, {}).get("restart_count", 0) + 1
            }
            
            return True
            
        except Exception as e:
            logger.error(f"Error restarting service: {e}")
            return False
    
    async def _clear_cache(self, parameters: Dict[str, Any]) -> bool:
        """Clear cache"""
        try:
            cache_type = parameters.get("cache_type", "all")
            
            # Mock cache clearing
            logger.info(f"Clearing cache: {cache_type}")
            
            # Simulate cache clearing delay
            await asyncio.sleep(0.5)
            
            return True
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
    
    async def _scale_resources(self, parameters: Dict[str, Any]) -> bool:
        """Scale resources"""
        try:
            cpu_limit = parameters.get("cpu_limit")
            memory_limit = parameters.get("memory_limit")
            
            # Mock resource scaling
            logger.info(f"Scaling resources - CPU: {cpu_limit}, Memory: {memory_limit}")
            
            # Simulate scaling delay
            await asyncio.sleep(2)
            
            return True
            
        except Exception as e:
            logger.error(f"Error scaling resources: {e}")
            return False
    
    async def _rollback_changes(self, parameters: Dict[str, Any]) -> bool:
        """Rollback changes"""
        try:
            rollback_point = parameters.get("rollback_point", "last_known_good")
            
            # Mock rollback
            logger.info(f"Rolling back to: {rollback_point}")
            
            # Simulate rollback delay
            await asyncio.sleep(3)
            
            return True
            
        except Exception as e:
            logger.error(f"Error rolling back changes: {e}")
            return False
    
    async def _isolate_component(self, parameters: Dict[str, Any]) -> bool:
        """Isolate a component"""
        try:
            isolation_level = parameters.get("isolation_level", "partial")
            component = parameters.get("component", "auto_detect")
            
            # Mock component isolation
            logger.info(f"Isolating component {component} with level: {isolation_level}")
            
            # Simulate isolation delay
            await asyncio.sleep(1)
            
            return True
            
        except Exception as e:
            logger.error(f"Error isolating component: {e}")
            return False
    
    async def _notify_admin(self, parameters: Dict[str, Any]) -> bool:
        """Notify administrator"""
        try:
            message = parameters.get("message", "System issue detected")
            priority = parameters.get("priority", "medium")
            
            # Mock admin notification
            logger.info(f"Notifying admin: {message} (Priority: {priority})")
            
            # Send alert if alert manager is available
            if self.alert_manager:
                await self.alert_manager.send_alert(
                    level="critical",
                    message=message,
                    component="auto_healer",
                    metadata={"priority": priority}
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error notifying admin: {e}")
            return False
    
    async def _execute_custom_action(self, parameters: Dict[str, Any]) -> bool:
        """Execute custom action"""
        try:
            action_name = parameters.get("action_name")
            
            if not action_name or action_name not in self.custom_actions:
                logger.warning(f"Custom action not found: {action_name}")
                return False
            
            action_func = self.custom_actions[action_name]
            
            # Execute custom action
            result = await action_func(parameters)
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"Error executing custom action: {e}")
            return False
    
    async def get_heal_rules(self) -> List[HealRule]:
        """Get all healing rules"""
        return list(self.heal_rules.values())
    
    async def get_heal_attempts(
        self,
        rule_id: str = None,
        limit: int = 100
    ) -> List[HealAttempt]:
        """Get healing attempts"""
        attempts = self.heal_attempts
        
        if rule_id:
            attempts = [a for a in attempts if a.rule_id == rule_id]
        
        # Sort by timestamp and limit
        attempts.sort(key=lambda x: x.timestamp, reverse=True)
        return attempts[:limit]
    
    async def get_component_status(self) -> Dict[str, Dict[str, Any]]:
        """Get component status"""
        return self.component_status.copy()
    
    async def get_healing_stats(self) -> Dict[str, Any]:
        """Get healing statistics"""
        try:
            total_attempts = len(self.heal_attempts)
            successful_attempts = len([a for a in self.heal_attempts if a.status == "success"])
            failed_attempts = len([a for a in self.heal_attempts if a.status == "failed"])
            
            # Recent attempts (last 24 hours)
            recent_cutoff = datetime.now() - timedelta(hours=24)
            recent_attempts = [
                a for a in self.heal_attempts
                if datetime.fromisoformat(a.timestamp) > recent_cutoff
            ]
            
            return {
                "total_attempts": total_attempts,
                "successful_attempts": successful_attempts,
                "failed_attempts": failed_attempts,
                "success_rate": successful_attempts / total_attempts if total_attempts > 0 else 0,
                "recent_attempts": len(recent_attempts),
                "active_rules": len([r for r in self.heal_rules.values() if r.enabled]),
                "total_rules": len(self.heal_rules),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting healing stats: {e}")
            return {}


# Global auto-healer instance
_auto_healer = None


def get_auto_healer() -> AutoHealer:
    """Get global auto-healer instance"""
    global _auto_healer
    if _auto_healer is None:
        _auto_healer = AutoHealer()
    return _auto_healer


# Export public API
__all__ = [
    "HealAction",
    "HealRule",
    "HealAttempt",
    "AutoHealer",
    "get_auto_healer"
]