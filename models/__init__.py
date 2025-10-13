"""
Atulya Tantra - AI Models Module
Audio, text, video models and model routing
"""

from .model_router import ModelRouter, get_model_router

__all__ = ['audio', 'text', 'video', 'ModelRouter', 'get_model_router']

