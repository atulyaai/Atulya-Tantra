"""
Advanced Structured Logging System
Centralized logging with aggregation, filtering, and analysis
"""

import json
import time
import asyncio
import threading
from typing import Dict, List, Any, Optional, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import logging.handlers
from pathlib import Path
import gzip
import shutil

from ..config.logging import get_logger
from ..config.exceptions import MonitoringError

logger = get_logger(__name__)


class LogLevel(str, Enum):
    """Log levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(str, Enum):
    """Log categories"""
    SYSTEM = "system"
    USER = "user"
    AI = "ai"
    AGENT = "agent"
    SECURITY = "security"
    PERFORMANCE = "performance"
    ERROR = "error"
    AUDIT = "audit"


@dataclass
class LogEntry:
    """Structured log entry"""
    timestamp: datetime
    level: LogLevel
    category: LogCategory
    component: str
    message: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = None
    stack_trace: Optional[str] = None
    duration_ms: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), default=str)


class StructuredLogger:
    """Advanced structured logging system"""
    
    def __init__(self, log_dir: str = "logs", max_file_size: int = 100 * 1024 * 1024, 
                 backup_count: int = 5, enable_compression: bool = True):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.enable_compression = enable_compression
        
        # Log storage
        self.log_entries: List[LogEntry] = []
        self.log_lock = threading.Lock()
        self.max_memory_entries = 10000
        
        # Loggers for different categories
        self.loggers: Dict[str, logging.Logger] = {}
        self._setup_loggers()
        
        # Background processing
        self.is_running = False
        self._start_background_processing()
    
    def _setup_loggers(self):
        """Setup loggers for different categories"""
        for category in LogCategory:
            logger_name = f"tantra.{category.value}"
            logger_obj = logging.getLogger(logger_name)
            logger_obj.setLevel(logging.DEBUG)
            
            # File handler
            log_file = self.log_dir / f"{category.value}.log"
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=self.max_file_size, backupCount=self.backup_count
            )
            
            # JSON formatter
            json_formatter = JSONFormatter()
            file_handler.setFormatter(json_formatter)
            logger_obj.addHandler(file_handler)
            
            # Console handler for errors and critical
            if category in [LogCategory.ERROR, LogCategory.SECURITY, LogCategory.CRITICAL]:
                console_handler = logging.StreamHandler()
                console_handler.setLevel(logging.WARNING)
                console_formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                console_handler.setFormatter(console_formatter)
                logger_obj.addHandler(console_handler)
            
            self.loggers[category.value] = logger_obj
    
    def _start_background_processing(self):
        """Start background log processing"""
        self.is_running = True
        
        def process_logs():
            while self.is_running:
                try:
                    # Process log entries
                    with self.log_lock:
                        if len(self.log_entries) > self.max_memory_entries:
                            # Keep only recent entries
                            self.log_entries = self.log_entries[-self.max_memory_entries:]
                    
                    # Compress old log files
                    if self.enable_compression:
                        self._compress_old_logs()
                    
                    time.sleep(60)  # Process every minute
                    
                except Exception as e:
                    logger.error(f"Error in background log processing: {e}")
                    time.sleep(60)
        
        thread = threading.Thread(target=process_logs, daemon=True)
        thread.start()
    
    def _compress_old_logs(self):
        """Compress old log files"""
        try:
            for log_file in self.log_dir.glob("*.log.*"):
                if not log_file.name.endswith('.gz'):
                    compressed_file = f"{log_file}.gz"
                    with open(log_file, 'rb') as f_in:
                        with gzip.open(compressed_file, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    log_file.unlink()  # Remove original file
        except Exception as e:
            logger.error(f"Error compressing log files: {e}")
    
    def log(self, level: LogLevel, category: LogCategory, component: str, 
            message: str, **kwargs) -> LogEntry:
        """Log a structured entry"""
        entry = LogEntry(
            timestamp=datetime.utcnow(),
            level=level,
            category=category,
            component=component,
            message=message,
            user_id=kwargs.get('user_id'),
            session_id=kwargs.get('session_id'),
            request_id=kwargs.get('request_id'),
            correlation_id=kwargs.get('correlation_id'),
            metadata=kwargs.get('metadata', {}),
            stack_trace=kwargs.get('stack_trace'),
            duration_ms=kwargs.get('duration_ms')
        )
        
        # Store in memory
        with self.log_lock:
            self.log_entries.append(entry)
        
        # Log to file
        logger_obj = self.loggers.get(category.value)
        if logger_obj:
            log_level = getattr(logging, level.value)
            logger_obj.log(log_level, entry.to_json())
        
        return entry
    
    def debug(self, category: LogCategory, component: str, message: str, **kwargs):
        """Log debug message"""
        return self.log(LogLevel.DEBUG, category, component, message, **kwargs)
    
    def info(self, category: LogCategory, component: str, message: str, **kwargs):
        """Log info message"""
        return self.log(LogLevel.INFO, category, component, message, **kwargs)
    
    def warning(self, category: LogCategory, component: str, message: str, **kwargs):
        """Log warning message"""
        return self.log(LogLevel.WARNING, category, component, message, **kwargs)
    
    def error(self, category: LogCategory, component: str, message: str, **kwargs):
        """Log error message"""
        return self.log(LogLevel.ERROR, category, component, message, **kwargs)
    
    def critical(self, category: LogCategory, component: str, message: str, **kwargs):
        """Log critical message"""
        return self.log(LogLevel.CRITICAL, category, component, message, **kwargs)
    
    def log_request(self, method: str, endpoint: str, status_code: int, 
                   duration_ms: float, user_id: str = None, **kwargs):
        """Log HTTP request"""
        category = LogCategory.SYSTEM if status_code < 400 else LogCategory.ERROR
        message = f"{method} {endpoint} {status_code} ({duration_ms:.2f}ms)"
        
        return self.info(
            category, "http", message,
            user_id=user_id,
            metadata={
                "method": method,
                "endpoint": endpoint,
                "status_code": status_code,
                "duration_ms": duration_ms
            },
            **kwargs
        )
    
    def log_ai_request(self, provider: str, model: str, tokens_used: int, 
                      response_time_ms: float, success: bool, **kwargs):
        """Log AI/LLM request"""
        category = LogCategory.AI
        level = LogLevel.INFO if success else LogLevel.ERROR
        message = f"AI request: {provider}/{model} ({tokens_used} tokens, {response_time_ms:.2f}ms)"
        
        return self.log(
            level, category, "ai", message,
            metadata={
                "provider": provider,
                "model": model,
                "tokens_used": tokens_used,
                "response_time_ms": response_time_ms,
                "success": success
            },
            **kwargs
        )
    
    def log_agent_execution(self, agent_type: str, task: str, success: bool, 
                           duration_ms: float, **kwargs):
        """Log agent execution"""
        category = LogCategory.AGENT
        level = LogLevel.INFO if success else LogLevel.ERROR
        message = f"Agent {agent_type}: {task} ({duration_ms:.2f}ms)"
        
        return self.log(
            level, category, "agent", message,
            metadata={
                "agent_type": agent_type,
                "task": task,
                "success": success,
                "duration_ms": duration_ms
            },
            **kwargs
        )
    
    def log_security_event(self, event_type: str, user_id: str = None, 
                          severity: str = "medium", **kwargs):
        """Log security event"""
        level = LogLevel.CRITICAL if severity == "high" else LogLevel.WARNING
        message = f"Security event: {event_type}"
        
        return self.log(
            level, LogCategory.SECURITY, "security", message,
            user_id=user_id,
            metadata={
                "event_type": event_type,
                "severity": severity
            },
            **kwargs
        )
    
    def log_user_action(self, action: str, user_id: str, **kwargs):
        """Log user action"""
        return self.info(
            LogCategory.USER, "user", f"User action: {action}",
            user_id=user_id,
            metadata={"action": action},
            **kwargs
        )
    
    def search_logs(self, start_time: datetime = None, end_time: datetime = None,
                   level: LogLevel = None, category: LogCategory = None,
                   component: str = None, user_id: str = None,
                   limit: int = 1000) -> List[LogEntry]:
        """Search logs with filters"""
        with self.log_lock:
            results = self.log_entries.copy()
        
        # Apply filters
        if start_time:
            results = [entry for entry in results if entry.timestamp >= start_time]
        if end_time:
            results = [entry for entry in results if entry.timestamp <= end_time]
        if level:
            results = [entry for entry in results if entry.level == level]
        if category:
            results = [entry for entry in results if entry.category == category]
        if component:
            results = [entry for entry in results if entry.component == component]
        if user_id:
            results = [entry for entry in results if entry.user_id == user_id]
        
        # Sort by timestamp (newest first)
        results.sort(key=lambda x: x.timestamp, reverse=True)
        
        return results[:limit]
    
    def get_log_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get log statistics for the last N hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        with self.log_lock:
            recent_logs = [entry for entry in self.log_entries 
                          if entry.timestamp >= cutoff_time]
        
        stats = {
            "total_entries": len(recent_logs),
            "by_level": {},
            "by_category": {},
            "by_component": {},
            "error_rate": 0,
            "top_errors": [],
            "unique_users": set(),
            "time_range": {
                "start": cutoff_time.isoformat(),
                "end": datetime.utcnow().isoformat()
            }
        }
        
        # Count by level
        for entry in recent_logs:
            level = entry.level.value
            stats["by_level"][level] = stats["by_level"].get(level, 0) + 1
            
            # Count by category
            category = entry.category.value
            stats["by_category"][category] = stats["by_category"].get(category, 0) + 1
            
            # Count by component
            component = entry.component
            stats["by_component"][component] = stats["by_component"].get(component, 0) + 1
            
            # Track users
            if entry.user_id:
                stats["unique_users"].add(entry.user_id)
        
        # Calculate error rate
        total_entries = stats["total_entries"]
        error_entries = stats["by_level"].get("ERROR", 0) + stats["by_level"].get("CRITICAL", 0)
        stats["error_rate"] = (error_entries / total_entries * 100) if total_entries > 0 else 0
        
        # Find top errors
        error_logs = [entry for entry in recent_logs 
                     if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]]
        error_messages = {}
        for entry in error_logs:
            message = entry.message
            error_messages[message] = error_messages.get(message, 0) + 1
        
        stats["top_errors"] = sorted(error_messages.items(), key=lambda x: x[1], reverse=True)[:10]
        stats["unique_users"] = len(stats["unique_users"])
        
        return stats
    
    def export_logs(self, start_time: datetime, end_time: datetime, 
                   format: str = "json") -> Union[str, List[Dict[str, Any]]]:
        """Export logs in specified format"""
        logs = self.search_logs(start_time, end_time)
        
        if format == "json":
            return [log.to_dict() for log in logs]
        elif format == "csv":
            # Convert to CSV format
            if not logs:
                return ""
            
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=logs[0].to_dict().keys())
            writer.writeheader()
            
            for log in logs:
                writer.writerow(log.to_dict())
            
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def stop(self):
        """Stop the structured logger"""
        self.is_running = False


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        """Format log record as JSON"""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                          'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                          'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                          'thread', 'threadName', 'processName', 'process', 'getMessage']:
                log_data[key] = value
        
        return json.dumps(log_data, default=str)


class LogAggregator:
    """Log aggregation and analysis system"""
    
    def __init__(self, structured_logger: StructuredLogger):
        self.logger = structured_logger
        self.aggregation_rules: List[Callable] = []
        self.alert_thresholds: Dict[str, int] = {}
    
    def add_aggregation_rule(self, rule: Callable):
        """Add custom aggregation rule"""
        self.aggregation_rules.append(rule)
    
    def set_alert_threshold(self, metric: str, threshold: int):
        """Set alert threshold for a metric"""
        self.alert_thresholds[metric] = threshold
    
    def analyze_logs(self, hours: int = 1) -> Dict[str, Any]:
        """Analyze logs for patterns and anomalies"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        logs = self.logger.search_logs(start_time=cutoff_time)
        
        analysis = {
            "time_range": f"Last {hours} hours",
            "total_logs": len(logs),
            "patterns": {},
            "anomalies": [],
            "recommendations": []
        }
        
        # Analyze error patterns
        error_logs = [log for log in logs if log.level in [LogLevel.ERROR, LogLevel.CRITICAL]]
        if error_logs:
            error_patterns = {}
            for log in error_logs:
                pattern = self._extract_error_pattern(log.message)
                error_patterns[pattern] = error_patterns.get(pattern, 0) + 1
            
            analysis["patterns"]["errors"] = error_patterns
            
            # Check for error spikes
            if len(error_logs) > self.alert_thresholds.get("error_count", 10):
                analysis["anomalies"].append({
                    "type": "error_spike",
                    "count": len(error_logs),
                    "threshold": self.alert_thresholds.get("error_count", 10)
                })
        
        # Analyze performance patterns
        performance_logs = [log for log in logs if log.category == LogCategory.PERFORMANCE]
        if performance_logs:
            durations = [log.duration_ms for log in performance_logs if log.duration_ms]
            if durations:
                avg_duration = sum(durations) / len(durations)
                analysis["patterns"]["avg_duration_ms"] = avg_duration
                
                # Check for performance degradation
                if avg_duration > self.alert_thresholds.get("avg_duration_ms", 5000):
                    analysis["anomalies"].append({
                        "type": "performance_degradation",
                        "avg_duration_ms": avg_duration,
                        "threshold": self.alert_thresholds.get("avg_duration_ms", 5000)
                    })
        
        # Generate recommendations
        if analysis["anomalies"]:
            analysis["recommendations"].append("Investigate anomalies detected in logs")
        
        if len(error_logs) > 0:
            analysis["recommendations"].append("Review error patterns and consider fixes")
        
        return analysis
    
    def _extract_error_pattern(self, message: str) -> str:
        """Extract error pattern from message"""
        # Simple pattern extraction - could be enhanced with regex
        if "timeout" in message.lower():
            return "timeout_error"
        elif "connection" in message.lower():
            return "connection_error"
        elif "permission" in message.lower():
            return "permission_error"
        elif "not found" in message.lower():
            return "not_found_error"
        else:
            return "generic_error"


# Global structured logger instance
_structured_logger: Optional[StructuredLogger] = None


def get_structured_logger() -> StructuredLogger:
    """Get global structured logger instance"""
    global _structured_logger
    if _structured_logger is None:
        _structured_logger = StructuredLogger()
    return _structured_logger


def get_log_aggregator() -> LogAggregator:
    """Get log aggregator instance"""
    logger = get_structured_logger()
    return LogAggregator(logger)