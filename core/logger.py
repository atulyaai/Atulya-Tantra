"""
Atulya Tantra - Centralized Logging System
Professional logging configuration for our entire system
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


class AtulyaLogger:
    """Centralized logger for Atulya Tantra system"""
    
    _instance: Optional['AtulyaLogger'] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._setup_logging()
            self._initialized = True
    
    def _setup_logging(self):
        """Setup logging configuration"""
        # Create logs directory
        log_dir = Path(__file__).parent.parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        # Create log file with timestamp
        timestamp = datetime.now().strftime('%Y%m%d')
        log_file = log_dir / f'atulya_{timestamp}.log'
        
        # Configure root logger
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Create logger
        self.logger = logging.getLogger('AtulyaTantra')
        self.logger.info("=" * 70)
        self.logger.info("ATULYA TANTRA - JARVIS PROTOCOL INITIALIZED")
        self.logger.info("=" * 70)
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a logger for a specific module
        
        Args:
            name: Module name
            
        Returns:
            Logger instance
        """
        return logging.getLogger(f'AtulyaTantra.{name}')


# Global logger instance
_atulya_logger = AtulyaLogger()


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module
    
    Args:
        name: Module name (e.g., 'models.audio', 'automation.agents')
        
    Returns:
        Configured logger instance
        
    Example:
        >>> from core.logger import get_logger
        >>> logger = get_logger('models.audio')
        >>> logger.info('Processing audio...')
    """
    return _atulya_logger.get_logger(name)


__all__ = ['get_logger', 'AtulyaLogger']

