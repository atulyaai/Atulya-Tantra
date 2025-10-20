"""
Atulya Tantra - Skynet Safety System
Version: 2.5.0
Implements safety constraints and security measures for autonomous operations
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Callable, Set
from datetime import datetime, timedelta
from enum import Enum
import json
import hashlib

logger = logging.getLogger(__name__)

class SafetyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ActionType(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    NETWORK = "network"
    SYSTEM = "system"

class SafetyViolation(str, Enum):
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DESTRUCTIVE_ACTION = "destructive_action"
    RESOURCE_ABUSE = "resource_abuse"
    DATA_BREACH = "data_breach"
    SYSTEM_COMPROMISE = "system_compromise"

@dataclass
class SafetyRule:
    """Represents a safety rule"""
    rule_id: str
    name: str
    description: str
    action_types: List[ActionType]
    safety_level: SafetyLevel
    conditions: Dict[str, Any]
    enforcement: str  # "block", "warn", "log"
    created_at: datetime

@dataclass
class SafetyEvent:
    """Represents a safety event"""
    event_id: str
    timestamp: datetime
    rule_id: str
    action_type: ActionType
    safety_level: SafetyLevel
    violation_type: SafetyViolation
    details: Dict[str, Any]
    user_id: Optional[str]
    agent_id: Optional[str]
    blocked: bool

class SafetySystem:
    """
    Implements comprehensive safety constraints for autonomous operations
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.safety_rules: Dict[str, SafetyRule] = {}
        self.safety_events: List[SafetyEvent] = []
        self.blocked_actions: Set[str] = set()
        self.user_permissions: Dict[str, Set[str]] = {}
        self.agent_permissions: Dict[str, Set[str]] = {}
        
        self._safety_lock = asyncio.Lock()
        self._event_handlers: List[Callable] = []
        
        # Initialize default safety rules
        self._initialize_default_rules()
        
        logger.info("SafetySystem initialized with %d default rules", len(self.safety_rules))
    
    def _initialize_default_rules(self):
        """Initialize default safety rules"""
        default_rules = [
            {
                "rule_id": "no_file_deletion",
                "name": "Prevent File Deletion",
                "description": "Block deletion of important system files",
                "action_types": [ActionType.DELETE],
                "safety_level": SafetyLevel.HIGH,
                "conditions": {
                    "file_patterns": ["*.exe", "*.dll", "*.sys", "*.ini", "*.cfg"],
                    "system_directories": ["C:\\Windows", "/etc", "/usr/bin"]
                },
                "enforcement": "block"
            },
            {
                "rule_id": "no_system_modification",
                "name": "Prevent System Modification",
                "description": "Block modification of system files and registry",
                "action_types": [ActionType.WRITE, ActionType.EXECUTE],
                "safety_level": SafetyLevel.CRITICAL,
                "conditions": {
                    "system_paths": ["C:\\Windows\\System32", "/etc", "/usr/bin"],
                    "registry_keys": ["HKEY_LOCAL_MACHINE", "HKEY_CURRENT_USER"]
                },
                "enforcement": "block"
            },
            {
                "rule_id": "network_access_control",
                "name": "Network Access Control",
                "description": "Control network access and external connections",
                "action_types": [ActionType.NETWORK],
                "safety_level": SafetyLevel.MEDIUM,
                "conditions": {
                    "allowed_domains": ["api.openai.com", "api.anthropic.com"],
                    "blocked_ports": [22, 23, 135, 139, 445]
                },
                "enforcement": "warn"
            },
            {
                "rule_id": "resource_limits",
                "name": "Resource Usage Limits",
                "description": "Limit resource usage to prevent system overload",
                "action_types": [ActionType.SYSTEM],
                "safety_level": SafetyLevel.MEDIUM,
                "conditions": {
                    "max_cpu_usage": 80,
                    "max_memory_usage": 80,
                    "max_disk_usage": 90
                },
                "enforcement": "warn"
            }
        ]
        
        for rule_data in default_rules:
            rule = SafetyRule(
                rule_id=rule_data["rule_id"],
                name=rule_data["name"],
                description=rule_data["description"],
                action_types=rule_data["action_types"],
                safety_level=rule_data["safety_level"],
                conditions=rule_data["conditions"],
                enforcement=rule_data["enforcement"],
                created_at=datetime.now()
            )
            self.safety_rules[rule.rule_id] = rule
    
    async def check_action_safety(
        self,
        action_type: ActionType,
        action_data: Dict[str, Any],
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check if an action is safe to perform
        
        Args:
            action_type: Type of action to check
            action_data: Data about the action
            user_id: ID of the user performing the action
            agent_id: ID of the agent performing the action
            
        Returns:
            Safety check result
        """
        async with self._safety_lock:
            violations = []
            blocked = False
            
            # Check against all applicable rules
            for rule in self.safety_rules.values():
                if action_type in rule.action_types:
                    violation = await self._check_rule_violation(rule, action_type, action_data)
                    if violation:
                        violations.append(violation)
                        
                        # Check enforcement level
                        if rule.enforcement == "block":
                            blocked = True
                        elif rule.enforcement == "warn" and rule.safety_level in [SafetyLevel.HIGH, SafetyLevel.CRITICAL]:
                            blocked = True
            
            # Check user permissions
            if user_id and not await self._check_user_permissions(user_id, action_type, action_data):
                violations.append({
                    "type": SafetyViolation.UNAUTHORIZED_ACCESS,
                    "message": f"User {user_id} lacks permission for {action_type.value} action"
                })
                blocked = True
            
            # Check agent permissions
            if agent_id and not await self._check_agent_permissions(agent_id, action_type, action_data):
                violations.append({
                    "type": SafetyViolation.UNAUTHORIZED_ACCESS,
                    "message": f"Agent {agent_id} lacks permission for {action_type.value} action"
                })
                blocked = True
            
            # Create safety event
            if violations:
                event = await self._create_safety_event(
                    action_type, violations, user_id, agent_id, blocked
                )
                self.safety_events.append(event)
                
                # Notify event handlers
                await self._notify_event_handlers(event)
            
            return {
                "safe": not blocked,
                "violations": violations,
                "blocked": blocked,
                "recommendations": await self._get_safety_recommendations(action_type, action_data)
            }
    
    async def _check_rule_violation(
        self,
        rule: SafetyRule,
        action_type: ActionType,
        action_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Check if an action violates a specific rule"""
        conditions = rule.conditions
        
        if action_type == ActionType.DELETE:
            # Check file deletion rules
            file_path = action_data.get("file_path", "")
            if file_path:
                # Check against blocked file patterns
                blocked_patterns = conditions.get("file_patterns", [])
                for pattern in blocked_patterns:
                    if self._match_pattern(file_path, pattern):
                        return {
                            "type": SafetyViolation.DESTRUCTIVE_ACTION,
                            "message": f"Deletion of {file_path} blocked by pattern {pattern}",
                            "rule_id": rule.rule_id,
                            "safety_level": rule.safety_level
                        }
                
                # Check against system directories
                system_dirs = conditions.get("system_directories", [])
                for sys_dir in system_dirs:
                    if file_path.startswith(sys_dir):
                        return {
                            "type": SafetyViolation.DESTRUCTIVE_ACTION,
                            "message": f"Deletion from system directory {sys_dir} blocked",
                            "rule_id": rule.rule_id,
                            "safety_level": rule.safety_level
                        }
        
        elif action_type == ActionType.WRITE:
            # Check file write rules
            file_path = action_data.get("file_path", "")
            if file_path:
                system_paths = conditions.get("system_paths", [])
                for sys_path in system_paths:
                    if file_path.startswith(sys_path):
                        return {
                            "type": SafetyViolation.SYSTEM_COMPROMISE,
                            "message": f"Write to system path {sys_path} blocked",
                            "rule_id": rule.rule_id,
                            "safety_level": rule.safety_level
                        }
        
        elif action_type == ActionType.NETWORK:
            # Check network access rules
            url = action_data.get("url", "")
            if url:
                allowed_domains = conditions.get("allowed_domains", [])
                if not any(domain in url for domain in allowed_domains):
                    return {
                        "type": SafetyViolation.UNAUTHORIZED_ACCESS,
                        "message": f"Network access to {url} not allowed",
                        "rule_id": rule.rule_id,
                        "safety_level": rule.safety_level
                    }
        
        elif action_type == ActionType.SYSTEM:
            # Check resource usage rules
            cpu_usage = action_data.get("cpu_usage", 0)
            memory_usage = action_data.get("memory_usage", 0)
            disk_usage = action_data.get("disk_usage", 0)
            
            max_cpu = conditions.get("max_cpu_usage", 100)
            max_memory = conditions.get("max_memory_usage", 100)
            max_disk = conditions.get("max_disk_usage", 100)
            
            if cpu_usage > max_cpu or memory_usage > max_memory or disk_usage > max_disk:
                return {
                    "type": SafetyViolation.RESOURCE_ABUSE,
                    "message": f"Resource usage exceeds limits (CPU: {cpu_usage}%, Memory: {memory_usage}%, Disk: {disk_usage}%)",
                    "rule_id": rule.rule_id,
                    "safety_level": rule.safety_level
                }
        
        return None
    
    def _match_pattern(self, file_path: str, pattern: str) -> bool:
        """Simple pattern matching for file paths"""
        import fnmatch
        return fnmatch.fnmatch(file_path.lower(), pattern.lower())
    
    async def _check_user_permissions(
        self,
        user_id: str,
        action_type: ActionType,
        action_data: Dict[str, Any]
    ) -> bool:
        """Check if user has permission for the action"""
        user_perms = self.user_permissions.get(user_id, set())
        
        # Check if user has permission for this action type
        if action_type.value not in user_perms:
            return False
        
        # Additional permission checks based on action data
        if action_type == ActionType.SYSTEM:
            # System actions require special permission
            return "system_access" in user_perms
        
        return True
    
    async def _check_agent_permissions(
        self,
        agent_id: str,
        action_type: ActionType,
        action_data: Dict[str, Any]
    ) -> bool:
        """Check if agent has permission for the action"""
        agent_perms = self.agent_permissions.get(agent_id, set())
        
        # Check if agent has permission for this action type
        if action_type.value not in agent_perms:
            return False
        
        # Additional permission checks based on action data
        if action_type == ActionType.SYSTEM:
            # System actions require special permission
            return "system_access" in agent_perms
        
        return True
    
    async def _create_safety_event(
        self,
        action_type: ActionType,
        violations: List[Dict[str, Any]],
        user_id: Optional[str],
        agent_id: Optional[str],
        blocked: bool
    ) -> SafetyEvent:
        """Create a safety event"""
        event_id = hashlib.md5(f"{datetime.now().isoformat()}{action_type.value}".encode()).hexdigest()
        
        # Determine highest safety level from violations
        safety_level = SafetyLevel.LOW
        for violation in violations:
            if violation.get("safety_level") == SafetyLevel.CRITICAL:
                safety_level = SafetyLevel.CRITICAL
                break
            elif violation.get("safety_level") == SafetyLevel.HIGH:
                safety_level = SafetyLevel.HIGH
            elif violation.get("safety_level") == SafetyLevel.MEDIUM:
                safety_level = SafetyLevel.MEDIUM
        
        # Determine violation type
        violation_type = SafetyViolation.UNAUTHORIZED_ACCESS
        for violation in violations:
            if violation.get("type"):
                violation_type = violation["type"]
                break
        
        event = SafetyEvent(
            event_id=event_id,
            timestamp=datetime.now(),
            rule_id=violations[0].get("rule_id", "unknown") if violations else "unknown",
            action_type=action_type,
            safety_level=safety_level,
            violation_type=violation_type,
            details={
                "violations": violations,
                "action_data": action_data
            },
            user_id=user_id,
            agent_id=agent_id,
            blocked=blocked
        )
        
        return event
    
    async def _notify_event_handlers(self, event: SafetyEvent):
        """Notify registered event handlers"""
        for handler in self._event_handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error("Error in safety event handler: %s", e)
    
    async def _get_safety_recommendations(
        self,
        action_type: ActionType,
        action_data: Dict[str, Any]
    ) -> List[str]:
        """Get safety recommendations for an action"""
        recommendations = []
        
        if action_type == ActionType.DELETE:
            recommendations.append("Consider moving files to trash instead of permanent deletion")
            recommendations.append("Create a backup before deleting important files")
        
        elif action_type == ActionType.SYSTEM:
            recommendations.append("Monitor system resources during operation")
            recommendations.append("Implement gradual resource allocation")
        
        elif action_type == ActionType.NETWORK:
            recommendations.append("Use secure connections (HTTPS) when possible")
            recommendations.append("Validate SSL certificates")
        
        return recommendations
    
    async def add_safety_rule(self, rule: SafetyRule):
        """Add a new safety rule"""
        async with self._safety_lock:
            self.safety_rules[rule.rule_id] = rule
            logger.info("Added safety rule: %s", rule.rule_id)
    
    async def remove_safety_rule(self, rule_id: str):
        """Remove a safety rule"""
        async with self._safety_lock:
            if rule_id in self.safety_rules:
                del self.safety_rules[rule_id]
                logger.info("Removed safety rule: %s", rule_id)
    
    async def grant_user_permission(self, user_id: str, permission: str):
        """Grant permission to a user"""
        if user_id not in self.user_permissions:
            self.user_permissions[user_id] = set()
        self.user_permissions[user_id].add(permission)
        logger.info("Granted permission %s to user %s", permission, user_id)
    
    async def revoke_user_permission(self, user_id: str, permission: str):
        """Revoke permission from a user"""
        if user_id in self.user_permissions:
            self.user_permissions[user_id].discard(permission)
            logger.info("Revoked permission %s from user %s", permission, user_id)
    
    async def grant_agent_permission(self, agent_id: str, permission: str):
        """Grant permission to an agent"""
        if agent_id not in self.agent_permissions:
            self.agent_permissions[agent_id] = set()
        self.agent_permissions[agent_id].add(permission)
        logger.info("Granted permission %s to agent %s", permission, agent_id)
    
    async def revoke_agent_permission(self, agent_id: str, permission: str):
        """Revoke permission from an agent"""
        if agent_id in self.agent_permissions:
            self.agent_permissions[agent_id].discard(permission)
            logger.info("Revoked permission %s from agent %s", permission, agent_id)
    
    def add_event_handler(self, handler: Callable):
        """Add a safety event handler"""
        self._event_handlers.append(handler)
    
    async def get_safety_events(
        self,
        limit: int = 100,
        safety_level: Optional[SafetyLevel] = None,
        hours: int = 24
    ) -> List[SafetyEvent]:
        """Get safety events with optional filtering"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        events = [e for e in self.safety_events if e.timestamp >= cutoff_time]
        
        if safety_level:
            events = [e for e in events if e.safety_level == safety_level]
        
        # Sort by timestamp (newest first)
        events.sort(key=lambda x: x.timestamp, reverse=True)
        
        return events[:limit]
    
    async def health_check(self) -> Dict[str, Any]:
        """Get safety system health status"""
        return {
            "safety_system": True,
            "total_rules": len(self.safety_rules),
            "total_events": len(self.safety_events),
            "blocked_actions": len(self.blocked_actions),
            "users_with_permissions": len(self.user_permissions),
            "agents_with_permissions": len(self.agent_permissions),
            "event_handlers": len(self._event_handlers)
        }


# Global safety system instance (permission grants moved to app startup)
safety_system = SafetySystem()
