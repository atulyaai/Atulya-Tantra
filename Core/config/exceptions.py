"""
Custom exceptions for Atulya Tantra AGI
"""

class TantraException(Exception):
    """Base exception for Tantra AGI"""
    pass

class ConfigurationError(TantraException):
    """Configuration related errors"""
    pass

class LLMProviderError(TantraException):
    """LLM provider related errors"""
    pass

class AgentError(TantraException):
    """Agent related errors"""
    pass

class DatabaseError(TantraException):
    """Database related errors"""
    pass