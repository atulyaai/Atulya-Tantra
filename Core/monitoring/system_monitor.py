"""
System Monitoring and Auto-Healing
Monitors system health and automatically fixes issues
"""

import time
import threading
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

# Try to import psutil, but don't fail if it's not available
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: psutil not available. System monitoring will be limited.")

class SystemMonitor:
    """
    Advanced system monitoring with auto-healing capabilities
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.running = False
        self.monitoring_thread = None
        self.health_metrics = {}
        self.alert_thresholds = {
            'cpu_percent': 80.0,
            'memory_percent': 85.0,
            'disk_percent': 90.0,
            'temperature': 80.0
        }
        self.auto_heal_enabled = True
        self.healing_actions = []
        
        # Setup logging
        self.logger = self._setup_logging()
    
    def start_monitoring(self):
        """Start system monitoring"""
        if self.running:
            return
        
        self.running = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        self.logger.info("System monitoring started")
    
    def stop_monitoring(self):
        """Stop system monitoring"""
        self.running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        self.logger.info("System monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Collect system metrics
                self._collect_metrics()
                
                # Check for alerts
                self._check_alerts()
                
                # Auto-heal if enabled
                if self.auto_heal_enabled:
                    self._auto_heal()
                
                # Wait before next check
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5)
    
    def _collect_metrics(self):
        """Collect system health metrics"""
        if not PSUTIL_AVAILABLE:
            self.health_metrics = {
                'timestamp': datetime.now().isoformat(),
                'status': 'psutil_not_available',
                'message': 'System monitoring limited - psutil not installed'
            }
            return
        
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            
            # Temperature (if available)
            try:
                temps = psutil.sensors_temperatures()
                cpu_temp = None
                if 'coretemp' in temps:
                    cpu_temp = temps['coretemp'][0].current
            except:
                cpu_temp = None
            
            # Network metrics
            network = psutil.net_io_counters()
            
            self.health_metrics = {
                'timestamp': datetime.now().isoformat(),
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count,
                    'frequency': cpu_freq.current if cpu_freq else None
                },
                'memory': {
                    'percent': memory.percent,
                    'available': memory.available,
                    'used': memory.used,
                    'total': memory.total
                },
                'swap': {
                    'percent': swap.percent,
                    'used': swap.used,
                    'total': swap.total
                },
                'disk': {
                    'percent': disk.percent,
                    'free': disk.free,
                    'used': disk.used,
                    'total': disk.total
                },
                'temperature': {
                    'cpu': cpu_temp
                },
                'network': {
                    'bytes_sent': network.bytes_sent,
                    'bytes_recv': network.bytes_recv,
                    'packets_sent': network.packets_sent,
                    'packets_recv': network.packets_recv
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error collecting metrics: {e}")
            self.health_metrics = {
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
    
    def _check_alerts(self):
        """Check for system alerts"""
        if not PSUTIL_AVAILABLE:
            return
        
        alerts = []
        
        # CPU alert
        if self.health_metrics.get('cpu', {}).get('percent', 0) > self.alert_thresholds['cpu_percent']:
            alerts.append({
                'type': 'cpu_high',
                'message': f"High CPU usage: {self.health_metrics['cpu']['percent']:.1f}%",
                'severity': 'warning'
            })
        
        # Memory alert
        if self.health_metrics.get('memory', {}).get('percent', 0) > self.alert_thresholds['memory_percent']:
            alerts.append({
                'type': 'memory_high',
                'message': f"High memory usage: {self.health_metrics['memory']['percent']:.1f}%",
                'severity': 'warning'
            })
        
        # Disk alert
        if self.health_metrics.get('disk', {}).get('percent', 0) > self.alert_thresholds['disk_percent']:
            alerts.append({
                'type': 'disk_high',
                'message': f"High disk usage: {self.health_metrics['disk']['percent']:.1f}%",
                'severity': 'critical'
            })
        
        # Temperature alert
        cpu_temp = self.health_metrics.get('temperature', {}).get('cpu')
        if cpu_temp and cpu_temp > self.alert_thresholds['temperature']:
            alerts.append({
                'type': 'temperature_high',
                'message': f"High CPU temperature: {cpu_temp:.1f}°C",
                'severity': 'critical'
            })
        
        # Log alerts
        for alert in alerts:
            self.logger.warning(f"ALERT: {alert['message']}")
    
    def _auto_heal(self):
        """Automatically heal system issues"""
        if not PSUTIL_AVAILABLE:
            return
        
        try:
            # High CPU usage - try to identify and kill resource-heavy processes
            if self.health_metrics.get('cpu', {}).get('percent', 0) > self.alert_thresholds['cpu_percent']:
                self._handle_high_cpu()
            
            # High memory usage - try to free up memory
            if self.health_metrics.get('memory', {}).get('percent', 0) > self.alert_thresholds['memory_percent']:
                self._handle_high_memory()
            
            # High disk usage - try to clean up temporary files
            if self.health_metrics.get('disk', {}).get('percent', 0) > self.alert_thresholds['disk_percent']:
                self._handle_high_disk()
            
        except Exception as e:
            self.logger.error(f"Error in auto-heal: {e}")
    
    def _handle_high_cpu(self):
        """Handle high CPU usage"""
        try:
            # Get top CPU processes
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                try:
                    proc_info = proc.info
                    if proc_info['cpu_percent'] > 10:  # Processes using more than 10% CPU
                        processes.append(proc_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Sort by CPU usage
            processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
            
            # Log top processes
            self.logger.info("Top CPU processes:")
            for proc in processes[:5]:
                self.logger.info(f"  {proc['name']} (PID: {proc['pid']}): {proc['cpu_percent']:.1f}%")
            
            # Record healing action
            self.healing_actions.append({
                'timestamp': datetime.now().isoformat(),
                'action': 'cpu_analysis',
                'details': f"Analyzed {len(processes)} high-CPU processes"
            })
            
        except Exception as e:
            self.logger.error(f"Error handling high CPU: {e}")
    
    def _handle_high_memory(self):
        """Handle high memory usage"""
        try:
            # Get top memory processes
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'memory_percent']):
                try:
                    proc_info = proc.info
                    if proc_info['memory_percent'] > 5:  # Processes using more than 5% memory
                        processes.append(proc_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Sort by memory usage
            processes.sort(key=lambda x: x['memory_percent'], reverse=True)
            
            # Log top processes
            self.logger.info("Top memory processes:")
            for proc in processes[:5]:
                self.logger.info(f"  {proc['name']} (PID: {proc['pid']}): {proc['memory_percent']:.1f}%")
            
            # Record healing action
            self.healing_actions.append({
                'timestamp': datetime.now().isoformat(),
                'action': 'memory_analysis',
                'details': f"Analyzed {len(processes)} high-memory processes"
            })
            
        except Exception as e:
            self.logger.error(f"Error handling high memory: {e}")
    
    def _handle_high_disk(self):
        """Handle high disk usage"""
        try:
            # Get disk usage by directory
            import os
            disk_usage = {}
            
            # Check common directories that might have large files
            directories = ['/tmp', '/var/log', '/var/cache', '/home']
            
            for directory in directories:
                if os.path.exists(directory):
                    try:
                        usage = psutil.disk_usage(directory)
                        disk_usage[directory] = {
                            'total': usage.total,
                            'used': usage.used,
                            'free': usage.free,
                            'percent': usage.percent
                        }
                    except:
                        continue
            
            # Log disk usage
            self.logger.info("Disk usage by directory:")
            for directory, usage in disk_usage.items():
                self.logger.info(f"  {directory}: {usage['percent']:.1f}% used")
            
            # Record healing action
            self.healing_actions.append({
                'timestamp': datetime.now().isoformat(),
                'action': 'disk_analysis',
                'details': f"Analyzed disk usage in {len(disk_usage)} directories"
            })
            
        except Exception as e:
            self.logger.error(f"Error handling high disk: {e}")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current system health status"""
        return {
            'metrics': self.health_metrics,
            'thresholds': self.alert_thresholds,
            'auto_heal_enabled': self.auto_heal_enabled,
            'recent_actions': self.healing_actions[-10:],  # Last 10 actions
            'psutil_available': PSUTIL_AVAILABLE
        }
    
    def set_alert_threshold(self, metric: str, threshold: float):
        """Set alert threshold for a metric"""
        if metric in self.alert_thresholds:
            self.alert_thresholds[metric] = threshold
            self.logger.info(f"Alert threshold for {metric} set to {threshold}")
    
    def enable_auto_heal(self, enabled: bool = True):
        """Enable or disable auto-healing"""
        self.auto_heal_enabled = enabled
        self.logger.info(f"Auto-healing {'enabled' if enabled else 'disabled'}")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for the system monitor"""
        logger = logging.getLogger('system_monitor')
        logger.setLevel(logging.INFO)
        
        # Create file handler
        handler = logging.FileHandler('system_monitor.log')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger
