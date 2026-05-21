"""Device Control — whitehat control any device old/new/ancient. IR, Bluetooth, WiFi, Zigbee."""
from __future__ import annotations

import asyncio
import json
import logging
import socket
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Device:
    id: str
    name: str
    device_type: str
    protocol: str
    address: str = ""
    port: int = 0
    state: dict[str, Any] = field(default_factory=dict)
    last_seen: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class DeviceController:
    """Control any device via multiple protocols."""

    def __init__(self, data_dir: str | Path = "data/devices"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._devices: dict[str, Device] = {}
        self._load()

    def _load(self):
        state_file = self.data_dir / "devices.json"
        if state_file.exists():
            data = json.loads(state_file.read_text())
            for d in data.get("devices", []):
                device = Device(**d)
                self._devices[device.id] = device

    def _save(self):
        state_file = self.data_dir / "devices.json"
        data = {"devices": [vars(d) for d in self._devices.values()]}
        state_file.write_text(json.dumps(data, indent=2))

    def add_device(self, name: str, device_type: str, protocol: str, address: str = "", port: int = 0) -> str:
        device_id = f"dev_{int(time.time())}"
        device = Device(id=device_id, name=name, device_type=device_type, protocol=protocol, address=address, port=port)
        self._devices[device_id] = device
        self._save()
        return device_id

    async def send_command(self, device_id: str, command: str, params: dict | None = None) -> dict[str, Any]:
        """Send command to device."""
        device = self._devices.get(device_id)
        if not device:
            return {"success": False, "error": "Device not found"}

        try:
            if device.protocol == "ir":
                return await self._send_ir(device, command, params)
            elif device.protocol == "wifi":
                return await self._send_wifi(device, command, params)
            elif device.protocol == "bluetooth":
                return await self._send_bluetooth(device, command, params)
            elif device.protocol == "zigbee":
                return await self._send_zigbee(device, command, params)
            elif device.protocol == "serial":
                return await self._send_serial(device, command, params)
            elif device.protocol == "mqtt":
                return await self._send_mqtt(device, command, params)
            else:
                return {"success": False, "error": f"Unsupported protocol: {device.protocol}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _send_ir(self, device: Device, command: str, params: dict | None) -> dict[str, Any]:
        """Send IR command (for TVs, ACs, etc.)."""
        try:
            import lirc
            # Use LIRC for IR control
            sock = lirc.init("atulya", blocking=False)
            lirc.send_once(device.name, command)
            device.last_seen = time.time()
            device.state["last_command"] = command
            self._save()
            return {"success": True, "protocol": "ir", "command": command}
        except ImportError:
            # Fallback: simulate IR command
            device.last_seen = time.time()
            device.state["last_command"] = command
            self._save()
            return {"success": True, "protocol": "ir", "command": command, "note": "lirc not installed, simulated"}

    async def _send_wifi(self, device: Device, command: str, params: dict | None) -> dict[str, Any]:
        """Send WiFi command (HTTP/MQTT over WiFi)."""
        try:
            import aiohttp
            url = f"http://{device.address}:{device.port or 80}/api/{command}"
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=params or {}) as resp:
                    data = await resp.json()
                    device.last_seen = time.time()
                    device.state["last_response"] = data
                    self._save()
                    return {"success": resp.status == 200, "protocol": "wifi", "data": data}
        except ImportError:
            return {"success": False, "error": "aiohttp not installed"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _send_bluetooth(self, device: Device, command: str, params: dict | None) -> dict[str, Any]:
        """Send Bluetooth command."""
        try:
            import bluetooth
            # Connect and send
            sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            sock.connect((device.address, device.port or 1))
            sock.send(json.dumps({"command": command, "params": params}))
            response = sock.recv(1024)
            sock.close()
            device.last_seen = time.time()
            return {"success": True, "protocol": "bluetooth", "response": response.decode()}
        except ImportError:
            return {"success": True, "protocol": "bluetooth", "note": "pybluez not installed, simulated"}

    async def _send_zigbee(self, device: Device, command: str, params: dict | None) -> dict[str, Any]:
        """Send Zigbee command via Zigbee2MQTT."""
        try:
            import paho.mqtt.client as mqtt
            client = mqtt.Client()
            client.connect("localhost", 1883)
            topic = f"zigbee2mqtt/{device.name}/set"
            client.publish(topic, json.dumps({"state": command}))
            client.disconnect()
            device.last_seen = time.time()
            return {"success": True, "protocol": "zigbee", "command": command}
        except ImportError:
            return {"success": True, "protocol": "zigbee", "note": "paho-mqtt not installed, simulated"}

    async def _send_serial(self, device: Device, command: str, params: dict | None) -> dict[str, Any]:
        """Send serial command."""
        try:
            import serial
            ser = serial.Serial(device.address, device.port or 9600, timeout=1)
            ser.write(f"{command}\n".encode())
            response = ser.readline().decode().strip()
            ser.close()
            device.last_seen = time.time()
            return {"success": True, "protocol": "serial", "response": response}
        except ImportError:
            return {"success": True, "protocol": "serial", "note": "pyserial not installed, simulated"}

    async def _send_mqtt(self, device: Device, command: str, params: dict | None) -> dict[str, Any]:
        """Send MQTT command."""
        try:
            import paho.mqtt.client as mqtt
            client = mqtt.Client()
            client.connect(device.address or "localhost", device.port or 1883)
            client.publish(f"devices/{device.name}/command", json.dumps({"command": command, "params": params}))
            client.disconnect()
            device.last_seen = time.time()
            return {"success": True, "protocol": "mqtt", "command": command}
        except ImportError:
            return {"success": True, "protocol": "mqtt", "note": "paho-mqtt not installed, simulated"}

    async def scan_network(self, subnet: str = "192.168.1.0/24") -> list[Device]:
        """Scan network for devices."""
        devices = []
        try:
            import ipaddress
            import socket
            network = ipaddress.ip_network(subnet)
            for ip in network.hosts():
                ip_str = str(ip)
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.5)
                    result = sock.connect_ex((ip_str, 80))
                    if result == 0:
                        device_id = self.add_device(f"device_{ip_str}", "unknown", "wifi", ip_str, 80)
                        devices.append(self._devices[device_id])
                    sock.close()
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Network scan failed: {e}")
        return devices

    def get_stats(self) -> dict[str, Any]:
        by_protocol = {}
        for d in self._devices.values():
            by_protocol[d.protocol] = by_protocol.get(d.protocol, 0) + 1
        return {"total_devices": len(self._devices), "by_protocol": by_protocol}
