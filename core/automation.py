"""
Atulya Tantra - Desktop Automation System
Version: 2.2.0
Handles desktop automation, screen control, and proactive AI features.
"""

import asyncio
import time
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import pyautogui
import cv2
import numpy as np
from PIL import Image
import psutil
import subprocess
import os

@dataclass
class ScreenRegion:
    """Screen region definition"""
    x: int
    y: int
    width: int
    height: int
    name: str = ""

@dataclass
class AutomationAction:
    """Automation action definition"""
    action_type: str  # click, type, scroll, screenshot, etc.
    target: Dict[str, Any]
    parameters: Dict[str, Any]
    timestamp: datetime = None

@dataclass
class AutomationRule:
    """Automation rule definition"""
    id: str
    name: str
    condition: str
    actions: List[AutomationAction]
    enabled: bool = True
    created_at: datetime = None

class ScreenCapture:
    """Screen capture utilities"""
    
    def __init__(self):
        self.screen_size = pyautogui.size()
    
    def capture_screen(self, region: Optional[ScreenRegion] = None) -> Image.Image:
        """Capture screen or region"""
        if region:
            return pyautogui.screenshot(region=(region.x, region.y, region.width, region.height))
        else:
            return pyautogui.screenshot()
    
    def capture_window(self, window_title: str) -> Optional[Image.Image]:
        """Capture specific window"""
        try:
            # Find window by title
            windows = pyautogui.getWindowsWithTitle(window_title)
            if windows:
                window = windows[0]
                return pyautogui.screenshot(region=(window.left, window.top, window.width, window.height))
        except Exception as e:
            print(f"Window capture error: {e}")
        return None
    
    def find_image_on_screen(self, template_path: str, confidence: float = 0.8) -> Optional[Tuple[int, int]]:
        """Find image on screen"""
        try:
            location = pyautogui.locateOnScreen(template_path, confidence=confidence)
            if location:
                center = pyautogui.center(location)
                return (center.x, center.y)
        except Exception as e:
            print(f"Image search error: {e}")
        return None

class MouseController:
    """Mouse control utilities"""
    
    def __init__(self):
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1
    
    def click(self, x: int, y: int, button: str = 'left', clicks: int = 1) -> bool:
        """Click at coordinates"""
        try:
            pyautogui.click(x, y, clicks=clicks, button=button)
            return True
        except Exception as e:
            print(f"Click error: {e}")
            return False
    
    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 1.0) -> bool:
        """Drag from start to end coordinates"""
        try:
            pyautogui.drag(end_x - start_x, end_y - start_y, duration=duration)
            return True
        except Exception as e:
            print(f"Drag error: {e}")
            return False
    
    def scroll(self, x: int, y: int, clicks: int) -> bool:
        """Scroll at coordinates"""
        try:
            pyautogui.scroll(clicks, x=x, y=y)
            return True
        except Exception as e:
            print(f"Scroll error: {e}")
            return False

class KeyboardController:
    """Keyboard control utilities"""
    
    def __init__(self):
        pyautogui.FAILSAFE = True
    
    def type_text(self, text: str, interval: float = 0.05) -> bool:
        """Type text"""
        try:
            pyautogui.typewrite(text, interval=interval)
            return True
        except Exception as e:
            print(f"Type error: {e}")
            return False
    
    def press_key(self, key: str) -> bool:
        """Press a key"""
        try:
            pyautogui.press(key)
            return True
        except Exception as e:
            print(f"Key press error: {e}")
            return False
    
    def hotkey(self, *keys: str) -> bool:
        """Press key combination"""
        try:
            pyautogui.hotkey(*keys)
            return True
        except Exception as e:
            print(f"Hotkey error: {e}")
            return False

class WindowManager:
    """Window management utilities"""
    
    def __init__(self):
        self.active_windows = {}
    
    def get_all_windows(self) -> List[Dict[str, Any]]:
        """Get all open windows"""
        windows = []
        try:
            for window in pyautogui.getAllWindows():
                if window.title:  # Only include windows with titles
                    windows.append({
                        'title': window.title,
                        'left': window.left,
                        'top': window.top,
                        'width': window.width,
                        'height': window.height,
                        'is_active': window.isActive
                    })
        except Exception as e:
            print(f"Window listing error: {e}")
        return windows
    
    def activate_window(self, window_title: str) -> bool:
        """Activate window by title"""
        try:
            windows = pyautogui.getWindowsWithTitle(window_title)
            if windows:
                window = windows[0]
                window.activate()
                return True
        except Exception as e:
            print(f"Window activation error: {e}")
        return False
    
    def minimize_window(self, window_title: str) -> bool:
        """Minimize window by title"""
        try:
            windows = pyautogui.getWindowsWithTitle(window_title)
            if windows:
                window = windows[0]
                window.minimize()
                return True
        except Exception as e:
            print(f"Window minimize error: {e}")
        return False
    
    def maximize_window(self, window_title: str) -> bool:
        """Maximize window by title"""
        try:
            windows = pyautogui.getWindowsWithTitle(window_title)
            if windows:
                window = windows[0]
                window.maximize()
                return True
        except Exception as e:
            print(f"Window maximize error: {e}")
        return False

class ProcessManager:
    """Process management utilities"""
    
    def __init__(self):
        pass
    
    def get_running_processes(self) -> List[Dict[str, Any]]:
        """Get all running processes"""
        processes = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cpu_percent': proc.info['cpu_percent'],
                    'memory_percent': proc.info['memory_percent']
                })
        except Exception as e:
            print(f"Process listing error: {e}")
        return processes
    
    def start_process(self, command: str, args: List[str] = None) -> Optional[int]:
        """Start a new process"""
        try:
            if args:
                proc = subprocess.Popen([command] + args)
            else:
                proc = subprocess.Popen(command)
            return proc.pid
        except Exception as e:
            print(f"Process start error: {e}")
            return None
    
    def kill_process(self, pid: int) -> bool:
        """Kill process by PID"""
        try:
            process = psutil.Process(pid)
            process.terminate()
            return True
        except Exception as e:
            print(f"Process kill error: {e}")
            return False

class AutomationEngine:
    """Main automation engine"""
    
    def __init__(self):
        self.screen_capture = ScreenCapture()
        self.mouse_controller = MouseController()
        self.keyboard_controller = KeyboardController()
        self.window_manager = WindowManager()
        self.process_manager = ProcessManager()
        self.automation_rules: List[AutomationRule] = []
        self.is_active = False
        self.automation_task: Optional[asyncio.Task] = None
    
    async def start_automation(self):
        """Start automation system"""
        if self.is_active:
            return
        
        self.is_active = True
        self.automation_task = asyncio.create_task(self._automation_loop())
    
    async def stop_automation(self):
        """Stop automation system"""
        self.is_active = False
        if self.automation_task:
            self.automation_task.cancel()
            try:
                await self.automation_task
            except asyncio.CancelledError:
                pass
    
    async def _automation_loop(self):
        """Main automation loop"""
        while self.is_active:
            try:
                # Check automation rules
                await self._check_automation_rules()
                
                # Monitor system state
                await self._monitor_system_state()
                
                await asyncio.sleep(1)  # Check every second
                
            except Exception as e:
                print(f"Automation loop error: {e}")
                await asyncio.sleep(5)
    
    async def _check_automation_rules(self):
        """Check and execute automation rules"""
        for rule in self.automation_rules:
            if rule.enabled and await self._evaluate_condition(rule.condition):
                await self._execute_actions(rule.actions)
    
    async def _evaluate_condition(self, condition: str) -> bool:
        """Evaluate automation condition"""
        try:
            # Simple condition evaluation (in production, use proper expression parser)
            if "time" in condition.lower():
                return await self._check_time_condition(condition)
            elif "window" in condition.lower():
                return await self._check_window_condition(condition)
            elif "process" in condition.lower():
                return await self._check_process_condition(condition)
            return False
        except Exception as e:
            print(f"Condition evaluation error: {e}")
            return False
    
    async def _check_time_condition(self, condition: str) -> bool:
        """Check time-based condition"""
        # Simple time checking (in production, use proper cron-like expressions)
        current_hour = datetime.now().hour
        if "morning" in condition.lower() and 6 <= current_hour < 12:
            return True
        elif "afternoon" in condition.lower() and 12 <= current_hour < 18:
            return True
        elif "evening" in condition.lower() and 18 <= current_hour < 22:
            return True
        return False
    
    async def _check_window_condition(self, condition: str) -> bool:
        """Check window-based condition"""
        windows = self.window_manager.get_all_windows()
        # Simple window checking
        return any("chrome" in w['title'].lower() for w in windows)
    
    async def _check_process_condition(self, condition: str) -> bool:
        """Check process-based condition"""
        processes = self.process_manager.get_running_processes()
        # Simple process checking
        return any("chrome" in p['name'].lower() for p in processes)
    
    async def _execute_actions(self, actions: List[AutomationAction]):
        """Execute automation actions"""
        for action in actions:
            try:
                await self._execute_action(action)
            except Exception as e:
                print(f"Action execution error: {e}")
    
    async def _execute_action(self, action: AutomationAction):
        """Execute single automation action"""
        if action.action_type == "click":
            x = action.target.get('x', 0)
            y = action.target.get('y', 0)
            self.mouse_controller.click(x, y)
        
        elif action.action_type == "type":
            text = action.parameters.get('text', '')
            self.keyboard_controller.type_text(text)
        
        elif action.action_type == "screenshot":
            region = action.target.get('region')
            if region:
                screen_region = ScreenRegion(**region)
                image = self.screen_capture.capture_screen(screen_region)
            else:
                image = self.screen_capture.capture_screen()
            # Save or process screenshot
        
        elif action.action_type == "window_action":
            window_title = action.target.get('title', '')
            action_name = action.parameters.get('action', 'activate')
            
            if action_name == "activate":
                self.window_manager.activate_window(window_title)
            elif action_name == "minimize":
                self.window_manager.minimize_window(window_title)
            elif action_name == "maximize":
                self.window_manager.maximize_window(window_title)
    
    def add_automation_rule(self, rule: AutomationRule):
        """Add automation rule"""
        self.automation_rules.append(rule)
    
    def remove_automation_rule(self, rule_id: str):
        """Remove automation rule"""
        self.automation_rules = [r for r in self.automation_rules if r.id != rule_id]
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        return {
            "is_active": self.is_active,
            "screen_size": self.screen_size,
            "active_windows": len(self.window_manager.get_all_windows()),
            "running_processes": len(self.process_manager.get_running_processes()),
            "automation_rules": len(self.automation_rules),
            "enabled_rules": len([r for r in self.automation_rules if r.enabled])
        }

# Global instances
_automation_engine: Optional[AutomationEngine] = None

def get_automation_engine() -> AutomationEngine:
    """Get global automation engine instance"""
    global _automation_engine
    if _automation_engine is None:
        _automation_engine = AutomationEngine()
    return _automation_engine

# Export main classes and functions
__all__ = [
    "ScreenRegion",
    "AutomationAction",
    "AutomationRule",
    "ScreenCapture",
    "MouseController",
    "KeyboardController",
    "WindowManager",
    "ProcessManager",
    "AutomationEngine",
    "get_automation_engine"
]
