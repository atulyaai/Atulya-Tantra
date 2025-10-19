"""
Atulya Tantra - Version Management System
Version: 2.0.1
Handles semantic versioning, release management, and version tracking.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class VersionType(Enum):
    """Version type enumeration"""
    MAJOR = "major"      # Breaking changes
    MINOR = "minor"      # New features, backward compatible
    PATCH = "patch"      # Bug fixes, backward compatible
    HOTFIX = "hotfix"    # Critical fixes
    ALPHA = "alpha"      # Pre-release
    BETA = "beta"        # Pre-release
    RC = "rc"           # Release candidate

@dataclass
class VersionInfo:
    """Version information structure"""
    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None
    build: Optional[str] = None
    codename: Optional[str] = None
    release_date: Optional[datetime] = None
    status: str = "stable"  # stable, beta, alpha, deprecated
    
    def __str__(self) -> str:
        """String representation of version"""
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        if self.build:
            version += f"+{self.build}"
        return version
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "version": str(self),
            "major": self.major,
            "minor": self.minor,
            "patch": self.patch,
            "prerelease": self.prerelease,
            "build": self.build,
            "codename": self.codename,
            "release_date": self.release_date.isoformat() if self.release_date else None,
            "status": self.status
        }

class VersionManager:
    """Manages version information and releases"""
    
    def __init__(self):
        self.current_version = VersionInfo(
            major=2,
            minor=0,
            patch=1,
            codename="Jarvis",
            release_date=datetime(2025, 1, 16),
            status="stable"
        )
        
        self.version_history = {
            "2.0.1": {
                "codename": "Jarvis",
                "release_date": "2025-01-16",
                "status": "stable",
                "changes": [
                    "Complete installation system with auto-detection",
                    "Unified configuration system",
                    "Core AGI modules implementation",
                    "Professional documentation and deployment",
                    "Clean architecture with proper folder structure"
                ],
                "breaking_changes": [],
                "new_features": [
                    "Auto-installation scripts for Linux/Windows",
                    "Unified configuration management",
                    "Memory management system",
                    "Monitoring and metrics collection",
                    "Health checking system"
                ],
                "bug_fixes": [],
                "improvements": [
                    "Restructured project architecture",
                    "Enhanced documentation",
                    "Improved installation process",
                    "Better error handling"
                ]
            },
            "1.0.7": {
                "codename": "Foundation",
                "release_date": "2025-01-15",
                "status": "deprecated",
                "changes": [
                    "Core infrastructure complete",
                    "JARVIS voice system",
                    "Multi-agent orchestration",
                    "Desktop automation",
                    "Hybrid model routing"
                ],
                "breaking_changes": [],
                "new_features": [
                    "Basic AGI system",
                    "Voice interface",
                    "Agent system",
                    "Automation capabilities"
                ],
                "bug_fixes": [],
                "improvements": []
            }
        }
    
    def get_current_version(self) -> VersionInfo:
        """Get current version information"""
        return self.current_version
    
    def get_version_string(self) -> str:
        """Get current version as string"""
        return str(self.current_version)
    
    def get_version_info(self, version: str) -> Optional[Dict]:
        """Get information for a specific version"""
        return self.version_history.get(version)
    
    def get_version_history(self) -> Dict[str, Dict]:
        """Get complete version history"""
        return self.version_history
    
    def increment_version(self, version_type: VersionType, prerelease: Optional[str] = None) -> VersionInfo:
        """Increment version based on type"""
        new_version = VersionInfo(
            major=self.current_version.major,
            minor=self.current_version.minor,
            patch=self.current_version.patch,
            prerelease=prerelease,
            codename=self.current_version.codename,
            release_date=datetime.now(),
            status="beta" if prerelease else "stable"
        )
        
        if version_type == VersionType.MAJOR:
            new_version.major += 1
            new_version.minor = 0
            new_version.patch = 0
        elif version_type == VersionType.MINOR:
            new_version.minor += 1
            new_version.patch = 0
        elif version_type == VersionType.PATCH:
            new_version.patch += 1
        elif version_type == VersionType.HOTFIX:
            new_version.patch += 1
            new_version.prerelease = "hotfix"
        
        return new_version
    
    def create_release_notes(self, version: str) -> str:
        """Create release notes for a version"""
        version_info = self.get_version_info(version)
        if not version_info:
            return f"No information available for version {version}"
        
        notes = f"# Atulya Tantra v{version} - {version_info['codename']}\n\n"
        notes += f"**Release Date:** {version_info['release_date']}\n"
        notes += f"**Status:** {version_info['status']}\n\n"
        
        if version_info['new_features']:
            notes += "## 🚀 New Features\n"
            for feature in version_info['new_features']:
                notes += f"- {feature}\n"
            notes += "\n"
        
        if version_info['improvements']:
            notes += "## 🔧 Improvements\n"
            for improvement in version_info['improvements']:
                notes += f"- {improvement}\n"
            notes += "\n"
        
        if version_info['bug_fixes']:
            notes += "## 🐛 Bug Fixes\n"
            for fix in version_info['bug_fixes']:
                notes += f"- {fix}\n"
            notes += "\n"
        
        if version_info['breaking_changes']:
            notes += "## ⚠️ Breaking Changes\n"
            for change in version_info['breaking_changes']:
                notes += f"- {change}\n"
            notes += "\n"
        
        return notes
    
    def get_changelog(self) -> str:
        """Generate complete changelog"""
        changelog = "# Atulya Tantra - Changelog\n\n"
        changelog += "All notable changes to this project will be documented in this file.\n\n"
        changelog += "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),\n"
        changelog += "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n\n"
        
        # Sort versions by release date (newest first)
        sorted_versions = sorted(
            self.version_history.items(),
            key=lambda x: x[1]['release_date'],
            reverse=True
        )
        
        for version, info in sorted_versions:
            changelog += f"## [{version}] - {info['release_date']}\n"
            
            if info['new_features']:
                changelog += "### Added\n"
                for feature in info['new_features']:
                    changelog += f"- {feature}\n"
                changelog += "\n"
            
            if info['improvements']:
                changelog += "### Changed\n"
                for improvement in info['improvements']:
                    changelog += f"- {improvement}\n"
                changelog += "\n"
            
            if info['bug_fixes']:
                changelog += "### Fixed\n"
                for fix in info['bug_fixes']:
                    changelog += f"- {fix}\n"
                changelog += "\n"
            
            if info['breaking_changes']:
                changelog += "### Breaking Changes\n"
                for change in info['breaking_changes']:
                    changelog += f"- {change}\n"
                changelog += "\n"
            
            changelog += "\n"
        
        return changelog
    
    def get_roadmap(self) -> str:
        """Generate roadmap based on version history and planned features"""
        roadmap = "# Atulya Tantra - Project Roadmap\n\n"
        roadmap += f"## Current Version: v{self.get_version_string()} ({self.current_version.codename})\n"
        roadmap += f"**Release Date:** {self.current_version.release_date.strftime('%Y-%m-%d')}\n"
        roadmap += f"**Status:** {self.current_version.status}\n\n"
        
        roadmap += "## 🎯 Completed Features\n\n"
        roadmap += "### Core Infrastructure ✅\n"
        roadmap += "- Clean architecture with proper folder structure\n"
        roadmap += "- Auto-installation system for Linux/Windows\n"
        roadmap += "- Unified configuration management\n"
        roadmap += "- Professional documentation\n"
        roadmap += "- Docker deployment support\n\n"
        
        roadmap += "### AGI System Components ✅\n"
        roadmap += "- Memory management system (knowledge graphs, vector stores)\n"
        roadmap += "- Monitoring and metrics collection\n"
        roadmap += "- Health checking system\n"
        roadmap += "- Version management system\n\n"
        
        roadmap += "## 🚧 In Development\n\n"
        roadmap += "### Core AGI Modules (Next Release)\n"
        roadmap += "- Voice system (STT, TTS, wake word detection)\n"
        roadmap += "- Multi-agent orchestration system\n"
        roadmap += "- Desktop automation and proactive AI\n"
        roadmap += "- Hybrid model router (Ollama + cloud models)\n"
        roadmap += "- Database management and ORM\n\n"
        
        roadmap += "### WebUI System (Next Release)\n"
        roadmap += "- Modern frontend interface\n"
        roadmap += "- Admin panel with analytics\n"
        roadmap += "- Real-time monitoring dashboard\n"
        roadmap += "- User management system\n\n"
        
        roadmap += "## 🔮 Future Releases\n\n"
        roadmap += "### v2.1.0 - Voice & Agents (Q1 2025)\n"
        roadmap += "- Complete voice interface\n"
        roadmap += "- Multi-agent system\n"
        roadmap += "- Desktop automation\n"
        roadmap += "- Advanced AI routing\n\n"
        
        roadmap += "### v2.2.0 - WebUI & Analytics (Q2 2025)\n"
        roadmap += "- Full web interface\n"
        roadmap += "- Real-time analytics\n"
        roadmap += "- User management\n"
        roadmap += "- Performance optimization\n\n"
        
        roadmap += "### v3.0.0 - Advanced AGI (Q3 2025)\n"
        roadmap += "- Advanced reasoning capabilities\n"
        roadmap += "- Multi-modal AI integration\n"
        roadmap += "- Advanced automation\n"
        roadmap += "- Enterprise features\n\n"
        
        roadmap += "## 📊 Development Status\n\n"
        roadmap += "| Component | Status | Progress |\n"
        roadmap += "|-----------|--------|----------|\n"
        roadmap += "| Core Infrastructure | ✅ Complete | 100% |\n"
        roadmap += "| Installation System | ✅ Complete | 100% |\n"
        roadmap += "| Configuration System | ✅ Complete | 100% |\n"
        roadmap += "| Memory Management | ✅ Complete | 100% |\n"
        roadmap += "| Monitoring System | ✅ Complete | 100% |\n"
        roadmap += "| Voice System | 🚧 In Progress | 30% |\n"
        roadmap += "| Agent System | 🚧 In Progress | 25% |\n"
        roadmap += "| Automation | 🚧 In Progress | 20% |\n"
        roadmap += "| WebUI | 🚧 In Progress | 15% |\n"
        roadmap += "| Testing Suite | 📋 Planned | 0% |\n\n"
        
        return roadmap

# Global version manager instance
_version_manager: Optional[VersionManager] = None

def get_version_manager() -> VersionManager:
    """Get global version manager instance"""
    global _version_manager
    if _version_manager is None:
        _version_manager = VersionManager()
    return _version_manager

def get_current_version() -> str:
    """Get current version string"""
    return get_version_manager().get_version_string()

def get_version_info() -> VersionInfo:
    """Get current version information"""
    return get_version_manager().get_current_version()

def get_changelog() -> str:
    """Get complete changelog"""
    return get_version_manager().get_changelog()

def get_roadmap() -> str:
    """Get project roadmap"""
    return get_version_manager().get_roadmap()

def get_release_notes(version: str) -> str:
    """Get release notes for specific version"""
    return get_version_manager().create_release_notes(version)

# Export main functions
__all__ = [
    "VersionType",
    "VersionInfo",
    "VersionManager",
    "get_version_manager",
    "get_current_version",
    "get_version_info",
    "get_changelog",
    "get_roadmap",
    "get_release_notes"
]
