"""
Self-Monitoring System for Atulya Tantra AGI
Health checks, performance monitoring, and automated alerts
"""

import asyncio
import psutil
import time
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import json
import threading

from ..config.settings import settings
from ..config.logging import get_logger
from ..config.exceptions import AgentError
from ..database.service import get_db_service, insert_record, get_record_by_id, update_record

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AlertLevel(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricType(str, Enum):
    """Types of metrics"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class SystemMetric:
    """Represents a system metric"""
    
    def __init__(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.GAUGE,
        labels: Dict[str, str] = None,
        timestamp: datetime = None
    ):
        self.name = name
        self.value = value
        self.metric_type = metric_type
        self.labels = labels or {}
        self.timestamp = timestamp or datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metric to dictionary"""
        return {
            "name": self.name,
            "value": self.value,
            "metric_type": self.metric_type.value,
            "labels": self.labels,
            "timestamp": self.timestamp.isoformat()
        }


class Alert:
    """Represents a system alert"""
    
    def __init__(
        self,
        alert_id: str = None,
        title: str = None,
        message: str = None,
        level: AlertLevel = AlertLevel.INFO,
        source: str = None,
        metric_name: str = None,
        threshold_value: float = None,
        current_value: float = None,
        resolved: bool = False,
        metadata: Dict[str, Any] = None
    ):
        self.alert_id = alert_id or f"alert_{int(time.time())}"
        self.title = title or "System Alert"
        self.message = message or ""
        self.level = level
        self.source = source or "system_monitor"
        self.metric_name = metric_name
        self.threshold_value = threshold_value
        self.current_value = current_value
        self.resolved = resolved
        self.metadata = metadata or {}
        
        self.created_at = datetime.utcnow()
        self.resolved_at = None
        self.acknowledged = False
        self.acknowledged_by = None
        self.acknowledged_at = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary"""
        return {
            "alert_id": self.alert_id,
            "title": self.title,
            "message": self.message,
            "level": self.level.value,
            "source": self.source,
            "metric_name": self.metric_name,
            "threshold_value": self.threshold_value,
            "current_value": self.current_value,
            "resolved": self.resolved,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "acknowledged": self.acknowledged,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None
        }


class HealthCheck:
    """Represents a health check"""
    
    def __init__(
        self,
        name: str,
        check_function: Callable,
        interval: int = 60,
        timeout: int = 30,
        enabled: bool = True,
        metadata: Dict[str, Any] = None
    ):
        self.name = name
        self.check_function = check_function
        self.interval = interval
        self.timeout = timeout
        self.enabled = enabled
        self.metadata = metadata or {}
        
        self.last_run = None
        self.last_status = HealthStatus.UNKNOWN
        self.last_result = None
        self.consecutive_failures = 0
        self.total_runs = 0
        self.successful_runs = 0
    
    async def run_check(self) -> Dict[str, Any]:
        """Run the health check"""
        try:
            self.total_runs += 1
            self.last_run = datetime.utcnow()
            
            # Run check with timeout
            result = await asyncio.wait_for(
                self.check_function(),
                timeout=self.timeout
            )
            
            self.last_result = result
            self.last_status = HealthStatus.HEALTHY
            self.consecutive_failures = 0
            self.successful_runs += 1
            
            return {
                "status": HealthStatus.HEALTHY.value,
                "result": result,
                "timestamp": self.last_run.isoformat(),
                "success": True
            }
            
        except asyncio.TimeoutError:
            self.last_status = HealthStatus.CRITICAL
            self.consecutive_failures += 1
            
            return {
                "status": HealthStatus.CRITICAL.value,
                "error": "Health check timed out",
                "timestamp": self.last_run.isoformat(),
                "success": False
            }
            
        except Exception as e:
            self.last_status = HealthStatus.CRITICAL
            self.consecutive_failures += 1
            
            return {
                "status": HealthStatus.CRITICAL.value,
                "error": str(e),
                "timestamp": self.last_run.isoformat(),
                "success": False
            }


class SystemMonitor:
    """Comprehensive system monitoring and health checking"""
    
    def __init__(self):
        self.health_checks: Dict[str, HealthCheck] = {}
        self.metrics: List[SystemMetric] = []
        self.alerts: List[Alert] = []
        self.is_monitoring = False
        self.monitoring_task: Optional[asyncio.Task] = None
        self.metrics_lock = threading.Lock()
        
        # Monitoring configuration
        self.monitoring_config = {
            "cpu_threshold": 80.0,
            "memory_threshold": 85.0,
            "disk_threshold": 90.0,
            "response_time_threshold": 5.0,
            "error_rate_threshold": 5.0
        }
        
        # Initialize default health checks
        self._initialize_default_health_checks()
    
    def _initialize_default_health_checks(self):
        """Initialize default health checks"""
        self.add_health_check(
            "system_resources",
            self._check_system_resources,
            interval=30
        )
        
        self.add_health_check(
            "database_connectivity",
            self._check_database_connectivity,
            interval=60
        )
        
        self.add_health_check(
            "ai_providers",
            self._check_ai_providers,
            interval=120
        )
        
        self.add_health_check(
            "agent_system",
            self._check_agent_system,
            interval=60
        )
        
        self.add_health_check(
            "disk_space",
            self._check_disk_space,
            interval=300
        )
        
        self.add_health_check(
            "network_connectivity",
            self._check_network_connectivity,
            interval=60
        )
    
    async def start_monitoring(self):
        """Start system monitoring"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("System monitoring started")
    
    async def stop_monitoring(self):
        """Stop system monitoring"""
        self.is_monitoring = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("System monitoring stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_monitoring:
            try:
                # Run health checks
                await self._run_health_checks()
                
                # Collect system metrics
                await self._collect_system_metrics()
                
                # Check for alerts
                await self._check_alerts()
                
                # Clean up old data
                await self._cleanup_old_data()
                
                # Wait before next cycle
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)
    
    async def _run_health_checks(self):
        """Run all enabled health checks"""
        for check_name, health_check in self.health_checks.items():
            if health_check.enabled:
                try:
                    result = await health_check.run_check()
                    
                    # Store result
                    await self._store_health_check_result(check_name, result)
                    
                    # Check if we need to create an alert
                    if result["status"] != HealthStatus.HEALTHY.value:
                        await self._create_health_alert(check_name, result)
                    
                except Exception as e:
                    logger.error(f"Error running health check {check_name}: {e}")
    
    async def _collect_system_metrics(self):
        """Collect system metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available = memory.available / (1024**3)  # GB
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_free = disk.free / (1024**3)  # GB
            
            # Network metrics
            network = psutil.net_io_counters()
            
            # Process metrics
            process = psutil.Process()
            process_memory = process.memory_info().rss / (1024**2)  # MB
            process_cpu = process.cpu_percent()
            
            # Create metrics
            metrics = [
                SystemMetric("cpu_usage_percent", cpu_percent, MetricType.GAUGE),
                SystemMetric("cpu_count", cpu_count, MetricType.GAUGE),
                SystemMetric("memory_usage_percent", memory_percent, MetricType.GAUGE),
                SystemMetric("memory_available_gb", memory_available, MetricType.GAUGE),
                SystemMetric("disk_usage_percent", disk_percent, MetricType.GAUGE),
                SystemMetric("disk_free_gb", disk_free, MetricType.GAUGE),
                SystemMetric("network_bytes_sent", network.bytes_sent, MetricType.COUNTER),
                SystemMetric("network_bytes_recv", network.bytes_recv, MetricType.COUNTER),
                SystemMetric("process_memory_mb", process_memory, MetricType.GAUGE),
                SystemMetric("process_cpu_percent", process_cpu, MetricType.GAUGE)
            ]
            
            # Store metrics
            with self.metrics_lock:
                self.metrics.extend(metrics)
                
                # Keep only last 1000 metrics
                if len(self.metrics) > 1000:
                    self.metrics = self.metrics[-1000:]
            
            # Store in database
            for metric in metrics:
                await self._store_metric(metric)
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    async def _check_alerts(self):
        """Check for alert conditions"""
        try:
            with self.metrics_lock:
                recent_metrics = self.metrics[-10:]  # Last 10 metrics
            
            for metric in recent_metrics:
                await self._evaluate_metric_alerts(metric)
                
        except Exception as e:
            logger.error(f"Error checking alerts: {e}")
    
    async def _evaluate_metric_alerts(self, metric: SystemMetric):
        """Evaluate alerts for a specific metric"""
        try:
            if metric.name == "cpu_usage_percent":
                if metric.value > self.monitoring_config["cpu_threshold"]:
                    await self._create_metric_alert(
                        "High CPU Usage",
                        f"CPU usage is {metric.value:.1f}% (threshold: {self.monitoring_config['cpu_threshold']}%)",
                        AlertLevel.WARNING,
                        metric.name,
                        self.monitoring_config["cpu_threshold"],
                        metric.value
                    )
            
            elif metric.name == "memory_usage_percent":
                if metric.value > self.monitoring_config["memory_threshold"]:
                    await self._create_metric_alert(
                        "High Memory Usage",
                        f"Memory usage is {metric.value:.1f}% (threshold: {self.monitoring_config['memory_threshold']}%)",
                        AlertLevel.WARNING,
                        metric.name,
                        self.monitoring_config["memory_threshold"],
                        metric.value
                    )
            
            elif metric.name == "disk_usage_percent":
                if metric.value > self.monitoring_config["disk_threshold"]:
                    await self._create_metric_alert(
                        "High Disk Usage",
                        f"Disk usage is {metric.value:.1f}% (threshold: {self.monitoring_config['disk_threshold']}%)",
                        AlertLevel.CRITICAL,
                        metric.name,
                        self.monitoring_config["disk_threshold"],
                        metric.value
                    )
            
        except Exception as e:
            logger.error(f"Error evaluating metric alerts: {e}")
    
    async def _create_metric_alert(
        self,
        title: str,
        message: str,
        level: AlertLevel,
        metric_name: str,
        threshold: float,
        current_value: float
    ):
        """Create an alert for a metric threshold breach"""
        # Check if similar alert already exists
        existing_alert = None
        for alert in self.alerts:
            if (alert.metric_name == metric_name and 
                not alert.resolved and 
                alert.level == level):
                existing_alert = alert
                break
        
        if existing_alert:
            # Update existing alert
            existing_alert.current_value = current_value
            existing_alert.message = message
        else:
            # Create new alert
            alert = Alert(
                title=title,
                message=message,
                level=level,
                source="system_monitor",
                metric_name=metric_name,
                threshold_value=threshold,
                current_value=current_value
            )
            
            self.alerts.append(alert)
            await self._store_alert(alert)
            
            logger.warning(f"Alert created: {title} - {message}")
    
    async def _create_health_alert(self, check_name: str, result: Dict[str, Any]):
        """Create an alert for a failed health check"""
        alert = Alert(
            title=f"Health Check Failed: {check_name}",
            message=result.get("error", "Health check failed"),
            level=AlertLevel.ERROR,
            source="health_check",
            metadata={"check_name": check_name, "result": result}
        )
        
        self.alerts.append(alert)
        await self._store_alert(alert)
        
        logger.warning(f"Health check alert: {check_name}")
    
    async def _cleanup_old_data(self):
        """Clean up old metrics and alerts"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            
            # Clean up old metrics
            with self.metrics_lock:
                self.metrics = [
                    m for m in self.metrics 
                    if m.timestamp > cutoff_time
                ]
            
            # Clean up old resolved alerts
            self.alerts = [
                a for a in self.alerts 
                if not a.resolved or a.created_at > cutoff_time
            ]
            
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
    
    def add_health_check(
        self,
        name: str,
        check_function: Callable,
        interval: int = 60,
        timeout: int = 30,
        enabled: bool = True
    ):
        """Add a health check"""
        health_check = HealthCheck(
            name=name,
            check_function=check_function,
            interval=interval,
            timeout=timeout,
            enabled=enabled
        )
        
        self.health_checks[name] = health_check
        logger.info(f"Added health check: {name}")
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status"""
        try:
            health_status = {
                "overall_status": HealthStatus.HEALTHY.value,
                "timestamp": datetime.utcnow().isoformat(),
                "checks": {},
                "metrics": {},
                "alerts": {
                    "total": len(self.alerts),
                    "unresolved": len([a for a in self.alerts if not a.resolved]),
                    "critical": len([a for a in self.alerts if a.level == AlertLevel.CRITICAL and not a.resolved])
                }
            }
            
            # Check health check statuses
            for name, check in self.health_checks.items():
                health_status["checks"][name] = {
                    "status": check.last_status.value,
                    "last_run": check.last_run.isoformat() if check.last_run else None,
                    "consecutive_failures": check.consecutive_failures,
                    "success_rate": check.successful_runs / check.total_runs if check.total_runs > 0 else 0
                }
                
                # Update overall status
                if check.last_status == HealthStatus.CRITICAL:
                    health_status["overall_status"] = HealthStatus.CRITICAL.value
                elif check.last_status == HealthStatus.WARNING and health_status["overall_status"] != HealthStatus.CRITICAL.value:
                    health_status["overall_status"] = HealthStatus.WARNING.value
            
            # Get recent metrics
            with self.metrics_lock:
                recent_metrics = self.metrics[-10:] if self.metrics else []
            
            for metric in recent_metrics:
                health_status["metrics"][metric.name] = metric.value
            
            return health_status
            
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {
                "overall_status": HealthStatus.UNKNOWN.value,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def get_metrics(self, metric_name: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get system metrics"""
        try:
            with self.metrics_lock:
                metrics = self.metrics
                
                if metric_name:
                    metrics = [m for m in metrics if m.name == metric_name]
                
                # Return last N metrics
                metrics = metrics[-limit:] if metrics else []
                
                return [metric.to_dict() for metric in metrics]
                
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return []
    
    async def get_alerts(self, unresolved_only: bool = False) -> List[Dict[str, Any]]:
        """Get system alerts"""
        try:
            alerts = self.alerts
            
            if unresolved_only:
                alerts = [a for a in alerts if not a.resolved]
            
            # Sort by creation time (newest first)
            alerts.sort(key=lambda a: a.created_at, reverse=True)
            
            return [alert.to_dict() for alert in alerts]
            
        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
            return []
    
    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert"""
        try:
            for alert in self.alerts:
                if alert.alert_id == alert_id:
                    alert.acknowledged = True
                    alert.acknowledged_by = acknowledged_by
                    alert.acknowledged_at = datetime.utcnow()
                    
                    await self._update_alert(alert)
                    logger.info(f"Alert acknowledged: {alert_id} by {acknowledged_by}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error acknowledging alert: {e}")
            return False
    
    async def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert"""
        try:
            for alert in self.alerts:
                if alert.alert_id == alert_id:
                    alert.resolved = True
                    alert.resolved_at = datetime.utcnow()
                    
                    await self._update_alert(alert)
                    logger.info(f"Alert resolved: {alert_id}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error resolving alert: {e}")
            return False
    
    # Default health check implementations
    async def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "cpu_usage": cpu_percent,
                "memory_usage": memory.percent,
                "disk_usage": disk.percent,
                "memory_available_gb": memory.available / (1024**3),
                "disk_free_gb": disk.free / (1024**3)
            }
            
        except Exception as e:
            raise AgentError(f"System resource check failed: {e}")
    
    async def _check_database_connectivity(self) -> Dict[str, Any]:
        """Check database connectivity"""
        try:
            db_service = await get_db_service()
            
            # Simple connectivity test
            start_time = time.time()
            # This would be a simple query like "SELECT 1"
            response_time = time.time() - start_time
            
            return {
                "connected": True,
                "response_time_ms": response_time * 1000,
                "database_type": settings.database_type
            }
            
        except Exception as e:
            raise AgentError(f"Database connectivity check failed: {e}")
    
    async def _check_ai_providers(self) -> Dict[str, Any]:
        """Check AI provider availability"""
        try:
            from ..brain import get_provider_status
            
            provider_status = await get_provider_status()
            
            return {
                "providers": provider_status,
                "available_providers": len([p for p in provider_status.values() if p.get("available", False)])
            }
            
        except Exception as e:
            raise AgentError(f"AI provider check failed: {e}")
    
    async def _check_agent_system(self) -> Dict[str, Any]:
        """Check agent system health"""
        try:
            from ..agents import get_orchestrator
            
            orchestrator = await get_orchestrator()
            agent_status = await orchestrator.get_agent_status()
            
            return {
                "agents": agent_status,
                "active_agents": len([a for a in agent_status if a.get("status") == "active"]),
                "total_agents": len(agent_status)
            }
            
        except Exception as e:
            raise AgentError(f"Agent system check failed: {e}")
    
    async def _check_disk_space(self) -> Dict[str, Any]:
        """Check disk space"""
        try:
            disk = psutil.disk_usage('/')
            
            return {
                "total_gb": disk.total / (1024**3),
                "used_gb": disk.used / (1024**3),
                "free_gb": disk.free / (1024**3),
                "usage_percent": (disk.used / disk.total) * 100
            }
            
        except Exception as e:
            raise AgentError(f"Disk space check failed: {e}")
    
    async def _check_network_connectivity(self) -> Dict[str, Any]:
        """Check network connectivity"""
        try:
            import socket
            
            # Test DNS resolution
            socket.gethostbyname("google.com")
            
            # Test network I/O
            network = psutil.net_io_counters()
            
            return {
                "dns_resolution": True,
                "bytes_sent": network.bytes_sent,
                "bytes_recv": network.bytes_recv,
                "packets_sent": network.packets_sent,
                "packets_recv": network.packets_recv
            }
            
        except Exception as e:
            raise AgentError(f"Network connectivity check failed: {e}")
    
    # Database operations
    async def _store_metric(self, metric: SystemMetric):
        """Store metric in database"""
        try:
            await insert_record("system_metrics", metric.to_dict())
        except Exception as e:
            logger.error(f"Error storing metric: {e}")
    
    async def _store_alert(self, alert: Alert):
        """Store alert in database"""
        try:
            await insert_record("system_alerts", alert.to_dict())
        except Exception as e:
            logger.error(f"Error storing alert: {e}")
    
    async def _update_alert(self, alert: Alert):
        """Update alert in database"""
        try:
            await update_record("system_alerts", alert.alert_id, alert.to_dict())
        except Exception as e:
            logger.error(f"Error updating alert: {e}")
    
    async def _store_health_check_result(self, check_name: str, result: Dict[str, Any]):
        """Store health check result in database"""
        try:
            data = {
                "check_name": check_name,
                "result": result,
                "timestamp": datetime.utcnow().isoformat()
            }
            await insert_record("health_check_results", data)
        except Exception as e:
            logger.error(f"Error storing health check result: {e}")


# Global system monitor instance
_system_monitor: Optional[SystemMonitor] = None


async def get_system_monitor() -> SystemMonitor:
    """Get global system monitor instance"""
    global _system_monitor
    
    if _system_monitor is None:
        _system_monitor = SystemMonitor()
        await _system_monitor.start_monitoring()
    
    return _system_monitor


async def get_system_health() -> Dict[str, Any]:
    """Get system health status"""
    monitor = await get_system_monitor()
    return await monitor.get_system_health()


async def get_system_metrics(metric_name: str = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Get system metrics"""
    monitor = await get_system_monitor()
    return await monitor.get_metrics(metric_name, limit)


async def get_system_alerts(unresolved_only: bool = False) -> List[Dict[str, Any]]:
    """Get system alerts"""
    monitor = await get_system_monitor()
    return await monitor.get_alerts(unresolved_only)


async def acknowledge_alert(alert_id: str, acknowledged_by: str) -> bool:
    """Acknowledge an alert"""
    monitor = await get_system_monitor()
    return await monitor.acknowledge_alert(alert_id, acknowledged_by)


async def resolve_alert(alert_id: str) -> bool:
    """Resolve an alert"""
    monitor = await get_system_monitor()
    return await monitor.resolve_alert(alert_id)


# Export public API
__all__ = [
    "HealthStatus",
    "AlertLevel",
    "MetricType",
    "SystemMetric",
    "Alert",
    "HealthCheck",
    "SystemMonitor",
    "get_system_monitor",
    "get_system_health",
    "get_system_metrics",
    "get_system_alerts",
    "acknowledge_alert",
    "resolve_alert"
]
