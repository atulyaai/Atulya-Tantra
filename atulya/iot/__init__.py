"""IoT & Smart Home Integration Module"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SmartDevice:
    """Represents a smart home device"""
    
    def __init__(self, device_id: str, device_type: str, name: str, location: str = ""):
        self.device_id = device_id
        self.device_type = device_type  # light, thermostat, door, camera, etc.
        self.name = name
        self.location = location
        self.status = "off"
        self.controllable = True
        self.metadata = {}
    
    def turn_on(self) -> bool:
        """Turn device on"""
        self.status = "on"
        logger.info(f"Turned on {self.name}")
        return True
    
    def turn_off(self) -> bool:
        """Turn device off"""
        self.status = "off"
        logger.info(f"Turned off {self.name}")
        return True
    
    def set_property(self, prop: str, value) -> bool:
        """Set device property"""
        self.metadata[prop] = value
        logger.info(f"Set {self.name}.{prop} = {value}")
        return True
    
    def get_status(self) -> Dict:
        """Get device status"""
        return {
            "device_id": self.device_id,
            "name": self.name,
            "type": self.device_type,
            "location": self.location,
            "status": self.status,
            "properties": self.metadata
        }


class SmartHome:
    """Smart home automation system"""
    
    def __init__(self):
        self.devices: Dict[str, SmartDevice] = {}
        self.rooms: Dict[str, List[str]] = {}  # room -> device_ids
        self.automations: Dict[str, Dict] = {}
        
        logger.info("SmartHome initialized")
    
    def register_device(self, device_id: str, device_type: str, 
                       name: str, location: str = "") -> SmartDevice:
        """Register a smart device"""
        device = SmartDevice(device_id, device_type, name, location)
        self.devices[device_id] = device
        
        # Add to room
        if location:
            if location not in self.rooms:
                self.rooms[location] = []
            self.rooms[location].append(device_id)
        
        logger.info(f"Device registered: {name} ({device_type}) in {location}")
        return device
    
    def get_device(self, device_id: str) -> Optional[SmartDevice]:
        """Get device by ID"""
        return self.devices.get(device_id)
    
    def find_devices(self, location: str = None, device_type: str = None) -> List[SmartDevice]:
        """Find devices by criteria"""
        results = []
        
        for device in self.devices.values():
            if location and device.location != location:
                continue
            if device_type and device.device_type != device_type:
                continue
            results.append(device)
        
        return results
    
    def control_lights(self, location: str = None, action: str = "toggle") -> List[str]:
        """Control room lights"""
        lights = self.find_devices(location=location, device_type="light")
        results = []
        
        for light in lights:
            if action == "on":
                light.turn_on()
                results.append(f"Turned on lights in {light.location}")
            elif action == "off":
                light.turn_off()
                results.append(f"Turned off lights in {light.location}")
            elif action == "toggle":
                if light.status == "on":
                    light.turn_off()
                else:
                    light.turn_on()
                results.append(f"Toggled lights in {light.location}")
        
        return results
    
    def set_temperature(self, location: str, temperature: float) -> str:
        """Set thermostat temperature"""
        thermostats = self.find_devices(location=location, device_type="thermostat")
        
        for thermostat in thermostats:
            thermostat.set_property("temperature_setpoint", temperature)
        
        if thermostats:
            return f"Temperature in {location} set to {temperature}°C"
        return f"No thermostat found in {location}"
    
    def get_room_status(self, location: str) -> str:
        """Get status of all devices in room"""
        devices = self.find_devices(location=location)
        
        if not devices:
            return f"No devices found in {location}"
        
        status = f"Status of {location}:\n"
        for device in devices:
            status += f"• {device.name}: {device.status}\n"
        
        return status
    
    def create_scene(self, scene_name: str, commands: List[Dict]) -> None:
        """Create automation scene"""
        self.automations[scene_name] = {
            "name": scene_name,
            "commands": commands
        }
        logger.info(f"Scene created: {scene_name}")
    
    def activate_scene(self, scene_name: str) -> str:
        """Activate a scene"""
        if scene_name not in self.automations:
            return f"Scene {scene_name} not found"
        
        scene = self.automations[scene_name]
        results = []
        
        for cmd in scene["commands"]:
            device_id = cmd.get("device_id")
            action = cmd.get("action")
            
            device = self.get_device(device_id)
            if device:
                if action == "on":
                    device.turn_on()
                    results.append(f"Activated {device.name}")
                elif action == "off":
                    device.turn_off()
                    results.append(f"Deactivated {device.name}")
        
        return f"Scene '{scene_name}' activated. {len(results)} devices updated."
    
    def get_summary(self) -> str:
        """Get smart home summary"""
        total_devices = len(self.devices)
        active_devices = len([d for d in self.devices.values() if d.status == "on"])
        
        return f"""
Smart Home System Status:
- Total Devices: {total_devices}
- Active Devices: {active_devices}
- Rooms: {len(self.rooms)}
- Scenes: {len(self.automations)}

All systems operational, Sir.
        """


class IoTManager:
    """Unified IoT management"""
    
    def __init__(self):
        self.smart_home = SmartHome()
        logger.info("IoTManager initialized")
    
    def execute_voice_command(self, command: str) -> str:
        """Execute voice command for smart home"""
        command_lower = command.lower()
        
        # Parse commands
        if "light" in command_lower:
            if "on" in command_lower:
                results = self.smart_home.control_lights(action="on")
                return " | ".join(results) or "No lights found"
            elif "off" in command_lower:
                results = self.smart_home.control_lights(action="off")
                return " | ".join(results) or "No lights found"
        
        elif "temperature" in command_lower:
            # Extract number from command
            import re
            match = re.search(r'(\d+)', command)
            if match:
                temp = int(match.group(1))
                return self.smart_home.set_temperature("Living Room", temp)
        
        elif "scene" in command_lower or "activate" in command_lower:
            # Extract scene name
            if "movie" in command_lower:
                return self.smart_home.activate_scene("Movie Time")
            elif "sleep" in command_lower:
                return self.smart_home.activate_scene("Sleep Mode")
            elif "morning" in command_lower:
                return self.smart_home.activate_scene("Good Morning")
        
        return f"Smart home command not understood: {command}"
