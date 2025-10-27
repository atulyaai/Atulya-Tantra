"""
Alerting System for Atulya Tantra AGI
Handles system alerts and notifications
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from ..config.logging import get_logger
from ..config.exceptions import SystemError, ValidationError

logger = get_logger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


@dataclass
class Alert:
    """Alert definition"""
    id: str
    level: AlertLevel
    message: str
    component: str
    status: AlertStatus
    created_at: str
    updated_at: str
    resolved_at: Optional[str]
    metadata: Dict[str, Any]
    user_id: Optional[str]


@dataclass
class AlertRule:
    """Alert rule definition"""
    id: str
    name: str
    condition: str
    level: AlertLevel
    enabled: bool
    cooldown_seconds: int
    max_alerts_per_hour: int
    notification_channels: List[str]
    created_at: str
    updated_at: str


class AlertManager:
    """Alert management system"""
    
    def __init__(self):
        self.alerts: Dict[str, Alert] = {}
        self.alert_rules: Dict[str, AlertRule] = {}
        self.notification_channels: Dict[str, Callable] = {}
        
        # Alert suppression
        self.suppressed_alerts: Dict[str, datetime] = {}
        
        # Initialize default rules
        self._initialize_default_rules()
        
        logger.info("Initialized Alert Manager")
    
    def _initialize_default_rules(self):
        """Initialize default alert rules"""
        try:
            # High CPU usage alert
            self.add_alert_rule(
                id="high_cpu_usage",
                name="High CPU Usage",
                condition="cpu_usage > 90",
                level=AlertLevel.WARNING,
                cooldown_seconds=300,
                max_alerts_per_hour=3,
                notification_channels=["log", "email"]
            )
            
            # High memory usage alert
            self.add_alert_rule(
                id="high_memory_usage",
                name="High Memory Usage",
                condition="memory_usage > 95",
                level=AlertLevel.ERROR,
                cooldown_seconds=300,
                max_alerts_per_hour=3,
                notification_channels=["log", "email", "slack"]
            )
            
            # Service down alert
            self.add_alert_rule(
                id="service_down",
                name="Service Down",
                condition="service_status == 'down'",
                level=AlertLevel.CRITICAL,
                cooldown_seconds=60,
                max_alerts_per_hour=10,
                notification_channels=["log", "email", "slack", "pagerduty"]
            )
            
            # Error rate alert
            self.add_alert_rule(
                id="high_error_rate",
                name="High Error Rate",
                condition="error_rate > 0.1",
                level=AlertLevel.ERROR,
                cooldown_seconds=600,
                max_alerts_per_hour=5,
                notification_channels=["log", "email"]
            )
            
            # Disk space alert
            self.add_alert_rule(
                id="low_disk_space",
                name="Low Disk Space",
                condition="disk_usage > 90",
                level=AlertLevel.WARNING,
                cooldown_seconds=1800,
                max_alerts_per_hour=2,
                notification_channels=["log", "email"]
            )
            
            logger.info("Initialized default alert rules")
            
        except Exception as e:
            logger.error(f"Error initializing default rules: {e}")
    
    def add_alert_rule(
        self,
        id: str,
        name: str,
        condition: str,
        level: AlertLevel,
        cooldown_seconds: int = 300,
        max_alerts_per_hour: int = 5,
        notification_channels: List[str] = None,
        enabled: bool = True
    ) -> bool:
        """Add an alert rule"""
        try:
            rule = AlertRule(
                id=id,
                name=name,
                condition=condition,
                level=level,
                enabled=enabled,
                cooldown_seconds=cooldown_seconds,
                max_alerts_per_hour=max_alerts_per_hour,
                notification_channels=notification_channels or ["log"],
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
            
            self.alert_rules[id] = rule
            logger.info(f"Added alert rule: {id}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding alert rule: {e}")
            return False
    
    def update_alert_rule(
        self,
        id: str,
        **kwargs
    ) -> bool:
        """Update an alert rule"""
        try:
            if id not in self.alert_rules:
                return False
            
            rule = self.alert_rules[id]
            
            # Update allowed fields
            allowed_fields = [
                "name", "condition", "level", "enabled", "cooldown_seconds",
                "max_alerts_per_hour", "notification_channels"
            ]
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    setattr(rule, field, value)
            
            rule.updated_at = datetime.now().isoformat()
            
            logger.info(f"Updated alert rule: {id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating alert rule: {e}")
            return False
    
    def remove_alert_rule(self, id: str) -> bool:
        """Remove an alert rule"""
        try:
            if id in self.alert_rules:
                del self.alert_rules[id]
                logger.info(f"Removed alert rule: {id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error removing alert rule: {e}")
            return False
    
    def add_notification_channel(
        self,
        name: str,
        channel_func: Callable
    ) -> bool:
        """Add a notification channel"""
        try:
            self.notification_channels[name] = channel_func
            logger.info(f"Added notification channel: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding notification channel: {e}")
            return False
    
    async def send_alert(
        self,
        level: AlertLevel,
        message: str,
        component: str,
        metadata: Dict[str, Any] = None,
        user_id: str = None
    ) -> str:
        """Send an alert"""
        try:
            # Create alert
            alert_id = f"alert_{int(datetime.now().timestamp())}"
            
            alert = Alert(
                id=alert_id,
                level=level,
                message=message,
                component=component,
                status=AlertStatus.ACTIVE,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                resolved_at=None,
                metadata=metadata or {},
                user_id=user_id
            )
            
            # Store alert
            self.alerts[alert_id] = alert
            
            # Send notifications
            await self._send_notifications(alert)
            
            logger.info(f"Sent alert: {alert_id} - {message}")
            return alert_id
            
        except Exception as e:
            logger.error(f"Error sending alert: {e}")
            return ""
    
    async def _send_notifications(self, alert: Alert):
        """Send notifications for an alert"""
        try:
            # Get notification channels
            channels = ["log"]  # Default to log
            
            # Find matching rule
            for rule in self.alert_rules.values():
                if rule.enabled and self._matches_rule(alert, rule):
                    channels = rule.notification_channels
                    break
            
            # Send to each channel
            for channel_name in channels:
                if channel_name in self.notification_channels:
                    try:
                        await self.notification_channels[channel_name](alert)
                    except Exception as e:
                        logger.error(f"Error sending to channel {channel_name}: {e}")
                else:
                    # Default log channel
                    await self._log_notification(alert)
            
        except Exception as e:
            logger.error(f"Error sending notifications: {e}")
    
    def _matches_rule(self, alert: Alert, rule: AlertRule) -> bool:
        """Check if alert matches a rule"""
        try:
            # Simple matching based on component and level
            # In a real implementation, this would use the condition field
            return (
                alert.component in rule.condition or
                alert.level.value in rule.condition or
                rule.condition == "always"
            )
            
        except Exception as e:
            logger.error(f"Error matching rule: {e}")
            return False
    
    async def _log_notification(self, alert: Alert):
        """Log notification"""
        try:
            logger.warning(
                f"ALERT [{alert.level.value.upper()}] {alert.component}: {alert.message}"
            )
            
        except Exception as e:
            logger.error(f"Error logging notification: {e}")
    
    async def acknowledge_alert(self, alert_id: str, user_id: str = None) -> bool:
        """Acknowledge an alert"""
        try:
            if alert_id not in self.alerts:
                return False
            
            alert = self.alerts[alert_id]
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.updated_at = datetime.now().isoformat()
            
            if user_id:
                alert.metadata["acknowledged_by"] = user_id
            
            logger.info(f"Acknowledged alert: {alert_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error acknowledging alert: {e}")
            return False
    
    async def resolve_alert(self, alert_id: str, user_id: str = None) -> bool:
        """Resolve an alert"""
        try:
            if alert_id not in self.alerts:
                return False
            
            alert = self.alerts[alert_id]
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.now().isoformat()
            alert.updated_at = datetime.now().isoformat()
            
            if user_id:
                alert.metadata["resolved_by"] = user_id
            
            logger.info(f"Resolved alert: {alert_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error resolving alert: {e}")
            return False
    
    async def suppress_alert(
        self,
        alert_id: str,
        duration_seconds: int = 3600,
        user_id: str = None
    ) -> bool:
        """Suppress an alert"""
        try:
            if alert_id not in self.alerts:
                return False
            
            alert = self.alerts[alert_id]
            alert.status = AlertStatus.SUPPRESSED
            alert.updated_at = datetime.now().isoformat()
            
            # Set suppression expiry
            self.suppressed_alerts[alert_id] = datetime.now() + timedelta(seconds=duration_seconds)
            
            if user_id:
                alert.metadata["suppressed_by"] = user_id
                alert.metadata["suppression_duration"] = duration_seconds
            
            logger.info(f"Suppressed alert: {alert_id} for {duration_seconds} seconds")
            return True
            
        except Exception as e:
            logger.error(f"Error suppressing alert: {e}")
            return False
    
    async def get_alerts(
        self,
        level: AlertLevel = None,
        status: AlertStatus = None,
        component: str = None,
        user_id: str = None,
        limit: int = 100
    ) -> List[Alert]:
        """Get alerts with filters"""
        try:
            filtered_alerts = []
            
            for alert in self.alerts.values():
                # Check level filter
                if level and alert.level != level:
                    continue
                
                # Check status filter
                if status and alert.status != status:
                    continue
                
                # Check component filter
                if component and alert.component != component:
                    continue
                
                # Check user filter
                if user_id and alert.user_id != user_id:
                    continue
                
                filtered_alerts.append(alert)
            
            # Sort by created_at and limit
            filtered_alerts.sort(key=lambda x: x.created_at, reverse=True)
            return filtered_alerts[:limit]
            
        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
            return []
    
    async def get_alert_rules(self) -> List[AlertRule]:
        """Get all alert rules"""
        return list(self.alert_rules.values())
    
    async def get_alert_stats(self) -> Dict[str, Any]:
        """Get alert statistics"""
        try:
            total_alerts = len(self.alerts)
            active_alerts = len([a for a in self.alerts.values() if a.status == AlertStatus.ACTIVE])
            acknowledged_alerts = len([a for a in self.alerts.values() if a.status == AlertStatus.ACKNOWLEDGED])
            resolved_alerts = len([a for a in self.alerts.values() if a.status == AlertStatus.RESOLVED])
            suppressed_alerts = len([a for a in self.alerts.values() if a.status == AlertStatus.SUPPRESSED])
            
            # Count by level
            level_counts = {}
            for alert in self.alerts.values():
                level = alert.level.value
                level_counts[level] = level_counts.get(level, 0) + 1
            
            # Count by component
            component_counts = {}
            for alert in self.alerts.values():
                component = alert.component
                component_counts[component] = component_counts.get(component, 0) + 1
            
            # Recent alerts (last 24 hours)
            recent_cutoff = datetime.now() - timedelta(hours=24)
            recent_alerts = [
                a for a in self.alerts.values()
                if datetime.fromisoformat(a.created_at) > recent_cutoff
            ]
            
            return {
                "total_alerts": total_alerts,
                "active_alerts": active_alerts,
                "acknowledged_alerts": acknowledged_alerts,
                "resolved_alerts": resolved_alerts,
                "suppressed_alerts": suppressed_alerts,
                "level_counts": level_counts,
                "component_counts": component_counts,
                "recent_alerts": len(recent_alerts),
                "active_rules": len([r for r in self.alert_rules.values() if r.enabled]),
                "total_rules": len(self.alert_rules),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting alert stats: {e}")
            return {}
    
    async def cleanup_expired_alerts(self, days: int = 30) -> int:
        """Cleanup expired alerts"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            expired_alerts = []
            
            for alert_id, alert in self.alerts.items():
                if datetime.fromisoformat(alert.created_at) < cutoff_date:
                    expired_alerts.append(alert_id)
            
            # Remove expired alerts
            for alert_id in expired_alerts:
                del self.alerts[alert_id]
            
            logger.info(f"Cleaned up {len(expired_alerts)} expired alerts")
            return len(expired_alerts)
            
        except Exception as e:
            logger.error(f"Error cleaning up expired alerts: {e}")
            return 0
    
    async def check_suppressed_alerts(self):
        """Check and unsuppress expired suppressed alerts"""
        try:
            current_time = datetime.now()
            expired_suppressions = []
            
            for alert_id, expiry_time in self.suppressed_alerts.items():
                if current_time > expiry_time:
                    expired_suppressions.append(alert_id)
            
            # Remove expired suppressions
            for alert_id in expired_suppressions:
                del self.suppressed_alerts[alert_id]
                
                # Update alert status if it exists
                if alert_id in self.alerts:
                    self.alerts[alert_id].status = AlertStatus.ACTIVE
                    self.alerts[alert_id].updated_at = current_time.isoformat()
            
            if expired_suppressions:
                logger.info(f"Unsuppressed {len(expired_suppressions)} alerts")
            
        except Exception as e:
            logger.error(f"Error checking suppressed alerts: {e}")


# Global alert manager instance
_alert_manager = None


def get_alert_manager() -> AlertManager:
    """Get global alert manager instance"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


# Export public API
__all__ = [
    "AlertLevel",
    "AlertStatus",
    "Alert",
    "AlertRule",
    "AlertManager",
    "get_alert_manager"
]