"""
Atulya Tantra - Test Configuration
Version: 2.5.0
Global test configuration and fixtures
"""

import os
import sys
import pytest
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set required environment variables for testing
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-32-characters-long")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-characters-long")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("ENVIRONMENT", "test")

@pytest.fixture(scope="session")
def test_env():
    """Set up test environment variables"""
    env_vars = {
        "ENCRYPTION_KEY": "test-encryption-key-32-characters-long",
        "SECRET_KEY": "test-secret-key-32-characters-long", 
        "JWT_SECRET": "test-jwt-secret-key-32-characters-long",
        "DATABASE_URL": "sqlite:///./test.db",
        "ENVIRONMENT": "test",
        "REDIS_URL": "redis://localhost:6379/1",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "OPENAI_API_KEY": "test-key",
        "ANTHROPIC_API_KEY": "test-key",
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
    
    yield env_vars
    
    # Cleanup after tests
    for key in env_vars:
        if key in os.environ:
            del os.environ[key]
