"""
Core configuration system for Atulya Tantra AGI
Supports multiple AI providers, feature flags, and environment management
"""

import os
from typing import Dict, List, Optional, Any
from pydantic import BaseSettings, Field
from enum import Enum


class AIProvider(str, Enum):
    """Supported AI providers"""
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class DatabaseType(str, Enum):
    """Supported database types"""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    JSON = "json"


class Settings(BaseSettings):
    """Main configuration class"""
    
    # Application
    app_name: str = "Atulya Tantra AGI"
    app_version: str = "3.0.0"
    debug: bool = Field(default=False, env="DEBUG")
    environment: str = Field(default="development", env="ENVIRONMENT")
    
    # Server
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    workers: int = Field(default=1, env="WORKERS")
    
    # Security
    secret_key: str = Field(default="your-secret-key-change-in-production", env="SECRET_KEY")
    jwt_secret: str = Field(default="your-jwt-secret-change-in-production", env="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 7
    
    # Database
    database_type: DatabaseType = Field(default=DatabaseType.SQLITE, env="DATABASE_TYPE")
    database_url: Optional[str] = Field(default=None, env="DATABASE_URL")
    sqlite_path: str = Field(default="data/tantra.db", env="SQLITE_PATH")
    
    # Redis (for caching and sessions)
    redis_url: Optional[str] = Field(default=None, env="REDIS_URL")
    redis_host: str = Field(default="localhost", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT")
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    
    # AI Providers
    primary_ai_provider: AIProvider = Field(default=AIProvider.OLLAMA, env="PRIMARY_AI_PROVIDER")
    
    # Ollama
    ollama_base_url: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="gemma2:2b", env="OLLAMA_MODEL")
    ollama_timeout: int = Field(default=30, env="OLLAMA_TIMEOUT")
    
    # OpenAI
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4-turbo", env="OPENAI_MODEL")
    openai_max_tokens: int = Field(default=4000, env="OPENAI_MAX_TOKENS")
    openai_temperature: float = Field(default=0.7, env="OPENAI_TEMPERATURE")
    
    # Anthropic
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-3-5-sonnet-20241022", env="ANTHROPIC_MODEL")
    anthropic_max_tokens: int = Field(default=4000, env="ANTHROPIC_MAX_TOKENS")
    anthropic_temperature: float = Field(default=0.7, env="ANTHROPIC_TEMPERATURE")
    
    # Vector Database (ChromaDB)
    chroma_host: str = Field(default="localhost", env="CHROMA_HOST")
    chroma_port: int = Field(default=8001, env="CHROMA_PORT")
    chroma_collection_name: str = Field(default="tantra_memory", env="CHROMA_COLLECTION")
    
    # Feature Flags
    features: Dict[str, bool] = Field(default={
        # Core Features
        "streaming": True,
        "markdown_rendering": True,
        "voice_interface": True,
        "vision": True,
        "file_attachments": True,
        
        # JARVIS Features
        "personality_engine": True,
        "proactive_assistance": True,
        "emotional_intelligence": True,
        
        # Skynet Features
        "autonomous_operations": False,  # Requires explicit enable
        "desktop_automation": False,      # Requires explicit enable
        "task_scheduling": True,
        "self_monitoring": True,
        
        # Specialized Agents
        "code_agent": True,
        "research_agent": True,
        "creative_agent": True,
        "data_agent": True,
        "system_agent": True,
        
        # Advanced Features
        "knowledge_graph": True,
        "vector_memory": True,
        "multi_modal": True,
        "web_search": True,
    }, env="FEATURES")
    
    # Rate Limiting
    rate_limit_requests: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(default=60, env="RATE_LIMIT_WINDOW")  # seconds
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")  # json or text
    log_file: Optional[str] = Field(default=None, env="LOG_FILE")
    
    # Monitoring
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    metrics_port: int = Field(default=9090, env="METRICS_PORT")
    
    # File Upload
    max_file_size: int = Field(default=10 * 1024 * 1024, env="MAX_FILE_SIZE")  # 10MB
    allowed_file_types: List[str] = Field(default=[
        "text/plain", "text/markdown", "application/pdf",
        "image/jpeg", "image/png", "image/gif", "image/webp"
    ], env="ALLOWED_FILE_TYPES")
    
    # Voice Settings
    voice_enabled: bool = Field(default=True, env="VOICE_ENABLED")
    voice_wake_word: str = Field(default="hey jarvis", env="VOICE_WAKE_WORD")
    voice_language: str = Field(default="en-US", env="VOICE_LANGUAGE")
    voice_energy_threshold: int = Field(default=300, env="VOICE_ENERGY_THRESHOLD")
    voice_pause_threshold: float = Field(default=0.8, env="VOICE_PAUSE_THRESHOLD")
    
    # Memory Settings
    max_conversation_history: int = Field(default=50, env="MAX_CONVERSATION_HISTORY")
    memory_compression_threshold: int = Field(default=20, env="MEMORY_COMPRESSION_THRESHOLD")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_database_url() -> str:
    """Get the appropriate database URL based on configuration"""
    if settings.database_url:
        return settings.database_url
    
    if settings.database_type == DatabaseType.SQLITE:
        return f"sqlite:///{settings.sqlite_path}"
    elif settings.database_type == DatabaseType.POSTGRESQL:
        return settings.database_url or "postgresql://user:password@localhost/tantra"
    else:
        return "json://data/"


def get_redis_url() -> str:
    """Get Redis URL"""
    if settings.redis_url:
        return settings.redis_url
    
    auth = f":{settings.redis_password}@" if settings.redis_password else ""
    return f"redis://{auth}{settings.redis_host}:{settings.redis_port}"


def is_feature_enabled(feature: str) -> bool:
    """Check if a feature is enabled"""
    return settings.features.get(feature, False)


def get_ai_provider_config(provider: AIProvider) -> Dict[str, Any]:
    """Get configuration for a specific AI provider"""
    configs = {
        AIProvider.OLLAMA: {
            "base_url": settings.ollama_base_url,
            "model": settings.ollama_model,
            "timeout": settings.ollama_timeout,
        },
        AIProvider.OPENAI: {
            "api_key": settings.openai_api_key,
            "model": settings.openai_model,
            "max_tokens": settings.openai_max_tokens,
            "temperature": settings.openai_temperature,
        },
        AIProvider.ANTHROPIC: {
            "api_key": settings.anthropic_api_key,
            "model": settings.anthropic_model,
            "max_tokens": settings.anthropic_max_tokens,
            "temperature": settings.anthropic_temperature,
        }
    }
    return configs.get(provider, {})


def validate_configuration() -> List[str]:
    """Validate configuration and return any errors"""
    errors = []
    
    # Check required settings based on enabled features
    if is_feature_enabled("autonomous_operations") and not settings.secret_key.startswith("your-"):
        errors.append("SECRET_KEY must be changed for autonomous operations")
    
    if settings.primary_ai_provider == AIProvider.OPENAI and not settings.openai_api_key:
        errors.append("OPENAI_API_KEY is required when using OpenAI as primary provider")
    
    if settings.primary_ai_provider == AIProvider.ANTHROPIC and not settings.anthropic_api_key:
        errors.append("ANTHROPIC_API_KEY is required when using Anthropic as primary provider")
    
    if settings.database_type == DatabaseType.POSTGRESQL and not settings.database_url:
        errors.append("DATABASE_URL is required for PostgreSQL")
    
    return errors


# Export commonly used settings
__all__ = [
    "Settings", "settings", "AIProvider", "DatabaseType",
    "get_database_url", "get_redis_url", "is_feature_enabled",
    "get_ai_provider_config", "validate_configuration"
]
