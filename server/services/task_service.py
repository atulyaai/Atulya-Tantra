"""
Task Service - Handles system automation and task execution
Independent microservice for executing actions
"""

import logging
import subprocess
import os
import psutil
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class TaskService:
    """Service for executing system tasks and automation"""
    
    def __init__(self):
        self.enabled_tasks = {
            'system_info': True,
            'file_operations': True,
            'app_control': True,
            'web_search': True,
        }
    
    async def execute_task(self, task_type: str, params: Dict) -> Dict:
        """
        Execute a task
        
        Args:
            task_type: Type of task to execute
            params: Task parameters
        
        Returns:
            Task result
        """
        logger.info(f"Executing task: {task_type} with params: {params}")
        
        if task_type == "system_info":
            return await self.get_system_info()
        
        elif task_type == "open_app":
            app_name = params.get("app_name")
            return await self.open_application(app_name)
        
        elif task_type == "file_search":
            query = params.get("query")
            directory = params.get("directory", ".")
            return await self.search_files(query, directory)
        
        elif task_type == "web_search":
            query = params.get("query")
            return await self.web_search(query)
        
        else:
            return {"success": False, "error": f"Unknown task type: {task_type}"}
    
    async def get_system_info(self) -> Dict:
        """Get system information"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "success": True,
                "cpu_usage": f"{cpu_percent}%",
                "memory_usage": f"{memory.percent}%",
                "memory_available": f"{memory.available / (1024**3):.1f} GB",
                "disk_usage": f"{disk.percent}%",
                "disk_free": f"{disk.free / (1024**3):.1f} GB"
            }
        except Exception as e:
            logger.error(f"System info error: {e}")
            return {"success": False, "error": str(e)}
    
    async def open_application(self, app_name: str) -> Dict:
        """Open an application"""
        if not self.enabled_tasks.get('app_control'):
            return {"success": False, "error": "App control disabled"}
        
        try:
            # Map common app names
            app_map = {
                'chrome': 'chrome',
                'firefox': 'firefox',
                'notepad': 'notepad',
                'calculator': 'calc',
                'explorer': 'explorer',
            }
            
            executable = app_map.get(app_name.lower(), app_name)
            
            # Launch
            if os.name == 'nt':  # Windows
                subprocess.Popen(executable, shell=True)
            else:  # Linux/Mac
                subprocess.Popen([executable])
            
            return {
                "success": True,
                "message": f"Opened {app_name}"
            }
        except Exception as e:
            logger.error(f"Open app error: {e}")
            return {"success": False, "error": str(e)}
    
    async def search_files(self, query: str, directory: str = ".") -> Dict:
        """Search for files"""
        try:
            from pathlib import Path
            
            matches = []
            search_path = Path(directory)
            
            for file in search_path.rglob(f"*{query}*"):
                if file.is_file():
                    matches.append(str(file))
                if len(matches) >= 20:  # Limit results
                    break
            
            return {
                "success": True,
                "found": len(matches),
                "files": matches
            }
        except Exception as e:
            logger.error(f"File search error: {e}")
            return {"success": False, "error": str(e)}
    
    async def web_search(self, query: str) -> Dict:
        """Perform web search (opens browser)"""
        try:
            import webbrowser
            import urllib.parse
            
            encoded_query = urllib.parse.quote(query)
            url = f"https://www.google.com/search?q={encoded_query}"
            
            webbrowser.open(url)
            
            return {
                "success": True,
                "message": f"Opened web search for: {query}",
                "url": url
            }
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return {"success": False, "error": str(e)}

# Singleton instance
task_service = TaskService()

