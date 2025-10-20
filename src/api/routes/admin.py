"""
Atulya Tantra - Admin API Routes
Version: 2.5.0
Administrative endpoints for system management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta

from src.core.security.rate_limiter import check_rate_limit
from src.core.security.encryption import verify_password
from src.services.chat_service import ChatService
from src.services.auth_service import auth_service
from src.core.agents.agent_coordinator import AgentCoordinator
from src.core.agents.skynet.monitor import SystemMonitor
from src.core.agents.skynet.decision_engine import DecisionEngine

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])
security = HTTPBearer()

async def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify admin JWT and ensure admin role"""
    payload = auth_service.verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    if not auth_service.require_roles(payload, ["admin"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    return payload

@router.get("/status")
async def get_system_status(
    admin_user: Dict[str, Any] = Depends(verify_admin_token)
) -> Dict[str, Any]:
    """Get comprehensive system status"""
    try:
        # Get system monitor status
        monitor = SystemMonitor()
        system_health = await monitor.get_system_health()
        
        # Get agent coordinator status
        coordinator = AgentCoordinator()
        agent_status = await coordinator.health_check()
        
        # Get decision engine status
        decision_engine = DecisionEngine()
        decision_status = await decision_engine.health_check()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "system_health": system_health,
            "agent_status": agent_status,
            "decision_engine": decision_status,
            "uptime": "24h 15m 30s",  # Mock uptime
            "version": "2.5.0"
        }
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system status"
        )

@router.get("/agents")
async def get_agent_status(
    admin_user: Dict[str, Any] = Depends(verify_admin_token)
) -> Dict[str, Any]:
    """Get status of all agents"""
    try:
        coordinator = AgentCoordinator()
        agent_status = await coordinator.get_agent_status()
        
        return {
            "status": "success",
            "agents": agent_status,
            "total_agents": len(agent_status),
            "active_agents": sum(1 for agent in agent_status.values() if agent.get("enabled", False))
        }
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get agent status"
        )

@router.post("/agents/{agent_id}/enable")
async def enable_agent(
    agent_id: str,
    admin_user: Dict[str, Any] = Depends(verify_admin_token)
) -> Dict[str, Any]:
    """Enable a specific agent"""
    try:
        coordinator = AgentCoordinator()
        agent = coordinator.agents.get(agent_id)
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found"
            )
        
        agent.enable()
        
        return {
            "status": "success",
            "message": f"Agent {agent_id} enabled",
            "agent_id": agent_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable agent {agent_id}"
        )

@router.post("/agents/{agent_id}/disable")
async def disable_agent(
    agent_id: str,
    admin_user: Dict[str, Any] = Depends(verify_admin_token)
) -> Dict[str, Any]:
    """Disable a specific agent"""
    try:
        coordinator = AgentCoordinator()
        agent = coordinator.agents.get(agent_id)
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found"
            )
        
        agent.disable()
        
        return {
            "status": "success",
            "message": f"Agent {agent_id} disabled",
            "agent_id": agent_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disable agent {agent_id}"
        )

@router.get("/metrics")
async def get_system_metrics(
    admin_user: Dict[str, Any] = Depends(verify_admin_token)
) -> Dict[str, Any]:
    """Get system metrics and performance data"""
    try:
        # Mock metrics data (in production, get from Prometheus)
        metrics = {
            "requests_per_second": 45.2,
            "average_response_time": 1.2,
            "error_rate": 0.02,
            "active_connections": 23,
            "memory_usage": 65.4,
            "cpu_usage": 42.1,
            "disk_usage": 78.9,
            "cache_hit_rate": 89.3,
            "agent_success_rate": 94.7,
            "autonomous_operations": 156,
            "conversations_today": 1247,
            "users_active": 89
        }
        
        return {
            "status": "success",
            "metrics": metrics,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system metrics"
        )

@router.get("/logs")
async def get_system_logs(
    limit: int = 100,
    level: Optional[str] = None,
    admin_user: Dict[str, Any] = Depends(verify_admin_token)
) -> Dict[str, Any]:
    """Get system logs"""
    try:
        # Mock log data (in production, get from ELK stack)
        logs = [
            {
                "timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "message": "User authentication successful",
                "user_id": "user123",
                "ip_address": "192.168.1.100"
            },
            {
                "timestamp": (datetime.now() - timedelta(minutes=1)).isoformat(),
                "level": "WARNING",
                "message": "High memory usage detected",
                "memory_usage": 85.2
            },
            {
                "timestamp": (datetime.now() - timedelta(minutes=2)).isoformat(),
                "level": "ERROR",
                "message": "Failed to connect to external API",
                "service": "openai",
                "error": "Connection timeout"
            }
        ]
        
        # Filter by level if specified
        if level:
            logs = [log for log in logs if log["level"].lower() == level.lower()]
        
        # Limit results
        logs = logs[:limit]
        
        return {
            "status": "success",
            "logs": logs,
            "total_count": len(logs),
            "filtered_by_level": level
        }
    except Exception as e:
        logger.error(f"Error getting system logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system logs"
        )

@router.get("/users")
async def get_user_statistics(
    admin_user: Dict[str, Any] = Depends(verify_admin_token)
) -> Dict[str, Any]:
    """Get user statistics and activity"""
    try:
        # Mock user statistics (in production, get from database)
        user_stats = {
            "total_users": 1247,
            "active_today": 89,
            "active_this_week": 234,
            "new_users_today": 12,
            "conversations_today": 1247,
            "average_session_duration": "15m 30s",
            "most_active_users": [
                {"user_id": "user123", "conversations": 45},
                {"user_id": "user456", "conversations": 38},
                {"user_id": "user789", "conversations": 32}
            ]
        }
        
        return {
            "status": "success",
            "user_statistics": user_stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting user statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user statistics"
        )

@router.get("/integrations")
async def get_integration_status(
    admin_user: Dict[str, Any] = Depends(verify_admin_token)
) -> Dict[str, Any]:
    """Get status of external integrations"""
    try:
        # Mock integration status (in production, check actual integrations)
        integrations = {
            "openai": {
                "status": "connected",
                "last_check": datetime.now().isoformat(),
                "api_calls_today": 1247,
                "rate_limit_remaining": 8753
            },
            "anthropic": {
                "status": "connected",
                "last_check": datetime.now().isoformat(),
                "api_calls_today": 892,
                "rate_limit_remaining": 9108
            },
            "google_calendar": {
                "status": "not_configured",
                "last_check": None,
                "api_calls_today": 0,
                "rate_limit_remaining": 0
            },
            "email": {
                "status": "not_configured",
                "last_check": None,
                "api_calls_today": 0,
                "rate_limit_remaining": 0
            }
        }
        
        return {
            "status": "success",
            "integrations": integrations,
            "total_integrations": len(integrations),
            "active_integrations": sum(1 for i in integrations.values() if i["status"] == "connected")
        }
    except Exception as e:
        logger.error(f"Error getting integration status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get integration status"
        )

@router.post("/maintenance/restart")
async def restart_system(
    admin_user: Dict[str, Any] = Depends(verify_admin_token)
) -> Dict[str, Any]:
    """Restart system components"""
    try:
        # In production, this would restart services
        logger.info("System restart requested by admin")
        
        return {
            "status": "success",
            "message": "System restart initiated",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error restarting system: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restart system"
        )

@router.post("/maintenance/clear-cache")
async def clear_cache(
    admin_user: Dict[str, Any] = Depends(verify_admin_token)
) -> Dict[str, Any]:
    """Clear system cache"""
    try:
        # In production, this would clear Redis cache
        logger.info("Cache clear requested by admin")
        
        return {
            "status": "success",
            "message": "Cache cleared successfully",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache"
        )

@router.get("/health/detailed")
async def get_detailed_health(
    admin_user: Dict[str, Any] = Depends(verify_admin_token)
) -> Dict[str, Any]:
    """Get detailed health information"""
    try:
        monitor = SystemMonitor()
        detailed_health = await monitor.get_detailed_health()
        
        return {
            "status": "success",
            "health_details": detailed_health,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting detailed health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get detailed health information"
        )