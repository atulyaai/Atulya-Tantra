"""
Atulya Tantra - Core Utilities
Shared utility functions used across our system
"""

import os
import sys
import time
import psutil
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


def get_project_root() -> Path:
    """Get the project root directory"""
    return Path(__file__).parent.parent


def get_system_info() -> Dict[str, Any]:
    """
    Get current system information
    
    Returns:
        Dictionary with system metrics
    """
    return {
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_percent': psutil.disk_usage('/').percent,
        'python_version': sys.version.split()[0],
        'platform': sys.platform,
        'timestamp': datetime.now().isoformat(),
    }


def format_uptime(start_time: float) -> str:
    """
    Format uptime from start timestamp
    
    Args:
        start_time: Start timestamp from time.time()
        
    Returns:
        Formatted uptime string
    """
    uptime_seconds = int(time.time() - start_time)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def ensure_directory(path: Path) -> Path:
    """
    Ensure directory exists, create if it doesn't
    
    Args:
        path: Directory path
        
    Returns:
        Path object
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_file_size_mb(file_path: Path) -> float:
    """
    Get file size in megabytes
    
    Args:
        file_path: Path to file
        
    Returns:
        File size in MB
    """
    return os.path.getsize(file_path) / (1024 * 1024)


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to maximum length
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def validate_model_name(model: str) -> bool:
    """
    Validate AI model name format
    
    Args:
        model: Model name to validate
        
    Returns:
        True if valid
    """
    # Basic validation: should contain at least one colon and alphanumeric characters
    if ':' not in model:
        return False
    
    parts = model.split(':')
    return len(parts) == 2 and all(part.strip() for part in parts)


def parse_version(version_str: str) -> tuple:
    """
    Parse version string to tuple
    
    Args:
        version_str: Version string (e.g., "1.0.1")
        
    Returns:
        Version tuple (e.g., (1, 0, 1))
    """
    try:
        return tuple(int(x) for x in version_str.split('.'))
    except ValueError:
        return (0, 0, 0)


def format_bytes(bytes_count: int) -> str:
    """
    Format bytes to human-readable string
    
    Args:
        bytes_count: Number of bytes
        
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.1f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.1f} PB"


class Timer:
    """Simple timer for performance monitoring"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, *args):
        self.end_time = time.time()
    
    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds"""
        if self.start_time is None:
            return 0.0
        end = self.end_time if self.end_time else time.time()
        return end - self.start_time
    
    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds"""
        return self.elapsed * 1000


__all__ = [
    'get_project_root',
    'get_system_info',
    'format_uptime',
    'ensure_directory',
    'get_file_size_mb',
    'truncate_text',
    'validate_model_name',
    'parse_version',
    'format_bytes',
    'Timer',
]

