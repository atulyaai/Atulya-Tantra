"""
Advanced Dashboard Management System
Grafana integration with dynamic dashboard creation and management
"""

import json
import time
import asyncio
import aiohttp
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from ..config.logging import get_logger
from ..config.exceptions import MonitoringError

logger = get_logger(__name__)


class DashboardType(str, Enum):
    """Types of dashboards"""
    SYSTEM_OVERVIEW = "system_overview"
    AI_METRICS = "ai_metrics"
    AGENT_PERFORMANCE = "agent_performance"
    USER_ANALYTICS = "user_analytics"
    SECURITY = "security"
    CUSTOM = "custom"


@dataclass
class DashboardPanel:
    """Dashboard panel configuration"""
    title: str
    type: str
    targets: List[Dict[str, Any]]
    gridPos: Dict[str, int]
    options: Dict[str, Any] = None


@dataclass
class DashboardConfig:
    """Dashboard configuration"""
    title: str
    type: DashboardType
    panels: List[DashboardPanel]
    refresh: str = "30s"
    time_range: str = "1h"
    tags: List[str] = None


class GrafanaDashboard:
    """Grafana dashboard management"""
    
    def __init__(self, grafana_url: str, api_key: str):
        self.grafana_url = grafana_url.rstrip('/')
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        self.available = False
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            headers={'Authorization': f'Bearer {self.api_key}'}
        )
        await self._check_availability()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def _check_availability(self):
        """Check if Grafana is available"""
        try:
            async with self.session.get(f"{self.grafana_url}/api/health") as response:
                if response.status == 200:
                    self.available = True
                    logger.info("Grafana connection established")
                else:
                    logger.warning(f"Grafana health check failed: {response.status}")
        except Exception as e:
            logger.warning(f"Grafana not available: {e}")
            self.available = False
    
    async def create_dashboard(self, config: DashboardConfig) -> Optional[Dict[str, Any]]:
        """Create a new dashboard in Grafana"""
        if not self.available:
            logger.warning("Grafana not available, skipping dashboard creation")
            return None
        
        try:
            dashboard_data = {
                "dashboard": {
                    "title": config.title,
                    "tags": config.tags or [],
                    "timezone": "browser",
                    "refresh": config.refresh,
                    "time": {
                        "from": f"now-{config.time_range}",
                        "to": "now"
                    },
                    "panels": []
                },
                "overwrite": True
            }
            
            # Add panels
            for i, panel in enumerate(config.panels):
                panel_data = {
                    "id": i + 1,
                    "title": panel.title,
                    "type": panel.type,
                    "gridPos": panel.gridPos,
                    "targets": panel.targets,
                    "options": panel.options or {}
                }
                dashboard_data["dashboard"]["panels"].append(panel_data)
            
            async with self.session.post(
                f"{self.grafana_url}/api/dashboards/db",
                json=dashboard_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"Dashboard '{config.title}' created successfully")
                    return result
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to create dashboard: {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error creating dashboard: {e}")
            return None
    
    async def get_dashboard(self, uid: str) -> Optional[Dict[str, Any]]:
        """Get dashboard by UID"""
        if not self.available:
            return None
        
        try:
            async with self.session.get(f"{self.grafana_url}/api/dashboards/uid/{uid}") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return None
        except Exception as e:
            logger.error(f"Error getting dashboard: {e}")
            return None
    
    async def list_dashboards(self) -> List[Dict[str, Any]]:
        """List all dashboards"""
        if not self.available:
            return []
        
        try:
            async with self.session.get(f"{self.grafana_url}/api/search?type=dash-db") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return []
        except Exception as e:
            logger.error(f"Error listing dashboards: {e}")
            return []


class DashboardManager:
    """Advanced dashboard management system"""
    
    def __init__(self, grafana_url: str = None, api_key: str = None):
        self.grafana_url = grafana_url or "http://localhost:3000"
        self.api_key = api_key
        self.dashboards: Dict[str, DashboardConfig] = {}
        self.grafana: Optional[GrafanaDashboard] = None
        
        # Initialize default dashboards
        self._create_default_dashboards()
    
    def _create_default_dashboards(self):
        """Create default dashboard configurations"""
        
        # System Overview Dashboard
        system_overview = DashboardConfig(
            title="Atulya Tantra - System Overview",
            type=DashboardType.SYSTEM_OVERVIEW,
            panels=[
                DashboardPanel(
                    title="Request Rate",
                    type="graph",
                    targets=[
                        {
                            "expr": "rate(tantra_requests_total[5m])",
                            "legendFormat": "{{method}} {{endpoint}}"
                        }
                    ],
                    gridPos={"x": 0, "y": 0, "w": 12, "h": 8}
                ),
                DashboardPanel(
                    title="Response Time",
                    type="graph",
                    targets=[
                        {
                            "expr": "histogram_quantile(0.95, rate(tantra_request_duration_seconds_bucket[5m]))",
                            "legendFormat": "95th percentile"
                        },
                        {
                            "expr": "histogram_quantile(0.50, rate(tantra_request_duration_seconds_bucket[5m]))",
                            "legendFormat": "50th percentile"
                        }
                    ],
                    gridPos={"x": 12, "y": 0, "w": 12, "h": 8}
                ),
                DashboardPanel(
                    title="System Resources",
                    type="graph",
                    targets=[
                        {
                            "expr": "tantra_cpu_usage_percent",
                            "legendFormat": "CPU Usage %"
                        },
                        {
                            "expr": "tantra_memory_usage_bytes / 1024 / 1024",
                            "legendFormat": "Memory Usage MB"
                        }
                    ],
                    gridPos={"x": 0, "y": 8, "w": 12, "h": 8}
                ),
                DashboardPanel(
                    title="Active Sessions",
                    type="stat",
                    targets=[
                        {
                            "expr": "tantra_active_sessions",
                            "legendFormat": "Active Sessions"
                        }
                    ],
                    gridPos={"x": 12, "y": 8, "w": 12, "h": 8}
                )
            ],
            tags=["system", "overview"]
        )
        
        # AI Metrics Dashboard
        ai_metrics = DashboardConfig(
            title="Atulya Tantra - AI Metrics",
            type=DashboardType.AI_METRICS,
            panels=[
                DashboardPanel(
                    title="LLM Request Rate",
                    type="graph",
                    targets=[
                        {
                            "expr": "rate(tantra_llm_requests_total[5m])",
                            "legendFormat": "{{provider}} {{model}}"
                        }
                    ],
                    gridPos={"x": 0, "y": 0, "w": 12, "h": 8}
                ),
                DashboardPanel(
                    title="LLM Response Time",
                    type="graph",
                    targets=[
                        {
                            "expr": "histogram_quantile(0.95, rate(tantra_llm_response_time_seconds_bucket[5m]))",
                            "legendFormat": "95th percentile"
                        }
                    ],
                    gridPos={"x": 12, "y": 0, "w": 12, "h": 8}
                ),
                DashboardPanel(
                    title="Token Usage",
                    type="graph",
                    targets=[
                        {
                            "expr": "rate(tantra_llm_tokens_total[5m])",
                            "legendFormat": "{{provider}} {{type}}"
                        }
                    ],
                    gridPos={"x": 0, "y": 8, "w": 12, "h": 8}
                ),
                DashboardPanel(
                    title="LLM Success Rate",
                    type="stat",
                    targets=[
                        {
                            "expr": "rate(tantra_llm_requests_total{status=\"success\"}[5m]) / rate(tantra_llm_requests_total[5m]) * 100",
                            "legendFormat": "Success Rate %"
                        }
                    ],
                    gridPos={"x": 12, "y": 8, "w": 12, "h": 8}
                )
            ],
            tags=["ai", "llm", "metrics"]
        )
        
        # Agent Performance Dashboard
        agent_performance = DashboardConfig(
            title="Atulya Tantra - Agent Performance",
            type=DashboardType.AGENT_PERFORMANCE,
            panels=[
                DashboardPanel(
                    title="Agent Execution Rate",
                    type="graph",
                    targets=[
                        {
                            "expr": "rate(tantra_agent_executions_total[5m])",
                            "legendFormat": "{{agent_type}}"
                        }
                    ],
                    gridPos={"x": 0, "y": 0, "w": 12, "h": 8}
                ),
                DashboardPanel(
                    title="Agent Duration",
                    type="graph",
                    targets=[
                        {
                            "expr": "histogram_quantile(0.95, rate(tantra_agent_duration_seconds_bucket[5m]))",
                            "legendFormat": "{{agent_type}} 95th percentile"
                        }
                    ],
                    gridPos={"x": 12, "y": 0, "w": 12, "h": 8}
                ),
                DashboardPanel(
                    title="Agent Success Rate",
                    type="stat",
                    targets=[
                        {
                            "expr": "rate(tantra_agent_executions_total{status=\"success\"}[5m]) / rate(tantra_agent_executions_total[5m]) * 100",
                            "legendFormat": "Success Rate %"
                        }
                    ],
                    gridPos={"x": 0, "y": 8, "w": 12, "h": 8}
                ),
                DashboardPanel(
                    title="Agent Errors",
                    type="graph",
                    targets=[
                        {
                            "expr": "rate(tantra_agent_executions_total{status=\"error\"}[5m])",
                            "legendFormat": "{{agent_type}} errors"
                        }
                    ],
                    gridPos={"x": 12, "y": 8, "w": 12, "h": 8}
                )
            ],
            tags=["agents", "performance"]
        )
        
        # User Analytics Dashboard
        user_analytics = DashboardConfig(
            title="Atulya Tantra - User Analytics",
            type=DashboardType.USER_ANALYTICS,
            panels=[
                DashboardPanel(
                    title="Conversations",
                    type="graph",
                    targets=[
                        {
                            "expr": "rate(tantra_conversations_total[5m])",
                            "legendFormat": "{{user_type}}"
                        }
                    ],
                    gridPos={"x": 0, "y": 0, "w": 12, "h": 8}
                ),
                DashboardPanel(
                    title="Messages",
                    type="graph",
                    targets=[
                        {
                            "expr": "rate(tantra_messages_total[5m])",
                            "legendFormat": "{{message_type}}"
                        }
                    ],
                    gridPos={"x": 12, "y": 0, "w": 12, "h": 8}
                ),
                DashboardPanel(
                    title="Active Users",
                    type="stat",
                    targets=[
                        {
                            "expr": "tantra_active_sessions",
                            "legendFormat": "Active Users"
                        }
                    ],
                    gridPos={"x": 0, "y": 8, "w": 12, "h": 8}
                ),
                DashboardPanel(
                    title="Error Rate",
                    type="graph",
                    targets=[
                        {
                            "expr": "rate(tantra_errors_total[5m])",
                            "legendFormat": "{{error_type}}"
                        }
                    ],
                    gridPos={"x": 12, "y": 8, "w": 12, "h": 8}
                )
            ],
            tags=["users", "analytics"]
        )
        
        # Security Dashboard
        security = DashboardConfig(
            title="Atulya Tantra - Security",
            type=DashboardType.SECURITY,
            panels=[
                DashboardPanel(
                    title="Authentication Failures",
                    type="graph",
                    targets=[
                        {
                            "expr": "rate(tantra_errors_total{error_type=\"auth_failure\"}[5m])",
                            "legendFormat": "Auth Failures"
                        }
                    ],
                    gridPos={"x": 0, "y": 0, "w": 12, "h": 8}
                ),
                DashboardPanel(
                    title="Rate Limit Hits",
                    type="graph",
                    targets=[
                        {
                            "expr": "rate(tantra_errors_total{error_type=\"rate_limit\"}[5m])",
                            "legendFormat": "Rate Limit Hits"
                        }
                    ],
                    gridPos={"x": 12, "y": 0, "w": 12, "h": 8}
                ),
                DashboardPanel(
                    title="Security Events",
                    type="graph",
                    targets=[
                        {
                            "expr": "rate(tantra_errors_total{component=\"security\"}[5m])",
                            "legendFormat": "Security Events"
                        }
                    ],
                    gridPos={"x": 0, "y": 8, "w": 12, "h": 8}
                ),
                DashboardPanel(
                    title="Failed Requests",
                    type="stat",
                    targets=[
                        {
                            "expr": "rate(tantra_requests_total{status_code=~\"4..|5..\"}[5m])",
                            "legendFormat": "Failed Requests/sec"
                        }
                    ],
                    gridPos={"x": 12, "y": 8, "w": 12, "h": 8}
                )
            ],
            tags=["security", "monitoring"]
        )
        
        # Store dashboards
        self.dashboards = {
            "system_overview": system_overview,
            "ai_metrics": ai_metrics,
            "agent_performance": agent_performance,
            "user_analytics": user_analytics,
            "security": security
        }
        
        logger.info(f"Created {len(self.dashboards)} default dashboard configurations")
    
    async def create_dashboard(self, name: str, config: DashboardConfig) -> bool:
        """Create a dashboard"""
        try:
            self.dashboards[name] = config
            
            # Create in Grafana if available
            if self.grafana and self.grafana.available:
                async with self.grafana as grafana:
                    result = await grafana.create_dashboard(config)
                    if result:
                        logger.info(f"Dashboard '{name}' created in Grafana")
                        return True
                    else:
                        logger.warning(f"Failed to create dashboard '{name}' in Grafana")
                        return False
            else:
                logger.info(f"Dashboard '{name}' configuration saved (Grafana not available)")
                return True
                
        except Exception as e:
            logger.error(f"Error creating dashboard '{name}': {e}")
            return False
    
    async def setup_grafana(self, grafana_url: str, api_key: str) -> bool:
        """Setup Grafana connection"""
        try:
            self.grafana_url = grafana_url
            self.api_key = api_key
            self.grafana = GrafanaDashboard(grafana_url, api_key)
            
            async with self.grafana as grafana:
                if grafana.available:
                    logger.info("Grafana setup successful")
                    return True
                else:
                    logger.warning("Grafana setup failed - service not available")
                    return False
                    
        except Exception as e:
            logger.error(f"Error setting up Grafana: {e}")
            return False
    
    async def deploy_all_dashboards(self) -> Dict[str, bool]:
        """Deploy all configured dashboards"""
        results = {}
        
        if not self.grafana or not self.grafana.available:
            logger.warning("Grafana not available, skipping dashboard deployment")
            return {name: False for name in self.dashboards.keys()}
        
        try:
            async with self.grafana as grafana:
                for name, config in self.dashboards.items():
                    result = await grafana.create_dashboard(config)
                    results[name] = result is not None
                    
                    if results[name]:
                        logger.info(f"Dashboard '{name}' deployed successfully")
                    else:
                        logger.warning(f"Dashboard '{name}' deployment failed")
                        
        except Exception as e:
            logger.error(f"Error deploying dashboards: {e}")
            results = {name: False for name in self.dashboards.keys()}
        
        return results
    
    def get_dashboard_config(self, name: str) -> Optional[DashboardConfig]:
        """Get dashboard configuration"""
        return self.dashboards.get(name)
    
    def list_dashboards(self) -> List[str]:
        """List all dashboard names"""
        return list(self.dashboards.keys())
    
    def create_custom_dashboard(self, name: str, title: str, panels: List[DashboardPanel], 
                              tags: List[str] = None) -> bool:
        """Create a custom dashboard"""
        config = DashboardConfig(
            title=title,
            type=DashboardType.CUSTOM,
            panels=panels,
            tags=tags or []
        )
        
        return asyncio.create_task(self.create_dashboard(name, config))
    
    def export_dashboard_config(self, name: str) -> Optional[Dict[str, Any]]:
        """Export dashboard configuration as JSON"""
        config = self.get_dashboard_config(name)
        if not config:
            return None
        
        return {
            "title": config.title,
            "type": config.type.value,
            "panels": [
                {
                    "title": panel.title,
                    "type": panel.type,
                    "targets": panel.targets,
                    "gridPos": panel.gridPos,
                    "options": panel.options
                }
                for panel in config.panels
            ],
            "refresh": config.refresh,
            "time_range": config.time_range,
            "tags": config.tags
        }


# Global dashboard manager instance
_dashboard_manager: Optional[DashboardManager] = None


def get_dashboard_manager() -> DashboardManager:
    """Get global dashboard manager instance"""
    global _dashboard_manager
    if _dashboard_manager is None:
        _dashboard_manager = DashboardManager()
    return _dashboard_manager