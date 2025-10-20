"""
Atulya Tantra - Health Check Routes
Version: 2.5.0
Health check endpoints for monitoring and observability
"""

from fastapi import APIRouter, Depends
from typing import Dict, Any
import asyncio
import logging
from datetime import datetime

from src.core.agents.agent_coordinator import AgentCoordinator
from src.core.agents.skynet.monitor import SystemMonitor
from src.core.agents.skynet.decision_engine import DecisionEngine
from src.core.agents.skynet.executor import task_executor
from src.core.agents.skynet.coordinator import MultiAgentCoordinator
from src.core.agents.skynet.safety import safety_system
from src.core.agents.jarvis.voice import JARVISVoiceInterface

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])

@router.get("/")
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "atulya-tantra",
        "version": "2.5.0"
    }

@router.get("/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """Detailed health check with component status"""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "atulya-tantra",
            "version": "2.5.0",
            "components": {}
        }
        
        # Check core components
        try:
            # System Monitor
            monitor = SystemMonitor()
            health_status["components"]["system_monitor"] = await monitor.health_check()
        except Exception as e:
            health_status["components"]["system_monitor"] = {"status": "error", "error": str(e)}
            health_status["status"] = "degraded"
        
        try:
            # Task Executor
            health_status["components"]["task_executor"] = await task_executor.health_check()
        except Exception as e:
            health_status["components"]["task_executor"] = {"status": "error", "error": str(e)}
            health_status["status"] = "degraded"
        
        try:
            # Safety System
            health_status["components"]["safety_system"] = await safety_system.health_check()
        except Exception as e:
            health_status["components"]["safety_system"] = {"status": "error", "error": str(e)}
            health_status["status"] = "degraded"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

@router.get("/ready")
async def readiness_check() -> Dict[str, Any]:
    """Readiness check for Kubernetes"""
    try:
        # Check if all critical components are ready
        ready_components = []
        
        # Check system monitor
        try:
            monitor = SystemMonitor()
            monitor_health = await monitor.health_check()
            if monitor_health.get("system_monitor"):
                ready_components.append("system_monitor")
        except Exception:
            pass
        
        # Check task executor
        try:
            executor_health = await task_executor.health_check()
            if executor_health.get("executor_running"):
                ready_components.append("task_executor")
        except Exception:
            pass
        
        # Check safety system
        try:
            safety_health = await safety_system.health_check()
            if safety_health.get("safety_system"):
                ready_components.append("safety_system")
        except Exception:
            pass
        
        is_ready = len(ready_components) >= 2  # At least 2 components must be ready
        
        return {
            "status": "ready" if is_ready else "not_ready",
            "timestamp": datetime.now().isoformat(),
            "ready_components": ready_components,
            "total_components": 3
        }
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {
            "status": "not_ready",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

@router.get("/live")
async def liveness_check() -> Dict[str, Any]:
    """Liveness check for Kubernetes"""
    return {
        "status": "alive",
        "timestamp": datetime.now().isoformat(),
        "uptime": "24h 15m 30s"  # Mock uptime
    }
