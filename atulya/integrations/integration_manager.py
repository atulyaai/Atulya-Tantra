"""Integration modules for external services"""

from typing import Dict, Any, Optional
from typing import List
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class IntegrationBase(ABC):
    """Base class for integrations"""

    def __init__(self, name: str, config: Dict = None):
        """
        Initialize integration
        
        Args:
            name: Integration name
            config: Configuration dictionary
        """
        self.name = name
        self.config = config or {}
        self.connected = False

    @abstractmethod
    def connect(self) -> bool:
        """Connect to external service"""
        pass

    @abstractmethod
    def execute(self, command: str, params: Dict = None) -> Dict:
        """Execute integration command"""
        pass


class APIIntegration(IntegrationBase):
    """Generic API integration"""

    def __init__(self, name: str, base_url: str, api_key: Optional[str] = None):
        """
        Initialize API integration
        
        Args:
            name: Integration name
            base_url: API base URL
            api_key: API authentication key
        """
        super().__init__(name, {"base_url": base_url, "api_key": api_key})
        self.base_url = base_url

    def connect(self) -> bool:
        """Connect to API"""
        self.connected = True
        logger.info(f"Connected to {self.name}")
        return True

    def execute(self, command: str, params: Dict = None) -> Dict:
        """
        Execute API command
        
        Args:
            command: API endpoint/command
            params: Request parameters
            
        Returns:
            API response
        """
        if not self.connected:
            return {"success": False, "error": "Not connected"}
        
        # Simulate API call
        return {
            "success": True,
            "command": command,
            "params": params,
            "response": f"Response from {self.name}"
        }


class DatabaseIntegration(IntegrationBase):
    """Database integration"""

    def __init__(self, name: str, db_type: str, connection_string: str):
        """
        Initialize database integration
        
        Args:
            name: Integration name
            db_type: Database type
            connection_string: Connection string
        """
        super().__init__(name, {
            "type": db_type,
            "connection_string": connection_string
        })

    def connect(self) -> bool:
        """Connect to database"""
        self.connected = True
        logger.info(f"Connected to {self.name}")
        return True

    def execute(self, command: str, params: Dict = None) -> Dict:
        """
        Execute database command
        
        Args:
            command: SQL command or query
            params: Query parameters
            
        Returns:
            Query result
        """
        if not self.connected:
            return {"success": False, "error": "Not connected"}
        
        return {
            "success": True,
            "command": command,
            "rows_affected": 0,
            "result": []
        }


class IntegrationManager:
    """Manages all integrations"""

    def __init__(self):
        """Initialize Integration Manager"""
        self.integrations = {}
        self.connection_status = {}
        logger.info("Integration Manager initialized")

    def register_integration(self, integration_name: str,
                            integration: IntegrationBase) -> bool:
        """
        Register an integration
        
        Args:
            integration_name: Name to register as
            integration: Integration instance
            
        Returns:
            Success status
        """
        self.integrations[integration_name] = integration
        logger.info(f"Integration '{integration_name}' registered")
        return True

    def connect_all(self) -> Dict[str, bool]:
        """
        Connect all registered integrations
        
        Returns:
            Connection status for each integration
        """
        status = {}
        
        for name, integration in self.integrations.items():
            try:
                result = integration.connect()
                status[name] = result
                self.connection_status[name] = result
            except Exception as e:
                logger.error(f"Failed to connect {name}: {str(e)}")
                status[name] = False
        
        return status

    def execute_integration(self, integration_name: str,
                          command: str, params: Dict = None) -> Dict:
        """
        Execute integration command
        
        Args:
            integration_name: Integration name
            command: Command to execute
            params: Command parameters
            
        Returns:
            Execution result
        """
        if integration_name not in self.integrations:
            return {
                "success": False,
                "error": f"Integration '{integration_name}' not found"
            }
        
        integration = self.integrations[integration_name]
        
        if not integration.connected:
            logger.warning(f"Integration {integration_name} not connected")
        
        return integration.execute(command, params)

    def list_integrations(self) -> List[Dict]:
        """
        List all registered integrations
        
        Returns:
            List of integration info
        """
        return [
            {
                "name": name,
                "type": integration.__class__.__name__,
                "connected": integration.connected
            }
            for name, integration in self.integrations.items()
        ]

    def disconnect_all(self) -> Dict[str, bool]:
        """
        Disconnect all integrations
        
        Returns:
            Disconnection status
        """
        status = {}
        
        for name, integration in self.integrations.items():
            integration.connected = False
            status[name] = True
        
        return status
