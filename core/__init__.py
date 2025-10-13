"""
Atulya Tantra - Core Module
Essential utilities and base components
"""

__version__ = "1.0.1"
__codename__ = "JARVIS"

from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

__all__ = [
    'PROJECT_ROOT',
    '__version__',
    '__codename__',
]

