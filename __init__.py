"""
Atulya Tantra - Advanced Personal AI Assistant
JARVIS & SKYNET Protocols

Our professional-grade AI system with emotional intelligence and multi-agent orchestration.
"""

from __version__ import __version__, __version_info__, get_version

__all__ = [
    '__version__',
    '__version_info__',
    'get_version',
]

# Package metadata
__author__ = "Atulya Tantra Team"
__email__ = "admin@atulvij.com"
__license__ = "MIT"
__status__ = "Active Development"
__codename__ = "JARVIS"

# Quick access to core components
def get_jarvis():
    """Get JARVIS Protocol interface"""
    from protocols.jarvis import JarvisInterface
    return JarvisInterface()

def get_skynet():
    """Get SKYNET Protocol orchestrator"""
    from protocols.skynet import SkynetOrchestrator
    return SkynetOrchestrator()

def get_settings():
    """Get global settings"""
    from configuration import settings
    return settings

def get_logger(name: str = 'AtulyaTantra'):
    """Get logger instance"""
    from core.logger import get_logger as _get_logger
    return _get_logger(name)


if __name__ == '__main__':
    print("=" * 70)
    print(f"Atulya Tantra {get_version()}")
    print("=" * 70)
    print(f"Status: {__status__}")
    print(f"License: {__license__}")
    print(f"Python Package: atulya-tantra")
    print("=" * 70)
    print("\nAvailable Protocols:")
    print("  • JARVIS Protocol - Conversational AI")
    print("  • SKYNET Protocol - Multi-Agent System")
    print("\nQuick Start:")
    print("  from atulya_tantra import get_jarvis, get_skynet")
    print("  jarvis = get_jarvis()")
    print("  await jarvis.activate()")
    print("=" * 70)

