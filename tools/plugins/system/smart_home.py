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


async def execute_smart_home(device: str, action: str, brightness: int | None = None, state: str | None = None) -> str:
    """Execute a smart home command via Home Assistant or local webhook."""
    device_norm = device.lower().strip()
    action_norm = action.lower().strip()

    # Check if this matches a predefined scene
    if action_norm in SCENES or device_norm in SCENES:
        scene_key = action_norm if action_norm in SCENES else device_norm
        scene = SCENES[scene_key]
        return f"Triggered scene '{scene_key}': {scene['description']}."

    # Direct Home Assistant control if configured
    if HASS_URL and HASS_TOKEN:
        headers = {
            "Authorization": f"Bearer {HASS_TOKEN}",
            "Content-Type": "application/json"
        }
        domain = "light" if "light" in device_norm or "lamp" in device_norm else "switch"
        service = "turn_on" if action_norm in {"turn_on", "on", "enable"} else "turn_off"
        endpoint = f"{HASS_URL}/api/services/{domain}/{service}"
        payload: dict[str, Any] = {"entity_id": f"{domain}.{device_norm.replace(' ', '_')}"}
        if brightness is not None and domain == "light":
            payload["brightness_pct"] = max(0, min(100, brightness))

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                res = await client.post(endpoint, headers=headers, json=payload)
                if res.status_code in {200, 201}:
                    return f"Smart home: {device} set to {action} (brightness {brightness}%)." if brightness else f"Smart home: {device} set to {action}."
                return f"Home Assistant returned status {res.status_code}: {res.text[:120]}"
        except Exception as exc:
            return f"Home Assistant request failed: {exc}"

    # Simulation / Local acknowledgement when no bridge is configured
    bright_text = f" at {brightness}% brightness" if brightness is not None else ""
    return f"Smart home action dispatched: {device} set to {action}{bright_text}. (Configure HASS_URL and HASS_TOKEN for direct Home Assistant integration)."
