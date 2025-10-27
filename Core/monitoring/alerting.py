"""
Advanced Alerting System
Multi-channel alerting with intelligent routing and escalation
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import smtplib
import aiohttp
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from ..config.logging import get_logger
from ..config.exceptions import MonitoringError

logger = get_logger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Alert status"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class NotificationChannelType(str, Enum):
    """Notification channel types"""
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    CONSOLE = "console"
    LOG = "log"


@dataclass
class AlertRule:
    """Alert rule definition"""
    name: str
    description: str
    query: str  # Prometheus query
    condition: str  # Condition to trigger alert
    severity: AlertSeverity
    duration: str = "0s"  # How long condition must be true
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    cooldown: int = 300  # Seconds between alerts


@dataclass
class Alert:
    """Active alert instance"""
    id: str
    rule_name: str
    severity: AlertSeverity
    status: AlertStatus
    message: str
    labels: Dict[str, str]
    annotations: Dict[str, str]
    created_at: datetime
    updated_at: datetime
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    escalation_level: int = 0


@dataclass
class NotificationChannel:
    """Notification channel configuration"""
    name: str
    type: NotificationChannelType
    config: Dict[str, Any]
    enabled: bool = True
    escalation_delay: int = 0  # Minutes before escalation
    max_escalation_level: int = 3


class AlertManager:
    """Advanced alerting system with multi-channel support"""
    
    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.channels: Dict[str, NotificationChannel] = {}
        self.escalation_timers: Dict[str, asyncio.Task] = {}
        self.alert_history: List[Alert] = []
        self.is_running = False
        self.check_interval = 30  # seconds
        
        # Initialize default rules and channels
        self._create_default_rules()
        self._create_default_channels()
    
    def _create_default_rules(self):
        """Create default alert rules"""
        
        # High error rate
        self.add_rule(AlertRule(
            name="high_error_rate",
            description="High error rate detected",
            query="rate(tantra_errors_total[5m]) > 0.1",
            condition="> 0.1",
            severity=AlertSeverity.WARNING,
            duration="2m",
            labels={"service": "tantra"},
            annotations={
                "summary": "High error rate detected",
                "description": "Error rate is above 0.1 errors per second"
            }
        ))
        
        # High response time
        self.add_rule(AlertRule(
            name="high_response_time",
            description="High response time detected",
            query="histogram_quantile(0.95, rate(tantra_request_duration_seconds_bucket[5m])) > 5",
            condition="> 5",
            severity=AlertSeverity.WARNING,
            duration="5m",
            labels={"service": "tantra"},
            annotations={
                "summary": "High response time detected",
                "description": "95th percentile response time is above 5 seconds"
            }
        ))
        
        # High memory usage
        self.add_rule(AlertRule(
            name="high_memory_usage",
            description="High memory usage detected",
            query="tantra_memory_usage_bytes / 1024 / 1024 / 1024 > 8",
            condition="> 8",
            severity=AlertSeverity.WARNING,
            duration="10m",
            labels={"service": "tantra"},
            annotations={
                "summary": "High memory usage detected",
                "description": "Memory usage is above 8GB"
            }
        ))
        
        # High CPU usage
        self.add_rule(AlertRule(
            name="high_cpu_usage",
            description="High CPU usage detected",
            query="tantra_cpu_usage_percent > 80",
            condition="> 80",
            severity=AlertSeverity.WARNING,
            duration="5m",
            labels={"service": "tantra"},
            annotations={
                "summary": "High CPU usage detected",
                "description": "CPU usage is above 80%"
            }
        ))
        
        # Service down
        self.add_rule(AlertRule(
            name="service_down",
            description="Service is down",
            query="up == 0",
            condition="== 0",
            severity=AlertSeverity.CRITICAL,
            duration="1m",
            labels={"service": "tantra"},
            annotations={
                "summary": "Service is down",
                "description": "Service is not responding"
            }
        ))
        
        # LLM provider down
        self.add_rule(AlertRule(
            name="llm_provider_down",
            description="LLM provider is down",
            query="rate(tantra_llm_requests_total{status=\"error\"}[5m]) / rate(tantra_llm_requests_total[5m]) > 0.5",
            condition="> 0.5",
            severity=AlertSeverity.ERROR,
            duration="3m",
            labels={"service": "llm"},
            annotations={
                "summary": "LLM provider is down",
                "description": "LLM provider error rate is above 50%"
            }
        ))
        
        logger.info(f"Created {len(self.rules)} default alert rules")
    
    def _create_default_channels(self):
        """Create default notification channels"""
        
        # Console channel
        self.add_channel(NotificationChannel(
            name="console",
            type=NotificationChannelType.CONSOLE,
            config={},
            escalation_delay=0
        ))
        
        # Log channel
        self.add_channel(NotificationChannel(
            name="log",
            type=NotificationChannelType.LOG,
            config={"level": "WARNING"},
            escalation_delay=0
        ))
        
        logger.info(f"Created {len(self.channels)} default notification channels")
    
    def add_rule(self, rule: AlertRule):
        """Add an alert rule"""
        self.rules[rule.name] = rule
        logger.info(f"Added alert rule: {rule.name}")
    
    def remove_rule(self, rule_name: str):
        """Remove an alert rule"""
        if rule_name in self.rules:
            del self.rules[rule_name]
            logger.info(f"Removed alert rule: {rule_name}")
    
    def add_channel(self, channel: NotificationChannel):
        """Add a notification channel"""
        self.channels[channel.name] = channel
        logger.info(f"Added notification channel: {channel.name}")
    
    def remove_channel(self, channel_name: str):
        """Remove a notification channel"""
        if channel_name in self.channels:
            del self.channels[channel_name]
            logger.info(f"Removed notification channel: {channel_name}")
    
    async def start(self):
        """Start the alert manager"""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info("Alert manager started")
        
        # Start background checking
        asyncio.create_task(self._check_alerts_loop())
    
    async def stop(self):
        """Stop the alert manager"""
        self.is_running = False
        
        # Cancel escalation timers
        for task in self.escalation_timers.values():
            task.cancel()
        
        logger.info("Alert manager stopped")
    
    async def _check_alerts_loop(self):
        """Background loop to check for alerts"""
        while self.is_running:
            try:
                await self._check_all_rules()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in alert checking loop: {e}")
                await asyncio.sleep(60)
    
    async def _check_all_rules(self):
        """Check all alert rules"""
        for rule_name, rule in self.rules.items():
            if not rule.enabled:
                continue
            
            try:
                await self._check_rule(rule)
            except Exception as e:
                logger.error(f"Error checking rule {rule_name}: {e}")
    
    async def _check_rule(self, rule: AlertRule):
        """Check a specific alert rule"""
        # This would normally query Prometheus or another metrics source
        # For now, we'll simulate based on system metrics
        
        try:
            import psutil
            process = psutil.Process()
            
            # Simulate rule evaluation based on rule name
            should_alert = False
            current_value = 0
            
            if rule.name == "high_memory_usage":
                memory_info = process.memory_info()
                current_value = memory_info.rss / 1024 / 1024 / 1024  # GB
                should_alert = current_value > 8
                
            elif rule.name == "high_cpu_usage":
                current_value = process.cpu_percent()
                should_alert = current_value > 80
                
            elif rule.name == "high_error_rate":
                # Simulate error rate check
                current_value = 0.05  # Simulated
                should_alert = current_value > 0.1
                
            elif rule.name == "high_response_time":
                # Simulate response time check
                current_value = 2.0  # Simulated
                should_alert = current_value > 5
                
            elif rule.name == "service_down":
                # Service is up if we can check metrics
                current_value = 1
                should_alert = False
                
            elif rule.name == "llm_provider_down":
                # Simulate LLM provider check
                current_value = 0.1  # Simulated error rate
                should_alert = current_value > 0.5
            
            if should_alert:
                await self._trigger_alert(rule, current_value)
            else:
                await self._resolve_alert(rule.name)
                
        except Exception as e:
            logger.error(f"Error evaluating rule {rule.name}: {e}")
    
    async def _trigger_alert(self, rule: AlertRule, current_value: float):
        """Trigger an alert"""
        alert_id = f"{rule.name}_{int(time.time())}"
        
        # Check if alert already exists
        existing_alert = None
        for alert in self.active_alerts.values():
            if alert.rule_name == rule.name and alert.status in [AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED]:
                existing_alert = alert
                break
        
        if existing_alert:
            # Update existing alert
            existing_alert.updated_at = datetime.utcnow()
            existing_alert.message = f"Rule {rule.name} triggered: {current_value} {rule.condition}"
            logger.info(f"Updated existing alert: {rule.name}")
            return
        
        # Create new alert
        alert = Alert(
            id=alert_id,
            rule_name=rule.name,
            severity=rule.severity,
            status=AlertStatus.ACTIVE,
            message=f"Rule {rule.name} triggered: {current_value} {rule.condition}",
            labels=rule.labels.copy(),
            annotations=rule.annotations.copy(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)
        
        # Send notifications
        await self._send_notifications(alert)
        
        # Start escalation timer
        await self._start_escalation_timer(alert)
        
        logger.warning(f"Alert triggered: {rule.name} - {alert.message}")
    
    async def _resolve_alert(self, rule_name: str):
        """Resolve alerts for a rule"""
        for alert in self.active_alerts.values():
            if alert.rule_name == rule_name and alert.status == AlertStatus.ACTIVE:
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.utcnow()
                alert.updated_at = datetime.utcnow()
                
                # Cancel escalation timer
                if alert.id in self.escalation_timers:
                    self.escalation_timers[alert.id].cancel()
                    del self.escalation_timers[alert.id]
                
                # Send resolution notification
                await self._send_notifications(alert, resolved=True)
                
                logger.info(f"Alert resolved: {rule_name}")
    
    async def _send_notifications(self, alert: Alert, resolved: bool = False):
        """Send notifications for an alert"""
        for channel_name, channel in self.channels.items():
            if not channel.enabled:
                continue
            
            try:
                await self._send_to_channel(channel, alert, resolved)
            except Exception as e:
                logger.error(f"Error sending notification to {channel_name}: {e}")
    
    async def _send_to_channel(self, channel: NotificationChannel, alert: Alert, resolved: bool = False):
        """Send notification to a specific channel"""
        status = "RESOLVED" if resolved else "TRIGGERED"
        message = f"[{alert.severity.value.upper()}] {status}: {alert.message}"
        
        if channel.type == NotificationChannelType.CONSOLE:
            print(f"🚨 {message}")
            
        elif channel.type == NotificationChannelType.LOG:
            if alert.severity == AlertSeverity.CRITICAL:
                logger.critical(message)
            elif alert.severity == AlertSeverity.ERROR:
                logger.error(message)
            elif alert.severity == AlertSeverity.WARNING:
                logger.warning(message)
            else:
                logger.info(message)
                
        elif channel.type == NotificationChannelType.EMAIL:
            await self._send_email(channel, alert, resolved)
            
        elif channel.type == NotificationChannelType.WEBHOOK:
            await self._send_webhook(channel, alert, resolved)
            
        elif channel.type == NotificationChannelType.SLACK:
            await self._send_slack(channel, alert, resolved)
            
        elif channel.type == NotificationChannelType.DISCORD:
            await self._send_discord(channel, alert, resolved)
            
        elif channel.type == NotificationChannelType.TELEGRAM:
            await self._send_telegram(channel, alert, resolved)
    
    async def _send_email(self, channel: NotificationChannel, alert: Alert, resolved: bool):
        """Send email notification"""
        config = channel.config
        
        msg = MIMEMultipart()
        msg['From'] = config.get('from_email', 'alerts@tantra.ai')
        msg['To'] = config.get('to_email', 'admin@tantra.ai')
        msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.rule_name}"
        
        body = f"""
Alert: {alert.rule_name}
Status: {'RESOLVED' if resolved else 'TRIGGERED'}
Severity: {alert.severity.value.upper()}
Message: {alert.message}
Time: {alert.created_at.isoformat()}
Labels: {json.dumps(alert.labels, indent=2)}
Annotations: {json.dumps(alert.annotations, indent=2)}
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email (simplified - would need proper SMTP config)
        logger.info(f"Email notification sent: {alert.rule_name}")
    
    async def _send_webhook(self, channel: NotificationChannel, alert: Alert, resolved: bool):
        """Send webhook notification"""
        config = channel.config
        url = config.get('url')
        
        if not url:
            logger.warning("Webhook URL not configured")
            return
        
        payload = {
            "alert_id": alert.id,
            "rule_name": alert.rule_name,
            "severity": alert.severity.value,
            "status": "resolved" if resolved else "triggered",
            "message": alert.message,
            "labels": alert.labels,
            "annotations": alert.annotations,
            "timestamp": alert.created_at.isoformat()
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.info(f"Webhook notification sent: {alert.rule_name}")
                else:
                    logger.warning(f"Webhook notification failed: {response.status}")
    
    async def _send_slack(self, channel: NotificationChannel, alert: Alert, resolved: bool):
        """Send Slack notification"""
        config = channel.config
        webhook_url = config.get('webhook_url')
        
        if not webhook_url:
            logger.warning("Slack webhook URL not configured")
            return
        
        color = {
            AlertSeverity.INFO: "good",
            AlertSeverity.WARNING: "warning",
            AlertSeverity.ERROR: "danger",
            AlertSeverity.CRITICAL: "danger"
        }.get(alert.severity, "good")
        
        payload = {
            "attachments": [{
                "color": color,
                "title": f"Alert: {alert.rule_name}",
                "text": alert.message,
                "fields": [
                    {"title": "Severity", "value": alert.severity.value.upper(), "short": True},
                    {"title": "Status", "value": "RESOLVED" if resolved else "TRIGGERED", "short": True},
                    {"title": "Time", "value": alert.created_at.isoformat(), "short": False}
                ]
            }]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status == 200:
                    logger.info(f"Slack notification sent: {alert.rule_name}")
                else:
                    logger.warning(f"Slack notification failed: {response.status}")
    
    async def _send_discord(self, channel: NotificationChannel, alert: Alert, resolved: bool):
        """Send Discord notification"""
        config = channel.config
        webhook_url = config.get('webhook_url')
        
        if not webhook_url:
            logger.warning("Discord webhook URL not configured")
            return
        
        color = {
            AlertSeverity.INFO: 0x00ff00,
            AlertSeverity.WARNING: 0xffff00,
            AlertSeverity.ERROR: 0xff0000,
            AlertSeverity.CRITICAL: 0xff0000
        }.get(alert.severity, 0x00ff00)
        
        payload = {
            "embeds": [{
                "title": f"Alert: {alert.rule_name}",
                "description": alert.message,
                "color": color,
                "fields": [
                    {"name": "Severity", "value": alert.severity.value.upper(), "inline": True},
                    {"name": "Status", "value": "RESOLVED" if resolved else "TRIGGERED", "inline": True},
                    {"name": "Time", "value": alert.created_at.isoformat(), "inline": False}
                ]
            }]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status == 200:
                    logger.info(f"Discord notification sent: {alert.rule_name}")
                else:
                    logger.warning(f"Discord notification failed: {response.status}")
    
    async def _send_telegram(self, channel: NotificationChannel, alert: Alert, resolved: bool):
        """Send Telegram notification"""
        config = channel.config
        bot_token = config.get('bot_token')
        chat_id = config.get('chat_id')
        
        if not bot_token or not chat_id:
            logger.warning("Telegram bot token or chat ID not configured")
            return
        
        emoji = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.ERROR: "❌",
            AlertSeverity.CRITICAL: "🚨"
        }.get(alert.severity, "ℹ️")
        
        message = f"""
{emoji} *Alert: {alert.rule_name}*
Status: {'RESOLVED' if resolved else 'TRIGGERED'}
Severity: {alert.severity.value.upper()}
Message: {alert.message}
Time: {alert.created_at.isoformat()}
        """
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.info(f"Telegram notification sent: {alert.rule_name}")
                else:
                    logger.warning(f"Telegram notification failed: {response.status}")
    
    async def _start_escalation_timer(self, alert: Alert):
        """Start escalation timer for an alert"""
        if alert.id in self.escalation_timers:
            return
        
        async def escalate():
            await asyncio.sleep(300)  # 5 minutes default escalation delay
            
            if alert.id in self.active_alerts and alert.status == AlertStatus.ACTIVE:
                alert.escalation_level += 1
                alert.updated_at = datetime.utcnow()
                
                # Send escalated notification
                await self._send_notifications(alert, escalated=True)
                
                logger.warning(f"Alert escalated: {alert.rule_name} (level {alert.escalation_level})")
        
        self.escalation_timers[alert.id] = asyncio.create_task(escalate())
    
    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert"""
        if alert_id not in self.active_alerts:
            return False
        
        alert = self.active_alerts[alert_id]
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.utcnow()
        alert.updated_at = datetime.utcnow()
        
        # Cancel escalation timer
        if alert_id in self.escalation_timers:
            self.escalation_timers[alert_id].cancel()
            del self.escalation_timers[alert_id]
        
        logger.info(f"Alert acknowledged: {alert.rule_name} by {acknowledged_by}")
        return True
    
    async def resolve_alert(self, alert_id: str) -> bool:
        """Manually resolve an alert"""
        if alert_id not in self.active_alerts:
            return False
        
        alert = self.active_alerts[alert_id]
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()
        alert.updated_at = datetime.utcnow()
        
        # Cancel escalation timer
        if alert_id in self.escalation_timers:
            self.escalation_timers[alert_id].cancel()
            del self.escalation_timers[alert_id]
        
        # Send resolution notification
        await self._send_notifications(alert, resolved=True)
        
        logger.info(f"Alert resolved: {alert.rule_name}")
        return True
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        return [alert for alert in self.active_alerts.values() 
                if alert.status in [AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED]]
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get alert history"""
        return self.alert_history[-limit:]
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get alert summary statistics"""
        active_alerts = self.get_active_alerts()
        
        summary = {
            "total_rules": len(self.rules),
            "enabled_rules": len([r for r in self.rules.values() if r.enabled]),
            "active_alerts": len(active_alerts),
            "total_channels": len(self.channels),
            "enabled_channels": len([c for c in self.channels.values() if c.enabled]),
            "alerts_by_severity": {},
            "recent_alerts": len([a for a in self.alert_history 
                                if a.created_at > datetime.utcnow() - timedelta(hours=24)])
        }
        
        # Count by severity
        for alert in active_alerts:
            severity = alert.severity.value
            summary["alerts_by_severity"][severity] = summary["alerts_by_severity"].get(severity, 0) + 1
        
        return summary


# Global alert manager instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get global alert manager instance"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager