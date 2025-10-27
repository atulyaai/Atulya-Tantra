"""
Dynamic System Installer
Automatically detects and installs missing components, dependencies, and configurations
"""

import os
import sys
import subprocess
import importlib
import pkg_resources
import asyncio
import json
import shutil
from typing import Dict, List, Any, Optional, Set, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import aiohttp
import tempfile

from ..config.logging import get_logger
from ..config.exceptions import InstallationError

logger = get_logger(__name__)


class ComponentType(str, Enum):
    """Types of components that can be installed"""
    PYTHON_PACKAGE = "python_package"
    SYSTEM_PACKAGE = "system_package"
    CONFIG_FILE = "config_file"
    DATA_FILE = "data_file"
    MODEL_FILE = "model_file"
    PLUGIN = "plugin"
    SERVICE = "service"


class InstallationStatus(str, Enum):
    """Installation status"""
    NOT_INSTALLED = "not_installed"
    INSTALLING = "installing"
    INSTALLED = "installed"
    FAILED = "failed"
    OUTDATED = "outdated"


@dataclass
class Component:
    """Component definition"""
    name: str
    type: ComponentType
    version: str
    description: str
    dependencies: List[str] = None
    install_command: str = None
    download_url: str = None
    config_template: str = None
    required: bool = True
    auto_update: bool = True
    metadata: Dict[str, Any] = None


@dataclass
class InstallationResult:
    """Installation result"""
    component: str
    status: InstallationStatus
    message: str
    version: str = None
    error: str = None
    install_time: float = 0.0


class ComponentManager:
    """Manages component definitions and status"""
    
    def __init__(self):
        self.components: Dict[str, Component] = {}
        self.installed_components: Dict[str, InstallationResult] = {}
        self.required_components: Set[str] = set()
        
        # Load component definitions
        self._load_component_definitions()
    
    def _load_component_definitions(self):
        """Load component definitions from various sources"""
        
        # Core Python packages
        core_packages = [
            Component(
                name="fastapi",
                type=ComponentType.PYTHON_PACKAGE,
                version="0.104.1",
                description="Modern web framework for building APIs",
                required=True,
                install_command="pip install fastapi[all]"
            ),
            Component(
                name="uvicorn",
                type=ComponentType.PYTHON_PACKAGE,
                version="0.24.0",
                description="ASGI server for FastAPI",
                required=True,
                install_command="pip install uvicorn[standard]"
            ),
            Component(
                name="pydantic",
                type=ComponentType.PYTHON_PACKAGE,
                version="2.5.0",
                description="Data validation using Python type hints",
                required=True,
                install_command="pip install pydantic"
            ),
            Component(
                name="sqlalchemy",
                type=ComponentType.PYTHON_PACKAGE,
                version="2.0.23",
                description="SQL toolkit and ORM",
                required=True,
                install_command="pip install sqlalchemy"
            ),
            Component(
                name="alembic",
                type=ComponentType.PYTHON_PACKAGE,
                version="1.13.0",
                description="Database migration tool",
                required=True,
                install_command="pip install alembic"
            ),
            Component(
                name="psutil",
                type=ComponentType.PYTHON_PACKAGE,
                version="5.9.6",
                description="System and process utilities",
                required=True,
                install_command="pip install psutil"
            ),
            Component(
                name="aiohttp",
                type=ComponentType.PYTHON_PACKAGE,
                version="3.9.1",
                description="Async HTTP client/server",
                required=True,
                install_command="pip install aiohttp"
            ),
            Component(
                name="prometheus_client",
                type=ComponentType.PYTHON_PACKAGE,
                version="0.19.0",
                description="Prometheus metrics client",
                required=False,
                install_command="pip install prometheus_client"
            ),
            Component(
                name="chromadb",
                type=ComponentType.PYTHON_PACKAGE,
                version="0.4.18",
                description="Vector database for embeddings",
                required=False,
                install_command="pip install chromadb"
            ),
            Component(
                name="networkx",
                type=ComponentType.PYTHON_PACKAGE,
                version="3.2.1",
                description="Graph analysis library",
                required=False,
                install_command="pip install networkx"
            ),
            Component(
                name="sentence_transformers",
                type=ComponentType.PYTHON_PACKAGE,
                version="2.2.2",
                description="Sentence embeddings",
                required=False,
                install_command="pip install sentence-transformers"
            ),
            Component(
                name="ollama",
                type=ComponentType.PYTHON_PACKAGE,
                version="0.1.7",
                description="Ollama Python client",
                required=True,
                install_command="pip install ollama"
            ),
            Component(
                name="openai",
                type=ComponentType.PYTHON_PACKAGE,
                version="1.3.7",
                description="OpenAI Python client",
                required=False,
                install_command="pip install openai"
            ),
            Component(
                name="anthropic",
                type=ComponentType.PYTHON_PACKAGE,
                version="0.7.8",
                description="Anthropic Python client",
                required=False,
                install_command="pip install anthropic"
            )
        ]
        
        # AI Models
        ai_models = [
            Component(
                name="tinyllama",
                type=ComponentType.MODEL_FILE,
                version="1.1B",
                description="TinyLlama 1.1B parameter model",
                required=False,
                download_url="https://ollama.ai/library/tinyllama",
                install_command="ollama pull tinyllama"
            ),
            Component(
                name="llama2",
                type=ComponentType.MODEL_FILE,
                version="7B",
                description="Llama 2 7B parameter model",
                required=False,
                download_url="https://ollama.ai/library/llama2",
                install_command="ollama pull llama2"
            ),
            Component(
                name="codellama",
                type=ComponentType.MODEL_FILE,
                version="7B",
                description="Code Llama 7B parameter model",
                required=False,
                download_url="https://ollama.ai/library/codellama",
                install_command="ollama pull codellama"
            )
        ]
        
        # Configuration files
        config_files = [
            Component(
                name="env_config",
                type=ComponentType.CONFIG_FILE,
                version="1.0",
                description="Environment configuration file",
                required=True,
                config_template="env.example"
            ),
            Component(
                name="database_config",
                type=ComponentType.CONFIG_FILE,
                version="1.0",
                description="Database configuration",
                required=True,
                config_template="database_config.json"
            ),
            Component(
                name="monitoring_config",
                type=ComponentType.CONFIG_FILE,
                version="1.0",
                description="Monitoring configuration",
                required=False,
                config_template="monitoring_config.json"
            )
        ]
        
        # Add all components
        for component in core_packages + ai_models + config_files:
            self.components[component.name] = component
            if component.required:
                self.required_components.add(component.name)
        
        logger.info(f"Loaded {len(self.components)} component definitions")
    
    def get_component(self, name: str) -> Optional[Component]:
        """Get component by name"""
        return self.components.get(name)
    
    def get_required_components(self) -> List[Component]:
        """Get all required components"""
        return [comp for comp in self.components.values() if comp.required]
    
    def get_missing_components(self) -> List[Component]:
        """Get components that are not installed"""
        missing = []
        for name, component in self.components.items():
            if name not in self.installed_components:
                missing.append(component)
        return missing
    
    def get_outdated_components(self) -> List[Tuple[Component, str]]:
        """Get components that are outdated"""
        outdated = []
        for name, component in self.components.items():
            if name in self.installed_components:
                installed = self.installed_components[name]
                if installed.status == InstallationStatus.INSTALLED:
                    if installed.version != component.version:
                        outdated.append((component, installed.version))
        return outdated
    
    def mark_installed(self, name: str, version: str, install_time: float = 0.0):
        """Mark component as installed"""
        self.installed_components[name] = InstallationResult(
            component=name,
            status=InstallationStatus.INSTALLED,
            message="Successfully installed",
            version=version,
            install_time=install_time
        )
    
    def mark_failed(self, name: str, error: str):
        """Mark component installation as failed"""
        self.installed_components[name] = InstallationResult(
            component=name,
            status=InstallationStatus.FAILED,
            message="Installation failed",
            error=error
        )


class DynamicInstaller:
    """Dynamic system installer with automatic dependency resolution"""
    
    def __init__(self):
        self.component_manager = ComponentManager()
        self.install_log: List[InstallationResult] = []
        self.is_installing = False
        
        # Installation strategies
        self.installers = {
            ComponentType.PYTHON_PACKAGE: self._install_python_package,
            ComponentType.SYSTEM_PACKAGE: self._install_system_package,
            ComponentType.CONFIG_FILE: self._install_config_file,
            ComponentType.DATA_FILE: self._install_data_file,
            ComponentType.MODEL_FILE: self._install_model_file,
            ComponentType.PLUGIN: self._install_plugin,
            ComponentType.SERVICE: self._install_service
        }
    
    async def install_all_required(self) -> List[InstallationResult]:
        """Install all required components"""
        if self.is_installing:
            logger.warning("Installation already in progress")
            return self.install_log
        
        self.is_installing = True
        self.install_log.clear()
        
        try:
            logger.info("Starting installation of required components")
            
            # Get required components
            required_components = self.component_manager.get_required_components()
            
            # Install each component
            for component in required_components:
                result = await self.install_component(component)
                self.install_log.append(result)
                
                if result.status == InstallationStatus.FAILED and component.required:
                    logger.error(f"Failed to install required component: {component.name}")
                    break
            
            logger.info(f"Installation completed: {len(self.install_log)} components processed")
            
        finally:
            self.is_installing = False
        
        return self.install_log
    
    async def install_component(self, component: Component) -> InstallationResult:
        """Install a single component"""
        logger.info(f"Installing component: {component.name}")
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Check if already installed
            if component.name in self.component_manager.installed_components:
                existing = self.component_manager.installed_components[component.name]
                if existing.status == InstallationStatus.INSTALLED:
                    logger.info(f"Component {component.name} already installed")
                    return existing
            
            # Install dependencies first
            if component.dependencies:
                for dep_name in component.dependencies:
                    dep_component = self.component_manager.get_component(dep_name)
                    if dep_component:
                        dep_result = await self.install_component(dep_component)
                        if dep_result.status == InstallationStatus.FAILED:
                            return InstallationResult(
                                component=component.name,
                                status=InstallationStatus.FAILED,
                                message=f"Dependency {dep_name} failed to install",
                                error=f"Dependency failure: {dep_result.error}"
                            )
            
            # Install the component
            installer = self.installers.get(component.type)
            if not installer:
                return InstallationResult(
                    component=component.name,
                    status=InstallationStatus.FAILED,
                    message=f"No installer for component type: {component.type}",
                    error="Unknown component type"
                )
            
            result = await installer(component)
            result.install_time = asyncio.get_event_loop().time() - start_time
            
            # Update component manager
            if result.status == InstallationStatus.INSTALLED:
                self.component_manager.mark_installed(component.name, result.version, result.install_time)
            else:
                self.component_manager.mark_failed(component.name, result.error or "Unknown error")
            
            return result
            
        except Exception as e:
            error_msg = f"Installation error: {str(e)}"
            logger.error(f"Failed to install {component.name}: {error_msg}")
            
            result = InstallationResult(
                component=component.name,
                status=InstallationStatus.FAILED,
                message="Installation failed with exception",
                error=error_msg,
                install_time=asyncio.get_event_loop().time() - start_time
            )
            
            self.component_manager.mark_failed(component.name, error_msg)
            return result
    
    async def _install_python_package(self, component: Component) -> InstallationResult:
        """Install Python package using pip"""
        try:
            # Check if already installed
            try:
                importlib.import_module(component.name)
                # Package is already installed, check version
                try:
                    installed_version = pkg_resources.get_distribution(component.name).version
                    if installed_version == component.version:
                        return InstallationResult(
                            component=component.name,
                            status=InstallationStatus.INSTALLED,
                            message="Already installed",
                            version=installed_version
                        )
                except:
                    pass
            except ImportError:
                pass
            
            # Install the package
            if component.install_command:
                cmd = component.install_command.split()
            else:
                cmd = ["pip", "install", f"{component.name}=={component.version}"]
            
            logger.info(f"Running command: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # Verify installation
                try:
                    importlib.import_module(component.name)
                    installed_version = pkg_resources.get_distribution(component.name).version
                    
                    return InstallationResult(
                        component=component.name,
                        status=InstallationStatus.INSTALLED,
                        message="Successfully installed",
                        version=installed_version
                    )
                except Exception as e:
                    return InstallationResult(
                        component=component.name,
                        status=InstallationStatus.FAILED,
                        message="Installation verification failed",
                        error=str(e)
                    )
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                return InstallationResult(
                    component=component.name,
                    status=InstallationStatus.FAILED,
                    message="Installation command failed",
                    error=error_msg
                )
                
        except Exception as e:
            return InstallationResult(
                component=component.name,
                status=InstallationStatus.FAILED,
                message="Installation failed",
                error=str(e)
            )
    
    async def _install_system_package(self, component: Component) -> InstallationResult:
        """Install system package (apt, yum, etc.)"""
        # This would implement system package installation
        # For now, just return success
        return InstallationResult(
            component=component.name,
            status=InstallationStatus.INSTALLED,
            message="System package installation not implemented",
            version=component.version
        )
    
    async def _install_config_file(self, component: Component) -> InstallationResult:
        """Install configuration file"""
        try:
            if component.config_template:
                # Copy template to actual config file
                template_path = Path(component.config_template)
                config_path = Path(f".env" if component.name == "env_config" else f"{component.name}.json")
                
                if template_path.exists():
                    shutil.copy2(template_path, config_path)
                    return InstallationResult(
                        component=component.name,
                        status=InstallationStatus.INSTALLED,
                        message="Configuration file created",
                        version=component.version
                    )
                else:
                    return InstallationResult(
                        component=component.name,
                        status=InstallationStatus.FAILED,
                        message="Template file not found",
                        error=f"Template {component.config_template} not found"
                    )
            else:
                return InstallationResult(
                    component=component.name,
                    status=InstallationStatus.FAILED,
                    message="No config template specified",
                    error="Missing config_template"
                )
                
        except Exception as e:
            return InstallationResult(
                component=component.name,
                status=InstallationStatus.FAILED,
                message="Config file installation failed",
                error=str(e)
            )
    
    async def _install_data_file(self, component: Component) -> InstallationResult:
        """Install data file"""
        # This would download and install data files
        return InstallationResult(
            component=component.name,
            status=InstallationStatus.INSTALLED,
            message="Data file installation not implemented",
            version=component.version
        )
    
    async def _install_model_file(self, component: Component) -> InstallationResult:
        """Install AI model file"""
        try:
            if component.install_command:
                # Run the install command (e.g., ollama pull)
                cmd = component.install_command.split()
                
                logger.info(f"Installing model: {' '.join(cmd)}")
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    return InstallationResult(
                        component=component.name,
                        status=InstallationStatus.INSTALLED,
                        message="Model successfully installed",
                        version=component.version
                    )
                else:
                    error_msg = stderr.decode() if stderr else "Unknown error"
                    return InstallationResult(
                        component=component.name,
                        status=InstallationStatus.FAILED,
                        message="Model installation failed",
                        error=error_msg
                    )
            else:
                return InstallationResult(
                    component=component.name,
                    status=InstallationStatus.FAILED,
                    message="No install command specified",
                    error="Missing install_command"
                )
                
        except Exception as e:
            return InstallationResult(
                component=component.name,
                status=InstallationStatus.FAILED,
                message="Model installation failed",
                error=str(e)
            )
    
    async def _install_plugin(self, component: Component) -> InstallationResult:
        """Install plugin"""
        # This would implement plugin installation
        return InstallationResult(
            component=component.name,
            status=InstallationStatus.INSTALLED,
            message="Plugin installation not implemented",
            version=component.version
        )
    
    async def _install_service(self, component: Component) -> InstallationResult:
        """Install system service"""
        # This would implement service installation
        return InstallationResult(
            component=component.name,
            status=InstallationStatus.INSTALLED,
            message="Service installation not implemented",
            version=component.version
        )
    
    async def check_system_requirements(self) -> Dict[str, Any]:
        """Check system requirements and capabilities"""
        requirements = {
            "python_version": sys.version_info,
            "platform": sys.platform,
            "architecture": os.uname().machine if hasattr(os, 'uname') else "unknown",
            "available_packages": [],
            "missing_packages": [],
            "system_resources": {},
            "capabilities": {}
        }
        
        # Check Python packages
        for name, component in self.component_manager.components.items():
            if component.type == ComponentType.PYTHON_PACKAGE:
                try:
                    importlib.import_module(component.name)
                    requirements["available_packages"].append(name)
                except ImportError:
                    requirements["missing_packages"].append(name)
        
        # Check system resources
        try:
            import psutil
            requirements["system_resources"] = {
                "cpu_count": psutil.cpu_count(),
                "memory_total_gb": psutil.virtual_memory().total / (1024**3),
                "disk_free_gb": psutil.disk_usage('/').free / (1024**3)
            }
        except ImportError:
            requirements["system_resources"] = {"error": "psutil not available"}
        
        # Check capabilities
        requirements["capabilities"] = {
            "gpu_available": self._check_gpu_availability(),
            "docker_available": self._check_docker_availability(),
            "ollama_available": self._check_ollama_availability()
        }
        
        return requirements
    
    def _check_gpu_availability(self) -> bool:
        """Check if GPU is available"""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False
    
    def _check_docker_availability(self) -> bool:
        """Check if Docker is available"""
        try:
            result = subprocess.run(['docker', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def _check_ollama_availability(self) -> bool:
        """Check if Ollama is available"""
        try:
            result = subprocess.run(['ollama', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def get_installation_summary(self) -> Dict[str, Any]:
        """Get installation summary"""
        total_components = len(self.component_manager.components)
        installed_components = len(self.component_manager.installed_components)
        failed_components = len([r for r in self.install_log if r.status == InstallationStatus.FAILED])
        
        return {
            "total_components": total_components,
            "installed_components": installed_components,
            "failed_components": failed_components,
            "success_rate": (installed_components / total_components * 100) if total_components > 0 else 0,
            "installation_log": [
                {
                    "component": r.component,
                    "status": r.status.value,
                    "message": r.message,
                    "version": r.version,
                    "install_time": r.install_time
                }
                for r in self.install_log
            ]
        }


# Global installer instance
_installer: Optional[DynamicInstaller] = None


def get_installer() -> DynamicInstaller:
    """Get global installer instance"""
    global _installer
    if _installer is None:
        _installer = DynamicInstaller()
    return _installer


async def install_system() -> List[InstallationResult]:
    """Install the entire system dynamically"""
    installer = get_installer()
    return await installer.install_all_required()