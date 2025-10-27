"""
Function Discovery for Atulya Tantra AGI
Dynamic function discovery and registration
"""

import inspect
import importlib
import pkgutil
from typing import Dict, Any, List, Optional, Callable, Type
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from ..config.logging import get_logger
from ..config.exceptions import SystemError, ValidationError

logger = get_logger(__name__)


class FunctionType(Enum):
    """Function type classification"""
    UTILITY = "utility"
    AI_OPERATION = "ai_operation"
    DATA_PROCESSING = "data_processing"
    SYSTEM_OPERATION = "system_operation"
    USER_INTERFACE = "user_interface"
    INTEGRATION = "integration"
    CUSTOM = "custom"


@dataclass
class FunctionMetadata:
    """Function metadata"""
    name: str
    description: str
    function_type: FunctionType
    parameters: List[Dict[str, Any]]
    return_type: str
    module: str
    file_path: str
    line_number: int
    is_async: bool
    is_generator: bool
    tags: List[str]
    version: str
    author: str
    created_at: str
    updated_at: str


@dataclass
class FunctionRegistry:
    """Function registry entry"""
    metadata: FunctionMetadata
    function: Callable
    usage_count: int
    last_used: Optional[str]
    is_enabled: bool


class FunctionDiscovery:
    """Dynamic function discovery and registration"""
    
    def __init__(self):
        self.functions: Dict[str, FunctionRegistry] = {}
        self.modules: Dict[str, Any] = {}
        self.discovery_paths: List[str] = []
        
        # Function type patterns
        self.type_patterns = {
            FunctionType.UTILITY: ["util", "helper", "common", "tool"],
            FunctionType.AI_OPERATION: ["ai", "llm", "model", "generate", "analyze"],
            FunctionType.DATA_PROCESSING: ["data", "process", "transform", "parse"],
            FunctionType.SYSTEM_OPERATION: ["system", "monitor", "health", "status"],
            FunctionType.USER_INTERFACE: ["ui", "interface", "display", "render"],
            FunctionType.INTEGRATION: ["api", "external", "service", "client"]
        }
        
        # Initialize discovery paths
        self._initialize_discovery_paths()
        
        logger.info("Initialized Function Discovery")
    
    def _initialize_discovery_paths(self):
        """Initialize function discovery paths"""
        try:
            # Add core modules
            self.discovery_paths.extend([
                "Core.actions",
                "Core.tools",
                "Core.agents",
                "Core.brain",
                "Core.memory",
                "Core.monitoring",
                "Core.skynet",
                "Core.jarvis"
            ])
            
            logger.info("Initialized discovery paths")
            
        except Exception as e:
            logger.error(f"Error initializing discovery paths: {e}")
    
    def add_discovery_path(self, path: str) -> bool:
        """Add a discovery path"""
        try:
            if path not in self.discovery_paths:
                self.discovery_paths.append(path)
                logger.info(f"Added discovery path: {path}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error adding discovery path: {e}")
            return False
    
    def remove_discovery_path(self, path: str) -> bool:
        """Remove a discovery path"""
        try:
            if path in self.discovery_paths:
                self.discovery_paths.remove(path)
                logger.info(f"Removed discovery path: {path}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error removing discovery path: {e}")
            return False
    
    async def discover_functions(self, path: str = None) -> List[str]:
        """Discover functions in a path"""
        try:
            discovered_functions = []
            
            if path:
                paths_to_scan = [path]
            else:
                paths_to_scan = self.discovery_paths
            
            for scan_path in paths_to_scan:
                try:
                    # Import the module
                    module = importlib.import_module(scan_path)
                    self.modules[scan_path] = module
                    
                    # Discover functions in the module
                    module_functions = self._discover_module_functions(module, scan_path)
                    discovered_functions.extend(module_functions)
                    
                except ImportError as e:
                    logger.warning(f"Could not import module {scan_path}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error discovering functions in {scan_path}: {e}")
                    continue
            
            logger.info(f"Discovered {len(discovered_functions)} functions")
            return discovered_functions
            
        except Exception as e:
            logger.error(f"Error discovering functions: {e}")
            return []
    
    def _discover_module_functions(
        self,
        module: Any,
        module_path: str
    ) -> List[str]:
        """Discover functions in a module"""
        try:
            discovered_functions = []
            
            # Get all members of the module
            for name, obj in inspect.getmembers(module):
                # Check if it's a function
                if inspect.isfunction(obj):
                    function_name = f"{module_path}.{name}"
                    if self._register_function(obj, function_name, module_path):
                        discovered_functions.append(function_name)
                
                # Check if it's a class with methods
                elif inspect.isclass(obj):
                    class_functions = self._discover_class_functions(obj, module_path)
                    discovered_functions.extend(class_functions)
            
            return discovered_functions
            
        except Exception as e:
            logger.error(f"Error discovering module functions: {e}")
            return []
    
    def _discover_class_functions(
        self,
        cls: Type,
        module_path: str
    ) -> List[str]:
        """Discover functions in a class"""
        try:
            discovered_functions = []
            
            for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
                # Skip private methods and special methods
                if name.startswith('_') and name not in ['__init__', '__call__']:
                    continue
                
                function_name = f"{module_path}.{cls.__name__}.{name}"
                if self._register_function(method, function_name, module_path, cls.__name__):
                    discovered_functions.append(function_name)
            
            return discovered_functions
            
        except Exception as e:
            logger.error(f"Error discovering class functions: {e}")
            return []
    
    def _register_function(
        self,
        func: Callable,
        function_name: str,
        module_path: str,
        class_name: str = None
    ) -> bool:
        """Register a function"""
        try:
            # Skip if already registered
            if function_name in self.functions:
                return False
            
            # Extract function metadata
            metadata = self._extract_function_metadata(
                func, function_name, module_path, class_name
            )
            
            # Create registry entry
            registry_entry = FunctionRegistry(
                metadata=metadata,
                function=func,
                usage_count=0,
                last_used=None,
                is_enabled=True
            )
            
            self.functions[function_name] = registry_entry
            
            logger.debug(f"Registered function: {function_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error registering function {function_name}: {e}")
            return False
    
    def _extract_function_metadata(
        self,
        func: Callable,
        function_name: str,
        module_path: str,
        class_name: str = None
    ) -> FunctionMetadata:
        """Extract metadata from a function"""
        try:
            # Get function signature
            signature = inspect.signature(func)
            
            # Extract parameters
            parameters = []
            for param_name, param in signature.parameters.items():
                param_info = {
                    "name": param_name,
                    "type": str(param.annotation) if param.annotation != inspect.Parameter.empty else "Any",
                    "default": param.default if param.default != inspect.Parameter.empty else None,
                    "required": param.default == inspect.Parameter.empty
                }
                parameters.append(param_info)
            
            # Determine function type
            function_type = self._classify_function_type(function_name, func)
            
            # Extract docstring
            docstring = inspect.getdoc(func) or ""
            description = docstring.split('\n')[0] if docstring else f"Function {function_name}"
            
            # Extract tags from docstring
            tags = self._extract_tags(docstring)
            
            # Get file information
            file_path = inspect.getfile(func)
            line_number = inspect.getsourcelines(func)[1]
            
            return FunctionMetadata(
                name=function_name,
                description=description,
                function_type=function_type,
                parameters=parameters,
                return_type=str(signature.return_annotation) if signature.return_annotation != inspect.Parameter.empty else "Any",
                module=module_path,
                file_path=file_path,
                line_number=line_number,
                is_async=inspect.iscoroutinefunction(func),
                is_generator=inspect.isgeneratorfunction(func),
                tags=tags,
                version="1.0.0",
                author="system",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"Error extracting function metadata: {e}")
            # Return minimal metadata
            return FunctionMetadata(
                name=function_name,
                description=f"Function {function_name}",
                function_type=FunctionType.CUSTOM,
                parameters=[],
                return_type="Any",
                module=module_path,
                file_path="",
                line_number=0,
                is_async=False,
                is_generator=False,
                tags=[],
                version="1.0.0",
                author="system",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
    
    def _classify_function_type(
        self,
        function_name: str,
        func: Callable
    ) -> FunctionType:
        """Classify function type based on name and context"""
        try:
            name_lower = function_name.lower()
            
            # Check against type patterns
            for func_type, patterns in self.type_patterns.items():
                for pattern in patterns:
                    if pattern in name_lower:
                        return func_type
            
            # Check docstring for type hints
            docstring = inspect.getdoc(func) or ""
            docstring_lower = docstring.lower()
            
            for func_type, patterns in self.type_patterns.items():
                for pattern in patterns:
                    if pattern in docstring_lower:
                        return func_type
            
            return FunctionType.CUSTOM
            
        except Exception as e:
            logger.error(f"Error classifying function type: {e}")
            return FunctionType.CUSTOM
    
    def _extract_tags(self, docstring: str) -> List[str]:
        """Extract tags from docstring"""
        try:
            tags = []
            
            if not docstring:
                return tags
            
            # Look for @tags in docstring
            for line in docstring.split('\n'):
                line = line.strip()
                if line.startswith('@'):
                    tag = line[1:].strip()
                    if tag:
                        tags.append(tag)
            
            return tags
            
        except Exception as e:
            logger.error(f"Error extracting tags: {e}")
            return []
    
    def get_function(self, function_name: str) -> Optional[FunctionRegistry]:
        """Get a function by name"""
        return self.functions.get(function_name)
    
    def get_functions_by_type(self, function_type: FunctionType) -> List[FunctionRegistry]:
        """Get functions by type"""
        return [
            registry for registry in self.functions.values()
            if registry.metadata.function_type == function_type
        ]
    
    def get_functions_by_tag(self, tag: str) -> List[FunctionRegistry]:
        """Get functions by tag"""
        return [
            registry for registry in self.functions.values()
            if tag in registry.metadata.tags
        ]
    
    def search_functions(self, query: str) -> List[FunctionRegistry]:
        """Search functions by query"""
        try:
            query_lower = query.lower()
            results = []
            
            for registry in self.functions.values():
                metadata = registry.metadata
                
                # Search in name, description, and tags
                if (query_lower in metadata.name.lower() or
                    query_lower in metadata.description.lower() or
                    any(query_lower in tag.lower() for tag in metadata.tags)):
                    results.append(registry)
            
            # Sort by relevance (name matches first)
            results.sort(key=lambda x: (
                query_lower not in x.metadata.name.lower(),
                query_lower not in x.metadata.description.lower()
            ))
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching functions: {e}")
            return []
    
    async def execute_function(
        self,
        function_name: str,
        parameters: Dict[str, Any] = None
    ) -> Any:
        """Execute a function"""
        try:
            if function_name not in self.functions:
                raise ValidationError(f"Function not found: {function_name}")
            
            registry = self.functions[function_name]
            
            if not registry.is_enabled:
                raise SystemError(f"Function is disabled: {function_name}")
            
            # Update usage stats
            registry.usage_count += 1
            registry.last_used = datetime.now().isoformat()
            
            # Execute function
            func = registry.function
            if registry.metadata.is_async:
                result = await func(**(parameters or {}))
            else:
                result = func(**(parameters or {}))
            
            logger.info(f"Executed function: {function_name}")
            return result
            
        except Exception as e:
            logger.error(f"Error executing function {function_name}: {e}")
            raise
    
    def enable_function(self, function_name: str) -> bool:
        """Enable a function"""
        try:
            if function_name in self.functions:
                self.functions[function_name].is_enabled = True
                logger.info(f"Enabled function: {function_name}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error enabling function: {e}")
            return False
    
    def disable_function(self, function_name: str) -> bool:
        """Disable a function"""
        try:
            if function_name in self.functions:
                self.functions[function_name].is_enabled = False
                logger.info(f"Disabled function: {function_name}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error disabling function: {e}")
            return False
    
    def get_function_stats(self) -> Dict[str, Any]:
        """Get function statistics"""
        try:
            total_functions = len(self.functions)
            enabled_functions = len([f for f in self.functions.values() if f.is_enabled])
            disabled_functions = total_functions - enabled_functions
            
            # Count by type
            type_counts = {}
            for registry in self.functions.values():
                func_type = registry.metadata.function_type.value
                type_counts[func_type] = type_counts.get(func_type, 0) + 1
            
            # Most used functions
            most_used = sorted(
                self.functions.values(),
                key=lambda x: x.usage_count,
                reverse=True
            )[:10]
            
            return {
                "total_functions": total_functions,
                "enabled_functions": enabled_functions,
                "disabled_functions": disabled_functions,
                "type_counts": type_counts,
                "most_used": [
                    {
                        "name": registry.metadata.name,
                        "usage_count": registry.usage_count,
                        "last_used": registry.last_used
                    }
                    for registry in most_used
                ],
                "discovery_paths": len(self.discovery_paths),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting function stats: {e}")
            return {}
    
    def get_all_functions(self) -> List[FunctionRegistry]:
        """Get all functions"""
        return list(self.functions.values())
    
    def remove_function(self, function_name: str) -> bool:
        """Remove a function"""
        try:
            if function_name in self.functions:
                del self.functions[function_name]
                logger.info(f"Removed function: {function_name}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error removing function: {e}")
            return False


# Global function discovery instance
_function_discovery = None


def get_function_discovery() -> FunctionDiscovery:
    """Get global function discovery instance"""
    global _function_discovery
    if _function_discovery is None:
        _function_discovery = FunctionDiscovery()
    return _function_discovery


# Export public API
__all__ = [
    "FunctionType",
    "FunctionMetadata",
    "FunctionRegistry",
    "FunctionDiscovery",
    "get_function_discovery"
]