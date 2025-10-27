"""
Advanced Health Checking System
Comprehensive health monitoring with dependency checks and status reporting
"""

import asyncio
import time
import psutil
import aiohttp
from typing import Dict, List, Any, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json

from ..config.logging import get_logger
from ..config.exceptions import MonitoringError

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CheckType(str, Enum):
    """Types of health checks"""
    SYSTEM = "system"
    DATABASE = "database"
    EXTERNAL = "external"
    SERVICE = "service"
    CUSTOM = "custom"


@dataclass
class HealthCheck:
    """Health check definition"""
    name: str
    check_type: CheckType
    check_function: Callable
    timeout: int = 30
    interval: int = 60
    enabled: bool = True
    critical: bool = True
    metadata: Dict[str, Any] = None


@dataclass
class HealthResult:
    """Health check result"""
    name: str
    status: HealthStatus
    message: str
    response_time_ms: float
    timestamp: datetime
    metadata: Dict[str, Any] = None
    error: Optional[str] = None


class HealthChecker:
    """Advanced health checking system"""
    
    def __init__(self):
        self.checks: Dict[str, HealthCheck] = {}
        self.results: Dict[str, HealthResult] = {}
        self.is_running = False
        self.check_tasks: Dict[str, asyncio.Task] = {}
        
        # Initialize default checks
        self._create_default_checks()
    
    def _create_default_checks(self):
        """Create default health checks"""
        
        # System resource checks
        self.add_check(HealthCheck(
            name="cpu_usage",
            check_type=CheckType.SYSTEM,
            check_function=self._check_cpu_usage,
            timeout=10,
            interval=30,
            critical=True
        ))
        
        self.add_check(HealthCheck(
            name="memory_usage",
            check_type=CheckType.SYSTEM,
            check_function=self._check_memory_usage,
            timeout=10,
            interval=30,
            critical=True
        ))
        
        self.add_check(HealthCheck(
            name="disk_usage",
            check_type=CheckType.SYSTEM,
            check_function=self._check_disk_usage,
            timeout=10,
            interval=60,
            critical=True
        ))
        
        # Database checks
        self.add_check(HealthCheck(
            name="database_connectivity",
            check_type=CheckType.DATABASE,
            check_function=self._check_database_connectivity,
            timeout=15,
            interval=60,
            critical=True
        ))
        
        # External service checks
        self.add_check(HealthCheck(
            name="llm_providers",
            check_type=CheckType.EXTERNAL,
            check_function=self._check_llm_providers,
            timeout=30,
            interval=120,
            critical=False
        ))
        
        logger.info(f"Created {len(self.checks)} default health checks")
    
    def add_check(self, check: HealthCheck):
        """Add a health check"""
        self.checks[check.name] = check
        logger.info(f"Added health check: {check.name}")
    
    def remove_check(self, name: str):
        """Remove a health check"""
        if name in self.checks:
            del self.checks[name]
            if name in self.check_tasks:
                self.check_tasks[name].cancel()
                del self.check_tasks[name]
            logger.info(f"Removed health check: {name}")
    
    async def start(self):
        """Start health checking"""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info("Health checker started")
        
        # Start all enabled checks
        for name, check in self.checks.items():
            if check.enabled:
                await self._start_check(name, check)
    
    async def stop(self):
        """Stop health checking"""
        self.is_running = False
        
        # Cancel all check tasks
        for task in self.check_tasks.values():
            task.cancel()
        
        self.check_tasks.clear()
        logger.info("Health checker stopped")
    
    async def _start_check(self, name: str, check: HealthCheck):
        """Start a specific health check"""
        async def run_check():
            while self.is_running and check.enabled:
                try:
                    result = await self._execute_check(check)
                    self.results[name] = result
                    
                    # Log critical failures
                    if result.status == HealthStatus.UNHEALTHY and check.critical:
                        logger.error(f"Critical health check failed: {name} - {result.message}")
                    
                except Exception as e:
                    logger.error(f"Error in health check {name}: {e}")
                    self.results[name] = HealthResult(
                        name=name,
                        status=HealthStatus.UNKNOWN,
                        message=f"Check failed with error: {str(e)}",
                        response_time_ms=0,
                        timestamp=datetime.utcnow(),
                        error=str(e)
                    )
                
                await asyncio.sleep(check.interval)
        
        self.check_tasks[name] = asyncio.create_task(run_check())
    
    async def _execute_check(self, check: HealthCheck) -> HealthResult:
        """Execute a health check"""
        start_time = time.time()
        
        try:
            # Run check with timeout
            result = await asyncio.wait_for(
                check.check_function(),
                timeout=check.timeout
            )
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthResult(
                name=check.name,
                status=result.get("status", HealthStatus.UNKNOWN),
                message=result.get("message", ""),
                response_time_ms=response_time,
                timestamp=datetime.utcnow(),
                metadata=result.get("metadata", {})
            )
            
        except asyncio.TimeoutError:
            return HealthResult(
                name=check.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check timed out after {check.timeout} seconds",
                response_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.utcnow(),
                error="timeout"
            )
        except Exception as e:
            return HealthResult(
                name=check.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {str(e)}",
                response_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def _check_cpu_usage(self) -> Dict[str, Any]:
        """Check CPU usage"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            
            if cpu_percent > 90:
                status = HealthStatus.UNHEALTHY
                message = f"CPU usage is critically high: {cpu_percent:.1f}%"
            elif cpu_percent > 80:
                status = HealthStatus.DEGRADED
                message = f"CPU usage is high: {cpu_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"CPU usage is normal: {cpu_percent:.1f}%"
            
            return {
                "status": status,
                "message": message,
                "metadata": {
                    "cpu_percent": cpu_percent,
                    "cpu_count": psutil.cpu_count()
                }
            }
            
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"Failed to check CPU usage: {str(e)}",
                "metadata": {}
            }
    
    async def _check_memory_usage(self) -> Dict[str, Any]:
        """Check memory usage"""
        try:
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            if memory_percent > 95:
                status = HealthStatus.UNHEALTHY
                message = f"Memory usage is critically high: {memory_percent:.1f}%"
            elif memory_percent > 85:
                status = HealthStatus.DEGRADED
                message = f"Memory usage is high: {memory_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage is normal: {memory_percent:.1f}%"
            
            return {
                "status": status,
                "message": message,
                "metadata": {
                    "memory_percent": memory_percent,
                    "memory_total_gb": memory.total / (1024**3),
                    "memory_available_gb": memory.available / (1024**3)
                }
            }
            
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"Failed to check memory usage: {str(e)}",
                "metadata": {}
            }
    
    async def _check_disk_usage(self) -> Dict[str, Any]:
        """Check disk usage"""
        try:
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            if disk_percent > 95:
                status = HealthStatus.UNHEALTHY
                message = f"Disk usage is critically high: {disk_percent:.1f}%"
            elif disk_percent > 85:
                status = HealthStatus.DEGRADED
                message = f"Disk usage is high: {disk_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk usage is normal: {disk_percent:.1f}%"
            
            return {
                "status": status,
                "message": message,
                "metadata": {
                    "disk_percent": disk_percent,
                    "disk_total_gb": disk.total / (1024**3),
                    "disk_free_gb": disk.free / (1024**3)
                }
            }
            
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"Failed to check disk usage: {str(e)}",
                "metadata": {}
            }
    
    async def _check_database_connectivity(self) -> Dict[str, Any]:
        """Check database connectivity"""
        try:
            # This would check actual database connectivity
            # For now, we'll simulate a check
            from ..database.service import get_db_service
            
            db_service = await get_db_service()
            # Simple connectivity test
            start_time = time.time()
            # This would be a simple query like "SELECT 1"
            response_time = (time.time() - start_time) * 1000
            
            if response_time < 1000:  # Less than 1 second
                status = HealthStatus.HEALTHY
                message = f"Database is responsive ({response_time:.1f}ms)"
            elif response_time < 5000:  # Less than 5 seconds
                status = HealthStatus.DEGRADED
                message = f"Database is slow ({response_time:.1f}ms)"
            else:
                status = HealthStatus.UNHEALTHY
                message = f"Database is very slow ({response_time:.1f}ms)"
            
            return {
                "status": status,
                "message": message,
                "metadata": {
                    "response_time_ms": response_time,
                    "database_type": "sqlite"  # Would be dynamic
                }
            }
            
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"Database connectivity failed: {str(e)}",
                "metadata": {}
            }
    
    async def _check_llm_providers(self) -> Dict[str, Any]:
        """Check LLM provider availability"""
        try:
            # This would check actual LLM provider availability
            # For now, we'll simulate a check
            providers = {
                "ollama": {"available": True, "response_time": 150},
                "openai": {"available": False, "response_time": 0},
                "anthropic": {"available": False, "response_time": 0}
            }
            
            available_count = sum(1 for p in providers.values() if p["available"])
            total_count = len(providers)
            
            if available_count == 0:
                status = HealthStatus.UNHEALTHY
                message = "No LLM providers available"
            elif available_count < total_count:
                status = HealthStatus.DEGRADED
                message = f"Only {available_count}/{total_count} LLM providers available"
            else:
                status = HealthStatus.HEALTHY
                message = f"All {total_count} LLM providers available"
            
            return {
                "status": status,
                "message": message,
                "metadata": {
                    "providers": providers,
                    "available_count": available_count,
                    "total_count": total_count
                }
            }
            
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"Failed to check LLM providers: {str(e)}",
                "metadata": {}
            }
    
    def get_overall_health(self) -> Dict[str, Any]:
        """Get overall system health"""
        if not self.results:
            return {
                "status": HealthStatus.UNKNOWN,
                "message": "No health checks have been run",
                "checks": {},
                "summary": {
                    "total_checks": len(self.checks),
                    "enabled_checks": len([c for c in self.checks.values() if c.enabled]),
                    "healthy_checks": 0,
                    "degraded_checks": 0,
                    "unhealthy_checks": 0,
                    "unknown_checks": 0
                }
            }
        
        # Calculate summary
        summary = {
            "total_checks": len(self.checks),
            "enabled_checks": len([c for c in self.checks.values() if c.enabled]),
            "healthy_checks": 0,
            "degraded_checks": 0,
            "unhealthy_checks": 0,
            "unknown_checks": 0
        }
        
        for result in self.results.values():
            if result.status == HealthStatus.HEALTHY:
                summary["healthy_checks"] += 1
            elif result.status == HealthStatus.DEGRADED:
                summary["degraded_checks"] += 1
            elif result.status == HealthStatus.UNHEALTHY:
                summary["unhealthy_checks"] += 1
            else:
                summary["unknown_checks"] += 1
        
        # Determine overall status
        if summary["unhealthy_checks"] > 0:
            overall_status = HealthStatus.UNHEALTHY
            message = f"{summary['unhealthy_checks']} checks are unhealthy"
        elif summary["degraded_checks"] > 0:
            overall_status = HealthStatus.DEGRADED
            message = f"{summary['degraded_checks']} checks are degraded"
        elif summary["healthy_checks"] > 0:
            overall_status = HealthStatus.HEALTHY
            message = f"All {summary['healthy_checks']} checks are healthy"
        else:
            overall_status = HealthStatus.UNKNOWN
            message = "No check results available"
        
        return {
            "status": overall_status,
            "message": message,
            "checks": {name: result.to_dict() if hasattr(result, 'to_dict') else {
                "name": result.name,
                "status": result.status.value,
                "message": result.message,
                "response_time_ms": result.response_time_ms,
                "timestamp": result.timestamp.isoformat(),
                "metadata": result.metadata or {},
                "error": result.error
            } for name, result in self.results.items()},
            "summary": summary,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_check_result(self, name: str) -> Optional[HealthResult]:
        """Get result for a specific check"""
        return self.results.get(name)
    
    def get_checks_by_type(self, check_type: CheckType) -> List[HealthResult]:
        """Get results for checks of a specific type"""
        results = []
        for name, check in self.checks.items():
            if check.check_type == check_type and name in self.results:
                results.append(self.results[name])
        return results
    
    def get_critical_issues(self) -> List[HealthResult]:
        """Get all critical health issues"""
        issues = []
        for name, check in self.checks.items():
            if check.critical and name in self.results:
                result = self.results[name]
                if result.status in [HealthStatus.UNHEALTHY, HealthStatus.DEGRADED]:
                    issues.append(result)
        return issues
    
    def is_healthy(self) -> bool:
        """Check if system is overall healthy"""
        overall = self.get_overall_health()
        return overall["status"] == HealthStatus.HEALTHY
    
    def is_degraded(self) -> bool:
        """Check if system is degraded"""
        overall = self.get_overall_health()
        return overall["status"] == HealthStatus.DEGRADED
    
    def has_critical_issues(self) -> bool:
        """Check if there are any critical issues"""
        return len(self.get_critical_issues()) > 0


# Global health checker instance
_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """Get global health checker instance"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker