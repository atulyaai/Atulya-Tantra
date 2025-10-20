"""
Atulya Tantra - Base Integration Interface
Version: 2.5.0
Base interface for external integrations
"""

import logging
from typing import Dict, List, Optional, Any, Protocol
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class IntegrationStatus(Enum):
    """Integration status"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    DISABLED = "disabled"


class IntegrationType(Enum):
    """Integration types"""
    CALENDAR = "calendar"
    EMAIL = "email"
    STORAGE = "storage"
    API = "api"
    DATABASE = "database"


@dataclass
class IntegrationConfig:
    """Integration configuration"""
    integration_id: str
    name: str
    type: IntegrationType
    status: IntegrationStatus
    credentials: Dict[str, Any]
    settings: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass
class IntegrationEvent:
    """Integration event"""
    event_id: str
    integration_id: str
    event_type: str
    data: Dict[str, Any]
    timestamp: datetime
    processed: bool


class BaseIntegration(Protocol):
    """Base interface for all integrations"""
    
    @property
    def integration_id(self) -> str:
        """Get integration unique identifier"""
        ...
    
    @property
    def name(self) -> str:
        """Get integration name"""
        ...
    
    @property
    def type(self) -> IntegrationType:
        """Get integration type"""
        ...
    
    @property
    def status(self) -> IntegrationStatus:
        """Get current integration status"""
        ...
    
    async def connect(self, credentials: Dict[str, Any]) -> bool:
        """Connect to the integration"""
        ...
    
    async def disconnect(self) -> bool:
        """Disconnect from the integration"""
        ...
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test the integration connection"""
        ...
    
    async def get_capabilities(self) -> List[str]:
        """Get integration capabilities"""
        ...
    
    async def health_check(self) -> Dict[str, Any]:
        """Check integration health"""
        ...


class IntegrationManager:
    """Manager for external integrations"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.integrations = {}  # integration_id -> BaseIntegration
        self.integration_events = []  # List of IntegrationEvent
        self.event_handlers = {}  # event_type -> List[Callable]
        
        logger.info("IntegrationManager initialized")
    
    def register_integration(self, integration: BaseIntegration):
        """Register a new integration"""
        self.integrations[integration.integration_id] = integration
        logger.info(f"Registered integration: {integration.name} ({integration.integration_id})")
    
    def unregister_integration(self, integration_id: str):
        """Unregister an integration"""
        if integration_id in self.integrations:
            del self.integrations[integration_id]
            logger.info(f"Unregistered integration: {integration_id}")
    
    async def get_available_integrations(self) -> List[BaseIntegration]:
        """Get list of available integrations"""
        return [
            integration for integration in self.integrations.values()
            if integration.status == IntegrationStatus.CONNECTED
        ]
    
    async def get_integration_status(self) -> Dict[str, Any]:
        """Get status of all integrations"""
        return {
            "total_integrations": len(self.integrations),
            "connected_integrations": len([
                i for i in self.integrations.values()
                if i.status == IntegrationStatus.CONNECTED
            ]),
            "integrations": [
                {
                    "integration_id": integration.integration_id,
                    "name": integration.name,
                    "type": integration.type.value,
                    "status": integration.status.value,
                    "capabilities": await integration.get_capabilities()
                }
                for integration in self.integrations.values()
            ]
        }
    
    async def register_event_handler(self, event_type: str, handler: Callable):
        """Register an event handler"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        
        self.event_handlers[event_type].append(handler)
        logger.info(f"Registered event handler for: {event_type}")
    
    async def trigger_event(self, integration_id: str, event_type: str, data: Dict[str, Any]):
        """Trigger an integration event"""
        event = IntegrationEvent(
            event_id=str(uuid.uuid4()),
            integration_id=integration_id,
            event_type=event_type,
            data=data,
            timestamp=datetime.now(),
            processed=False
        )
        
        self.integration_events.append(event)
        
        # Process event handlers
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Error in event handler for {event_type}: {e}")
        
        event.processed = True
        logger.info(f"Triggered event: {event_type} for integration {integration_id}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of integration manager"""
        return {
            "integration_manager": True,
            "total_integrations": len(self.integrations),
            "connected_integrations": len([
                i for i in self.integrations.values()
                if i.status == IntegrationStatus.CONNECTED
            ]),
            "total_events": len(self.integration_events),
            "event_handlers": len(self.event_handlers)
        }
