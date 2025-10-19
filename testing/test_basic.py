"""
Atulya Tantra - Basic System Tests
Version: 2.2.0
Basic tests to verify the system is working correctly.
"""

import pytest
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_import_core_modules():
    """Test that core modules can be imported"""
    import core.config
    import core.memory
    import core.monitoring
    import core.voice
    import core.agents
    import core.automation
    import core.models
    import core.version
    assert True

def test_server_startup():
    """Test that server can be imported and initialized"""
    import server
    assert hasattr(server, 'app')
    assert True

def test_configuration_loading():
    """Test that configuration can be loaded"""
    from configuration.unified_config import get_config
    config = get_config()
    assert config.system_name == "Atulya Tantra"
    assert config.system_version == "2.2.0"
    assert True

def test_version_info():
    """Test that version information is available"""
    from core.version import get_current_version, get_version_info
    version = get_current_version()
    version_info = get_version_info()
    assert version == "2.2.0"
    assert version_info.codename == "WebMaster"
    assert True

def test_memory_system():
    """Test that memory system can be initialized"""
    from core.memory import get_memory_manager
    memory_manager = get_memory_manager()
    assert memory_manager is not None
    assert True

def test_monitoring_system():
    """Test that monitoring system can be initialized"""
    from core.monitoring import get_monitoring_system
    monitoring_system = get_monitoring_system()
    assert monitoring_system is not None
    assert True

def test_voice_system():
    """Test that voice system can be initialized"""
    from core.voice import get_voice_engine
    voice_engine = get_voice_engine()
    assert voice_engine is not None
    assert True

def test_agent_system():
    """Test that agent system can be initialized"""
    from core.agents import get_multi_agent_orchestrator
    orchestrator = get_multi_agent_orchestrator()
    assert orchestrator is not None
    assert True

def test_automation_system():
    """Test that automation system can be initialized"""
    from core.automation import get_automation_engine
    automation_engine = get_automation_engine()
    assert automation_engine is not None
    assert True

def test_model_router():
    """Test that model router can be initialized"""
    from core.models import get_hybrid_model_router
    model_router = get_hybrid_model_router()
    assert model_router is not None
    assert True

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
