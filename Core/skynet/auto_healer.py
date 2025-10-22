"""
Auto-Healing System for Atulya Tantra AGI
Automated problem detection, diagnosis, and resolution
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Callable, Tuple
from datetime import datetime, timedelta
from enum import Enum
import json
import traceback

from ..config.settings import settings
from ..config.logging import get_logger
from ..config.exceptions import AgentError
from ..agents import get_orchestrator, submit_task, AgentPriority
from .system_monitor import get_system_monitor, AlertLevel, HealthStatus
from .task_scheduler import get_task_scheduler, schedule_task, ScheduleType, TaskPriority

logger = get_logger(__name__)


class HealingAction(str, Enum):
    """Types of healing actions"""
    RESTART_SERVICE = "restart_service"
    CLEAR_CACHE = "clear_cache"
    FREE_MEMORY = "free_memory"
    CLEAN_DISK = "clean_disk"
    RESTART_AGENT = "restart_agent"
    SCALE_RESOURCES = "scale_resources"
    FAILOVER = "failover"
    CUSTOM = "custom"


class HealingPriority(str, Enum):
    """Healing priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class HealingRule:
    """Represents a healing rule"""
    
    def __init__(
        self,
        rule_id: str = None,
        name: str = None,
        description: str = None,
        condition: Dict[str, Any] = None,
        actions: List[Dict[str, Any]] = None,
        priority: HealingPriority = HealingPriority.NORMAL,
        enabled: bool = True,
        cooldown: int = 300,
        max_attempts: int = 3,
        metadata: Dict[str, Any] = None
    ):
        self.rule_id = rule_id or f"rule_{int(time.time())}"
        self.name = name or f"Healing Rule {self.rule_id[:8]}"
        self.description = description or ""
        self.condition = condition or {}
        self.actions = actions or []
        self.priority = priority
        self.enabled = enabled
        self.cooldown = cooldown  # seconds
        self.max_attempts = max_attempts
        self.metadata = metadata or {}
        
        self.last_triggered = None
        self.trigger_count = 0
        self.success_count = 0
        self.failure_count = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert rule to dictionary"""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "condition": self.condition,
            "actions": self.actions,
            "priority": self.priority.value,
            "enabled": self.enabled,
            "cooldown": self.cooldown,
            "max_attempts": self.max_attempts,
            "metadata": self.metadata,
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
            "trigger_count": self.trigger_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count
        }


class HealingSession:
    """Represents a healing session"""
    
    def __init__(
        self,
        session_id: str = None,
        rule_id: str = None,
        trigger_reason: str = None,
        priority: HealingPriority = HealingPriority.NORMAL,
        metadata: Dict[str, Any] = None
    ):
        self.session_id = session_id or f"healing_{int(time.time())}"
        self.rule_id = rule_id
        self.trigger_reason = trigger_reason or "Unknown"
        self.priority = priority
        self.metadata = metadata or {}
        
        self.status = "pending"
        self.started_at = datetime.utcnow()
        self.completed_at = None
        self.actions_executed = []
        self.results = {}
        self.success = False
        self.error = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary"""
        return {
            "session_id": self.session_id,
            "rule_id": self.rule_id,
            "trigger_reason": self.trigger_reason,
            "priority": self.priority.value,
            "metadata": self.metadata,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "actions_executed": self.actions_executed,
            "results": self.results,
            "success": self.success,
            "error": self.error
        }


class AutoHealer:
    """Automated healing system for system issues"""
    
    def __init__(self):
        self.healing_rules: Dict[str, HealingRule] = {}
        self.healing_sessions: List[HealingSession] = []
        self.is_monitoring = False
        self.monitoring_task: Optional[asyncio.Task] = None
        self.healing_actions: Dict[str, Callable] = {}
        
        # Initialize default healing rules
        self._initialize_default_rules()
        
        # Initialize healing actions
        self._initialize_healing_actions()
    
    def _initialize_default_rules(self):
        """Initialize default healing rules"""
        # High CPU usage rule
        self.add_healing_rule(
            name="High CPU Usage",
            description="Heal high CPU usage by clearing caches and restarting services",
            condition={
                "type": "metric_threshold",
                "metric": "cpu_usage_percent",
                "operator": ">",
                "value": 85.0,
                "duration": 300  # 5 minutes
            },
            actions=[
                {"type": "clear_cache", "params": {}},
                {"type": "restart_service", "params": {"service": "low_priority"}},
                {"type": "free_memory", "params": {}}
            ],
            priority=HealingPriority.HIGH,
            cooldown=600
        )
        
        # High memory usage rule
        self.add_healing_rule(
            name="High Memory Usage",
            description="Heal high memory usage by freeing memory and clearing caches",
            condition={
                "type": "metric_threshold",
                "metric": "memory_usage_percent",
                "operator": ">",
                "value": 90.0,
                "duration": 180  # 3 minutes
            },
            actions=[
                {"type": "free_memory", "params": {}},
                {"type": "clear_cache", "params": {}},
                {"type": "restart_agent", "params": {"agent_type": "non_critical"}}
            ],
            priority=HealingPriority.CRITICAL,
            cooldown=300
        )
        
        # Disk space rule
        self.add_healing_rule(
            name="Low Disk Space",
            description="Heal low disk space by cleaning temporary files",
            condition={
                "type": "metric_threshold",
                "metric": "disk_usage_percent",
                "operator": ">",
                "value": 95.0,
                "duration": 60  # 1 minute
            },
            actions=[
                {"type": "clean_disk", "params": {"clean_logs": True, "clean_temp": True}},
                {"type": "clear_cache", "params": {}}
            ],
            priority=HealingPriority.CRITICAL,
            cooldown=1800
        )
        
        # Agent failure rule
        self.add_healing_rule(
            name="Agent Failure",
            description="Heal failed agents by restarting them",
            condition={
                "type": "health_check",
                "check": "agent_system",
                "status": "critical",
                "duration": 120  # 2 minutes
            },
            actions=[
                {"type": "restart_agent", "params": {"agent_type": "failed"}},
                {"type": "clear_cache", "params": {}}
            ],
            priority=HealingPriority.HIGH,
            cooldown=300
        )
        
        # Database connectivity rule
        self.add_healing_rule(
            name="Database Connectivity",
            description="Heal database connectivity issues",
            condition={
                "type": "health_check",
                "check": "database_connectivity",
                "status": "critical",
                "duration": 60  # 1 minute
            },
            actions=[
                {"type": "restart_service", "params": {"service": "database"}},
                {"type": "failover", "params": {"service": "database"}}
            ],
            priority=HealingPriority.CRITICAL,
            cooldown=600
        )
    
    def _initialize_healing_actions(self):
        """Initialize healing action handlers"""
        self.healing_actions.update({
            "restart_service": self._action_restart_service,
            "clear_cache": self._action_clear_cache,
            "free_memory": self._action_free_memory,
            "clean_disk": self._action_clean_disk,
            "restart_agent": self._action_restart_agent,
            "scale_resources": self._action_scale_resources,
            "failover": self._action_failover
        })
    
    async def start_monitoring(self):
        """Start auto-healing monitoring"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Auto-healing monitoring started")
    
    async def stop_monitoring(self):
        """Stop auto-healing monitoring"""
        self.is_monitoring = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Auto-healing monitoring stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop for healing triggers"""
        while self.is_monitoring:
            try:
                # Check for healing triggers
                await self._check_healing_triggers()
                
                # Wait before next check
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in healing monitoring loop: {e}")
                await asyncio.sleep(60)
    
    async def _check_healing_triggers(self):
        """Check for conditions that trigger healing"""
        try:
            # Get system health and metrics
            system_monitor = await get_system_monitor()
            health_status = await system_monitor.get_system_health()
            recent_metrics = await system_monitor.get_metrics(limit=10)
            
            # Check each healing rule
            for rule_id, rule in self.healing_rules.items():
                if not rule.enabled:
                    continue
                
                # Check cooldown
                if rule.last_triggered:
                    time_since_last = datetime.utcnow() - rule.last_triggered
                    if time_since_last.total_seconds() < rule.cooldown:
                        continue
                
                # Check if rule condition is met
                if await self._evaluate_condition(rule.condition, health_status, recent_metrics):
                    await self._trigger_healing(rule)
                
        except Exception as e:
            logger.error(f"Error checking healing triggers: {e}")
    
    async def _evaluate_condition(
        self, 
        condition: Dict[str, Any], 
        health_status: Dict[str, Any], 
        metrics: List[Dict[str, Any]]
    ) -> bool:
        """Evaluate a healing condition"""
        try:
            condition_type = condition.get("type")
            
            if condition_type == "metric_threshold":
                return await self._evaluate_metric_threshold(condition, metrics)
            
            elif condition_type == "health_check":
                return await self._evaluate_health_check(condition, health_status)
            
            elif condition_type == "custom":
                return await self._evaluate_custom_condition(condition)
            
            return False
            
        except Exception as e:
            logger.error(f"Error evaluating condition: {e}")
            return False
    
    async def _evaluate_metric_threshold(
        self, 
        condition: Dict[str, Any], 
        metrics: List[Dict[str, Any]]
    ) -> bool:
        """Evaluate metric threshold condition"""
        try:
            metric_name = condition.get("metric")
            operator = condition.get("operator", ">")
            threshold_value = condition.get("value")
            duration = condition.get("duration", 60)
            
            # Find recent metrics for this metric name
            recent_metrics = [
                m for m in metrics 
                if m.get("name") == metric_name
            ]
            
            if not recent_metrics:
                return False
            
            # Check if threshold is exceeded for the specified duration
            cutoff_time = datetime.utcnow() - timedelta(seconds=duration)
            
            threshold_exceeded_count = 0
            for metric in recent_metrics:
                metric_time = datetime.fromisoformat(metric["timestamp"])
                if metric_time >= cutoff_time:
                    metric_value = metric["value"]
                    
                    if operator == ">" and metric_value > threshold_value:
                        threshold_exceeded_count += 1
                    elif operator == ">=" and metric_value >= threshold_value:
                        threshold_exceeded_count += 1
                    elif operator == "<" and metric_value < threshold_value:
                        threshold_exceeded_count += 1
                    elif operator == "<=" and metric_value <= threshold_value:
                        threshold_exceeded_count += 1
            
            # Consider condition met if threshold exceeded for most of the duration
            return threshold_exceeded_count >= len(recent_metrics) * 0.8
            
        except Exception as e:
            logger.error(f"Error evaluating metric threshold: {e}")
            return False
    
    async def _evaluate_health_check(
        self, 
        condition: Dict[str, Any], 
        health_status: Dict[str, Any]
    ) -> bool:
        """Evaluate health check condition"""
        try:
            check_name = condition.get("check")
            expected_status = condition.get("status")
            duration = condition.get("duration", 60)
            
            # Check if the health check has the expected status
            checks = health_status.get("checks", {})
            if check_name in checks:
                check_status = checks[check_name].get("status")
                return check_status == expected_status
            
            return False
            
        except Exception as e:
            logger.error(f"Error evaluating health check: {e}")
            return False
    
    async def _evaluate_custom_condition(self, condition: Dict[str, Any]) -> bool:
        """Evaluate custom condition"""
        try:
            # This would allow for custom condition evaluation
            # For now, return False as a placeholder
            return False
            
        except Exception as e:
            logger.error(f"Error evaluating custom condition: {e}")
            return False
    
    async def _trigger_healing(self, rule: HealingRule):
        """Trigger healing for a rule"""
        try:
            logger.warning(f"Triggering healing for rule: {rule.name}")
            
            # Update rule statistics
            rule.last_triggered = datetime.utcnow()
            rule.trigger_count += 1
            
            # Create healing session
            session = HealingSession(
                rule_id=rule.rule_id,
                trigger_reason=f"Rule condition met: {rule.name}",
                priority=rule.priority,
                metadata={"rule": rule.to_dict()}
            )
            
            self.healing_sessions.append(session)
            
            # Execute healing actions
            await self._execute_healing_session(session, rule)
            
        except Exception as e:
            logger.error(f"Error triggering healing: {e}")
    
    async def _execute_healing_session(self, session: HealingSession, rule: HealingRule):
        """Execute a healing session"""
        try:
            session.status = "running"
            
            logger.info(f"Starting healing session: {session.session_id}")
            
            # Execute each action in sequence
            for action_config in rule.actions:
                try:
                    action_type = action_config.get("type")
                    action_params = action_config.get("params", {})
                    
                    if action_type in self.healing_actions:
                        action_handler = self.healing_actions[action_type]
                        result = await action_handler(action_params)
                        
                        session.actions_executed.append({
                            "type": action_type,
                            "params": action_params,
                            "result": result,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        
                        logger.info(f"Executed healing action: {action_type}")
                        
                    else:
                        logger.warning(f"Unknown healing action: {action_type}")
                        
                except Exception as e:
                    logger.error(f"Error executing healing action {action_type}: {e}")
                    session.actions_executed.append({
                        "type": action_type,
                        "params": action_config.get("params", {}),
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat()
                    })
            
            # Mark session as completed
            session.status = "completed"
            session.completed_at = datetime.utcnow()
            session.success = True
            
            # Update rule statistics
            rule.success_count += 1
            
            logger.info(f"Completed healing session: {session.session_id}")
            
        except Exception as e:
            logger.error(f"Error executing healing session: {e}")
            
            session.status = "failed"
            session.completed_at = datetime.utcnow()
            session.success = False
            session.error = str(e)
            
            # Update rule statistics
            rule.failure_count += 1
    
    # Healing action implementations
    async def _action_restart_service(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Restart a service"""
        try:
            service = params.get("service", "general")
            
            logger.info(f"Restarting service: {service}")
            
            # This would integrate with actual service management
            # For now, simulate the action
            await asyncio.sleep(2)
            
            return {
                "success": True,
                "message": f"Service {service} restarted successfully",
                "service": service
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "service": params.get("service", "unknown")
            }
    
    async def _action_clear_cache(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Clear system caches"""
        try:
            logger.info("Clearing system caches")
            
            # This would clear actual caches
            # For now, simulate the action
            await asyncio.sleep(1)
            
            return {
                "success": True,
                "message": "Caches cleared successfully",
                "cache_size_freed": "256 MB"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _action_free_memory(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Free up memory"""
        try:
            logger.info("Freeing up memory")
            
            # This would perform actual memory cleanup
            # For now, simulate the action
            await asyncio.sleep(1)
            
            return {
                "success": True,
                "message": "Memory freed successfully",
                "memory_freed": "512 MB"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _action_clean_disk(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Clean disk space"""
        try:
            clean_logs = params.get("clean_logs", True)
            clean_temp = params.get("clean_temp", True)
            
            logger.info(f"Cleaning disk space (logs: {clean_logs}, temp: {clean_temp})")
            
            # This would perform actual disk cleanup
            # For now, simulate the action
            await asyncio.sleep(3)
            
            return {
                "success": True,
                "message": "Disk cleaned successfully",
                "space_freed": "1.2 GB",
                "files_removed": 45
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _action_restart_agent(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Restart an agent"""
        try:
            agent_type = params.get("agent_type", "general")
            
            logger.info(f"Restarting agent: {agent_type}")
            
            # This would restart the actual agent
            # For now, simulate the action
            await asyncio.sleep(2)
            
            return {
                "success": True,
                "message": f"Agent {agent_type} restarted successfully",
                "agent_type": agent_type
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "agent_type": params.get("agent_type", "unknown")
            }
    
    async def _action_scale_resources(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Scale system resources"""
        try:
            scale_factor = params.get("scale_factor", 1.5)
            
            logger.info(f"Scaling resources by factor: {scale_factor}")
            
            # This would scale actual resources
            # For now, simulate the action
            await asyncio.sleep(2)
            
            return {
                "success": True,
                "message": f"Resources scaled by factor {scale_factor}",
                "scale_factor": scale_factor
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _action_failover(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Perform failover"""
        try:
            service = params.get("service", "general")
            
            logger.info(f"Performing failover for service: {service}")
            
            # This would perform actual failover
            # For now, simulate the action
            await asyncio.sleep(3)
            
            return {
                "success": True,
                "message": f"Failover completed for service {service}",
                "service": service
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "service": params.get("service", "unknown")
            }
    
    def add_healing_rule(
        self,
        name: str,
        description: str = None,
        condition: Dict[str, Any] = None,
        actions: List[Dict[str, Any]] = None,
        priority: HealingPriority = HealingPriority.NORMAL,
        cooldown: int = 300,
        max_attempts: int = 3,
        enabled: bool = True
    ) -> str:
        """Add a healing rule"""
        rule = HealingRule(
            name=name,
            description=description,
            condition=condition,
            actions=actions,
            priority=priority,
            cooldown=cooldown,
            max_attempts=max_attempts,
            enabled=enabled
        )
        
        self.healing_rules[rule.rule_id] = rule
        logger.info(f"Added healing rule: {name}")
        return rule.rule_id
    
    def remove_healing_rule(self, rule_id: str) -> bool:
        """Remove a healing rule"""
        if rule_id in self.healing_rules:
            del self.healing_rules[rule_id]
            logger.info(f"Removed healing rule: {rule_id}")
            return True
        return False
    
    def enable_healing_rule(self, rule_id: str) -> bool:
        """Enable a healing rule"""
        if rule_id in self.healing_rules:
            self.healing_rules[rule_id].enabled = True
            logger.info(f"Enabled healing rule: {rule_id}")
            return True
        return False
    
    def disable_healing_rule(self, rule_id: str) -> bool:
        """Disable a healing rule"""
        if rule_id in self.healing_rules:
            self.healing_rules[rule_id].enabled = False
            logger.info(f"Disabled healing rule: {rule_id}")
            return True
        return False
    
    async def get_healing_status(self) -> Dict[str, Any]:
        """Get auto-healing status"""
        try:
            active_sessions = len([s for s in self.healing_sessions if s.status == "running"])
            total_rules = len(self.healing_rules)
            enabled_rules = len([r for r in self.healing_rules.values() if r.enabled])
            
            recent_sessions = self.healing_sessions[-10:] if self.healing_sessions else []
            
            return {
                "monitoring_active": self.is_monitoring,
                "total_rules": total_rules,
                "enabled_rules": enabled_rules,
                "active_sessions": active_sessions,
                "recent_sessions": [s.to_dict() for s in recent_sessions],
                "rules": [r.to_dict() for r in self.healing_rules.values()]
            }
            
        except Exception as e:
            logger.error(f"Error getting healing status: {e}")
            return {"error": str(e)}
    
    async def trigger_manual_healing(
        self, 
        rule_id: str, 
        reason: str = "Manual trigger"
    ) -> str:
        """Manually trigger healing for a rule"""
        try:
            if rule_id not in self.healing_rules:
                raise AgentError(f"Healing rule not found: {rule_id}")
            
            rule = self.healing_rules[rule_id]
            
            # Create healing session
            session = HealingSession(
                rule_id=rule_id,
                trigger_reason=reason,
                priority=rule.priority,
                metadata={"manual_trigger": True}
            )
            
            self.healing_sessions.append(session)
            
            # Execute healing session
            await self._execute_healing_session(session, rule)
            
            return session.session_id
            
        except Exception as e:
            logger.error(f"Error triggering manual healing: {e}")
            raise AgentError(f"Manual healing failed: {e}")


# Global auto-healer instance
_auto_healer: Optional[AutoHealer] = None


async def get_auto_healer() -> AutoHealer:
    """Get global auto-healer instance"""
    global _auto_healer
    
    if _auto_healer is None:
        _auto_healer = AutoHealer()
        await _auto_healer.start_monitoring()
    
    return _auto_healer


async def get_healing_status() -> Dict[str, Any]:
    """Get auto-healing status"""
    healer = await get_auto_healer()
    return await healer.get_healing_status()


async def trigger_manual_healing(rule_id: str, reason: str = "Manual trigger") -> str:
    """Manually trigger healing"""
    healer = await get_auto_healer()
    return await healer.trigger_manual_healing(rule_id, reason)


# Export public API
__all__ = [
    "HealingAction",
    "HealingPriority",
    "HealingRule",
    "HealingSession",
    "AutoHealer",
    "get_auto_healer",
    "get_healing_status",
    "trigger_manual_healing"
]
