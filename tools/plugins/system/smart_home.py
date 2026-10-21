"""Smart Home and Ambient Device Automation for Atulya-Tantra (Jarvis).

Integrates:
- Home Assistant (REST API / Webhooks)
- Local HTTP smart plugs & bulbs (Tuya, Tasmota, Shelly, Matter bridges)
- Cinematic Automation Scenes (Movie Mode, Work Mode, Goodnight, Away)
"""
from __future__ import annotations

import os
from typing import Any
import httpx

HASS_URL = os.environ.get("HASS_URL", "").rstrip("/")
HASS_TOKEN = os.environ.get("HASS_TOKEN", "")

# Pre-configured ambient scene profiles
SCENES: dict[str, dict[str, Any]] = {
    "movie_mode": {
        "description": "Dim ambient lights, ready TV, and pause background music",
        "actions": [
            {"service": "light/turn_on", "target": "all", "params": {"brightness_pct": 20, "color_temp": 400}},
            {"device": "tv", "command": "media_control", "detail": "play"},
        ]
    },
    "work_mode": {
        "description": "Bright daylight lighting, focus audio, open productivity tools",
        "actions": [
            {"service": "light/turn_on", "target": "all", "params": {"brightness_pct": 100, "color_temp": 250}},
        ]
    },
    "goodnight": {
        "description": "Turn off all lights, verify door sensors, mute non-emergency notifications",
        "actions": [
            {"service": "light/turn_off", "target": "all"},
            {"device": "tv", "command": "media_control", "detail": "pause"},
        ]
    },
    "relax": {
        "description": "Warm ambient lighting with calming volume",
        "actions": [
            {"service": "light/turn_on", "target": "all", "params": {"brightness_pct": 40, "color_temp": 500}},
        ]
    }
}


NOT_CONNECTED = "Not connected: set HASS_URL/HASS_TOKEN; nothing was changed."


async def execute_smart_home(device: str, action: str, brightness: int | None = None, state: str | None = None) -> str:
    """Execute a smart home command via Home Assistant. Never reports success it did not get."""
    device_norm = device.lower().strip()
    action_norm = action.lower().strip()
    hass_url = os.environ.get("HASS_URL", HASS_URL).rstrip("/")
    hass_token = os.environ.get("HASS_TOKEN", HASS_TOKEN)

    if action_norm in SCENES or device_norm in SCENES:
        scene_key = action_norm if action_norm in SCENES else device_norm
        # Scenes are described but not wired to Home Assistant yet.
        return f"Scene '{scene_key}' is unsupported for now; nothing was changed."

    if not (hass_url and hass_token):
        return NOT_CONNECTED

    headers = {
        "Authorization": f"Bearer {hass_token}",
        "Content-Type": "application/json"
    }
    domain = "light" if "light" in device_norm or "lamp" in device_norm else "switch"
    service = "turn_on" if action_norm in {"turn_on", "on", "enable"} else "turn_off"
    endpoint = f"{hass_url}/api/services/{domain}/{service}"
    payload: dict[str, Any] = {"entity_id": f"{domain}.{device_norm.replace(' ', '_')}"}
    if brightness is not None and domain == "light":
        payload["brightness_pct"] = max(0, min(100, brightness))

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(endpoint, headers=headers, json=payload)
            if res.status_code in {200, 201}:
                return f"Smart home: {device} set to {action} (brightness {brightness}%)." if brightness else f"Smart home: {device} set to {action}."
            return f"Home Assistant returned status {res.status_code}: {res.text[:120]}. Nothing was confirmed changed."
    except Exception as exc:
        return f"Home Assistant request failed: {exc}. Nothing was changed."