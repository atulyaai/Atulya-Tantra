"""
Atulya Tantra - Monitoring and Metrics System
Version: 2.0.1
Comprehensive monitoring, metrics collection, and health checking for the AGI system.
"""

import asyncio
import time
import psutil
import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict, deque
import threading
from prometheus_client import Counter, Histogram, Gauge, start_http_server

@dataclass
class Metric:
    """Metric data structure"""
    name: str
    value: float
    timestamp: datetime
    labels: Dict[str, str]
    metric_type: str  # 'counter', 'gauge', 'histogram'

@dataclass
class HealthStatus:
    """Health status data structure"""
    component: str
    status: str  # 'healthy', 'degraded', 'unhealthy'
    message: str
    timestamp: datetime
    metrics: Dict[str, Any]

class MetricsCollector:
    """Collects and stores system metrics"""
    
    def __init__(self, max_metrics: int = 10000):
        self.metrics: deque = deque(maxlen=max_metrics)
        self.counters: Dict[str, Counter] = {}
        self.gauges: Dict[str, Gauge] = {}
        self.histograms: Dict[str, Histogram] = {}
        self._init_prometheus_metrics()
    
    def _init_prometheus_metrics(self):
        """Initialize Prometheus metrics"""
        # Request metrics
        self.counters['requests_total'] = Counter(
            'atulya_requests_total',
            'Total number of requests',
            ['method', 'endpoint', 'status']
        )
        
        self.histograms['request_duration'] = Histogram(
            'atulya_request_duration_seconds',
            'Request duration in seconds',
            ['method', 'endpoint']
        )
        
        # AI model metrics
        self.counters['model_requests'] = Counter(
            'atulya_model_requests_total',
            'Total model requests',
            ['provider', 'model', 'status']
        )
        
        self.histograms['model_response_time'] = Histogram(
            'atulya_model_response_time_seconds',
            'Model response time in seconds',
            ['provider', 'model']
        )
        
        self.gauges['model_tokens_used'] = Gauge(
            'atulya_model_tokens_used',
            'Total tokens used by model',
            ['provider', 'model']
        )
        
        # System metrics
        self.gauges['memory_usage'] = Gauge(
            'atulya_memory_usage_bytes',
            'Memory usage in bytes'
        )
        
        self.gauges['cpu_usage'] = Gauge(
            'atulya_cpu_usage_percent',
            'CPU usage percentage'
        )
        
        self.gauges['active_connections'] = Gauge(
            'atulya_active_connections',
            'Number of active connections'
        )
    
    def record_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Record HTTP request metrics"""
        self.counters['requests_total'].labels(
            method=method,
            endpoint=endpoint,
            status=str(status_code)
        ).inc()
        
        self.histograms['request_duration'].labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    def record_model_request(self, provider: str, model: str, status: str, 
                           response_time: float, tokens_used: int = 0):
        """Record AI model request metrics"""
        self.counters['model_requests'].labels(
            provider=provider,
            model=model,
            status=status
        ).inc()
        
        self.histograms['model_response_time'].labels(
            provider=provider,
            model=model
        ).observe(response_time)
        
        if tokens_used > 0:
            self.gauges['model_tokens_used'].labels(
                provider=provider,
                model=model
            ).set(tokens_used)
    
    def update_system_metrics(self):
        """Update system resource metrics"""
        # Memory usage
        memory = psutil.virtual_memory()
        self.gauges['memory_usage'].set(memory.used)
        
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        self.gauges['cpu_usage'].set(cpu_percent)
    
    def get_metrics_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Get metrics summary for the last N hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # Filter recent metrics
        recent_metrics = [
            m for m in self.metrics 
            if m.timestamp > cutoff_time
        ]
        
        # Group by metric type
        summary = defaultdict(list)
        for metric in recent_metrics:
            summary[metric.name].append(metric.value)
        
        # Calculate statistics
        result = {}
        for name, values in summary.items():
            if values:
                result[name] = {
                    'count': len(values),
                    'min': min(values),
                    'max': max(values),
                    'avg': sum(values) / len(values),
                    'latest': values[-1]
                }
        
        return dict(result)

class HealthChecker:
    """Health checking system for all components"""
    
    def __init__(self):
        self.health_checks: Dict[str, Callable] = {}
        self.health_status: Dict[str, HealthStatus] = {}
        self._register_default_checks()
    
    def _register_default_checks(self):
        """Register default health checks"""
        self.register_check("database", self._check_database)
        self.register_check("memory", self._check_memory)
        self.register_check("cpu", self._check_cpu)
        self.register_check("disk", self._check_disk)
        self.register_check("network", self._check_network)
    
    def register_check(self, name: str, check_func: Callable):
        """Register a health check function"""
        self.health_checks[name] = check_func
    
    async def _check_database(self) -> HealthStatus:
        """Check database health"""
        try:
            # Try to connect to database
            import sqlite3
            conn = sqlite3.connect("data/database/atulya_tantra.db")
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            
            return HealthStatus(
                component="database",
                status="healthy",
                message="Database connection successful",
                timestamp=datetime.now(),
                metrics={"response_time": 0.001}
            )
        except Exception as e:
            return HealthStatus(
                component="database",
                status="unhealthy",
                message=f"Database error: {str(e)}",
                timestamp=datetime.now(),
                metrics={}
            )
    
    async def _check_memory(self) -> HealthStatus:
        """Check memory health"""
        try:
            memory = psutil.virtual_memory()
            usage_percent = memory.percent
            
            if usage_percent < 80:
                status = "healthy"
                message = f"Memory usage: {usage_percent:.1f}%"
            elif usage_percent < 90:
                status = "degraded"
                message = f"High memory usage: {usage_percent:.1f}%"
            else:
                status = "unhealthy"
                message = f"Critical memory usage: {usage_percent:.1f}%"
            
            return HealthStatus(
                component="memory",
                status=status,
                message=message,
                timestamp=datetime.now(),
                metrics={
                    "usage_percent": usage_percent,
                    "available_gb": memory.available / (1024**3),
                    "total_gb": memory.total / (1024**3)
                }
            )
        except Exception as e:
            return HealthStatus(
                component="memory",
                status="unhealthy",
                message=f"Memory check failed: {str(e)}",
                timestamp=datetime.now(),
                metrics={}
            )
    
    async def _check_cpu(self) -> HealthStatus:
        """Check CPU health"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            
            if cpu_percent < 70:
                status = "healthy"
                message = f"CPU usage: {cpu_percent:.1f}%"
            elif cpu_percent < 85:
                status = "degraded"
                message = f"High CPU usage: {cpu_percent:.1f}%"
            else:
                status = "unhealthy"
                message = f"Critical CPU usage: {cpu_percent:.1f}%"
            
            return HealthStatus(
                component="cpu",
                status=status,
                message=message,
                timestamp=datetime.now(),
                metrics={
                    "usage_percent": cpu_percent,
                    "core_count": psutil.cpu_count()
                }
            )
        except Exception as e:
            return HealthStatus(
                component="cpu",
                status="unhealthy",
                message=f"CPU check failed: {str(e)}",
                timestamp=datetime.now(),
                metrics={}
            )
    
    async def _check_disk(self) -> HealthStatus:
        """Check disk health"""
        try:
            disk = psutil.disk_usage('/')
            usage_percent = (disk.used / disk.total) * 100
            
            if usage_percent < 80:
                status = "healthy"
                message = f"Disk usage: {usage_percent:.1f}%"
            elif usage_percent < 90:
                status = "degraded"
                message = f"High disk usage: {usage_percent:.1f}%"
            else:
                status = "unhealthy"
                message = f"Critical disk usage: {usage_percent:.1f}%"
            
            return HealthStatus(
                component="disk",
                status=status,
                message=message,
                timestamp=datetime.now(),
                metrics={
                    "usage_percent": usage_percent,
                    "free_gb": disk.free / (1024**3),
                    "total_gb": disk.total / (1024**3)
                }
            )
        except Exception as e:
            return HealthStatus(
                component="disk",
                status="unhealthy",
                message=f"Disk check failed: {str(e)}",
                timestamp=datetime.now(),
                metrics={}
            )
    
    async def _check_network(self) -> HealthStatus:
        """Check network health"""
        try:
            # Simple network connectivity check
            import socket
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            
            return HealthStatus(
                component="network",
                status="healthy",
                message="Network connectivity OK",
                timestamp=datetime.now(),
                metrics={}
            )
        except Exception as e:
            return HealthStatus(
                component="network",
                status="unhealthy",
                message=f"Network error: {str(e)}",
                timestamp=datetime.now(),
                metrics={}
            )
    
    async def run_all_checks(self) -> Dict[str, HealthStatus]:
        """Run all registered health checks"""
        results = {}
        
        for name, check_func in self.health_checks.items():
            try:
                result = await check_func()
                results[name] = result
                self.health_status[name] = result
            except Exception as e:
                results[name] = HealthStatus(
                    component=name,
                    status="unhealthy",
                    message=f"Check failed: {str(e)}",
                    timestamp=datetime.now(),
                    metrics={}
                )
        
        return results
    
    def get_overall_health(self) -> str:
        """Get overall system health status"""
        if not self.health_status:
            return "unknown"
        
        statuses = [status.status for status in self.health_status.values()]
        
        if "unhealthy" in statuses:
            return "unhealthy"
        elif "degraded" in statuses:
            return "degraded"
        else:
            return "healthy"

class ContextMonitor:
    """Monitor system context and performance"""
    
    def __init__(self):
        self.context_history: deque = deque(maxlen=1000)
        self.performance_data: Dict[str, List[float]] = defaultdict(list)
    
    def record_context(self, context: Dict[str, Any]):
        """Record system context"""
        context_entry = {
            "timestamp": datetime.now(),
            "context": context
        }
        self.context_history.append(context_entry)
    
    def record_performance(self, metric_name: str, value: float):
        """Record performance metric"""
        self.performance_data[metric_name].append(value)
        
        # Keep only last 1000 values
        if len(self.performance_data[metric_name]) > 1000:
            self.performance_data[metric_name] = self.performance_data[metric_name][-1000:]
    
    def get_performance_summary(self, metric_name: str) -> Dict[str, float]:
        """Get performance summary for a metric"""
        values = self.performance_data.get(metric_name, [])
        
        if not values:
            return {}
        
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "latest": values[-1]
        }
    
    def get_context_trends(self, hours: int = 1) -> Dict[str, Any]:
        """Get context trends over time"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent_contexts = [
            entry for entry in self.context_history
            if entry["timestamp"] > cutoff_time
        ]
        
        # Analyze trends (simplified)
        trends = {
            "total_contexts": len(recent_contexts),
            "time_range": {
                "start": recent_contexts[0]["timestamp"] if recent_contexts else None,
                "end": recent_contexts[-1]["timestamp"] if recent_contexts else None
            }
        }
        
        return trends

class MonitoringSystem:
    """Main monitoring system coordinator"""
    
    def __init__(self, prometheus_port: int = 9090):
        self.metrics_collector = MetricsCollector()
        self.health_checker = HealthChecker()
        self.context_monitor = ContextMonitor()
        self.prometheus_port = prometheus_port
        self.monitoring_active = False
        self.monitoring_task: Optional[asyncio.Task] = None
    
    def start_prometheus_server(self):
        """Start Prometheus metrics server"""
        try:
            start_http_server(self.prometheus_port)
            print(f"Prometheus metrics server started on port {self.prometheus_port}")
        except Exception as e:
            print(f"Failed to start Prometheus server: {e}")
    
    async def start_monitoring(self):
        """Start continuous monitoring"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
    
    async def stop_monitoring(self):
        """Stop continuous monitoring"""
        self.monitoring_active = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.monitoring_active:
            try:
                # Update system metrics
                self.metrics_collector.update_system_metrics()
                
                # Run health checks
                await self.health_checker.run_all_checks()
                
                # Record context
                context = {
                    "active_connections": 0,  # Placeholder
                    "memory_usage": psutil.virtual_memory().percent,
                    "cpu_usage": psutil.cpu_percent()
                }
                self.context_monitor.record_context(context)
                
                # Wait before next check
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                print(f"Monitoring error: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            "overall_health": self.health_checker.get_overall_health(),
            "health_details": {
                name: asdict(status) for name, status in self.health_checker.health_status.items()
            },
            "metrics_summary": self.metrics_collector.get_metrics_summary(),
            "performance_summary": {
                name: self.context_monitor.get_performance_summary(name)
                for name in self.context_monitor.performance_data.keys()
            },
            "context_trends": self.context_monitor.get_context_trends()
        }

# Global instances
_metrics_collector: Optional[MetricsCollector] = None
_health_checker: Optional[HealthChecker] = None
_context_monitor: Optional[ContextMonitor] = None
_monitoring_system: Optional[MonitoringSystem] = None

def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector

def get_health_checker() -> HealthChecker:
    """Get global health checker instance"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker

def get_context_monitor() -> ContextMonitor:
    """Get global context monitor instance"""
    global _context_monitor
    if _context_monitor is None:
        _context_monitor = ContextMonitor()
    return _context_monitor

def get_monitoring_system() -> MonitoringSystem:
    """Get global monitoring system instance"""
    global _monitoring_system
    if _monitoring_system is None:
        _monitoring_system = MonitoringSystem()
    return _monitoring_system

# Export main classes and functions
__all__ = [
    "Metric",
    "HealthStatus",
    "MetricsCollector",
    "HealthChecker", 
    "ContextMonitor",
    "MonitoringSystem",
    "get_metrics_collector",
    "get_health_checker",
    "get_context_monitor",
    "get_monitoring_system"
]
