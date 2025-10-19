#!/usr/bin/env python3
"""
Atulya Tantra - Cross-Platform Auto-Installation Script
Version: 2.0.1
This script automatically detects the system and installs Atulya Tantra from zero
"""

import os
import sys
import platform
import subprocess
import shutil
import json
import urllib.request
import zipfile
import tarfile
from pathlib import Path
from typing import Dict, List, Optional

class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    PURPLE = '\033[0;35m'
    NC = '\033[0m'  # No Color

class Logger:
    """Logging utility with colored output"""
    
    @staticmethod
    def log(message: str):
        print(f"{Colors.GREEN}[{Logger._timestamp()}] {message}{Colors.NC}")
    
    @staticmethod
    def error(message: str):
        print(f"{Colors.RED}[ERROR] {message}{Colors.NC}", file=sys.stderr)
    
    @staticmethod
    def warning(message: str):
        print(f"{Colors.YELLOW}[WARNING] {message}{Colors.NC}")
    
    @staticmethod
    def info(message: str):
        print(f"{Colors.BLUE}[INFO] {message}{Colors.NC}")
    
    @staticmethod
    def _timestamp():
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

class SystemDetector:
    """Detects system information and requirements"""
    
    def __init__(self):
        self.system = platform.system().lower()
        self.arch = platform.machine().lower()
        self.python_version = sys.version_info
        self.is_admin = self._check_admin()
    
    def _check_admin(self) -> bool:
        """Check if running with administrator privileges"""
        try:
            if self.system == "windows":
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin()
            else:
                return os.geteuid() == 0
        except:
            return False
    
    def get_system_info(self) -> Dict[str, str]:
        """Get comprehensive system information"""
        return {
            "os": self.system,
            "architecture": self.arch,
            "python_version": f"{self.python_version.major}.{self.python_version.minor}.{self.python_version.micro}",
            "is_admin": self.is_admin,
            "platform": platform.platform(),
            "processor": platform.processor()
        }
    
    def check_requirements(self) -> bool:
        """Check if system meets minimum requirements"""
        Logger.info("Checking system requirements...")
        
        # Check Python version
        if self.python_version < (3, 8):
            Logger.error(f"Python 3.8+ required, found {self.python_version.major}.{self.python_version.minor}")
            return False
        
        Logger.info(f"Python {self.python_version.major}.{self.python_version.minor} ✓")
        
        # Check if running as admin (warning only)
        if not self.is_admin:
            Logger.warning("Not running with administrator privileges. Some features may not work.")
        
        return True

class PackageManager:
    """Handles package installation across different systems"""
    
    def __init__(self, system: str):
        self.system = system
        self.package_managers = self._detect_package_managers()
    
    def _detect_package_managers(self) -> List[str]:
        """Detect available package managers"""
        managers = []
        
        if self.system == "linux":
            if shutil.which("apt-get"):
                managers.append("apt")
            if shutil.which("yum"):
                managers.append("yum")
            if shutil.which("dnf"):
                managers.append("dnf")
            if shutil.which("pacman"):
                managers.append("pacman")
            if shutil.which("zypper"):
                managers.append("zypper")
        elif self.system == "darwin":
            if shutil.which("brew"):
                managers.append("brew")
        elif self.system == "windows":
            if shutil.which("choco"):
                managers.append("choco")
            if shutil.which("winget"):
                managers.append("winget")
        
        return managers
    
    def install_system_packages(self, packages: List[str]) -> bool:
        """Install system packages using available package manager"""
        if not self.package_managers:
            Logger.warning("No package manager found, skipping system package installation")
            return True
        
        manager = self.package_managers[0]  # Use first available manager
        
        try:
            if manager == "apt":
                subprocess.run(["sudo", "apt-get", "update"], check=True)
                subprocess.run(["sudo", "apt-get", "install", "-y"] + packages, check=True)
            elif manager == "yum":
                subprocess.run(["sudo", "yum", "install", "-y"] + packages, check=True)
            elif manager == "dnf":
                subprocess.run(["sudo", "dnf", "install", "-y"] + packages, check=True)
            elif manager == "pacman":
                subprocess.run(["sudo", "pacman", "-S", "--noconfirm"] + packages, check=True)
            elif manager == "zypper":
                subprocess.run(["sudo", "zypper", "install", "-y"] + packages, check=True)
            elif manager == "brew":
                subprocess.run(["brew", "install"] + packages, check=True)
            elif manager == "choco":
                subprocess.run(["choco", "install", "-y"] + packages, check=True)
            elif manager == "winget":
                subprocess.run(["winget", "install"] + packages, check=True)
            
            Logger.log(f"System packages installed successfully using {manager}")
            return True
            
        except subprocess.CalledProcessError as e:
            Logger.error(f"Failed to install system packages: {e}")
            return False

class PythonEnvironment:
    """Manages Python virtual environment and dependencies"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.venv_path = project_root / ".venv"
        self.python_exe = self._get_python_exe()
    
    def _get_python_exe(self) -> Path:
        """Get Python executable path"""
        if self.system == "windows":
            return self.venv_path / "Scripts" / "python.exe"
        else:
            return self.venv_path / "bin" / "python"
    
    def create_venv(self) -> bool:
        """Create virtual environment"""
        try:
            Logger.info("Creating virtual environment...")
            subprocess.run([sys.executable, "-m", "venv", str(self.venv_path)], check=True)
            Logger.log("Virtual environment created successfully")
            return True
        except subprocess.CalledProcessError as e:
            Logger.error(f"Failed to create virtual environment: {e}")
            return False
    
    def install_dependencies(self) -> bool:
        """Install Python dependencies"""
        try:
            Logger.info("Installing Python dependencies...")
            
            # Upgrade pip
            subprocess.run([str(self.python_exe), "-m", "pip", "install", "--upgrade", "pip"], check=True)
            
            # Install requirements
            requirements_file = self.project_root / "requirements.txt"
            if requirements_file.exists():
                subprocess.run([str(self.python_exe), "-m", "pip", "install", "-r", str(requirements_file)], check=True)
                Logger.log("Python dependencies installed successfully")
                return True
            else:
                Logger.error("requirements.txt not found!")
                return False
                
        except subprocess.CalledProcessError as e:
            Logger.error(f"Failed to install Python dependencies: {e}")
            return False

class AtulyaInstaller:
    """Main installer class"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.detector = SystemDetector()
        self.package_manager = PackageManager(self.detector.system)
        self.python_env = PythonEnvironment(self.project_root)
    
    def print_banner(self):
        """Print installation banner"""
        banner = f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════╗
║                    Atulya Tantra AGI System                ║
║                    Cross-Platform Installer                ║
║                        Version 2.0.1                       ║
╚══════════════════════════════════════════════════════════════╝{Colors.NC}
"""
        print(banner)
    
    def setup_directories(self) -> bool:
        """Setup required directories"""
        try:
            Logger.info("Setting up data directories...")
            
            directories = [
                "data",
                "data/logs",
                "data/uploads", 
                "data/cache",
                "data/security",
                "data/analytics",
                "data/database",
                "data/models",
                "data/models/audio",
                "data/models/vision",
                "data/models/text"
            ]
            
            for dir_path in directories:
                full_path = self.project_root / dir_path
                full_path.mkdir(parents=True, exist_ok=True)
            
            Logger.log("Data directories created successfully")
            return True
            
        except Exception as e:
            Logger.error(f"Failed to setup directories: {e}")
            return False
    
    def initialize_config(self) -> bool:
        """Initialize configuration files"""
        try:
            Logger.info("Initializing configuration...")
            
            env_file = self.project_root / ".env"
            env_example = self.project_root / ".env.example"
            
            if not env_file.exists():
                if env_example.exists():
                    shutil.copy(env_example, env_file)
                    Logger.warning("Created .env from .env.example. Please edit it with your API keys.")
                else:
                    Logger.error(".env.example not found!")
                    return False
            
            Logger.log("Configuration initialized")
            return True
            
        except Exception as e:
            Logger.error(f"Failed to initialize configuration: {e}")
            return False
    
    def run_tests(self) -> bool:
        """Run system tests"""
        try:
            Logger.info("Running system tests...")
            
            testing_dir = self.project_root / "testing"
            if testing_dir.exists():
                subprocess.run([str(self.python_env.python_exe), "-m", "pytest", str(testing_dir), "-v"], check=True)
                Logger.log("Tests completed successfully")
            else:
                Logger.warning("No tests found, skipping...")
            
            return True
            
        except subprocess.CalledProcessError as e:
            Logger.warning(f"Some tests failed: {e}")
            return True  # Don't fail installation for test failures
    
    def initialize_database(self) -> bool:
        """Initialize database"""
        try:
            Logger.info("Initializing database...")
            
            init_script = self.project_root / "scripts" / "init_admin_db.py"
            if init_script.exists():
                subprocess.run([str(self.python_env.python_exe), str(init_script)], check=True)
                Logger.log("Database initialized successfully")
            else:
                Logger.warning("Database initialization script not found, skipping...")
            
            return True
            
        except subprocess.CalledProcessError as e:
            Logger.warning(f"Database initialization failed: {e}")
            return True  # Don't fail installation for DB init failures
    
    def install(self) -> bool:
        """Main installation process"""
        self.print_banner()
        
        Logger.log("Starting Atulya Tantra installation...")
        
        # System checks
        if not self.detector.check_requirements():
            return False
        
        system_info = self.detector.get_system_info()
        Logger.info(f"Installing on: {system_info['platform']}")
        
        # Install system packages
        system_packages = ["git", "curl", "wget"]
        if self.detector.system == "linux":
            system_packages.extend(["python3", "python3-pip", "build-essential"])
        elif self.detector.system == "darwin":
            system_packages.extend(["python3"])
        elif self.detector.system == "windows":
            system_packages.extend(["python3", "git"])
        
        if not self.package_manager.install_system_packages(system_packages):
            Logger.warning("System package installation failed, continuing...")
        
        # Python environment setup
        if not self.python_env.create_venv():
            return False
        
        if not self.python_env.install_dependencies():
            return False
        
        # Project setup
        if not self.setup_directories():
            return False
        
        if not self.initialize_config():
            return False
        
        if not self.initialize_database():
            return False
        
        if not self.run_tests():
            return False
        
        Logger.log("Installation completed successfully!")
        
        # Success message
        success_banner = f"""
{Colors.GREEN}╔══════════════════════════════════════════════════════════════╗
║                    Installation Complete!                  ║
╚══════════════════════════════════════════════════════════════╝{Colors.NC}
"""
        print(success_banner)
        
        print(f"{Colors.BLUE}Next steps:{Colors.NC}")
        print("1. Edit .env file with your API keys")
        print("2. Start the server:")
        
        if self.detector.system == "windows":
            print("   .venv\\Scripts\\python server.py")
        else:
            print("   source .venv/bin/activate && python server.py")
        
        print("3. Access the web interface: http://localhost:8000")
        print("4. Admin panel: http://localhost:8000/admin")
        
        return True

def main():
    """Main entry point"""
    installer = AtulyaInstaller()
    
    try:
        success = installer.install()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        Logger.warning("Installation cancelled by user")
        sys.exit(1)
    except Exception as e:
        Logger.error(f"Installation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
