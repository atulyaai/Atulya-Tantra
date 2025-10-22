"""
Atulya Tantra AGI - Core Package
Main application package for the AGI system
"""

__version__ = "3.0.0"
__author__ = "Atulya AI"
__license__ = "MIT"

from .config import settings, is_feature_enabled
from .config.logging import setup_logging, get_logger

# Initialize logging on import
setup_logging()

__all__ = [
    "__version__",
    "settings",
    "is_feature_enabled",
    "setup_logging",
    "get_logger"
]

