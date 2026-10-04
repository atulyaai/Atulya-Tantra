"""Wake-on-LAN: switch on a PC, console or TV that supports it, from anywhere on the home network."""
from __future__ import annotations

import asyncio
import re
import socket
from typing import Any

from atulya.devices.base import Capability, DeviceError, DeviceRecord, Driver, is_lan_host

_MAC = re.compile(r"^([0-9a-f]{2}[:-]){5}[0-9a-f]{2}$", re.I)


def magic_packet(mac: str) -> bytes:
    if not _MAC.match(mac or ""):
        raise DeviceError("That MAC address doesn't look right. It should be like AA:BB:CC:DD:EE:FF.")
    raw = bytes.fromhex(re.sub(r"[:-]", "", mac))
    return b"\xff" * 6 + raw * 16


class WolDriver(Driver):
    id = "wol"

    async def capabilities(self, device: DeviceRecord) -> list[Capability]:
        return [Capability("power_on", "Wake it up over the network", ["turn on", "switch on", "wake", "wake up", "power on"])]

    async def execute(self, device: DeviceRecord, capability: str, args: dict[str, Any]) -> str:
        if capability != "power_on":
            raise DeviceError(f"{device.name} can only be switched on this way.")
        packet = magic_packet(str(device.config.get("mac", "")))
        target = str(device.config.get("broadcast") or "255.255.255.255")
        if target != "255.255.255.255" and not is_lan_host(target):
            raise DeviceError("The broadcast address must be on your home network.")
        port = int(device.config.get("wol_port") or 9)

        def send() -> None:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                for _ in range(3):  # UDP can drop; three is the usual habit
                    s.sendto(packet, (target, port))
        try:
            await asyncio.to_thread(send)
        except OSError as exc:
            raise DeviceError(f"I couldn't send the wake signal: {exc}") from exc
        return f"Sent the wake signal to {device.name}. It can take a few seconds."
