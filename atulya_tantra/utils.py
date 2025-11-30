"""
Utility Functions
Common utilities used across the system
"""
import os
import logging
from pathlib import Path
from typing import Optional
from .constants import LOG_LEVEL, LOG_FORMAT


def setup_logging(level: Optional[str] = None, format_str: Optional[str] = None):
    """
    Configure logging for the application
    
    Args:
        level: Logging level (default: from constants)
        format_str: Log format string (default: from constants)
    """
    logging.basicConfig(
        level=getattr(logging, level or LOG_LEVEL),
        format=format_str or LOG_FORMAT,
        handlers=[logging.StreamHandler()]
    )


def get_env_var(key: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    """
    Get environment variable with validation
    
    Args:
        key: Environment variable name
        default: Default value if not found
        required: If True, raise error if not found
        
    Returns:
        Environment variable value
        
    Raises:
        ValueError: If required and not found
    """
    value = os.getenv(key, default)
    
    if required and value is None:
        raise ValueError(f"Required environment variable '{key}' not found")
    
    return value


def resolve_path(path: str, base_dir: Optional[Path] = None) -> Path:
    """
    Resolve path relative to base directory
    
    Args:
        path: Path to resolve
        base_dir: Base directory (default: project root)
        
    Returns:
        Resolved absolute path
    """
    from .constants import PROJECT_ROOT
    
    path_obj = Path(path)
    
    if path_obj.is_absolute():
        return path_obj
    
    base = base_dir or PROJECT_ROOT
    return (base / path_obj).resolve()


def format_error(error: Exception, include_traceback: bool = False) -> str:
    """
    Format error message for logging
    
    Args:
        error: Exception to format
        include_traceback: Include full traceback
        
    Returns:
        Formatted error string
    """
    if include_traceback:
        import traceback
        return f"{type(error).__name__}: {str(error)}\n{''.join(traceback.format_tb(error.__traceback__))}"
    
    return f"{type(error).__name__}: {str(error)}"


def ensure_dir(path: Path) -> Path:
    """
    Ensure directory exists, create if needed
    
    Args:
        path: Directory path
        
    Returns:
        Path object
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_cache_dir(name: str) -> Path:
    """
    Get cache directory for a specific component
    
    Args:
        name: Component name
        
    Returns:
        Cache directory path
    """
    from .constants import MODELS_CACHE_DIR
    
    cache_dir = MODELS_CACHE_DIR / name
    return ensure_dir(cache_dir)


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
