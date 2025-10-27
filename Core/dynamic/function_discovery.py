"""
Function Discovery and Auto-Import System
Automatically discovers, imports, and manages functions and modules
"""

import os
import sys
import importlib
import inspect
import asyncio
import json
from typing import Dict, List, Any, Optional, Callable, Type, Union
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import threading
import time

from ..config.logging import get_logger
from ..config.exceptions import DiscoveryError

logger = get_logger(__name__)


class FunctionType(str, Enum):
    """Types of functions"""
    UTILITY = "utility"
    AI_FUNCTION = "ai_function"
    DATA_PROCESSOR = "data_processor"
    API_ENDPOINT = "api_endpoint"
    VALIDATOR = "validator"
    TRANSFORMER = "transformer"
    ANALYZER = "analyzer"
    GENERATOR = "generator"
    CUSTOM = "custom"


class ModuleType(str, Enum):
    """Types of modules"""
    CORE = "core"
    PLUGIN = "plugin"
    EXTENSION = "extension"
    UTILITY = "utility"
    INTEGRATION = "integration"


@dataclass
class FunctionInfo:
    """Information about a discovered function"""
    name: str
    module: str
    function_type: FunctionType
    signature: inspect.Signature
    docstring: str
    is_async: bool
    is_generator: bool
    parameters: List[str]
    return_annotation: Any
    file_path: str
    line_number: int
    discovered_at: datetime
    metadata: Dict[str, Any] = None


@dataclass
class ModuleInfo:
    """Information about a discovered module"""
    name: str
    module_type: ModuleType
    file_path: str
    functions: List[FunctionInfo]
    classes: List[str]
    imports: List[str]
    discovered_at: datetime
    metadata: Dict[str, Any] = None


class FunctionDiscovery:
    """Discovers and catalogs functions and modules"""
    
    def __init__(self, search_paths: List[str] = None):
        self.search_paths = search_paths or [".", "Core", "Tools", "Plugins"]
        self.discovered_functions: Dict[str, FunctionInfo] = {}
        self.discovered_modules: Dict[str, ModuleInfo] = {}
        self.function_registry: Dict[str, Callable] = {}
        self.module_registry: Dict[str, Any] = {}
        self.is_scanning = False
        self.scan_lock = threading.Lock()
        
        # Function type patterns
        self.function_patterns = {
            FunctionType.UTILITY: ["util", "helper", "common"],
            FunctionType.AI_FUNCTION: ["ai", "llm", "model", "generate", "predict"],
            FunctionType.DATA_PROCESSOR: ["process", "parse", "transform", "convert"],
            FunctionType.API_ENDPOINT: ["endpoint", "route", "api", "handler"],
            FunctionType.VALIDATOR: ["validate", "check", "verify", "is_valid"],
            FunctionType.TRANSFORMER: ["transform", "convert", "map", "translate"],
            FunctionType.ANALYZER: ["analyze", "analyze", "examine", "inspect"],
            FunctionType.GENERATOR: ["generate", "create", "build", "make"]
        }
    
    async def scan_all(self) -> Dict[str, Any]:
        """Scan all search paths for functions and modules"""
        if self.is_scanning:
            logger.warning("Scan already in progress")
            return {"status": "already_scanning"}
        
        with self.scan_lock:
            self.is_scanning = True
        
        try:
            logger.info("Starting function and module discovery scan")
            
            scan_results = {
                "start_time": datetime.utcnow(),
                "functions_discovered": 0,
                "modules_discovered": 0,
                "errors": []
            }
            
            # Scan each search path
            for search_path in self.search_paths:
                try:
                    path_results = await self._scan_path(search_path)
                    scan_results["functions_discovered"] += path_results["functions"]
                    scan_results["modules_discovered"] += path_results["modules"]
                    scan_results["errors"].extend(path_results["errors"])
                except Exception as e:
                    error_msg = f"Error scanning {search_path}: {e}"
                    logger.error(error_msg)
                    scan_results["errors"].append(error_msg)
            
            scan_results["end_time"] = datetime.utcnow()
            scan_results["duration"] = (scan_results["end_time"] - scan_results["start_time"]).total_seconds()
            
            logger.info(f"Discovery scan completed: {scan_results['functions_discovered']} functions, "
                       f"{scan_results['modules_discovered']} modules")
            
            return scan_results
            
        finally:
            self.is_scanning = False
    
    async def _scan_path(self, path: str) -> Dict[str, Any]:
        """Scan a specific path for functions and modules"""
        results = {
            "functions": 0,
            "modules": 0,
            "errors": []
        }
        
        try:
            path_obj = Path(path)
            if not path_obj.exists():
                logger.warning(f"Path does not exist: {path}")
                return results
            
            # Scan Python files
            for py_file in path_obj.rglob("*.py"):
                try:
                    module_info = await self._scan_file(py_file)
                    if module_info:
                        self.discovered_modules[module_info.name] = module_info
                        results["modules"] += 1
                        results["functions"] += len(module_info.functions)
                        
                        # Register functions
                        for func_info in module_info.functions:
                            self.discovered_functions[func_info.name] = func_info
                            
                except Exception as e:
                    error_msg = f"Error scanning file {py_file}: {e}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
            
        except Exception as e:
            error_msg = f"Error scanning path {path}: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
        
        return results
    
    async def _scan_file(self, file_path: Path) -> Optional[ModuleInfo]:
        """Scan a Python file for functions and classes"""
        try:
            # Read the file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse the file
            tree = compile(content, str(file_path), 'exec', dont_inherit=True)
            
            # Extract module name
            module_name = file_path.stem
            if file_path.parent.name != ".":
                module_name = f"{file_path.parent.name}.{module_name}"
            
            # Discover functions and classes
            functions = []
            classes = []
            imports = []
            
            for node in tree.co_consts:
                if inspect.iscode(node):
                    # This is a code object, extract information
                    pass
            
            # Use AST parsing for better analysis
            import ast
            
            try:
                tree_ast = ast.parse(content)
                
                for node in ast.walk(tree_ast):
                    if isinstance(node, ast.FunctionDef):
                        func_info = self._extract_function_info(node, module_name, file_path)
                        if func_info:
                            functions.append(func_info)
                    elif isinstance(node, ast.ClassDef):
                        classes.append(node.name)
                    elif isinstance(node, (ast.Import, ast.ImportFrom)):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                imports.append(alias.name)
                        else:
                            module_name_import = node.module or ""
                            for alias in node.names:
                                imports.append(f"{module_name_import}.{alias.name}")
                
            except SyntaxError as e:
                logger.warning(f"Syntax error in {file_path}: {e}")
                return None
            
            # Determine module type
            module_type = self._determine_module_type(module_name, file_path, functions)
            
            return ModuleInfo(
                name=module_name,
                module_type=module_type,
                file_path=str(file_path),
                functions=functions,
                classes=classes,
                imports=imports,
                discovered_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error scanning file {file_path}: {e}")
            return None
    
    def _extract_function_info(self, node: ast.FunctionDef, module_name: str, file_path: Path) -> Optional[FunctionInfo]:
        """Extract function information from AST node"""
        try:
            # Get function signature
            args = []
            for arg in node.args.args:
                args.append(arg.arg)
            
            # Determine function type
            function_type = self._determine_function_type(node.name, node.docstring)
            
            # Check if async
            is_async = isinstance(node, ast.AsyncFunctionDef)
            
            # Check if generator
            is_generator = False
            for child in ast.walk(node):
                if isinstance(child, ast.Yield):
                    is_generator = True
                    break
            
            return FunctionInfo(
                name=node.name,
                module=module_name,
                function_type=function_type,
                signature=inspect.Signature(),  # Simplified
                docstring=ast.get_docstring(node) or "",
                is_async=is_async,
                is_generator=is_generator,
                parameters=args,
                return_annotation=node.returns.id if node.returns else None,
                file_path=str(file_path),
                line_number=node.lineno,
                discovered_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error extracting function info for {node.name}: {e}")
            return None
    
    def _determine_function_type(self, name: str, docstring: str) -> FunctionType:
        """Determine function type based on name and docstring"""
        name_lower = name.lower()
        doc_lower = (docstring or "").lower()
        
        for func_type, patterns in self.function_patterns.items():
            for pattern in patterns:
                if pattern in name_lower or pattern in doc_lower:
                    return func_type
        
        return FunctionType.CUSTOM
    
    def _determine_module_type(self, name: str, file_path: Path, functions: List[FunctionInfo]) -> ModuleType:
        """Determine module type based on name, path, and functions"""
        name_lower = name.lower()
        path_str = str(file_path).lower()
        
        if "core" in name_lower or "core" in path_str:
            return ModuleType.CORE
        elif "plugin" in name_lower or "plugin" in path_str:
            return ModuleType.PLUGIN
        elif "extension" in name_lower or "extension" in path_str:
            return ModuleType.EXTENSION
        elif "integration" in name_lower or "integration" in path_str:
            return ModuleType.INTEGRATION
        elif any(func.function_type == FunctionType.UTILITY for func in functions):
            return ModuleType.UTILITY
        else:
            return ModuleType.CORE
    
    def get_functions_by_type(self, function_type: FunctionType) -> List[FunctionInfo]:
        """Get all functions of a specific type"""
        return [
            func for func in self.discovered_functions.values()
            if func.function_type == function_type
        ]
    
    def get_functions_by_module(self, module_name: str) -> List[FunctionInfo]:
        """Get all functions from a specific module"""
        return [
            func for func in self.discovered_functions.values()
            if func.module == module_name
        ]
    
    def search_functions(self, query: str) -> List[FunctionInfo]:
        """Search functions by name or docstring"""
        query_lower = query.lower()
        results = []
        
        for func in self.discovered_functions.values():
            if (query_lower in func.name.lower() or 
                query_lower in func.docstring.lower()):
                results.append(func)
        
        return results
    
    def get_function_info(self, name: str) -> Optional[FunctionInfo]:
        """Get information about a specific function"""
        return self.discovered_functions.get(name)
    
    def get_module_info(self, name: str) -> Optional[ModuleInfo]:
        """Get information about a specific module"""
        return self.discovered_modules.get(name)
    
    def list_all_functions(self) -> List[Dict[str, Any]]:
        """List all discovered functions"""
        return [
            {
                "name": func.name,
                "module": func.module,
                "type": func.function_type.value,
                "is_async": func.is_async,
                "is_generator": func.is_generator,
                "parameters": func.parameters,
                "docstring": func.docstring[:100] + "..." if len(func.docstring) > 100 else func.docstring,
                "file_path": func.file_path,
                "line_number": func.line_number
            }
            for func in self.discovered_functions.values()
        ]
    
    def list_all_modules(self) -> List[Dict[str, Any]]:
        """List all discovered modules"""
        return [
            {
                "name": module.name,
                "type": module.module_type.value,
                "file_path": module.file_path,
                "function_count": len(module.functions),
                "class_count": len(module.classes),
                "import_count": len(module.imports)
            }
            for module in self.discovered_modules.values()
        ]
    
    def get_discovery_statistics(self) -> Dict[str, Any]:
        """Get statistics about discovered functions and modules"""
        function_types = {}
        module_types = {}
        
        for func in self.discovered_functions.values():
            func_type = func.function_type.value
            function_types[func_type] = function_types.get(func_type, 0) + 1
        
        for module in self.discovered_modules.values():
            module_type = module.module_type.value
            module_types[module_type] = module_types.get(module_type, 0) + 1
        
        return {
            "total_functions": len(self.discovered_functions),
            "total_modules": len(self.discovered_modules),
            "function_types": function_types,
            "module_types": module_types,
            "async_functions": len([f for f in self.discovered_functions.values() if f.is_async]),
            "generator_functions": len([f for f in self.discovered_functions.values() if f.is_generator])
        }


class AutoImporter:
    """Automatically imports and manages functions and modules"""
    
    def __init__(self, discovery: FunctionDiscovery):
        self.discovery = discovery
        self.imported_functions: Dict[str, Callable] = {}
        self.imported_modules: Dict[str, Any] = {}
        self.import_cache: Dict[str, Any] = {}
    
    async def import_function(self, name: str) -> Optional[Callable]:
        """Import a specific function"""
        if name in self.imported_functions:
            return self.imported_functions[name]
        
        func_info = self.discovery.get_function_info(name)
        if not func_info:
            logger.warning(f"Function not found: {name}")
            return None
        
        try:
            # Import the module
            module = await self.import_module(func_info.module)
            if not module:
                return None
            
            # Get the function
            if hasattr(module, name):
                func = getattr(module, name)
                self.imported_functions[name] = func
                logger.info(f"Imported function: {name}")
                return func
            else:
                logger.warning(f"Function {name} not found in module {func_info.module}")
                return None
                
        except Exception as e:
            logger.error(f"Error importing function {name}: {e}")
            return None
    
    async def import_module(self, name: str) -> Optional[Any]:
        """Import a specific module"""
        if name in self.imported_modules:
            return self.imported_modules[name]
        
        module_info = self.discovery.get_module_info(name)
        if not module_info:
            logger.warning(f"Module not found: {name}")
            return None
        
        try:
            # Import the module
            module = importlib.import_module(name)
            self.imported_modules[name] = module
            logger.info(f"Imported module: {name}")
            return module
            
        except Exception as e:
            logger.error(f"Error importing module {name}: {e}")
            return None
    
    async def import_functions_by_type(self, function_type: FunctionType) -> Dict[str, Callable]:
        """Import all functions of a specific type"""
        functions = self.discovery.get_functions_by_type(function_type)
        imported = {}
        
        for func_info in functions:
            func = await self.import_function(func_info.name)
            if func:
                imported[func_info.name] = func
        
        return imported
    
    async def import_all_utility_functions(self) -> Dict[str, Callable]:
        """Import all utility functions"""
        return await self.import_functions_by_type(FunctionType.UTILITY)
    
    async def import_all_ai_functions(self) -> Dict[str, Callable]:
        """Import all AI functions"""
        return await self.import_functions_by_type(FunctionType.AI_FUNCTION)
    
    async def execute_function(self, name: str, *args, **kwargs) -> Any:
        """Execute a function by name"""
        func = await self.import_function(name)
        if not func:
            raise DiscoveryError(f"Function not found: {name}")
        
        try:
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error executing function {name}: {e}")
            raise DiscoveryError(f"Function execution failed: {e}")
    
    def get_imported_functions(self) -> List[str]:
        """Get list of imported function names"""
        return list(self.imported_functions.keys())
    
    def get_imported_modules(self) -> List[str]:
        """Get list of imported module names"""
        return list(self.imported_modules.keys())
    
    def clear_cache(self):
        """Clear import cache"""
        self.imported_functions.clear()
        self.imported_modules.clear()
        self.import_cache.clear()
        logger.info("Import cache cleared")


# Global instances
_discovery: Optional[FunctionDiscovery] = None
_auto_importer: Optional[AutoImporter] = None


def get_discovery() -> FunctionDiscovery:
    """Get global function discovery instance"""
    global _discovery
    if _discovery is None:
        _discovery = FunctionDiscovery()
    return _discovery


def get_auto_importer() -> AutoImporter:
    """Get global auto importer instance"""
    global _auto_importer
    if _auto_importer is None:
        _auto_importer = AutoImporter(get_discovery())
    return _auto_importer


async def discover_and_import_all() -> Dict[str, Any]:
    """Discover and import all available functions and modules"""
    discovery = get_discovery()
    importer = get_auto_importer()
    
    # Run discovery scan
    scan_results = await discovery.scan_all()
    
    # Import utility functions
    utility_functions = await importer.import_all_utility_functions()
    
    # Import AI functions
    ai_functions = await importer.import_all_ai_functions()
    
    return {
        "discovery": scan_results,
        "imported_utilities": len(utility_functions),
        "imported_ai_functions": len(ai_functions),
        "total_imported": len(importer.get_imported_functions())
    }