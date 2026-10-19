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

    if not (HASS_URL and HASS_TOKEN):
        # Never report a change that did not happen.
        return (f"Smart home is not connected, so nothing was changed ({device} → {action}). "
                "The owner connects Home Assistant by setting HASS_URL and HASS_TOKEN on the server.")

    # A predefined scene runs each of its Home Assistant service calls and reports what really happened.
    if action_norm in SCENES or device_norm in SCENES:
        scene_key = action_norm if action_norm in SCENES else device_norm
        scene = SCENES[scene_key]
        done, failed = 0, []
        lights = [step for step in scene["actions"] if "service" in step]
        others = [f"{step.get('device', 'device')} {step.get('detail') or step.get('command', '')}".strip()
                  for step in scene["actions"] if "service" not in step]
        async with httpx.AsyncClient(timeout=10) as client:
            for step in lights:
                body: dict[str, Any] = {"entity_id": step.get("target", "all"), **step.get("params", {})}
                try:
                    res = await client.post(f"{HASS_URL}/api/services/{step['service']}",
                                            headers={"Authorization": f"Bearer {HASS_TOKEN}"}, json=body)
                    if res.status_code in {200, 201}:
                        done += 1
                    else:
                        failed.append(f"{step['service']} → HTTP {res.status_code}")
                except httpx.HTTPError as exc:
                    failed.append(f"{step['service']} → {type(exc).__name__}")
        not_done = f" Not done (needs a paired device): {', '.join(others)}." if others else ""
        if failed:
            return (f"Scene '{scene_key}': {done} of {len(lights)} Home Assistant steps confirmed; "
                    f"failed: {'; '.join(failed)}.{not_done}")
        return f"Scene '{scene_key}' confirmed by Home Assistant ({done} steps).{not_done}"

    # Direct Home Assistant control
    if HASS_URL and HASS_TOKEN:
        services = {"on": "turn_on", "enable": "turn_on", "turn_on": "turn_on",
                    "off": "turn_off", "disable": "turn_off", "turn_off": "turn_off", "toggle": "toggle"}
        service = services.get(action_norm)
        if service is None:
            return f"Unsupported smart home action '{action}'. Nothing was changed. Use on, off, toggle, or a configured scene."
        headers = {
            "Authorization": f"Bearer {HASS_TOKEN}",
            "Content-Type": "application/json"
        }
        domain = device_norm.split(".", 1)[0] if "." in device_norm else "light" if "light" in device_norm or "lamp" in device_norm else "switch"
        if domain not in {"light", "switch"}:
            return "Only light and switch entities are supported. Nothing was changed."
        endpoint = f"{HASS_URL}/api/services/{domain}/{service}"
        entity = device_norm if "." in device_norm else f"{domain}.{device_norm.replace(' ', '_')}"
        payload: dict[str, Any] = {"entity_id": entity}
        if brightness is not None and domain == "light":
            payload["brightness_pct"] = max(0, min(100, brightness))

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                res = await client.post(endpoint, headers=headers, json=payload)
                if res.status_code in {200, 201}:
                    return f"Home Assistant accepted {service} for {device} ({entity})" + (f" (brightness {payload['brightness_pct']}%)." if "brightness_pct" in payload else ".")
                return f"Home Assistant returned status {res.status_code}: {res.text[:120]}"
        except Exception as exc:
            return f"Home Assistant request failed: {exc}"

