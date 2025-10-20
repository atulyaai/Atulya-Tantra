"""
Atulya Tantra - Skynet System Control
Version: 2.5.0
System control and automation for desktop operations
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import subprocess
import platform
import psutil
import os
import json
import asyncio
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SystemInfo:
    """System information structure"""
    platform: str
    architecture: str
    cpu_count: int
    cpu_usage: float
    memory_total: int
    memory_available: int
    memory_usage_percent: float
    disk_usage: Dict[str, Dict[str, Any]]
    network_info: Dict[str, Any]
    running_processes: int
    uptime: float


@dataclass
class ProcessInfo:
    """Process information structure"""
    pid: int
    name: str
    status: str
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    create_time: float
    command_line: str


@dataclass
class WindowInfo:
    """Window information structure"""
    title: str
    process_name: str
    pid: int
    geometry: Tuple[int, int, int, int]  # x, y, width, height
    is_active: bool
    is_visible: bool


class SystemController:
    """System control and automation controller"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.platform = platform.system().lower()
        self.automation_enabled = config.get("automation_enabled", False)
        self.safety_mode = config.get("safety_mode", True)
        self.allowed_processes = config.get("allowed_processes", [])
        self.blocked_processes = config.get("blocked_processes", [])
        
        logger.info(f"SystemController initialized for {self.platform}")
    
    async def get_system_info(self) -> SystemInfo:
        """Get comprehensive system information"""
        
        try:
            # Basic system info
            cpu_count = psutil.cpu_count()
            cpu_usage = psutil.cpu_percent(interval=1)
            
            # Memory info
            memory = psutil.virtual_memory()
            memory_total = memory.total
            memory_available = memory.available
            memory_usage_percent = memory.percent
            
            # Disk usage
            disk_usage = {}
            for partition in psutil.disk_partitions():
                try:
                    partition_usage = psutil.disk_usage(partition.mountpoint)
                    disk_usage[partition.mountpoint] = {
                        "total": partition_usage.total,
                        "used": partition_usage.used,
                        "free": partition_usage.free,
                        "percent": (partition_usage.used / partition_usage.total) * 100
                    }
                except PermissionError:
                    continue
            
            # Network info
            network_info = {}
            for interface, addrs in psutil.net_if_addrs().items():
                network_info[interface] = {
                    "addresses": [addr.address for addr in addrs],
                    "stats": psutil.net_if_stats().get(interface, {}).__dict__ if psutil.net_if_stats().get(interface) else {}
                }
            
            # Process count
            running_processes = len(psutil.pids())
            
            # System uptime
            uptime = psutil.boot_time()
            current_time = datetime.now().timestamp()
            uptime_hours = (current_time - uptime) / 3600
            
            return SystemInfo(
                platform=self.platform,
                architecture=platform.machine(),
                cpu_count=cpu_count,
                cpu_usage=cpu_usage,
                memory_total=memory_total,
                memory_available=memory_available,
                memory_usage_percent=memory_usage_percent,
                disk_usage=disk_usage,
                network_info=network_info,
                running_processes=running_processes,
                uptime=uptime_hours
            )
            
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            raise
    
    async def get_processes(self, limit: int = 50) -> List[ProcessInfo]:
        """Get list of running processes"""
        
        processes = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'status', 'cpu_percent', 'memory_percent', 'memory_info', 'create_time', 'cmdline']):
                try:
                    proc_info = proc.info
                    memory_info = proc_info['memory_info']
                    memory_mb = memory_info.rss / (1024 * 1024) if memory_info else 0
                    
                    process = ProcessInfo(
                        pid=proc_info['pid'],
                        name=proc_info['name'],
                        status=proc_info['status'],
                        cpu_percent=proc_info['cpu_percent'] or 0,
                        memory_percent=proc_info['memory_percent'] or 0,
                        memory_mb=memory_mb,
                        create_time=proc_info['create_time'],
                        command_line=' '.join(proc_info['cmdline']) if proc_info['cmdline'] else ''
                    )
                    processes.append(process)
                    
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            # Sort by memory usage
            processes.sort(key=lambda x: x.memory_percent, reverse=True)
            
            return processes[:limit]
            
        except Exception as e:
            logger.error(f"Error getting processes: {e}")
            return []
    
    async def get_process_by_name(self, process_name: str) -> Optional[ProcessInfo]:
        """Get process information by name"""
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'status', 'cpu_percent', 'memory_percent', 'memory_info', 'create_time', 'cmdline']):
                try:
                    if proc.info['name'].lower() == process_name.lower():
                        proc_info = proc.info
                        memory_info = proc_info['memory_info']
                        memory_mb = memory_info.rss / (1024 * 1024) if memory_info else 0
                        
                        return ProcessInfo(
                            pid=proc_info['pid'],
                            name=proc_info['name'],
                            status=proc_info['status'],
                            cpu_percent=proc_info['cpu_percent'] or 0,
                            memory_percent=proc_info['memory_percent'] or 0,
                            memory_mb=memory_mb,
                            create_time=proc_info['create_time'],
                            command_line=' '.join(proc_info['cmdline']) if proc_info['cmdline'] else ''
                        )
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting process by name: {e}")
            return None
    
    async def start_process(self, command: str, args: List[str] = None) -> Dict[str, Any]:
        """Start a new process"""
        
        if not self.automation_enabled:
            return {"error": "Automation is disabled"}
        
        if self.safety_mode and not self._is_process_allowed(command):
            return {"error": f"Process '{command}' is not allowed in safety mode"}
        
        try:
            # Start process
            process = subprocess.Popen(
                [command] + (args or []),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait a moment to check if process started successfully
            await asyncio.sleep(0.5)
            
            if process.poll() is None:  # Process is still running
                return {
                    "success": True,
                    "pid": process.pid,
                    "command": command,
                    "args": args or [],
                    "status": "started"
                }
            else:
                # Process exited immediately, get error
                stdout, stderr = process.communicate()
                return {
                    "error": f"Process failed to start: {stderr or stdout}"
                }
                
        except FileNotFoundError:
            return {"error": f"Command '{command}' not found"}
        except Exception as e:
            logger.error(f"Error starting process: {e}")
            return {"error": str(e)}
    
    async def stop_process(self, pid: int, force: bool = False) -> Dict[str, Any]:
        """Stop a process by PID"""
        
        if not self.automation_enabled:
            return {"error": "Automation is disabled"}
        
        try:
            process = psutil.Process(pid)
            
            if self.safety_mode and not self._is_process_allowed(process.name()):
                return {"error": f"Process '{process.name()}' cannot be stopped in safety mode"}
            
            if force:
                process.kill()
            else:
                process.terminate()
            
            # Wait for process to stop
            try:
                process.wait(timeout=5)
                return {
                    "success": True,
                    "pid": pid,
                    "status": "stopped"
                }
            except psutil.TimeoutExpired:
                # Force kill if termination didn't work
                process.kill()
                return {
                    "success": True,
                    "pid": pid,
                    "status": "force_stopped"
                }
                
        except psutil.NoSuchProcess:
            return {"error": f"Process with PID {pid} not found"}
        except psutil.AccessDenied:
            return {"error": f"Access denied to process with PID {pid}"}
        except Exception as e:
            logger.error(f"Error stopping process: {e}")
            return {"error": str(e)}
    
    async def get_system_performance(self) -> Dict[str, Any]:
        """Get system performance metrics"""
        
        try:
            # CPU usage over time
            cpu_percentages = psutil.cpu_percent(interval=1, percpu=True)
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Disk I/O
            disk_io = psutil.disk_io_counters()
            
            # Network I/O
            network_io = psutil.net_io_counters()
            
            # Load average (Unix systems)
            load_avg = None
            if hasattr(os, 'getloadavg'):
                load_avg = os.getloadavg()
            
            return {
                "cpu": {
                    "per_core": cpu_percentages,
                    "average": sum(cpu_percentages) / len(cpu_percentages) if cpu_percentages else 0,
                    "count": len(cpu_percentages)
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "used": memory.used,
                    "percent": memory.percent,
                    "cached": getattr(memory, 'cached', 0),
                    "buffers": getattr(memory, 'buffers', 0)
                },
                "disk": {
                    "read_bytes": disk_io.read_bytes if disk_io else 0,
                    "write_bytes": disk_io.write_bytes if disk_io else 0,
                    "read_count": disk_io.read_count if disk_io else 0,
                    "write_count": disk_io.write_count if disk_io else 0
                },
                "network": {
                    "bytes_sent": network_io.bytes_sent if network_io else 0,
                    "bytes_recv": network_io.bytes_recv if network_io else 0,
                    "packets_sent": network_io.packets_sent if network_io else 0,
                    "packets_recv": network_io.packets_recv if network_io else 0
                },
                "load_average": load_avg
            }
            
        except Exception as e:
            logger.error(f"Error getting system performance: {e}")
            return {"error": str(e)}
    
    async def optimize_system(self) -> Dict[str, Any]:
        """Perform basic system optimization"""
        
        if not self.automation_enabled:
            return {"error": "Automation is disabled"}
        
        optimizations = []
        
        try:
            # Check for high memory usage processes
            processes = await self.get_processes(limit=20)
            high_memory_processes = [p for p in processes if p.memory_percent > 10]
            
            if high_memory_processes:
                optimizations.append({
                    "type": "high_memory_usage",
                    "description": "Processes using high memory detected",
                    "processes": [{"name": p.name, "memory_percent": p.memory_percent} for p in high_memory_processes[:5]]
                })
            
            # Check disk space
            disk_usage = {}
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    if usage.percent > 90:
                        optimizations.append({
                            "type": "low_disk_space",
                            "description": f"Low disk space on {partition.mountpoint}",
                            "usage_percent": usage.percent,
                            "free_gb": usage.free / (1024**3)
                        })
                except PermissionError:
                    continue
            
            # Check CPU usage
            cpu_usage = psutil.cpu_percent(interval=1)
            if cpu_usage > 80:
                optimizations.append({
                    "type": "high_cpu_usage",
                    "description": "High CPU usage detected",
                    "cpu_percent": cpu_usage
                })
            
            return {
                "optimizations": optimizations,
                "total_issues": len(optimizations),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error optimizing system: {e}")
            return {"error": str(e)}
    
    def _is_process_allowed(self, process_name: str) -> bool:
        """Check if a process is allowed to be controlled"""
        
        # Check blocked processes first
        if process_name.lower() in [p.lower() for p in self.blocked_processes]:
            return False
        
        # If allowed_processes is specified, check if process is in the list
        if self.allowed_processes:
            return process_name.lower() in [p.lower() for p in self.allowed_processes]
        
        # Default: allow all if no restrictions
        return True
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of system controller"""
        return {
            "system_controller": True,
            "platform": self.platform,
            "automation_enabled": self.automation_enabled,
            "safety_mode": self.safety_mode,
            "allowed_processes": len(self.allowed_processes),
            "blocked_processes": len(self.blocked_processes)
        }
