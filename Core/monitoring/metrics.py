"""
Advanced Metrics Collection System
Prometheus integration with custom metrics and business intelligence
"""

import time
import threading
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import asyncio
import json

try:
    from prometheus_client import Counter, Histogram, Gauge, Summary, CollectorRegistry, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Mock classes for when prometheus_client is not available
    class Counter:
        def __init__(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    class Histogram:
        def __init__(self, *args, **kwargs): pass
        def observe(self, *args, **kwargs): pass
        def time(self): return self
        def __enter__(self): return self
        def __exit__(self, *args): pass
    class Gauge:
        def __init__(self, *args, **kwargs): pass
        def set(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def dec(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    class Summary:
        def __init__(self, *args, **kwargs): pass
        def observe(self, *args, **kwargs): pass
        def time(self): return self
        def __enter__(self): return self
        def __exit__(self, *args): pass
    class CollectorRegistry:
        def __init__(self): pass
    def generate_latest(registry): return b""

from ..config.logging import get_logger
from ..config.exceptions import MonitoringError

logger = get_logger(__name__)


class MetricType(str, Enum):
    """Types of metrics supported"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricDefinition:
    """Definition of a custom metric"""
    name: str
    type: MetricType
    description: str
    labels: List[str] = None
    buckets: List[float] = None  # For histograms
    quantiles: List[float] = None  # For summaries


class MetricsCollector:
    """Advanced metrics collection system with Prometheus integration"""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or CollectorRegistry()
        self.metrics: Dict[str, Any] = {}
        self.custom_metrics: Dict[str, MetricDefinition] = {}
        self.metric_data: Dict[str, List[Dict[str, Any]]] = {}
        self.lock = threading.Lock()
        self.start_time = time.time()
        
        # Initialize core metrics
        self._initialize_core_metrics()
        
        # Start background collection
        self._start_background_collection()
    
    def _initialize_core_metrics(self):
        """Initialize core system metrics"""
        try:
            # Request metrics
            self.metrics['requests_total'] = Counter(
                'tantra_requests_total',
                'Total number of requests',
                ['method', 'endpoint', 'status_code'],
                registry=self.registry
            )
            
            self.metrics['request_duration'] = Histogram(
                'tantra_request_duration_seconds',
                'Request duration in seconds',
                ['method', 'endpoint'],
                buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0],
                registry=self.registry
            )
            
            # AI/LLM metrics
            self.metrics['llm_requests_total'] = Counter(
                'tantra_llm_requests_total',
                'Total LLM requests',
                ['provider', 'model', 'status'],
                registry=self.registry
            )
            
            self.metrics['llm_tokens_used'] = Counter(
                'tantra_llm_tokens_total',
                'Total tokens used',
                ['provider', 'model', 'type'],
                registry=self.registry
            )
            
            self.metrics['llm_response_time'] = Histogram(
                'tantra_llm_response_time_seconds',
                'LLM response time',
                ['provider', 'model'],
                buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
                registry=self.registry
            )
            
            # Agent metrics
            self.metrics['agent_executions_total'] = Counter(
                'tantra_agent_executions_total',
                'Total agent executions',
                ['agent_type', 'status'],
                registry=self.registry
            )
            
            self.metrics['agent_duration'] = Histogram(
                'tantra_agent_duration_seconds',
                'Agent execution duration',
                ['agent_type'],
                buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
                registry=self.registry
            )
            
            # System metrics
            self.metrics['active_sessions'] = Gauge(
                'tantra_active_sessions',
                'Number of active user sessions',
                registry=self.registry
            )
            
            self.metrics['memory_usage'] = Gauge(
                'tantra_memory_usage_bytes',
                'Memory usage in bytes',
                ['type'],
                registry=self.registry
            )
            
            self.metrics['cpu_usage'] = Gauge(
                'tantra_cpu_usage_percent',
                'CPU usage percentage',
                registry=self.registry
            )
            
            # Business metrics
            self.metrics['conversations_total'] = Counter(
                'tantra_conversations_total',
                'Total conversations',
                ['user_type'],
                registry=self.registry
            )
            
            self.metrics['messages_total'] = Counter(
                'tantra_messages_total',
                'Total messages processed',
                ['message_type'],
                registry=self.registry
            )
            
            self.metrics['errors_total'] = Counter(
                'tantra_errors_total',
                'Total errors',
                ['error_type', 'component'],
                registry=self.registry
            )
            
            logger.info("Core metrics initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize core metrics: {e}")
            raise MonitoringError(f"Metrics initialization failed: {e}")
    
    def create_custom_metric(self, definition: MetricDefinition):
        """Create a custom metric"""
        try:
            with self.lock:
                if definition.name in self.custom_metrics:
                    logger.warning(f"Metric {definition.name} already exists")
                    return
                
                self.custom_metrics[definition.name] = definition
                
                # Create the actual metric based on type
                if definition.type == MetricType.COUNTER:
                    metric = Counter(
                        definition.name,
                        definition.description,
                        definition.labels or [],
                        registry=self.registry
                    )
                elif definition.type == MetricType.GAUGE:
                    metric = Gauge(
                        definition.name,
                        definition.description,
                        definition.labels or [],
                        registry=self.registry
                    )
                elif definition.type == MetricType.HISTOGRAM:
                    metric = Histogram(
                        definition.name,
                        definition.description,
                        definition.labels or [],
                        buckets=definition.buckets or [0.1, 0.5, 1.0, 2.5, 5.0, 10.0],
                        registry=self.registry
                    )
                elif definition.type == MetricType.SUMMARY:
                    metric = Summary(
                        definition.name,
                        definition.description,
                        definition.labels or [],
                        registry=self.registry
                    )
                else:
                    raise ValueError(f"Unknown metric type: {definition.type}")
                
                self.metrics[definition.name] = metric
                logger.info(f"Created custom metric: {definition.name}")
                
        except Exception as e:
            logger.error(f"Failed to create custom metric {definition.name}: {e}")
            raise MonitoringError(f"Custom metric creation failed: {e}")
    
    def record_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Record HTTP request metrics"""
        try:
            self.metrics['requests_total'].labels(
                method=method,
                endpoint=endpoint,
                status_code=str(status_code)
            ).inc()
            
            self.metrics['request_duration'].labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
            
        except Exception as e:
            logger.error(f"Failed to record request metrics: {e}")
    
    def record_llm_request(self, provider: str, model: str, status: str, 
                          tokens_used: int, response_time: float, token_type: str = "total"):
        """Record LLM request metrics"""
        try:
            self.metrics['llm_requests_total'].labels(
                provider=provider,
                model=model,
                status=status
            ).inc()
            
            self.metrics['llm_tokens_used'].labels(
                provider=provider,
                model=model,
                type=token_type
            ).inc(tokens_used)
            
            self.metrics['llm_response_time'].labels(
                provider=provider,
                model=model
            ).observe(response_time)
            
        except Exception as e:
            logger.error(f"Failed to record LLM metrics: {e}")
    
    def record_agent_execution(self, agent_type: str, status: str, duration: float):
        """Record agent execution metrics"""
        try:
            self.metrics['agent_executions_total'].labels(
                agent_type=agent_type,
                status=status
            ).inc()
            
            self.metrics['agent_duration'].labels(
                agent_type=agent_type
            ).observe(duration)
            
        except Exception as e:
            logger.error(f"Failed to record agent metrics: {e}")
    
    def record_error(self, error_type: str, component: str):
        """Record error metrics"""
        try:
            self.metrics['errors_total'].labels(
                error_type=error_type,
                component=component
            ).inc()
            
        except Exception as e:
            logger.error(f"Failed to record error metrics: {e}")
    
    def update_system_metrics(self, memory_usage: Dict[str, float], cpu_usage: float, 
                             active_sessions: int):
        """Update system resource metrics"""
        try:
            self.metrics['active_sessions'].set(active_sessions)
            self.metrics['cpu_usage'].set(cpu_usage)
            
            for mem_type, usage in memory_usage.items():
                self.metrics['memory_usage'].labels(type=mem_type).set(usage)
                
        except Exception as e:
            logger.error(f"Failed to update system metrics: {e}")
    
    def record_business_event(self, event_type: str, **labels):
        """Record business events"""
        try:
            if event_type == "conversation":
                self.metrics['conversations_total'].labels(
                    user_type=labels.get('user_type', 'unknown')
                ).inc()
            elif event_type == "message":
                self.metrics['messages_total'].labels(
                    message_type=labels.get('message_type', 'unknown')
                ).inc()
                
        except Exception as e:
            logger.error(f"Failed to record business event: {e}")
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics"""
        try:
            with self.lock:
                summary = {
                    "uptime_seconds": time.time() - self.start_time,
                    "total_metrics": len(self.metrics),
                    "custom_metrics": len(self.custom_metrics),
                    "prometheus_available": PROMETHEUS_AVAILABLE,
                    "registry_type": type(self.registry).__name__
                }
                
                # Add metric data if available
                for metric_name, metric_data in self.metric_data.items():
                    if metric_data:
                        summary[f"{metric_name}_count"] = len(metric_data)
                        summary[f"{metric_name}_latest"] = metric_data[-1]
                
                return summary
                
        except Exception as e:
            logger.error(f"Failed to get metrics summary: {e}")
            return {"error": str(e)}
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format"""
        try:
            if not PROMETHEUS_AVAILABLE:
                return "# Prometheus client not available\n"
            
            return generate_latest(self.registry).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Failed to export Prometheus metrics: {e}")
            return f"# Error exporting metrics: {e}\n"
    
    def _start_background_collection(self):
        """Start background metrics collection"""
        def collect_metrics():
            while True:
                try:
                    # Collect system metrics
                    import psutil
                    process = psutil.Process()
                    memory_info = process.memory_info()
                    
                    memory_usage = {
                        'rss': memory_info.rss,
                        'vms': memory_info.vms
                    }
                    
                    cpu_usage = process.cpu_percent()
                    
                    # Update metrics
                    self.update_system_metrics(memory_usage, cpu_usage, 0)  # Active sessions would be tracked elsewhere
                    
                    time.sleep(30)  # Collect every 30 seconds
                    
                except Exception as e:
                    logger.error(f"Background metrics collection error: {e}")
                    time.sleep(60)
        
        thread = threading.Thread(target=collect_metrics, daemon=True)
        thread.start()
        logger.info("Background metrics collection started")


class PrometheusMetrics:
    """Prometheus-specific metrics utilities"""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
        self.registry = collector.registry
    
    def get_metrics_endpoint(self) -> str:
        """Get metrics endpoint content"""
        return self.collector.export_prometheus()
    
    def get_health_check(self) -> Dict[str, Any]:
        """Get health check for metrics system"""
        return {
            "status": "healthy" if PROMETHEUS_AVAILABLE else "degraded",
            "prometheus_available": PROMETHEUS_AVAILABLE,
            "metrics_count": len(self.collector.metrics),
            "uptime": time.time() - self.collector.start_time
        }
    
    def create_dashboard_config(self) -> Dict[str, Any]:
        """Create Grafana dashboard configuration"""
        return {
            "dashboard": {
                "title": "Atulya Tantra AGI Metrics",
                "panels": [
                    {
                        "title": "Request Rate",
                        "type": "graph",
                        "targets": [
                            {
                                "expr": "rate(tantra_requests_total[5m])",
                                "legendFormat": "{{method}} {{endpoint}}"
                            }
                        ]
                    },
                    {
                        "title": "Response Time",
                        "type": "graph", 
                        "targets": [
                            {
                                "expr": "histogram_quantile(0.95, rate(tantra_request_duration_seconds_bucket[5m]))",
                                "legendFormat": "95th percentile"
                            }
                        ]
                    },
                    {
                        "title": "LLM Usage",
                        "type": "graph",
                        "targets": [
                            {
                                "expr": "rate(tantra_llm_requests_total[5m])",
                                "legendFormat": "{{provider}} {{model}}"
                            }
                        ]
                    },
                    {
                        "title": "System Resources",
                        "type": "graph",
                        "targets": [
                            {
                                "expr": "tantra_cpu_usage_percent",
                                "legendFormat": "CPU Usage %"
                            },
                            {
                                "expr": "tantra_memory_usage_bytes / 1024 / 1024",
                                "legendFormat": "Memory Usage MB"
                            }
                        ]
                    }
                ]
            }
        }


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def get_prometheus_metrics() -> PrometheusMetrics:
    """Get Prometheus metrics instance"""
    collector = get_metrics_collector()
    return PrometheusMetrics(collector)