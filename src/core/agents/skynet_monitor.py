"""
Atulya Tantra - Skynet System Monitor
Version: 2.5.0
System monitoring and health checking for autonomous operations
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import json
import asyncio
import psutil
import time
from collections import defaultdict, deque
import threading

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class HealthCheck:
    """Health check result"""
    component: str
    status: HealthStatus
    message: str
    timestamp: datetime
    metrics: Dict[str, Any]
    recovery_actions: List[str]


@dataclass
class Alert:
    """System alert"""
    alert_id: str
    level: AlertLevel
    component: str
    message: str
    timestamp: datetime
    resolved: bool
    resolution_time: Optional[datetime]
    metadata: Dict[str, Any]


@dataclass
class PerformanceMetrics:
    """Performance metrics"""
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: Dict[str, float]
    network_io: Dict[str, int]
    response_time: float
    error_rate: float
    throughput: float


class SystemMonitor:
    """System monitoring and health checking"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.is_monitoring = False
        self.monitor_thread = None
        self.health_checks = {}  # component -> HealthCheck
        self.alerts = deque(maxlen=1000)  # Keep last 1000 alerts
        self.performance_history = deque(maxlen=1000)  # Keep last 1000 metrics
        self.thresholds = config.get("thresholds", {})
        self.check_intervals = config.get("check_intervals", {})
        self.lock = threading.Lock()
        
        # Default thresholds
        self.default_thresholds = {
            "cpu_usage": {"warning": 70, "critical": 90},
            "memory_usage": {"warning": 80, "critical": 95},
            "disk_usage": {"warning": 80, "critical": 95},
            "response_time": {"warning": 2000, "critical": 5000},  # milliseconds
            "error_rate": {"warning": 5, "critical": 10}  # percentage
        }
        
        # Merge with config thresholds
        for key, value in self.default_thresholds.items():
            if key not in self.thresholds:
                self.thresholds[key] = value
        
        # Default check intervals (seconds)
        self.default_intervals = {
            "system_metrics": 30,
            "service_health": 60,
            "performance_metrics": 15,
            "alert_check": 10
        }
        
        # Merge with config intervals
        for key, value in self.default_intervals.items():
            if key not in self.check_intervals:
                self.check_intervals[key] = value
        
        logger.info("SystemMonitor initialized")
    
    async def start_monitoring(self):
        """Start system monitoring"""
        
        if self.is_monitoring:
            return {"error": "Monitoring already active"}
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info("System monitoring started")
        return {"success": True, "status": "started"}
    
    async def stop_monitoring(self):
        """Stop system monitoring"""
        
        if not self.is_monitoring:
            return {"error": "Monitoring not active"}
        
        self.is_monitoring = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        logger.info("System monitoring stopped")
        return {"success": True, "status": "stopped"}
    
    async def perform_health_check(self, component: str = None) -> Dict[str, Any]:
        """Perform health check for specific component or all components"""
        
        if component:
            return await self._check_component(component)
        else:
            # Check all components
            results = {}
            for comp in ["system", "services", "database", "ai_models", "api"]:
                results[comp] = await self._check_component(comp)
            return results
    
    async def get_system_metrics(self) -> PerformanceMetrics:
        """Get current system performance metrics"""
        
        try:
            # CPU usage
            cpu_usage = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_usage = memory.percent
            
            # Disk usage
            disk_usage = {}
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_usage[partition.mountpoint] = usage.percent
                except PermissionError:
                    continue
            
            # Network I/O
            network_io = psutil.net_io_counters()._asdict()
            
            # Application-specific metrics (placeholders)
            response_time = 0.0  # Would be measured from actual API calls
            error_rate = 0.0     # Would be calculated from error logs
            throughput = 0.0     # Would be measured from request rates
            
            return PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                disk_usage=disk_usage,
                network_io=network_io,
                response_time=response_time,
                error_rate=error_rate,
                throughput=throughput
            )
            
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_usage=0,
                memory_usage=0,
                disk_usage={},
                network_io={},
                response_time=0,
                error_rate=0,
                throughput=0
            )
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get overall system health status"""
        
        with self.lock:
            # Calculate overall status
            statuses = [check.status for check in self.health_checks.values()]
            
            if not statuses:
                overall_status = HealthStatus.UNKNOWN
            elif HealthStatus.CRITICAL in statuses:
                overall_status = HealthStatus.CRITICAL
            elif HealthStatus.WARNING in statuses:
                overall_status = HealthStatus.WARNING
            else:
                overall_status = HealthStatus.HEALTHY
            
            # Get recent alerts
            recent_alerts = [alert for alert in self.alerts if not alert.resolved][-10:]
            
            # Get performance trend
            performance_trend = "stable"
            if len(self.performance_history) >= 2:
                recent_metrics = list(self.performance_history)[-5:]
                avg_cpu = sum(m.cpu_usage for m in recent_metrics) / len(recent_metrics)
                if avg_cpu > 80:
                    performance_trend = "degrading"
                elif avg_cpu < 30:
                    performance_trend = "improving"
            
            return {
                "overall_status": overall_status.value,
                "components": {
                    comp: {
                        "status": check.status.value,
                        "message": check.message,
                        "timestamp": check.timestamp.isoformat()
                    }
                    for comp, check in self.health_checks.items()
                },
                "recent_alerts": [
                    {
                        "level": alert.level.value,
                        "component": alert.component,
                        "message": alert.message,
                        "timestamp": alert.timestamp.isoformat()
                    }
                    for alert in recent_alerts
                ],
                "performance_trend": performance_trend,
                "monitoring_active": self.is_monitoring
            }
    
    async def get_alerts(
        self,
        level: Optional[AlertLevel] = None,
        component: Optional[str] = None,
        resolved: Optional[bool] = None,
        limit: int = 100
    ) -> List[Alert]:
        """Get filtered alerts"""
        
        with self.lock:
            alerts = list(self.alerts)
        
        # Apply filters
        if level:
            alerts = [a for a in alerts if a.level == level]
        
        if component:
            alerts = [a for a in alerts if a.component == component]
        
        if resolved is not None:
            alerts = [a for a in alerts if a.resolved == resolved]
        
        # Sort by timestamp (newest first)
        alerts.sort(key=lambda x: x.timestamp, reverse=True)
        
        return alerts[:limit]
    
    async def resolve_alert(self, alert_id: str) -> Dict[str, Any]:
        """Resolve an alert"""
        
        with self.lock:
            for alert in self.alerts:
                if alert.alert_id == alert_id:
                    alert.resolved = True
                    alert.resolution_time = datetime.now()
                    
                    logger.info(f"Resolved alert: {alert_id}")
                    return {"success": True, "alert_id": alert_id}
        
        return {"error": "Alert not found"}
    
    async def get_performance_history(
        self,
        hours: int = 24,
        component: Optional[str] = None
    ) -> List[PerformanceMetrics]:
        """Get performance metrics history"""
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self.lock:
            return [
                metrics for metrics in self.performance_history
                if metrics.timestamp >= cutoff_time
            ]
    
    async def set_threshold(self, metric: str, level: str, value: float):
        """Set monitoring threshold"""
        
        if metric not in self.thresholds:
            self.thresholds[metric] = {}
        
        self.thresholds[metric][level] = value
        logger.info(f"Set threshold: {metric}.{level} = {value}")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        
        last_checks = {}
        
        while self.is_monitoring:
            try:
                current_time = time.time()
                
                # System metrics check
                if (current_time - last_checks.get("system_metrics", 0) >= 
                    self.check_intervals["system_metrics"]):
                    await self._check_system_metrics()
                    last_checks["system_metrics"] = current_time
                
                # Service health check
                if (current_time - last_checks.get("service_health", 0) >= 
                    self.check_intervals["service_health"]):
                    await self._check_service_health()
                    last_checks["service_health"] = current_time
                
                # Performance metrics collection
                if (current_time - last_checks.get("performance_metrics", 0) >= 
                    self.check_intervals["performance_metrics"]):
                    await self._collect_performance_metrics()
                    last_checks["performance_metrics"] = current_time
                
                # Alert processing
                if (current_time - last_checks.get("alert_check", 0) >= 
                    self.check_intervals["alert_check"]):
                    await self._process_alerts()
                    last_checks["alert_check"] = current_time
                
                # Sleep for a short interval
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5)
    
    async def _check_system_metrics(self):
        """Check system-level metrics"""
        
        metrics = await self.get_system_metrics()
        
        # Check CPU usage
        if metrics.cpu_usage > self.thresholds["cpu_usage"]["critical"]:
            await self._create_alert(
                AlertLevel.CRITICAL,
                "system",
                f"High CPU usage: {metrics.cpu_usage:.1f}%",
                {"cpu_usage": metrics.cpu_usage}
            )
        elif metrics.cpu_usage > self.thresholds["cpu_usage"]["warning"]:
            await self._create_alert(
                AlertLevel.WARNING,
                "system",
                f"Elevated CPU usage: {metrics.cpu_usage:.1f}%",
                {"cpu_usage": metrics.cpu_usage}
            )
        
        # Check memory usage
        if metrics.memory_usage > self.thresholds["memory_usage"]["critical"]:
            await self._create_alert(
                AlertLevel.CRITICAL,
                "system",
                f"High memory usage: {metrics.memory_usage:.1f}%",
                {"memory_usage": metrics.memory_usage}
            )
        elif metrics.memory_usage > self.thresholds["memory_usage"]["warning"]:
            await self._create_alert(
                AlertLevel.WARNING,
                "system",
                f"Elevated memory usage: {metrics.memory_usage:.1f}%",
                {"memory_usage": metrics.memory_usage}
            )
        
        # Check disk usage
        for partition, usage in metrics.disk_usage.items():
            if usage > self.thresholds["disk_usage"]["critical"]:
                await self._create_alert(
                    AlertLevel.CRITICAL,
                    "system",
                    f"High disk usage on {partition}: {usage:.1f}%",
                    {"partition": partition, "disk_usage": usage}
                )
            elif usage > self.thresholds["disk_usage"]["warning"]:
                await self._create_alert(
                    AlertLevel.WARNING,
                    "system",
                    f"Elevated disk usage on {partition}: {usage:.1f}%",
                    {"partition": partition, "disk_usage": usage}
                )
    
    async def _check_service_health(self):
        """Check health of application services"""
        
        # Check API health
        api_health = await self._check_api_health()
        self._update_health_check("api", api_health)
        
        # Check database health
        db_health = await self._check_database_health()
        self._update_health_check("database", db_health)
        
        # Check AI models health
        ai_health = await self._check_ai_models_health()
        self._update_health_check("ai_models", ai_health)
    
    async def _check_api_health(self) -> HealthCheck:
        """Check API service health"""
        
        try:
            # This would be an actual health check call to your API
            # For now, simulate the check
            response_time = 100  # milliseconds
            
            if response_time > self.thresholds["response_time"]["critical"]:
                return HealthCheck(
                    component="api",
                    status=HealthStatus.CRITICAL,
                    message=f"API response time critical: {response_time}ms",
                    timestamp=datetime.now(),
                    metrics={"response_time": response_time},
                    recovery_actions=["restart_api", "check_dependencies"]
                )
            elif response_time > self.thresholds["response_time"]["warning"]:
                return HealthCheck(
                    component="api",
                    status=HealthStatus.WARNING,
                    message=f"API response time elevated: {response_time}ms",
                    timestamp=datetime.now(),
                    metrics={"response_time": response_time},
                    recovery_actions=["monitor_closely"]
                )
            else:
                return HealthCheck(
                    component="api",
                    status=HealthStatus.HEALTHY,
                    message="API responding normally",
                    timestamp=datetime.now(),
                    metrics={"response_time": response_time},
                    recovery_actions=[]
                )
                
        except Exception as e:
            return HealthCheck(
                component="api",
                status=HealthStatus.CRITICAL,
                message=f"API health check failed: {str(e)}",
                timestamp=datetime.now(),
                metrics={},
                recovery_actions=["restart_api", "check_connectivity"]
            )
    
    async def _check_database_health(self) -> HealthCheck:
        """Check database health"""
        
        try:
            # This would be an actual database health check
            # For now, simulate the check
            connection_time = 50  # milliseconds
            
            if connection_time > 1000:  # 1 second
                return HealthCheck(
                    component="database",
                    status=HealthStatus.CRITICAL,
                    message=f"Database connection slow: {connection_time}ms",
                    timestamp=datetime.now(),
                    metrics={"connection_time": connection_time},
                    recovery_actions=["restart_database", "check_connections"]
                )
            else:
                return HealthCheck(
                    component="database",
                    status=HealthStatus.HEALTHY,
                    message="Database responding normally",
                    timestamp=datetime.now(),
                    metrics={"connection_time": connection_time},
                    recovery_actions=[]
                )
                
        except Exception as e:
            return HealthCheck(
                component="database",
                status=HealthStatus.CRITICAL,
                message=f"Database health check failed: {str(e)}",
                timestamp=datetime.now(),
                metrics={},
                recovery_actions=["restart_database", "check_config"]
            )
    
    async def _check_ai_models_health(self) -> HealthCheck:
        """Check AI models health"""
        
        try:
            # This would check actual AI model availability
            # For now, simulate the check
            models_available = 3
            total_models = 3
            
            if models_available == 0:
                return HealthCheck(
                    component="ai_models",
                    status=HealthStatus.CRITICAL,
                    message="No AI models available",
                    timestamp=datetime.now(),
                    metrics={"available": models_available, "total": total_models},
                    recovery_actions=["restart_ai_service", "check_model_config"]
                )
            elif models_available < total_models:
                return HealthCheck(
                    component="ai_models",
                    status=HealthStatus.WARNING,
                    message=f"Some AI models unavailable: {models_available}/{total_models}",
                    timestamp=datetime.now(),
                    metrics={"available": models_available, "total": total_models},
                    recovery_actions=["check_model_status"]
                )
            else:
                return HealthCheck(
                    component="ai_models",
                    status=HealthStatus.HEALTHY,
                    message="All AI models available",
                    timestamp=datetime.now(),
                    metrics={"available": models_available, "total": total_models},
                    recovery_actions=[]
                )
                
        except Exception as e:
            return HealthCheck(
                component="ai_models",
                status=HealthStatus.CRITICAL,
                message=f"AI models health check failed: {str(e)}",
                timestamp=datetime.now(),
                metrics={},
                recovery_actions=["restart_ai_service"]
            )
    
    async def _collect_performance_metrics(self):
        """Collect and store performance metrics"""
        
        metrics = await self.get_system_metrics()
        
        with self.lock:
            self.performance_history.append(metrics)
    
    async def _process_alerts(self):
        """Process and manage alerts"""
        
        # This could include alert escalation, notification sending, etc.
        # For now, just log any critical alerts
        with self.lock:
            recent_critical = [
                alert for alert in self.alerts
                if (alert.level == AlertLevel.CRITICAL and 
                    not alert.resolved and
                    alert.timestamp > datetime.now() - timedelta(minutes=5))
            ]
        
        for alert in recent_critical:
            logger.critical(f"Critical alert: {alert.message}")
    
    async def _create_alert(
        self,
        level: AlertLevel,
        component: str,
        message: str,
        metadata: Dict[str, Any] = None
    ):
        """Create a new alert"""
        
        alert = Alert(
            alert_id=f"alert_{int(time.time())}_{len(self.alerts)}",
            level=level,
            component=component,
            message=message,
            timestamp=datetime.now(),
            resolved=False,
            resolution_time=None,
            metadata=metadata or {}
        )
        
        with self.lock:
            self.alerts.append(alert)
        
        logger.warning(f"Alert created: {level.value} - {component} - {message}")
    
    def _update_health_check(self, component: str, health_check: HealthCheck):
        """Update health check for a component"""
        
        with self.lock:
            self.health_checks[component] = health_check
        
        # Create alert if status is warning or critical
        if health_check.status == HealthStatus.CRITICAL:
            asyncio.create_task(self._create_alert(
                AlertLevel.CRITICAL,
                component,
                health_check.message,
                health_check.metrics
            ))
        elif health_check.status == HealthStatus.WARNING:
            asyncio.create_task(self._create_alert(
                AlertLevel.WARNING,
                component,
                health_check.message,
                health_check.metrics
            ))
    
    async def _check_component(self, component: str) -> Dict[str, Any]:
        """Check health of a specific component"""
        
        if component == "system":
            metrics = await self.get_system_metrics()
            return {
                "status": "healthy",
                "metrics": {
                    "cpu_usage": metrics.cpu_usage,
                    "memory_usage": metrics.memory_usage,
                    "disk_usage": metrics.disk_usage
                },
                "timestamp": datetime.now().isoformat()
            }
        elif component == "services":
            api_health = await self._check_api_health()
            db_health = await self._check_database_health()
            ai_health = await self._check_ai_models_health()
            
            return {
                "api": {
                    "status": api_health.status.value,
                    "message": api_health.message
                },
                "database": {
                    "status": db_health.status.value,
                    "message": db_health.message
                },
                "ai_models": {
                    "status": ai_health.status.value,
                    "message": ai_health.message
                },
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {"error": f"Unknown component: {component}"}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of the monitor itself"""
        return {
            "system_monitor": True,
            "is_monitoring": self.is_monitoring,
            "health_checks": len(self.health_checks),
            "alerts": len(self.alerts),
            "performance_history": len(self.performance_history),
            "thresholds_configured": len(self.thresholds)
        }
