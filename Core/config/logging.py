"""
Structured logging system for Atulya Tantra AGI
Supports both JSON and text format with correlation IDs and context
"""

import logging
import logging.handlers
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import traceback

from .settings import settings


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for machine parsing"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add correlation ID if available
        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = record.correlation_id
        
        # Add user ID if available
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        
        # Add extra context
        if hasattr(record, "extra"):
            log_data["extra"] = record.extra
        
        # Add exception information if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_data)


class TextFormatter(logging.Formatter):
    """Format logs as human-readable text"""
    
    # Color codes for terminal output
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        # Add color if outputting to terminal
        if sys.stderr.isatty():
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            reset = self.COLORS['RESET']
            level = f"{color}{record.levelname:8}{reset}"
        else:
            level = f"{record.levelname:8}"
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Build log message
        message = f"{timestamp} | {level} | {record.name} | {record.getMessage()}"
        
        # Add correlation ID if available
        if hasattr(record, "correlation_id"):
            message += f" | correlation_id={record.correlation_id}"
        
        # Add exception information if present
        if record.exc_info:
            message += f"\n{self.formatException(record.exc_info)}"
        
        return message


class ContextFilter(logging.Filter):
    """Add contextual information to log records"""
    
    def __init__(self):
        super().__init__()
        self.correlation_id: Optional[str] = None
        self.user_id: Optional[str] = None
        self.extra: Dict[str, Any] = {}
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Add context to record
        if self.correlation_id:
            record.correlation_id = self.correlation_id
        if self.user_id:
            record.user_id = self.user_id
        if self.extra:
            record.extra = self.extra
        return True


# Global context filter instance
_context_filter = ContextFilter()


def setup_logging() -> None:
    """Setup logging configuration"""
    
    # Get log level from settings
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Choose formatter based on settings
    if settings.log_format.lower() == "json":
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(_context_filter)
    root_logger.addHandler(console_handler)
    
    # File handler if log file is configured
    if settings.log_file:
        log_path = Path(settings.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Rotating file handler (10MB max, keep 5 backups)
        file_handler = logging.handlers.RotatingFileHandler(
            settings.log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(_context_filter)
        root_logger.addHandler(file_handler)
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging initialized - Level: {settings.log_level}, "
        f"Format: {settings.log_format}, "
        f"File: {settings.log_file or 'None'}"
    )


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for all subsequent logs"""
    _context_filter.correlation_id = correlation_id


def set_user_id(user_id: str) -> None:
    """Set user ID for all subsequent logs"""
    _context_filter.user_id = user_id


def set_extra_context(**kwargs) -> None:
    """Set extra context for all subsequent logs"""
    _context_filter.extra.update(kwargs)


def clear_context() -> None:
    """Clear all logging context"""
    _context_filter.correlation_id = None
    _context_filter.user_id = None
    _context_filter.extra = {}


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name"""
    return logging.getLogger(name)


# Helper functions for structured logging
def log_request(logger: logging.Logger, method: str, path: str, user_id: Optional[str] = None) -> None:
    """Log an HTTP request"""
    logger.info(f"Request: {method} {path}", extra={"user_id": user_id})


def log_response(logger: logging.Logger, method: str, path: str, status: int, duration_ms: float) -> None:
    """Log an HTTP response"""
    logger.info(
        f"Response: {method} {path} - Status: {status} - Duration: {duration_ms:.2f}ms",
        extra={"status": status, "duration_ms": duration_ms}
    )


def log_error(logger: logging.Logger, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
    """Log an error with context"""
    logger.error(
        f"Error: {type(error).__name__}: {str(error)}",
        exc_info=True,
        extra=context or {}
    )


def log_agent_execution(
    logger: logging.Logger,
    agent_name: str,
    task: str,
    status: str,
    duration_ms: float,
    result: Optional[str] = None
) -> None:
    """Log agent execution"""
    logger.info(
        f"Agent: {agent_name} - Task: {task} - Status: {status} - Duration: {duration_ms:.2f}ms",
        extra={
            "agent": agent_name,
            "task": task,
            "status": status,
            "duration_ms": duration_ms,
            "result": result
        }
    )


def log_llm_call(
    logger: logging.Logger,
    provider: str,
    model: str,
    tokens_used: int,
    duration_ms: float,
    cost: Optional[float] = None
) -> None:
    """Log LLM API call"""
    logger.info(
        f"LLM Call: {provider}/{model} - Tokens: {tokens_used} - Duration: {duration_ms:.2f}ms",
        extra={
            "provider": provider,
            "model": model,
            "tokens_used": tokens_used,
            "duration_ms": duration_ms,
            "cost": cost
        }
    )


# Export public API
__all__ = [
    "setup_logging",
    "get_logger",
    "set_correlation_id",
    "set_user_id",
    "set_extra_context",
    "clear_context",
    "log_request",
    "log_response",
    "log_error",
    "log_agent_execution",
    "log_llm_call",
    "JSONFormatter",
    "TextFormatter"
]

