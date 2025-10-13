"""
Atulya Tantra - Custom Exceptions
Centralized exception handling for our system
"""


class AtulyaException(Exception):
    """Base exception for all Atulya Tantra errors"""
    pass


class ModelException(AtulyaException):
    """Exceptions related to AI model operations"""
    pass


class ConfigurationException(AtulyaException):
    """Exceptions related to configuration"""
    pass


class VoiceException(AtulyaException):
    """Exceptions related to voice processing"""
    pass


class AgentException(AtulyaException):
    """Exceptions related to agent operations"""
    pass


class MCPException(AtulyaException):
    """Exceptions related to Model Context Protocol"""
    pass


class MemoryException(AtulyaException):
    """Exceptions related to memory operations"""
    pass


class NetworkException(AtulyaException):
    """Exceptions related to network operations"""
    pass


class SecurityException(AtulyaException):
    """Exceptions related to security violations"""
    pass


__all__ = [
    'AtulyaException',
    'ModelException',
    'ConfigurationException',
    'VoiceException',
    'AgentException',
    'MCPException',
    'MemoryException',
    'NetworkException',
    'SecurityException',
]

