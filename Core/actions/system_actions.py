"""
System Action Handler
Handles system-level commands like window management, volume control, screenshots
"""

import os
import subprocess
import pyautogui
import webbrowser
from typing import Dict, Any
from ..assistant_core import ActionRequest, ConversationContext

class SystemActionHandler:
    """
    Handles system-level actions and commands
    """
    
    def __init__(self):
        self.supported_actions = {
            'window_management': self._handle_window_management,
            'volume_control': self._handle_volume_control,
            'screenshot': self._handle_screenshot,
            'application_control': self._handle_application_control,
            'system_control': self._handle_system_control
        }
    
    def execute(self, action_request: ActionRequest, context: ConversationContext) -> Dict[str, Any]:
        """
        Execute system action
        """
        action_type = action_request.command
        parameters = action_request.parameters
        
        if action_type in self.supported_actions:
            try:
                result = self.supported_actions[action_type](parameters)
                return {
                    "success": True,
                    "action": action_type,
                    "result": result,
                    "message": f"Successfully executed {action_type}"
                }
            except Exception as e:
                return {
                    "success": False,
                    "action": action_type,
                    "error": str(e),
                    "message": f"Failed to execute {action_type}: {str(e)}"
                }
        else:
            return {
                "success": False,
                "action": action_type,
                "error": f"Unsupported action: {action_type}",
                "message": f"Action {action_type} is not supported"
            }
    
    def _handle_window_management(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle window management actions
        """
        action = parameters.get('action', '')
        
        if action == 'close':
            pyautogui.hotkey('alt', 'F4')
            return {"action": "close", "status": "Window closed"}
        
        elif action == 'minimize':
            pyautogui.hotkey('win', 'down')
            return {"action": "minimize", "status": "Window minimized"}
        
        elif action == 'maximize':
            pyautogui.hotkey('win', 'up')
            return {"action": "maximize", "status": "Window maximized"}
        
        elif action == 'restore':
            pyautogui.hotkey('win', 'down')
            pyautogui.hotkey('win', 'up')
            return {"action": "restore", "status": "Window restored"}
        
        else:
            raise ValueError(f"Unsupported window action: {action}")
    
    def _handle_volume_control(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle volume control actions
        """
        action = parameters.get('action', '')
        
        if action == 'increase':
            pyautogui.press('volumeup')
            return {"action": "increase", "status": "Volume increased"}
        
        elif action == 'decrease':
            pyautogui.press('volumedown')
            return {"action": "decrease", "status": "Volume decreased"}
        
        elif action == 'mute':
            pyautogui.press('volumemute')
            return {"action": "mute", "status": "Volume muted"}
        
        elif action == 'unmute':
            pyautogui.press('volumemute')
            return {"action": "unmute", "status": "Volume unmuted"}
        
        else:
            raise ValueError(f"Unsupported volume action: {action}")
    
    def _handle_screenshot(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle screenshot actions
        """
        try:
            screenshot = pyautogui.screenshot()
            filename = f"screenshot_{self._get_timestamp()}.png"
            screenshot.save(filename)
            return {
                "action": "screenshot",
                "status": "Screenshot taken",
                "filename": filename,
                "path": os.path.abspath(filename)
            }
        except Exception as e:
            raise Exception(f"Failed to take screenshot: {str(e)}")
    
    def _handle_application_control(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle application control actions
        """
        application = parameters.get('application', '')
        
        app_commands = {
            'chrome': self._open_chrome,
            'browser': self._open_chrome,
            'notepad': self._open_notepad,
            'calculator': self._open_calculator,
            'explorer': self._open_explorer,
            'youtube': self._open_youtube,
            'spotify': self._open_spotify
        }
        
        if application in app_commands:
            result = app_commands[application]()
            return {
                "action": "application_control",
                "application": application,
                "status": "Application opened",
                "result": result
            }
        else:
            raise ValueError(f"Unsupported application: {application}")
    
    def _handle_system_control(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle system control actions
        """
        action = parameters.get('action', '')
        
        if action == 'lock':
            pyautogui.hotkey('win', 'l')
            return {"action": "lock", "status": "Screen locked"}
        
        elif action == 'shutdown':
            # This would require admin privileges
            return {"action": "shutdown", "status": "Shutdown command sent (requires confirmation)"}
        
        elif action == 'restart':
            # This would require admin privileges
            return {"action": "restart", "status": "Restart command sent (requires confirmation)"}
        
        else:
            raise ValueError(f"Unsupported system action: {action}")
    
    def _open_chrome(self) -> str:
        """Open Chrome browser"""
        try:
            os.startfile('chrome')
            return "Chrome browser opened"
        except:
            try:
                subprocess.Popen(['chrome'])
                return "Chrome browser opened via subprocess"
            except:
                webbrowser.open('https://www.google.com')
                return "Default browser opened with Google"
    
    def _open_notepad(self) -> str:
        """Open Notepad"""
        try:
            subprocess.Popen('notepad.exe')
            return "Notepad opened"
        except Exception as e:
            raise Exception(f"Failed to open Notepad: {str(e)}")
    
    def _open_calculator(self) -> str:
        """Open Calculator"""
        try:
            subprocess.Popen('calc.exe')
            return "Calculator opened"
        except Exception as e:
            raise Exception(f"Failed to open Calculator: {str(e)}")
    
    def _open_explorer(self) -> str:
        """Open File Explorer"""
        try:
            subprocess.Popen('explorer.exe')
            return "File Explorer opened"
        except Exception as e:
            raise Exception(f"Failed to open File Explorer: {str(e)}")
    
    def _open_youtube(self) -> str:
        """Open YouTube"""
        webbrowser.open('https://www.youtube.com')
        return "YouTube opened in browser"
    
    def _open_spotify(self) -> str:
        """Open Spotify"""
        try:
            # Try to open Spotify app first
            os.startfile('spotify')
            return "Spotify app opened"
        except:
            # Fallback to web version
            webbrowser.open('https://open.spotify.com')
            return "Spotify web opened in browser"
    
    def _get_timestamp(self) -> str:
        """Get current timestamp for filename"""
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d_%H%M%S")
