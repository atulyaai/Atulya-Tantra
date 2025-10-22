"""
Custom exceptions for Atulya Tantra AGI
Provides structured error handling across the application
"""

from typing import Optional, Dict, Any


class TantraException(Exception):
    """Base exception for all Tantra-specific errors"""
    
    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code or self.__class__.__name__
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details
            }
        }


# Configuration Exceptions
class ConfigurationError(TantraException):
    """Raised when configuration is invalid"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "CONFIGURATION_ERROR", 500, details)


class FeatureNotEnabledError(TantraException):
    """Raised when attempting to use a disabled feature"""
    
    def __init__(self, feature: str):
        super().__init__(
            f"Feature '{feature}' is not enabled",
            "FEATURE_NOT_ENABLED",
            403,
            {"feature": feature}
        )


# Authentication & Authorization Exceptions
class AuthenticationError(TantraException):
    """Raised when authentication fails"""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, "AUTHENTICATION_ERROR", 401)


class AuthorizationError(TantraException):
    """Raised when user lacks required permissions"""
    
    def __init__(self, message: str = "Insufficient permissions", required_role: Optional[str] = None):
        super().__init__(
            message,
            "AUTHORIZATION_ERROR",
            403,
            {"required_role": required_role} if required_role else None
        )


class InvalidTokenError(TantraException):
    """Raised when JWT token is invalid or expired"""
    
    def __init__(self, message: str = "Invalid or expired token"):
        super().__init__(message, "INVALID_TOKEN", 401)


# Database Exceptions
class DatabaseError(TantraException):
    """Base class for database errors"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "DATABASE_ERROR", 500, details)


class RecordNotFoundError(DatabaseError):
    """Raised when a database record is not found"""
    
    def __init__(self, model: str, identifier: Any):
        super().__init__(
            f"{model} not found",
            {"model": model, "identifier": str(identifier)}
        )
        self.code = "RECORD_NOT_FOUND"
        self.status_code = 404


class DuplicateRecordError(DatabaseError):
    """Raised when attempting to create a duplicate record"""
    
    def __init__(self, model: str, field: str, value: Any):
        super().__init__(
            f"{model} with {field}='{value}' already exists",
            {"model": model, "field": field, "value": str(value)}
        )
        self.code = "DUPLICATE_RECORD"
        self.status_code = 409


# AI/LLM Exceptions
class AIProviderError(TantraException):
    """Base class for AI provider errors"""
    
    def __init__(self, provider: str, message: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["provider"] = provider
        super().__init__(message, "AI_PROVIDER_ERROR", 502, details)


class ModelNotAvailableError(AIProviderError):
    """Raised when requested AI model is not available"""
    
    def __init__(self, provider: str, model: str):
        super().__init__(
            provider,
            f"Model '{model}' is not available",
            {"model": model}
        )
        self.code = "MODEL_NOT_AVAILABLE"


class TokenLimitExceededError(AIProviderError):
    """Raised when token limit is exceeded"""
    
    def __init__(self, provider: str, requested: int, limit: int):
        super().__init__(
            provider,
            f"Token limit exceeded: requested {requested}, limit {limit}",
            {"requested": requested, "limit": limit}
        )
        self.code = "TOKEN_LIMIT_EXCEEDED"
        self.status_code = 400


class AIProviderTimeoutError(AIProviderError):
    """Raised when AI provider times out"""
    
    def __init__(self, provider: str, timeout: float):
        super().__init__(
            provider,
            f"Request to {provider} timed out after {timeout}s",
            {"timeout": timeout}
        )
        self.code = "AI_PROVIDER_TIMEOUT"
        self.status_code = 504


# Agent Exceptions
class AgentError(TantraException):
    """Base class for agent errors"""
    
    def __init__(self, agent: str, message: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["agent"] = agent
        super().__init__(message, "AGENT_ERROR", 500, details)


class AgentNotFoundError(AgentError):
    """Raised when requested agent is not found"""
    
    def __init__(self, agent: str):
        super().__init__(agent, f"Agent '{agent}' not found")
        self.code = "AGENT_NOT_FOUND"
        self.status_code = 404


class AgentExecutionError(AgentError):
    """Raised when agent execution fails"""
    
    def __init__(self, agent: str, task: str, error: str):
        super().__init__(
            agent,
            f"Agent '{agent}' failed to execute task: {error}",
            {"task": task, "error": error}
        )
        self.code = "AGENT_EXECUTION_ERROR"


# Memory Exceptions
class MemoryError(TantraException):
    """Base class for memory system errors"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "MEMORY_ERROR", 500, details)


class VectorStoreError(MemoryError):
    """Raised when vector store operation fails"""
    
    def __init__(self, operation: str, error: str):
        super().__init__(
            f"Vector store {operation} failed: {error}",
            {"operation": operation, "error": error}
        )
        self.code = "VECTOR_STORE_ERROR"


class KnowledgeGraphError(MemoryError):
    """Raised when knowledge graph operation fails"""
    
    def __init__(self, operation: str, error: str):
        super().__init__(
            f"Knowledge graph {operation} failed: {error}",
            {"operation": operation, "error": error}
        )
        self.code = "KNOWLEDGE_GRAPH_ERROR"


# File Processing Exceptions
class FileProcessingError(TantraException):
    """Base class for file processing errors"""
    
    def __init__(self, filename: str, message: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["filename"] = filename
        super().__init__(message, "FILE_PROCESSING_ERROR", 400, details)


class FileTypeNotSupportedError(FileProcessingError):
    """Raised when file type is not supported"""
    
    def __init__(self, filename: str, file_type: str):
        super().__init__(
            filename,
            f"File type '{file_type}' is not supported",
            {"file_type": file_type}
        )
        self.code = "FILE_TYPE_NOT_SUPPORTED"


class FileTooLargeError(FileProcessingError):
    """Raised when file size exceeds limit"""
    
    def __init__(self, filename: str, size: int, max_size: int):
        super().__init__(
            filename,
            f"File size ({size} bytes) exceeds maximum allowed size ({max_size} bytes)",
            {"size": size, "max_size": max_size}
        )
        self.code = "FILE_TOO_LARGE"
        self.status_code = 413


# Rate Limiting Exceptions
class RateLimitExceededError(TantraException):
    """Raised when rate limit is exceeded"""
    
    def __init__(self, limit: int, window: int, retry_after: Optional[int] = None):
        super().__init__(
            f"Rate limit exceeded: {limit} requests per {window} seconds",
            "RATE_LIMIT_EXCEEDED",
            429,
            {"limit": limit, "window": window, "retry_after": retry_after}
        )


# Skynet/Autonomous Operation Exceptions
class AutonomousOperationError(TantraException):
    """Base class for autonomous operation errors"""
    
    def __init__(self, operation: str, message: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["operation"] = operation
        super().__init__(message, "AUTONOMOUS_OPERATION_ERROR", 500, details)


class OperationNotPermittedError(AutonomousOperationError):
    """Raised when autonomous operation is not permitted"""
    
    def __init__(self, operation: str, reason: str):
        super().__init__(
            operation,
            f"Operation '{operation}' not permitted: {reason}",
            {"reason": reason}
        )
        self.code = "OPERATION_NOT_PERMITTED"
        self.status_code = 403


class SchedulerError(AutonomousOperationError):
    """Raised when task scheduling fails"""
    
    def __init__(self, task: str, error: str):
        super().__init__(
            "schedule",
            f"Failed to schedule task '{task}': {error}",
            {"task": task, "error": error}
        )
        self.code = "SCHEDULER_ERROR"


# Validation Exceptions
class ValidationError(TantraException):
    """Raised when input validation fails"""
    
    def __init__(self, field: str, message: str, value: Optional[Any] = None):
        super().__init__(
            f"Validation error for field '{field}': {message}",
            "VALIDATION_ERROR",
            400,
            {"field": field, "message": message, "value": str(value) if value is not None else None}
        )


# Export all exceptions
__all__ = [
    # Base
    "TantraException",
    
    # Configuration
    "ConfigurationError",
    "FeatureNotEnabledError",
    
    # Authentication
    "AuthenticationError",
    "AuthorizationError",
    "InvalidTokenError",
    
    # Database
    "DatabaseError",
    "RecordNotFoundError",
    "DuplicateRecordError",
    
    # AI/LLM
    "AIProviderError",
    "ModelNotAvailableError",
    "TokenLimitExceededError",
    "AIProviderTimeoutError",
    
    # Agents
    "AgentError",
    "AgentNotFoundError",
    "AgentExecutionError",
    
    # Memory
    "MemoryError",
    "VectorStoreError",
    "KnowledgeGraphError",
    
    # File Processing
    "FileProcessingError",
    "FileTypeNotSupportedError",
    "FileTooLargeError",
    
    # Rate Limiting
    "RateLimitExceededError",
    
    # Autonomous Operations
    "AutonomousOperationError",
    "OperationNotPermittedError",
    "SchedulerError",
    
    # Validation
    "ValidationError",
]

