"""
Advanced Performance Monitoring System
Real-time performance tracking, profiling, and optimization recommendations
"""

import time
import asyncio
import threading
import psutil
import tracemalloc
from typing import Dict, List, Any, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json
import functools
import inspect
from collections import defaultdict, deque

from ..config.logging import get_logger
from ..config.exceptions import MonitoringError

logger = get_logger(__name__)


class PerformanceMetric(str, Enum):
    """Performance metric types"""
    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"
    ERROR_RATE = "error_rate"
    CONCURRENT_REQUESTS = "concurrent_requests"
    CACHE_HIT_RATE = "cache_hit_rate"
    DATABASE_QUERY_TIME = "database_query_time"
    LLM_RESPONSE_TIME = "llm_response_time"
    AGENT_EXECUTION_TIME = "agent_execution_time"


@dataclass
class PerformanceData:
    """Performance data point"""
    metric: PerformanceMetric
    value: float
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceProfile:
    """Performance profile for a function or operation"""
    name: str
    total_calls: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    avg_time: float = 0.0
    last_call: Optional[datetime] = None
    error_count: int = 0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0


class PerformanceMonitor:
    """Advanced performance monitoring system"""
    
    def __init__(self, max_history: int = 10000, check_interval: int = 30):
        self.max_history = max_history
        self.check_interval = check_interval
        self.is_running = False
        
        # Performance data storage
        self.metrics: Dict[PerformanceMetric, deque] = {
            metric: deque(maxlen=max_history) for metric in PerformanceMetric
        }
        self.profiles: Dict[str, PerformanceProfile] = {}
        self.active_requests: Dict[str, Dict[str, Any]] = {}
        self.request_counter = 0
        
        # System monitoring
        self.system_metrics = {
            'cpu_percent': deque(maxlen=1000),
            'memory_percent': deque(maxlen=1000),
            'memory_usage': deque(maxlen=1000),
            'disk_io': deque(maxlen=1000),
            'network_io': deque(maxlen=1000)
        }
        
        # Performance thresholds
        self.thresholds = {
            PerformanceMetric.RESPONSE_TIME: 5.0,  # seconds
            PerformanceMetric.MEMORY_USAGE: 80.0,  # percent
            PerformanceMetric.CPU_USAGE: 80.0,  # percent
            PerformanceMetric.ERROR_RATE: 5.0,  # percent
            PerformanceMetric.CONCURRENT_REQUESTS: 100
        }
        
        # Alerts and recommendations
        self.alerts: List[Dict[str, Any]] = []
        self.recommendations: List[Dict[str, Any]] = []
        
        # Start system monitoring
        self._start_system_monitoring()
    
    def _start_system_monitoring(self):
        """Start background system monitoring"""
        def monitor_system():
            while True:
                try:
                    # CPU usage
                    cpu_percent = psutil.cpu_percent(interval=1)
                    self.system_metrics['cpu_percent'].append({
                        'value': cpu_percent,
                        'timestamp': datetime.utcnow()
                    })
                    
                    # Memory usage
                    memory = psutil.virtual_memory()
                    self.system_metrics['memory_percent'].append({
                        'value': memory.percent,
                        'timestamp': datetime.utcnow()
                    })
                    self.system_metrics['memory_usage'].append({
                        'value': memory.used / (1024**3),  # GB
                        'timestamp': datetime.utcnow()
                    })
                    
                    # Disk I/O
                    disk_io = psutil.disk_io_counters()
                    if disk_io:
                        self.system_metrics['disk_io'].append({
                            'read_bytes': disk_io.read_bytes,
                            'write_bytes': disk_io.write_bytes,
                            'timestamp': datetime.utcnow()
                        })
                    
                    # Network I/O
                    network_io = psutil.net_io_counters()
                    if network_io:
                        self.system_metrics['network_io'].append({
                            'bytes_sent': network_io.bytes_sent,
                            'bytes_recv': network_io.bytes_recv,
                            'timestamp': datetime.utcnow()
                        })
                    
                    time.sleep(self.check_interval)
                    
                except Exception as e:
                    logger.error(f"Error in system monitoring: {e}")
                    time.sleep(60)
        
        thread = threading.Thread(target=monitor_system, daemon=True)
        thread.start()
    
    def start_request(self, request_id: str = None, **metadata) -> str:
        """Start tracking a request"""
        if request_id is None:
            self.request_counter += 1
            request_id = f"req_{self.request_counter}_{int(time.time())}"
        
        self.active_requests[request_id] = {
            'start_time': time.time(),
            'start_datetime': datetime.utcnow(),
            'metadata': metadata
        }
        
        return request_id
    
    def end_request(self, request_id: str, success: bool = True, **metadata):
        """End tracking a request"""
        if request_id not in self.active_requests:
            return
        
        request_data = self.active_requests[request_id]
        duration = time.time() - request_data['start_time']
        
        # Record response time
        self.record_metric(
            PerformanceMetric.RESPONSE_TIME,
            duration,
            labels={'success': str(success)},
            metadata=metadata
        )
        
        # Update request metadata
        request_data.update({
            'end_time': time.time(),
            'duration': duration,
            'success': success,
            'metadata': {**request_data['metadata'], **metadata}
        })
        
        # Remove from active requests
        del self.active_requests[request_id]
        
        # Check thresholds
        self._check_thresholds(PerformanceMetric.RESPONSE_TIME, duration)
    
    def record_metric(self, metric: PerformanceMetric, value: float, 
                     labels: Dict[str, str] = None, metadata: Dict[str, Any] = None):
        """Record a performance metric"""
        data_point = PerformanceData(
            metric=metric,
            value=value,
            timestamp=datetime.utcnow(),
            labels=labels or {},
            metadata=metadata or {}
        )
        
        self.metrics[metric].append(data_point)
        
        # Check thresholds
        self._check_thresholds(metric, value)
    
    def _check_thresholds(self, metric: PerformanceMetric, value: float):
        """Check if metric exceeds thresholds"""
        threshold = self.thresholds.get(metric)
        if threshold is None:
            return
        
        if value > threshold:
            alert = {
                'metric': metric.value,
                'value': value,
                'threshold': threshold,
                'timestamp': datetime.utcnow(),
                'severity': 'warning' if value < threshold * 1.5 else 'critical'
            }
            
            self.alerts.append(alert)
            logger.warning(f"Performance threshold exceeded: {metric.value} = {value} (threshold: {threshold})")
    
    def profile_function(self, func: Callable) -> Callable:
        """Decorator to profile a function"""
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            start_memory = self._get_memory_usage()
            
            try:
                result = await func(*args, **kwargs)
                success = True
            except Exception as e:
                success = False
                raise
            finally:
                end_time = time.time()
                end_memory = self._get_memory_usage()
                
                duration = end_time - start_time
                memory_used = end_memory - start_memory
                
                self._update_profile(func.__name__, duration, success, memory_used)
                
                # Record as agent execution time if it's an agent function
                if 'agent' in func.__name__.lower():
                    self.record_metric(
                        PerformanceMetric.AGENT_EXECUTION_TIME,
                        duration,
                        labels={'function': func.__name__, 'success': str(success)}
                    )
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            start_memory = self._get_memory_usage()
            
            try:
                result = func(*args, **kwargs)
                success = True
            except Exception as e:
                success = False
                raise
            finally:
                end_time = time.time()
                end_memory = self._get_memory_usage()
                
                duration = end_time - start_time
                memory_used = end_memory - start_memory
                
                self._update_profile(func.__name__, duration, success, memory_used)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        try:
            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)
        except:
            return 0.0
    
    def _update_profile(self, name: str, duration: float, success: bool, memory_used: float):
        """Update function profile"""
        if name not in self.profiles:
            self.profiles[name] = PerformanceProfile(name=name)
        
        profile = self.profiles[name]
        profile.total_calls += 1
        profile.total_time += duration
        profile.min_time = min(profile.min_time, duration)
        profile.max_time = max(profile.max_time, duration)
        profile.avg_time = profile.total_time / profile.total_calls
        profile.last_call = datetime.utcnow()
        profile.memory_usage = memory_used
        
        if not success:
            profile.error_count += 1
    
    def get_metrics_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Get performance metrics summary"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        summary = {
            'time_range': f'Last {hours} hours',
            'metrics': {},
            'system_health': self._get_system_health(),
            'active_requests': len(self.active_requests),
            'alerts': len(self.alerts),
            'recommendations': len(self.recommendations)
        }
        
        # Analyze each metric
        for metric, data_points in self.metrics.items():
            recent_points = [dp for dp in data_points if dp.timestamp >= cutoff_time]
            
            if not recent_points:
                continue
            
            values = [dp.value for dp in recent_points]
            
            summary['metrics'][metric.value] = {
                'count': len(values),
                'min': min(values),
                'max': max(values),
                'avg': sum(values) / len(values),
                'latest': values[-1] if values else None,
                'threshold_exceeded': any(v > self.thresholds.get(metric, float('inf')) for v in values)
            }
        
        return summary
    
    def _get_system_health(self) -> Dict[str, Any]:
        """Get system health metrics"""
        if not self.system_metrics['cpu_percent']:
            return {'status': 'unknown', 'message': 'No system data available'}
        
        # Get latest values
        latest_cpu = self.system_metrics['cpu_percent'][-1]['value']
        latest_memory = self.system_metrics['memory_percent'][-1]['value']
        
        # Determine health status
        if latest_cpu > 90 or latest_memory > 95:
            status = 'critical'
            message = f'System under high load: CPU {latest_cpu:.1f}%, Memory {latest_memory:.1f}%'
        elif latest_cpu > 80 or latest_memory > 85:
            status = 'warning'
            message = f'System under moderate load: CPU {latest_cpu:.1f}%, Memory {latest_memory:.1f}%'
        else:
            status = 'healthy'
            message = f'System running normally: CPU {latest_cpu:.1f}%, Memory {latest_memory:.1f}%'
        
        return {
            'status': status,
            'message': message,
            'cpu_percent': latest_cpu,
            'memory_percent': latest_memory,
            'memory_usage_gb': self.system_metrics['memory_usage'][-1]['value'] if self.system_metrics['memory_usage'] else 0
        }
    
    def get_performance_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Get performance profiles for all functions"""
        profiles = {}
        
        for name, profile in self.profiles.items():
            profiles[name] = {
                'name': profile.name,
                'total_calls': profile.total_calls,
                'total_time': profile.total_time,
                'min_time': profile.min_time if profile.min_time != float('inf') else 0,
                'max_time': profile.max_time,
                'avg_time': profile.avg_time,
                'last_call': profile.last_call.isoformat() if profile.last_call else None,
                'error_count': profile.error_count,
                'error_rate': (profile.error_count / profile.total_calls * 100) if profile.total_calls > 0 else 0,
                'memory_usage': profile.memory_usage,
                'efficiency_score': self._calculate_efficiency_score(profile)
            }
        
        return profiles
    
    def _calculate_efficiency_score(self, profile: PerformanceProfile) -> float:
        """Calculate efficiency score for a function (0-100)"""
        if profile.total_calls == 0:
            return 0.0
        
        # Base score
        score = 100.0
        
        # Penalize for errors
        error_rate = (profile.error_count / profile.total_calls) * 100
        score -= error_rate * 2  # 2 points per error percent
        
        # Penalize for slow execution
        if profile.avg_time > 1.0:  # More than 1 second
            score -= min(50, (profile.avg_time - 1.0) * 10)  # Up to 50 points penalty
        
        # Penalize for high memory usage
        if profile.memory_usage > 100:  # More than 100MB
            score -= min(30, (profile.memory_usage - 100) / 10)  # Up to 30 points penalty
        
        return max(0.0, score)
    
    def get_slowest_functions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get slowest functions by average execution time"""
        profiles = self.get_performance_profiles()
        
        # Sort by average time (descending)
        sorted_profiles = sorted(
            profiles.items(),
            key=lambda x: x[1]['avg_time'],
            reverse=True
        )
        
        return [
            {
                'name': name,
                'avg_time': data['avg_time'],
                'total_calls': data['total_calls'],
                'efficiency_score': data['efficiency_score']
            }
            for name, data in sorted_profiles[:limit]
        ]
    
    def get_most_called_functions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most called functions"""
        profiles = self.get_performance_profiles()
        
        # Sort by total calls (descending)
        sorted_profiles = sorted(
            profiles.items(),
            key=lambda x: x[1]['total_calls'],
            reverse=True
        )
        
        return [
            {
                'name': name,
                'total_calls': data['total_calls'],
                'avg_time': data['avg_time'],
                'total_time': data['total_time']
            }
            for name, data in sorted_profiles[:limit]
        ]
    
    def get_recommendations(self) -> List[Dict[str, Any]]:
        """Get performance optimization recommendations"""
        recommendations = []
        
        # Analyze slow functions
        slow_functions = self.get_slowest_functions(5)
        for func in slow_functions:
            if func['avg_time'] > 1.0:  # More than 1 second
                recommendations.append({
                    'type': 'slow_function',
                    'priority': 'high' if func['avg_time'] > 5.0 else 'medium',
                    'title': f"Optimize slow function: {func['name']}",
                    'description': f"Function {func['name']} takes {func['avg_time']:.2f}s on average",
                    'suggestion': "Consider caching, async operations, or algorithm optimization"
                })
        
        # Analyze error-prone functions
        profiles = self.get_performance_profiles()
        for name, data in profiles.items():
            if data['error_rate'] > 10:  # More than 10% error rate
                recommendations.append({
                    'type': 'error_prone_function',
                    'priority': 'high',
                    'title': f"Fix error-prone function: {name}",
                    'description': f"Function {name} has {data['error_rate']:.1f}% error rate",
                    'suggestion': "Add better error handling and input validation"
                })
        
        # Analyze memory usage
        high_memory_functions = [
            (name, data) for name, data in profiles.items()
            if data['memory_usage'] > 50  # More than 50MB
        ]
        
        if high_memory_functions:
            recommendations.append({
                'type': 'memory_usage',
                'priority': 'medium',
                'title': "Optimize memory usage",
                'description': f"{len(high_memory_functions)} functions use significant memory",
                'suggestion': "Consider memory pooling, lazy loading, or garbage collection optimization"
            })
        
        # Analyze system resources
        system_health = self._get_system_health()
        if system_health['status'] in ['warning', 'critical']:
            recommendations.append({
                'type': 'system_resources',
                'priority': 'high' if system_health['status'] == 'critical' else 'medium',
                'title': "System resource optimization needed",
                'description': system_health['message'],
                'suggestion': "Consider scaling, load balancing, or resource optimization"
            })
        
        return recommendations
    
    def get_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get performance alerts from the last N hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        recent_alerts = [
            alert for alert in self.alerts
            if alert['timestamp'] >= cutoff_time
        ]
        
        return sorted(recent_alerts, key=lambda x: x['timestamp'], reverse=True)
    
    def clear_old_data(self, hours: int = 24):
        """Clear old performance data"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Clear old metrics
        for metric_data in self.metrics.values():
            while metric_data and metric_data[0].timestamp < cutoff_time:
                metric_data.popleft()
        
        # Clear old system metrics
        for system_data in self.system_metrics.values():
            while system_data and system_data[0]['timestamp'] < cutoff_time:
                system_data.popleft()
        
        # Clear old alerts
        self.alerts = [
            alert for alert in self.alerts
            if alert['timestamp'] >= cutoff_time
        ]
        
        logger.info(f"Cleared performance data older than {hours} hours")


class Profiler:
    """Advanced code profiler with memory tracking"""
    
    def __init__(self):
        self.traces = {}
        self.memory_snapshots = {}
        self.is_profiling = False
    
    def start_profiling(self):
        """Start profiling"""
        if not self.is_profiling:
            tracemalloc.start()
            self.is_profiling = True
            logger.info("Profiling started")
    
    def stop_profiling(self):
        """Stop profiling"""
        if self.is_profiling:
            tracemalloc.stop()
            self.is_profiling = False
            logger.info("Profiling stopped")
    
    def take_memory_snapshot(self, name: str):
        """Take a memory snapshot"""
        if not self.is_profiling:
            return
        
        snapshot = tracemalloc.take_snapshot()
        self.memory_snapshots[name] = {
            'snapshot': snapshot,
            'timestamp': datetime.utcnow()
        }
    
    def compare_snapshots(self, snapshot1: str, snapshot2: str) -> Dict[str, Any]:
        """Compare two memory snapshots"""
        if snapshot1 not in self.memory_snapshots or snapshot2 not in self.memory_snapshots:
            return {}
        
        snap1 = self.memory_snapshots[snapshot1]['snapshot']
        snap2 = self.memory_snapshots[snapshot2]['snapshot']
        
        top_stats = snap2.compare_to(snap1, 'lineno')
        
        return {
            'snapshot1': snapshot1,
            'snapshot2': snapshot2,
            'top_stats': [
                {
                    'filename': stat.traceback.format()[0],
                    'size_diff': stat.size_diff,
                    'count_diff': stat.count_diff
                }
                for stat in top_stats[:10]
            ]
        }
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get current memory statistics"""
        if not self.is_profiling:
            return {}
        
        current, peak = tracemalloc.get_traced_memory()
        
        return {
            'current_mb': current / (1024 * 1024),
            'peak_mb': peak / (1024 * 1024),
            'snapshots_count': len(self.memory_snapshots)
        }


# Global performance monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


def get_profiler() -> Profiler:
    """Get profiler instance"""
    return Profiler()