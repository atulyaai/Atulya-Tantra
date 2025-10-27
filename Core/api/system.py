"""
System Management API for Atulya Tantra AGI
System monitoring, health checks, and management endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime

from ..skynet.system_monitor import SystemMonitor, HealthStatus, AlertLevel
from ..skynet.auto_healer import AutoHealer
from ..auth.jwt import verify_token, TokenData
from ..auth.rbac import require_permission, Permission
from ..config.logging import get_logger
from ..config.exceptions import SystemError, ValidationError

logger = get_logger(__name__)

router = APIRouter(prefix="/system", tags=["system"])


class SystemStatus(BaseModel):
    """System status model"""
    status: str
    uptime: str
    version: str
    health_score: float
    components: Dict[str, Any]
    alerts: List[Dict[str, Any]]


class HealthCheck(BaseModel):
    """Health check model"""
    component: str
    status: str
    message: str
    timestamp: str
    response_time: float


class SystemMetric(BaseModel):
    """System metric model"""
    name: str
    value: float
    unit: str
    timestamp: str
    tags: Dict[str, str] = {}


class AlertResponse(BaseModel):
    """Alert response model"""
    alert_id: str
    level: str
    message: str
    component: str
    created_at: str
    resolved_at: Optional[str] = None


def get_current_user(token: str = Depends(verify_token)) -> TokenData:
    """Get current user from token"""
    return token


@router.get("/status", response_model=SystemStatus)
async def get_system_status(current_user: TokenData = Depends(get_current_user)):
    """Get overall system status"""
    try:
        monitor = SystemMonitor()
        status = monitor.get_system_status()
        
        return SystemStatus(
            status=status["status"].value,
            uptime=status["uptime"],
            version=status["version"],
            health_score=status["health_score"],
            components=status["components"],
            alerts=status["alerts"]
        )
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system status")


@router.get("/health", response_model=List[HealthCheck])
async def get_health_checks(current_user: TokenData = Depends(get_current_user)):
    """Get system health checks"""
    try:
        monitor = SystemMonitor()
        health_checks = monitor.get_health_checks()
        
        health_responses = []
        for check in health_checks:
            health_responses.append(HealthCheck(
                component=check.component,
                status=check.status.value,
                message=check.message,
                timestamp=check.timestamp.isoformat(),
                response_time=check.response_time
            ))
        
        return health_responses
        
    except Exception as e:
        logger.error(f"Error getting health checks: {e}")
        raise HTTPException(status_code=500, detail="Failed to get health checks")


@router.get("/metrics", response_model=List[SystemMetric])
async def get_system_metrics(
    metric_name: Optional[str] = None,
    limit: int = 100,
    current_user: TokenData = Depends(get_current_user)
):
    """Get system metrics"""
    try:
        monitor = SystemMonitor()
        metrics = monitor.get_metrics(
            metric_name=metric_name,
            limit=limit
        )
        
        metric_responses = []
        for metric in metrics:
            metric_responses.append(SystemMetric(
                name=metric.name,
                value=metric.value,
                unit=metric.unit,
                timestamp=metric.timestamp.isoformat(),
                tags=metric.tags
            ))
        
        return metric_responses
        
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system metrics")


@router.get("/alerts", response_model=List[AlertResponse])
async def get_alerts(
    level: Optional[str] = None,
    resolved: Optional[bool] = None,
    current_user: TokenData = Depends(get_current_user)
):
    """Get system alerts"""
    try:
        monitor = SystemMonitor()
        alerts = monitor.get_alerts(
            level=AlertLevel(level) if level else None,
            resolved=resolved
        )
        
        alert_responses = []
        for alert in alerts:
            alert_responses.append(AlertResponse(
                alert_id=alert.alert_id,
                level=alert.level.value,
                message=alert.message,
                component=alert.component,
                created_at=alert.created_at.isoformat(),
                resolved_at=alert.resolved_at.isoformat() if alert.resolved_at else None
            ))
        
        return alert_responses
        
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get alerts")


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Resolve an alert"""
    try:
        monitor = SystemMonitor()
        success = monitor.resolve_alert(alert_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {"message": f"Alert {alert_id} resolved successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving alert: {e}")
        raise HTTPException(status_code=500, detail="Failed to resolve alert")


@router.post("/maintenance/start")
async def start_maintenance(
    reason: str,
    estimated_duration: int,
    current_user: TokenData = Depends(get_current_user)
):
    """Start maintenance mode"""
    try:
        monitor = SystemMonitor()
        success = monitor.start_maintenance_mode(
            reason=reason,
            estimated_duration=estimated_duration,
            started_by=current_user.user_id
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to start maintenance mode")
        
        return {"message": "Maintenance mode started successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting maintenance mode: {e}")
        raise HTTPException(status_code=500, detail="Failed to start maintenance mode")


@router.post("/maintenance/stop")
async def stop_maintenance(current_user: TokenData = Depends(get_current_user)):
    """Stop maintenance mode"""
    try:
        monitor = SystemMonitor()
        success = monitor.stop_maintenance_mode(current_user.user_id)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to stop maintenance mode")
        
        return {"message": "Maintenance mode stopped successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping maintenance mode: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop maintenance mode")


@router.get("/maintenance/status")
async def get_maintenance_status(current_user: TokenData = Depends(get_current_user)):
    """Get maintenance mode status"""
    try:
        monitor = SystemMonitor()
        status = monitor.get_maintenance_status()
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting maintenance status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get maintenance status")


@router.post("/heal")
async def trigger_healing(
    component: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
    current_user: TokenData = Depends(get_current_user)
):
    """Trigger auto-healing"""
    try:
        healer = AutoHealer()
        
        if background_tasks:
            background_tasks.add_task(healer.heal_system, component)
            return {"message": "Healing process started in background"}
        else:
            success = healer.heal_system(component)
            if not success:
                raise HTTPException(status_code=400, detail="Healing failed")
            return {"message": "Healing completed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering healing: {e}")
        raise HTTPException(status_code=500, detail="Failed to trigger healing")


@router.get("/performance")
async def get_performance_metrics(current_user: TokenData = Depends(get_current_user)):
    """Get performance metrics"""
    try:
        monitor = SystemMonitor()
        performance = monitor.get_performance_metrics()
        
        return performance
        
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get performance metrics")


@router.get("/logs")
async def get_system_logs(
    level: Optional[str] = None,
    component: Optional[str] = None,
    limit: int = 100,
    current_user: TokenData = Depends(get_current_user)
):
    """Get system logs"""
    try:
        monitor = SystemMonitor()
        logs = monitor.get_logs(
            level=level,
            component=component,
            limit=limit
        )
        
        return {"logs": logs}
        
    except Exception as e:
        logger.error(f"Error getting system logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system logs")


@router.post("/restart")
async def restart_system(
    background_tasks: BackgroundTasks,
    current_user: TokenData = Depends(get_current_user)
):
    """Restart system (admin only)"""
    try:
        # Check admin permission
        if not current_user.roles or "admin" not in current_user.roles:
            raise HTTPException(status_code=403, detail="Admin permission required")
        
        # Schedule restart
        background_tasks.add_task(monitor.restart_system)
        
        return {"message": "System restart scheduled"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restarting system: {e}")
        raise HTTPException(status_code=500, detail="Failed to restart system")


@router.get("/config")
async def get_system_config(current_user: TokenData = Depends(get_current_user)):
    """Get system configuration"""
    try:
        monitor = SystemMonitor()
        config = monitor.get_system_config()
        
        return config
        
    except Exception as e:
        logger.error(f"Error getting system config: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system config")


@router.put("/config")
async def update_system_config(
    config: Dict[str, Any],
    current_user: TokenData = Depends(get_current_user)
):
    """Update system configuration (admin only)"""
    try:
        # Check admin permission
        if not current_user.roles or "admin" not in current_user.roles:
            raise HTTPException(status_code=403, detail="Admin permission required")
        
        monitor = SystemMonitor()
        success = monitor.update_system_config(config)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update system config")
        
        return {"message": "System configuration updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating system config: {e}")
        raise HTTPException(status_code=500, detail="Failed to update system config")