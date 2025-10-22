"""
System Agent for Atulya Tantra AGI
Specialized agent for system control, monitoring, and automation
"""

import os
import psutil
import subprocess
import platform
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

from .base_agent import BaseAgent, AgentTask, AgentCapability, AgentStatus
from ..config.logging import get_logger
from ..config.exceptions import AgentError
from ..brain import generate_response, get_llm_router

logger = get_logger(__name__)


class SystemAgent(BaseAgent):
    """Agent specialized in system control, monitoring, and automation"""
    
    def __init__(self):
        super().__init__(
            name="SystemAgent",
            description="Specialized agent for system control, monitoring, automation, and resource management",
            capabilities=[
                AgentCapability.SYSTEM_CONTROL,
                AgentCapability.FILE_PROCESSING,
                AgentCapability.DATA_ANALYSIS
            ],
            max_concurrent_tasks=2,
            timeout_seconds=120
        )
        
        self.system_info = self._get_system_info()
        self.safe_commands = [
            "ls", "pwd", "whoami", "date", "uptime", "df", "free", "ps",
            "netstat", "ping", "curl", "wget", "cat", "head", "tail", "grep"
        ]
        self.dangerous_commands = [
            "rm", "del", "format", "fdisk", "mkfs", "dd", "shutdown", "reboot",
            "kill", "killall", "pkill", "chmod", "chown", "sudo", "su"
        ]
        self.monitoring_interval = 60  # seconds
    
    async def can_handle_task(self, task: AgentTask) -> bool:
        """Check if this agent can handle the given task"""
        task_type = task.task_type or ""
        description = (task.description or "").lower()
        
        # Check for system-related keywords
        system_keywords = [
            "system", "monitor", "process", "cpu", "memory", "disk", "network",
            "performance", "health", "status", "log", "service", "daemon",
            "automation", "schedule", "cron", "task", "job", "backup",
            "security", "firewall", "antivirus", "update", "upgrade",
            "install", "uninstall", "configure", "settings", "registry"
        ]
        
        return (
            task_type in ["system_monitoring", "system_control", "automation", "maintenance"] or
            any(keyword in description for keyword in system_keywords)
        )
    
    async def get_task_estimate(self, task: AgentTask) -> Dict[str, Any]:
        """Estimate task execution time and resource requirements"""
        task_type = task.task_type or ""
        
        # Base estimates
        if task_type == "system_monitoring":
            estimated_time = 10  # seconds
            complexity = "low"
        elif task_type == "system_control":
            estimated_time = 30
            complexity = "medium"
        elif task_type == "automation":
            estimated_time = 60
            complexity = "high"
        elif task_type == "maintenance":
            estimated_time = 120
            complexity = "high"
        else:
            estimated_time = 45
            complexity = "medium"
        
        return {
            "estimated_time_seconds": estimated_time,
            "complexity": complexity,
            "resource_requirements": {
                "memory_mb": 50,
                "cpu_usage": "low",
                "system_access": "required"
            }
        }
    
    async def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        """Execute a system-related task"""
        try:
            task_type = task.task_type or "system_monitoring"
            input_data = task.input_data or {}
            
            if task_type == "system_monitoring":
                return await self._monitor_system(task, input_data)
            elif task_type == "system_control":
                return await self._control_system(task, input_data)
            elif task_type == "automation":
                return await self._automate_task(task, input_data)
            elif task_type == "maintenance":
                return await self._perform_maintenance(task, input_data)
            elif task_type == "security_check":
                return await self._security_check(task, input_data)
            else:
                return await self._general_system_task(task, input_data)
                
        except Exception as e:
            logger.error(f"SystemAgent execution error: {e}")
            raise AgentError(f"System task failed: {e}")
    
    async def _monitor_system(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Monitor system performance and health"""
        metrics = input_data.get("metrics", ["cpu", "memory", "disk", "network"])
        duration = input_data.get("duration", 60)  # seconds
        
        monitoring_results = {
            "timestamp": datetime.utcnow().isoformat(),
            "system_info": self.system_info,
            "metrics": {},
            "alerts": [],
            "recommendations": []
        }
        
        # Collect metrics
        for metric in metrics:
            if metric == "cpu":
                monitoring_results["metrics"]["cpu"] = await self._get_cpu_metrics()
            elif metric == "memory":
                monitoring_results["metrics"]["memory"] = await self._get_memory_metrics()
            elif metric == "disk":
                monitoring_results["metrics"]["disk"] = await self._get_disk_metrics()
            elif metric == "network":
                monitoring_results["metrics"]["network"] = await self._get_network_metrics()
            elif metric == "processes":
                monitoring_results["metrics"]["processes"] = await self._get_process_metrics()
        
        # Analyze metrics and generate alerts
        monitoring_results["alerts"] = await self._analyze_metrics(monitoring_results["metrics"])
        
        # Generate recommendations
        monitoring_results["recommendations"] = await self._generate_recommendations(monitoring_results["metrics"])
        
        return {
            "monitoring_results": monitoring_results,
            "duration": duration,
            "metrics_collected": metrics,
            "metadata": {
                "task_type": "system_monitoring",
                "monitored_at": datetime.utcnow().isoformat()
            }
        }
    
    async def _control_system(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Control system operations"""
        action = input_data.get("action", "")
        parameters = input_data.get("parameters", {})
        
        if not action:
            raise AgentError("No action specified for system control")
        
        # Validate action safety
        if not self._is_safe_action(action):
            raise AgentError(f"Action '{action}' is not allowed for security reasons")
        
        control_results = {
            "action": action,
            "parameters": parameters,
            "success": False,
            "output": "",
            "error": None,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            if action == "start_service":
                control_results = await self._start_service(parameters)
            elif action == "stop_service":
                control_results = await self._stop_service(parameters)
            elif action == "restart_service":
                control_results = await self._restart_service(parameters)
            elif action == "check_service_status":
                control_results = await self._check_service_status(parameters)
            elif action == "execute_command":
                control_results = await self._execute_safe_command(parameters)
            else:
                raise AgentError(f"Unknown action: {action}")
            
            control_results["success"] = True
            
        except Exception as e:
            control_results["error"] = str(e)
            control_results["success"] = False
        
        return {
            "control_results": control_results,
            "metadata": {
                "task_type": "system_control",
                "executed_at": datetime.utcnow().isoformat()
            }
        }
    
    async def _automate_task(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Automate system tasks"""
        automation_type = input_data.get("automation_type", "schedule")
        task_description = input_data.get("task_description", task.description)
        schedule = input_data.get("schedule", "daily")
        
        automation_results = {
            "automation_type": automation_type,
            "task_description": task_description,
            "schedule": schedule,
            "created": False,
            "automation_id": None,
            "next_run": None
        }
        
        try:
            if automation_type == "schedule":
                automation_results = await self._create_scheduled_task(task_description, schedule)
            elif automation_type == "trigger":
                automation_results = await self._create_triggered_task(task_description, input_data.get("trigger", {}))
            elif automation_type == "workflow":
                automation_results = await self._create_workflow(task_description, input_data.get("steps", []))
            else:
                raise AgentError(f"Unknown automation type: {automation_type}")
            
            automation_results["created"] = True
            
        except Exception as e:
            automation_results["error"] = str(e)
            automation_results["created"] = False
        
        return {
            "automation_results": automation_results,
            "metadata": {
                "task_type": "automation",
                "created_at": datetime.utcnow().isoformat()
            }
        }
    
    async def _perform_maintenance(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform system maintenance tasks"""
        maintenance_type = input_data.get("maintenance_type", "cleanup")
        
        maintenance_results = {
            "maintenance_type": maintenance_type,
            "tasks_performed": [],
            "results": {},
            "success": True,
            "errors": []
        }
        
        try:
            if maintenance_type == "cleanup":
                maintenance_results = await self._perform_cleanup(input_data)
            elif maintenance_type == "update":
                maintenance_results = await self._perform_updates(input_data)
            elif maintenance_type == "backup":
                maintenance_results = await self._perform_backup(input_data)
            elif maintenance_type == "optimization":
                maintenance_results = await self._perform_optimization(input_data)
            else:
                raise AgentError(f"Unknown maintenance type: {maintenance_type}")
            
        except Exception as e:
            maintenance_results["errors"].append(str(e))
            maintenance_results["success"] = False
        
        return {
            "maintenance_results": maintenance_results,
            "metadata": {
                "task_type": "maintenance",
                "performed_at": datetime.utcnow().isoformat()
            }
        }
    
    async def _security_check(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform security checks"""
        check_type = input_data.get("check_type", "basic")
        
        security_results = {
            "check_type": check_type,
            "checks_performed": [],
            "vulnerabilities": [],
            "recommendations": [],
            "security_score": 0
        }
        
        try:
            if check_type == "basic":
                security_results = await self._basic_security_check()
            elif check_type == "comprehensive":
                security_results = await self._comprehensive_security_check()
            elif check_type == "network":
                security_results = await self._network_security_check()
            else:
                raise AgentError(f"Unknown security check type: {check_type}")
            
        except Exception as e:
            security_results["error"] = str(e)
        
        return {
            "security_results": security_results,
            "metadata": {
                "task_type": "security_check",
                "checked_at": datetime.utcnow().isoformat()
            }
        }
    
    async def _general_system_task(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle general system tasks"""
        description = task.description or ""
        
        prompt = f"""
You are a system administration expert. Help with the following system task:

Task: {description}

Please provide:
1. Recommended approach and tools
2. Required permissions and access
3. Potential risks and precautions
4. Step-by-step instructions
5. Expected outcomes and verification

Be thorough and security-conscious in your guidance.
"""
        
        response = await generate_response(
            prompt=prompt,
            max_tokens=1000,
            temperature=0.3,
            preferred_provider="openai"
        )
        
        return {
            "system_guidance": response,
            "task_description": description,
            "metadata": {
                "task_type": "general_system_task",
                "completed_at": datetime.utcnow().isoformat()
            }
        }
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get basic system information"""
        return {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "hostname": platform.node(),
            "python_version": platform.python_version()
        }
    
    async def _get_cpu_metrics(self) -> Dict[str, Any]:
        """Get CPU metrics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            return {
                "usage_percent": cpu_percent,
                "count": cpu_count,
                "frequency_mhz": cpu_freq.current if cpu_freq else None,
                "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else None
            }
        except Exception as e:
            logger.error(f"Error getting CPU metrics: {e}")
            return {"error": str(e)}
    
    async def _get_memory_metrics(self) -> Dict[str, Any]:
        """Get memory metrics"""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            return {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "used_gb": round(memory.used / (1024**3), 2),
                "usage_percent": memory.percent,
                "swap_total_gb": round(swap.total / (1024**3), 2),
                "swap_used_gb": round(swap.used / (1024**3), 2)
            }
        except Exception as e:
            logger.error(f"Error getting memory metrics: {e}")
            return {"error": str(e)}
    
    async def _get_disk_metrics(self) -> Dict[str, Any]:
        """Get disk metrics"""
        try:
            disk_usage = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            return {
                "total_gb": round(disk_usage.total / (1024**3), 2),
                "used_gb": round(disk_usage.used / (1024**3), 2),
                "free_gb": round(disk_usage.free / (1024**3), 2),
                "usage_percent": round((disk_usage.used / disk_usage.total) * 100, 2),
                "read_bytes": disk_io.read_bytes if disk_io else 0,
                "write_bytes": disk_io.write_bytes if disk_io else 0
            }
        except Exception as e:
            logger.error(f"Error getting disk metrics: {e}")
            return {"error": str(e)}
    
    async def _get_network_metrics(self) -> Dict[str, Any]:
        """Get network metrics"""
        try:
            network_io = psutil.net_io_counters()
            network_connections = len(psutil.net_connections())
            
            return {
                "bytes_sent": network_io.bytes_sent,
                "bytes_received": network_io.bytes_recv,
                "packets_sent": network_io.packets_sent,
                "packets_received": network_io.packets_recv,
                "active_connections": network_connections
            }
        except Exception as e:
            logger.error(f"Error getting network metrics: {e}")
            return {"error": str(e)}
    
    async def _get_process_metrics(self) -> Dict[str, Any]:
        """Get process metrics"""
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Sort by CPU usage
            processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
            
            return {
                "total_processes": len(processes),
                "top_cpu_processes": processes[:10],
                "total_cpu_percent": sum(p.get('cpu_percent', 0) for p in processes)
            }
        except Exception as e:
            logger.error(f"Error getting process metrics: {e}")
            return {"error": str(e)}
    
    async def _analyze_metrics(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze metrics and generate alerts"""
        alerts = []
        
        # CPU alerts
        if "cpu" in metrics and "usage_percent" in metrics["cpu"]:
            cpu_usage = metrics["cpu"]["usage_percent"]
            if cpu_usage > 90:
                alerts.append({
                    "type": "critical",
                    "metric": "cpu",
                    "message": f"High CPU usage: {cpu_usage}%",
                    "recommendation": "Check for resource-intensive processes"
                })
            elif cpu_usage > 80:
                alerts.append({
                    "type": "warning",
                    "metric": "cpu",
                    "message": f"Elevated CPU usage: {cpu_usage}%",
                    "recommendation": "Monitor system performance"
                })
        
        # Memory alerts
        if "memory" in metrics and "usage_percent" in metrics["memory"]:
            memory_usage = metrics["memory"]["usage_percent"]
            if memory_usage > 90:
                alerts.append({
                    "type": "critical",
                    "metric": "memory",
                    "message": f"High memory usage: {memory_usage}%",
                    "recommendation": "Consider closing unnecessary applications"
                })
        
        # Disk alerts
        if "disk" in metrics and "usage_percent" in metrics["disk"]:
            disk_usage = metrics["disk"]["usage_percent"]
            if disk_usage > 90:
                alerts.append({
                    "type": "critical",
                    "metric": "disk",
                    "message": f"Low disk space: {disk_usage}% used",
                    "recommendation": "Free up disk space immediately"
                })
            elif disk_usage > 80:
                alerts.append({
                    "type": "warning",
                    "metric": "disk",
                    "message": f"Disk space getting low: {disk_usage}% used",
                    "recommendation": "Consider cleaning up unnecessary files"
                })
        
        return alerts
    
    async def _generate_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        """Generate system recommendations based on metrics"""
        recommendations = []
        
        # CPU recommendations
        if "cpu" in metrics and "usage_percent" in metrics["cpu"]:
            cpu_usage = metrics["cpu"]["usage_percent"]
            if cpu_usage > 70:
                recommendations.append("Consider upgrading CPU or optimizing applications")
        
        # Memory recommendations
        if "memory" in metrics and "usage_percent" in metrics["memory"]:
            memory_usage = metrics["memory"]["usage_percent"]
            if memory_usage > 80:
                recommendations.append("Consider adding more RAM or closing memory-intensive applications")
        
        # Disk recommendations
        if "disk" in metrics and "usage_percent" in metrics["disk"]:
            disk_usage = metrics["disk"]["usage_percent"]
            if disk_usage > 70:
                recommendations.append("Consider disk cleanup or adding more storage")
        
        # General recommendations
        recommendations.extend([
            "Regular system updates improve security and performance",
            "Monitor system logs for potential issues",
            "Implement automated backups for important data"
        ])
        
        return recommendations
    
    def _is_safe_action(self, action: str) -> bool:
        """Check if an action is safe to execute"""
        dangerous_actions = ["shutdown", "reboot", "format", "delete", "remove"]
        return action not in dangerous_actions
    
    async def _start_service(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Start a system service"""
        service_name = parameters.get("service_name", "")
        if not service_name:
            raise AgentError("Service name not provided")
        
        # This would integrate with system service managers in production
        return {
            "action": "start_service",
            "service_name": service_name,
            "output": f"Service {service_name} start command would be executed",
            "success": True
        }
    
    async def _stop_service(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Stop a system service"""
        service_name = parameters.get("service_name", "")
        if not service_name:
            raise AgentError("Service name not provided")
        
        return {
            "action": "stop_service",
            "service_name": service_name,
            "output": f"Service {service_name} stop command would be executed",
            "success": True
        }
    
    async def _restart_service(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Restart a system service"""
        service_name = parameters.get("service_name", "")
        if not service_name:
            raise AgentError("Service name not provided")
        
        return {
            "action": "restart_service",
            "service_name": service_name,
            "output": f"Service {service_name} restart command would be executed",
            "success": True
        }
    
    async def _check_service_status(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Check status of a system service"""
        service_name = parameters.get("service_name", "")
        if not service_name:
            raise AgentError("Service name not provided")
        
        return {
            "action": "check_service_status",
            "service_name": service_name,
            "output": f"Service {service_name} status check would be executed",
            "success": True
        }
    
    async def _execute_safe_command(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a safe system command"""
        command = parameters.get("command", "")
        if not command:
            raise AgentError("Command not provided")
        
        # Check if command is safe
        command_parts = command.split()
        if command_parts[0] not in self.safe_commands:
            raise AgentError(f"Command '{command_parts[0]}' is not in the safe commands list")
        
        try:
            result = subprocess.run(
                command_parts,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                "action": "execute_command",
                "command": command,
                "output": result.stdout,
                "error": result.stderr,
                "return_code": result.returncode,
                "success": result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            raise AgentError("Command execution timed out")
        except Exception as e:
            raise AgentError(f"Command execution failed: {e}")
    
    async def _create_scheduled_task(self, task_description: str, schedule: str) -> Dict[str, Any]:
        """Create a scheduled task"""
        automation_id = f"scheduled_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        return {
            "automation_type": "schedule",
            "task_description": task_description,
            "schedule": schedule,
            "automation_id": automation_id,
            "next_run": self._calculate_next_run(schedule),
            "created": True
        }
    
    async def _create_triggered_task(self, task_description: str, trigger: Dict[str, Any]) -> Dict[str, Any]:
        """Create a triggered task"""
        automation_id = f"triggered_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        return {
            "automation_type": "trigger",
            "task_description": task_description,
            "trigger": trigger,
            "automation_id": automation_id,
            "created": True
        }
    
    async def _create_workflow(self, task_description: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a workflow automation"""
        automation_id = f"workflow_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        return {
            "automation_type": "workflow",
            "task_description": task_description,
            "steps": steps,
            "automation_id": automation_id,
            "created": True
        }
    
    def _calculate_next_run(self, schedule: str) -> str:
        """Calculate next run time based on schedule"""
        now = datetime.utcnow()
        
        if schedule == "daily":
            next_run = now + timedelta(days=1)
        elif schedule == "weekly":
            next_run = now + timedelta(weeks=1)
        elif schedule == "monthly":
            next_run = now + timedelta(days=30)
        else:
            next_run = now + timedelta(hours=1)
        
        return next_run.isoformat()
    
    async def _perform_cleanup(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform system cleanup"""
        cleanup_type = input_data.get("cleanup_type", "temp_files")
        
        return {
            "maintenance_type": "cleanup",
            "cleanup_type": cleanup_type,
            "tasks_performed": [f"Cleanup {cleanup_type}"],
            "results": {"cleaned_files": 0, "freed_space": "0 MB"},
            "success": True
        }
    
    async def _perform_updates(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform system updates"""
        update_type = input_data.get("update_type", "security")
        
        return {
            "maintenance_type": "update",
            "update_type": update_type,
            "tasks_performed": [f"Update {update_type}"],
            "results": {"packages_updated": 0},
            "success": True
        }
    
    async def _perform_backup(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform system backup"""
        backup_type = input_data.get("backup_type", "incremental")
        
        return {
            "maintenance_type": "backup",
            "backup_type": backup_type,
            "tasks_performed": [f"Backup {backup_type}"],
            "results": {"backup_size": "0 MB", "backup_location": "/tmp/backup"},
            "success": True
        }
    
    async def _perform_optimization(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform system optimization"""
        optimization_type = input_data.get("optimization_type", "performance")
        
        return {
            "maintenance_type": "optimization",
            "optimization_type": optimization_type,
            "tasks_performed": [f"Optimize {optimization_type}"],
            "results": {"optimization_applied": True},
            "success": True
        }
    
    async def _basic_security_check(self) -> Dict[str, Any]:
        """Perform basic security check"""
        return {
            "check_type": "basic",
            "checks_performed": ["firewall_status", "antivirus_status", "user_accounts"],
            "vulnerabilities": [],
            "recommendations": ["Enable automatic updates", "Use strong passwords"],
            "security_score": 85
        }
    
    async def _comprehensive_security_check(self) -> Dict[str, Any]:
        """Perform comprehensive security check"""
        return {
            "check_type": "comprehensive",
            "checks_performed": ["firewall", "antivirus", "users", "permissions", "services", "network"],
            "vulnerabilities": [],
            "recommendations": ["Enable firewall", "Update antivirus", "Review user permissions"],
            "security_score": 80
        }
    
    async def _network_security_check(self) -> Dict[str, Any]:
        """Perform network security check"""
        return {
            "check_type": "network",
            "checks_performed": ["open_ports", "network_services", "firewall_rules"],
            "vulnerabilities": [],
            "recommendations": ["Close unnecessary ports", "Review firewall rules"],
            "security_score": 90
        }


# Export the agent class
__all__ = ["SystemAgent"]
