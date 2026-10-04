"""Home Assistant bridge — real smart-home control.

When ``HOME_ASSISTANT_URL`` and ``HOME_ASSISTANT_TOKEN`` (a long-lived access
token from your Home Assistant profile page) are set, Atulya's ``home_control``
tool drives real devices through Home Assistant's REST API instead of its
built-in simulation. Home Assistant in turn speaks to Zigbee, Z-Wave, Wi-Fi,
Matter, Hue, Tuya, etc., so one integration covers most real homes.

Device ids map to Home Assistant entity ids by convention
(``living_room_light`` -> ``light.living_room``) or explicitly through
``HOME_ASSISTANT_ENTITIES``, a JSON object, e.g.::

    HOME_ASSISTANT_ENTITIES='{"living_room_light": "light.lounge", "fan": "switch.bedroom_fan"}'

A device id that already looks like an entity id (``switch.coffee``) is used as-is.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_CONVENTION = {
    "living_room_light": "light.living_room",
    "kitchen_light": "light.kitchen",
    "bedroom_light": "light.bedroom",
    "thermostat": "climate.thermostat",
    "front_door": "lock.front_door",
}
_ON_OFF_DOMAINS = {"light", "switch", "fan", "media_player", "climate", "input_boolean", "cover"}


class HomeAssistantError(RuntimeError):
    pass


def _env_entities() -> dict[str, str]:
    raw = os.environ.get("HOME_ASSISTANT_ENTITIES", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("HOME_ASSISTANT_ENTITIES is not valid JSON; ignoring it")
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


class HomeAssistantBridge:
    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
        entities: dict[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 10.0,
    ):
        self.url = (url if url is not None else os.environ.get("HOME_ASSISTANT_URL", "")).rstrip("/")
        self.token = token if token is not None else os.environ.get("HOME_ASSISTANT_TOKEN", "")
        self.entities = {**_CONVENTION, **(entities if entities is not None else _env_entities())}
        self._transport = transport
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.url and self.token)

    def entity_for(self, device_id: str) -> str | None:
        if device_id in self.entities:
            return self.entities[device_id]
        if "." in device_id:  # already an entity id, e.g. "switch.coffee"
            return device_id
        return None

    @staticmethod
    def service_call(entity_id: str, action: str, value: str = "") -> tuple[str, str, dict[str, Any], str]:
        """Map (entity, action) to (domain, service, data, past-tense description)."""
        domain = entity_id.split(".", 1)[0]
        data: dict[str, Any] = {"entity_id": entity_id}
        act = (action or "").strip().lower()
        if act in ("on", "off") and domain in _ON_OFF_DOMAINS:
            return domain, f"turn_{act}", data, f"turned {act}"
        if act == "set_brightness" and domain == "light":
            data["brightness_pct"] = max(0, min(100, int(float(value))))
            return "light", "turn_on", data, f"brightness set to {data['brightness_pct']}%"
        if act in ("lock", "unlock") and domain == "lock":
            return "lock", act, data, f"{act}ed"
        if act == "set_temperature" and domain == "climate":
            data["temperature"] = float(value)
            return "climate", "set_temperature", data, f"set to {value}°"
        raise HomeAssistantError(f"action '{action}' isn't supported for {entity_id}")

    async def control(self, device_id: str, action: str, value: str = "") -> str:
        entity = self.entity_for(device_id)
        if not entity:
            raise HomeAssistantError(
                f"no Home Assistant entity is mapped for '{device_id}' (set HOME_ASSISTANT_ENTITIES)"
            )
        domain, service, data, done = self.service_call(entity, action, value)
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            resp = await client.post(
                f"{self.url}/api/services/{domain}/{service}",
                json=data,
                headers={"Authorization": f"Bearer {self.token}"},
            )
        if resp.status_code >= 400:
            raise HomeAssistantError(f"Home Assistant returned {resp.status_code}: {resp.text[:200]}")
        return f"{entity} {done} (via Home Assistant)."

    async def state(self, entity_id: str) -> dict[str, Any]:
        """One entity's current state, e.g. {"state": "on", "attributes": {...}}."""
        data = await self._get(f"/api/states/{entity_id}")
        return data if isinstance(data, dict) else {}

    async def states(self) -> list[dict[str, Any]]:
        """Every entity's state (used to watch sensors such as doorbells)."""
        data = await self._get("/api/states")
        return [s for s in data if isinstance(s, dict)] if isinstance(data, list) else []

    async def _get(self, path: str) -> Any:
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            resp = await client.get(f"{self.url}{path}", headers={"Authorization": f"Bearer {self.token}"})
        if resp.status_code >= 400:
            raise HomeAssistantError(f"Home Assistant returned {resp.status_code}: {resp.text[:200]}")
        return resp.json()
