"""
Atulya Tantra - Skynet Desktop Automation
Version: 2.5.0
Desktop automation for file operations, window management, and user interface control
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import os
import shutil
import json
import asyncio
from pathlib import Path
import platform

logger = logging.getLogger(__name__)

# Import automation libraries conditionally
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    logger.warning("PyAutoGUI not available - desktop automation disabled")

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logger.warning("Watchdog not available - file monitoring disabled")


@dataclass
class FileOperation:
    """File operation result"""
    operation_type: str
    source_path: str
    target_path: Optional[str]
    success: bool
    error_message: Optional[str]
    timestamp: datetime
    metadata: Dict[str, Any]


@dataclass
class WindowInfo:
    """Window information"""
    title: str
    process_name: str
    pid: int
    geometry: Tuple[int, int, int, int]  # x, y, width, height
    is_active: bool
    is_visible: bool


class FileSystemEventHandler(FileSystemEventHandler):
    """Custom file system event handler"""
    
    def __init__(self, automation_controller):
        self.automation_controller = automation_controller
    
    def on_created(self, event):
        if not event.is_directory:
            self.automation_controller._handle_file_event("created", event.src_path)
    
    def on_modified(self, event):
        if not event.is_directory:
            self.automation_controller._handle_file_event("modified", event.src_path)
    
    def on_deleted(self, event):
        if not event.is_directory:
            self.automation_controller._handle_file_event("deleted", event.src_path)


class DesktopAutomation:
    """Desktop automation controller"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.automation_enabled = config.get("automation_enabled", False)
        self.safety_mode = config.get("safety_mode", True)
        self.allowed_directories = config.get("allowed_directories", [])
        self.blocked_extensions = config.get("blocked_extensions", [".exe", ".bat", ".cmd", ".sh"])
        self.file_monitor = None
        self.file_events = []
        
        # Configure PyAutoGUI if available
        if PYAUTOGUI_AVAILABLE:
            pyautogui.FAILSAFE = True  # Move mouse to corner to stop
            pyautogui.PAUSE = 0.1  # Small pause between actions
        
        logger.info(f"DesktopAutomation initialized (PyAutoGUI: {PYAUTOGUI_AVAILABLE}, Watchdog: {WATCHDOG_AVAILABLE})")
    
    async def file_operation(
        self,
        operation: str,
        source_path: str,
        target_path: Optional[str] = None,
        options: Dict[str, Any] = None
    ) -> FileOperation:
        """Perform file operation with safety checks"""
        
        if not self.automation_enabled:
            return FileOperation(
                operation_type=operation,
                source_path=source_path,
                target_path=target_path,
                success=False,
                error_message="Automation is disabled",
                timestamp=datetime.now(),
                metadata={}
            )
        
        options = options or {}
        
        try:
            # Safety checks
            if not self._is_path_allowed(source_path):
                return FileOperation(
                    operation_type=operation,
                    source_path=source_path,
                    target_path=target_path,
                    success=False,
                    error_message=f"Path '{source_path}' is not allowed",
                    timestamp=datetime.now(),
                    metadata={}
                )
            
            if target_path and not self._is_path_allowed(target_path):
                return FileOperation(
                    operation_type=operation,
                    source_path=source_path,
                    target_path=target_path,
                    success=False,
                    error_message=f"Target path '{target_path}' is not allowed",
                    timestamp=datetime.now(),
                    metadata={}
                )
            
            # Perform operation
            result = await self._perform_file_operation(operation, source_path, target_path, options)
            return result
            
        except Exception as e:
            logger.error(f"File operation error: {e}")
            return FileOperation(
                operation_type=operation,
                source_path=source_path,
                target_path=target_path,
                success=False,
                error_message=str(e),
                timestamp=datetime.now(),
                metadata={}
            )
    
    async def batch_file_operations(
        self,
        operations: List[Dict[str, Any]]
    ) -> List[FileOperation]:
        """Perform multiple file operations"""
        
        results = []
        
        for operation in operations:
            result = await self.file_operation(
                operation.get("operation"),
                operation.get("source_path"),
                operation.get("target_path"),
                operation.get("options", {})
            )
            results.append(result)
            
            # Stop on first failure if safety mode is enabled
            if self.safety_mode and not result.success:
                break
        
        return results
    
    async def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get detailed file information"""
        
        try:
            path = Path(file_path)
            
            if not path.exists():
                return {"error": "File does not exist"}
            
            stat = path.stat()
            
            return {
                "path": str(path),
                "name": path.name,
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "accessed": datetime.fromtimestamp(stat.st_atime).isoformat(),
                "is_file": path.is_file(),
                "is_directory": path.is_dir(),
                "extension": path.suffix,
                "parent": str(path.parent),
                "permissions": oct(stat.st_mode)[-3:],
                "absolute_path": str(path.absolute())
            }
            
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
            return {"error": str(e)}
    
    async def search_files(
        self,
        directory: str,
        pattern: str,
        recursive: bool = True,
        file_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Search for files matching pattern"""
        
        if not self._is_path_allowed(directory):
            return [{"error": f"Directory '{directory}' is not allowed"}]
        
        try:
            results = []
            search_path = Path(directory)
            
            if not search_path.exists():
                return [{"error": "Directory does not exist"}]
            
            # Search pattern
            if recursive:
                matching_files = search_path.rglob(pattern)
            else:
                matching_files = search_path.glob(pattern)
            
            for file_path in matching_files:
                # Filter by file types if specified
                if file_types and file_path.suffix not in file_types:
                    continue
                
                # Get file info
                file_info = await self.get_file_info(str(file_path))
                if "error" not in file_info:
                    results.append(file_info)
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching files: {e}")
            return [{"error": str(e)}]
    
    async def start_file_monitoring(
        self,
        directory: str,
        recursive: bool = True
    ) -> Dict[str, Any]:
        """Start monitoring directory for file changes"""
        
        if not WATCHDOG_AVAILABLE:
            return {"error": "Watchdog not available"}
        
        if not self._is_path_allowed(directory):
            return {"error": f"Directory '{directory}' is not allowed"}
        
        try:
            if self.file_monitor:
                return {"error": "File monitoring already active"}
            
            # Create observer
            observer = Observer()
            event_handler = FileSystemEventHandler(self)
            
            # Start watching
            observer.schedule(event_handler, directory, recursive=recursive)
            observer.start()
            
            self.file_monitor = observer
            
            return {
                "success": True,
                "directory": directory,
                "recursive": recursive,
                "status": "monitoring"
            }
            
        except Exception as e:
            logger.error(f"Error starting file monitoring: {e}")
            return {"error": str(e)}
    
    async def stop_file_monitoring(self) -> Dict[str, Any]:
        """Stop file monitoring"""
        
        try:
            if self.file_monitor:
                self.file_monitor.stop()
                self.file_monitor.join()
                self.file_monitor = None
                
                return {"success": True, "status": "stopped"}
            else:
                return {"error": "No active monitoring"}
                
        except Exception as e:
            logger.error(f"Error stopping file monitoring: {e}")
            return {"error": str(e)}
    
    async def get_file_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent file events"""
        
        return self.file_events[-limit:]
    
    async def take_screenshot(
        self,
        region: Optional[Tuple[int, int, int, int]] = None,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Take screenshot of screen or region"""
        
        if not PYAUTOGUI_AVAILABLE:
            return {"error": "PyAutoGUI not available"}
        
        try:
            # Take screenshot
            if region:
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()
            
            # Save if filename provided
            if filename:
                screenshot.save(filename)
                return {
                    "success": True,
                    "filename": filename,
                    "region": region,
                    "size": screenshot.size
                }
            else:
                # Return base64 encoded image
                import io
                import base64
                
                buffer = io.BytesIO()
                screenshot.save(buffer, format='PNG')
                image_data = base64.b64encode(buffer.getvalue()).decode()
                
                return {
                    "success": True,
                    "image_data": image_data,
                    "region": region,
                    "size": screenshot.size
                }
                
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            return {"error": str(e)}
    
    async def get_window_info(self) -> List[WindowInfo]:
        """Get information about open windows"""
        
        if not PYAUTOGUI_AVAILABLE:
            return []
        
        try:
            # This is a simplified implementation
            # In production, you'd use platform-specific APIs
            windows = []
            
            # Get screen size
            screen_width, screen_height = pyautogui.size()
            
            # This is a placeholder - real implementation would enumerate actual windows
            # For now, return basic screen info
            windows.append(WindowInfo(
                title="Screen",
                process_name="system",
                pid=0,
                geometry=(0, 0, screen_width, screen_height),
                is_active=True,
                is_visible=True
            ))
            
            return windows
            
        except Exception as e:
            logger.error(f"Error getting window info: {e}")
            return []
    
    async def _perform_file_operation(
        self,
        operation: str,
        source_path: str,
        target_path: Optional[str],
        options: Dict[str, Any]
    ) -> FileOperation:
        """Perform the actual file operation"""
        
        source = Path(source_path)
        target = Path(target_path) if target_path else None
        
        # Create backup if requested
        if options.get("backup", False) and source.exists():
            backup_path = source.with_suffix(source.suffix + ".backup")
            shutil.copy2(source, backup_path)
        
        if operation == "copy":
            if not target:
                return FileOperation(
                    operation_type=operation,
                    source_path=source_path,
                    target_path=target_path,
                    success=False,
                    error_message="Target path required for copy operation",
                    timestamp=datetime.now(),
                    metadata={}
                )
            
            if source.is_file():
                shutil.copy2(source, target)
            else:
                shutil.copytree(source, target)
            
            return FileOperation(
                operation_type=operation,
                source_path=source_path,
                target_path=target_path,
                success=True,
                error_message=None,
                timestamp=datetime.now(),
                metadata={"size": target.stat().st_size if target.exists() else 0}
            )
        
        elif operation == "move":
            if not target:
                return FileOperation(
                    operation_type=operation,
                    source_path=source_path,
                    target_path=target_path,
                    success=False,
                    error_message="Target path required for move operation",
                    timestamp=datetime.now(),
                    metadata={}
                )
            
            shutil.move(source, target)
            
            return FileOperation(
                operation_type=operation,
                source_path=source_path,
                target_path=target_path,
                success=True,
                error_message=None,
                timestamp=datetime.now(),
                metadata={}
            )
        
        elif operation == "delete":
            if self.safety_mode and not options.get("force", False):
                # Move to trash instead of permanent delete
                trash_path = Path.home() / ".local" / "share" / "Trash" / "files"
                trash_path.mkdir(parents=True, exist_ok=True)
                
                if source.is_file():
                    shutil.move(source, trash_path / source.name)
                else:
                    shutil.move(source, trash_path / source.name)
            else:
                if source.is_file():
                    source.unlink()
                else:
                    shutil.rmtree(source)
            
            return FileOperation(
                operation_type=operation,
                source_path=source_path,
                target_path=target_path,
                success=True,
                error_message=None,
                timestamp=datetime.now(),
                metadata={"trash": self.safety_mode and not options.get("force", False)}
            )
        
        elif operation == "create_directory":
            source.mkdir(parents=True, exist_ok=True)
            
            return FileOperation(
                operation_type=operation,
                source_path=source_path,
                target_path=target_path,
                success=True,
                error_message=None,
                timestamp=datetime.now(),
                metadata={}
            )
        
        else:
            return FileOperation(
                operation_type=operation,
                source_path=source_path,
                target_path=target_path,
                success=False,
                error_message=f"Unknown operation: {operation}",
                timestamp=datetime.now(),
                metadata={}
            )
    
    def _is_path_allowed(self, path: str) -> bool:
        """Check if path is allowed for operations"""
        
        path_obj = Path(path).resolve()
        
        # Check if path is in allowed directories
        if self.allowed_directories:
            is_allowed = False
            for allowed_dir in self.allowed_directories:
                try:
                    allowed_path = Path(allowed_dir).resolve()
                    if path_obj.is_relative_to(allowed_path):
                        is_allowed = True
                        break
                except ValueError:
                    continue
            
            if not is_allowed:
                return False
        
        # Check blocked extensions
        if path_obj.suffix.lower() in self.blocked_extensions:
            return False
        
        # Block system directories
        system_dirs = ["/", "/System", "/Windows", "/Program Files", "/usr/bin", "/bin", "/sbin"]
        for sys_dir in system_dirs:
            try:
                if path_obj.is_relative_to(Path(sys_dir)):
                    return False
            except ValueError:
                continue
        
        return True
    
    def _handle_file_event(self, event_type: str, file_path: str):
        """Handle file system events"""
        
        event = {
            "type": event_type,
            "path": file_path,
            "timestamp": datetime.now().isoformat()
        }
        
        self.file_events.append(event)
        
        # Keep only recent events
        if len(self.file_events) > 1000:
            self.file_events = self.file_events[-500:]
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of desktop automation"""
        return {
            "desktop_automation": True,
            "pyautogui_available": PYAUTOGUI_AVAILABLE,
            "watchdog_available": WATCHDOG_AVAILABLE,
            "automation_enabled": self.automation_enabled,
            "safety_mode": self.safety_mode,
            "file_monitoring_active": self.file_monitor is not None,
            "recent_file_events": len(self.file_events),
            "allowed_directories": len(self.allowed_directories),
            "blocked_extensions": len(self.blocked_extensions)
        }
