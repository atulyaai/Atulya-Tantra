# Pytest configuration for Atulya Tantra
# Phase D: Automated Test Suite

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Shared fixtures
import pytest
import logging

@pytest.fixture
def mock_memory():
    """Mock memory manager for testing."""
    from core.memory_manager import MemoryManager
    return MemoryManager()

@pytest.fixture
def mock_governor(mock_memory):
    """Mock governor for testing."""
    from core.governor import Governor
    return Governor(mock_memory)

@pytest.fixture
def disable_logging():
    """Disable logging during tests to reduce noise."""
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)

@pytest.fixture
def sample_facts():
    """Sample facts for knowledge brain testing."""
    return [
        {
            "id": "fact_001",
            "topic": "TEST",
            "content": "This is a test fact about testing.",
            "confidence": 0.9
        },
        {
            "id": "fact_002",
            "topic": "TEST",
            "content": "Testing is important for reliability.",
            "confidence": 0.85
        }
    ]
