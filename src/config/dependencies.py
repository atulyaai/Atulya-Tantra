"""
Atulya Tantra - Dependency Injection Container
Version: 2.5.0
Clean dependency injection for loose coupling
"""

from functools import lru_cache
from typing import Dict, Type, Callable, Any, Optional
import logging

logger = logging.getLogger(__name__)


class DIContainer:
    """Dependency injection container"""
    
    def __init__(self):
        self._services: Dict[Type, Callable] = {}
        self._singletons: Dict[Type, Any] = {}
        self._instances: Dict[Type, Any] = {}
    
    def register(self, interface: Type, implementation: Callable, singleton: bool = True):
        """Register a service"""
        self._services[interface] = implementation
        if singleton:
            self._singletons[interface] = None
        logger.debug(f"Registered {interface.__name__} as {'singleton' if singleton else 'transient'}")
    
    def register_instance(self, interface: Type, instance: Any):
        """Register a pre-created instance"""
        self._instances[interface] = instance
        logger.debug(f"Registered instance for {interface.__name__}")
    
    def get(self, interface: Type):
        """Get service instance"""
        # Check for pre-registered instance
        if interface in self._instances:
            return self._instances[interface]
        
        # Check for singleton
        if interface in self._singletons:
            if self._singletons[interface] is None:
                self._singletons[interface] = self._services[interface]()
            return self._singletons[interface]
        
        # Create new instance
        if interface in self._services:
            return self._services[interface]()
        
        raise ValueError(f"Service {interface.__name__} not registered")
    
    def clear(self):
        """Clear all registrations (useful for testing)"""
        self._services.clear()
        self._singletons.clear()
        self._instances.clear()


# Global container
container = DIContainer()


def setup_dependencies():
    """Register all dependencies"""
    from src.config.settings import get_settings
    
    settings = get_settings()
    
    # Register settings as singleton
    container.register_instance(type(settings), settings)
    
    logger.info("Dependency injection container initialized")


def get_service(service_type: Type):
    """Get service from container"""
    return container.get(service_type)


# Common service getters for FastAPI dependencies
@lru_cache()
def get_settings_service():
    """Get settings service"""
    return container.get(type(get_settings()))


def get_chat_service():
    """Get chat service (will be implemented)"""
    # This will be implemented when ChatService is created
    pass


def get_ai_service():
    """Get AI service (will be implemented)"""
    # This will be implemented when AIService is created
    pass
