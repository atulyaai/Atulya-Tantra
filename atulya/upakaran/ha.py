"""Home Assistant as a device source: one connection brings thousands of brands (Samsung, LG, Sonos, Hue, Matter,
Zigbee, Z-Wave, Tuya …). Every Home Assistant entity becomes a device; its domain decides the capabilities.

Set ``HOME_ASSISTANT_URL`` and ``HOME_ASSISTANT_TOKEN`` (a long-lived token from your Home Assistant profile).
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from atulya.upakaran.base import Capability, DeviceError, DeviceRecord, Driver, coerce, is_lan_host

# Home Assistant's own service names per domain: (capability, service, phrases, params, data builder)
_ONOFF = [("power_on", "turn_on", ["turn on", "switch on"]), ("power_off", "turn_off", ["turn off", "switch off"]), ("toggle", "toggle", ["toggle"])]
_DOMAINS: dict[str, list[tuple[str, str, list[str], dict[str, Any], str]]] = {
    "light": [(*c, {}, "") for c in _ONOFF] + [("set_brightness", "turn_on", ["brightness", "dim"], {"value": {"type": "integer", "min": 0, "max": 100}}, "brightness_pct")],
    "switch": [(*c, {}, "") for c in _ONOFF],
    "fan": [(*c, {}, "") for c in _ONOFF],
    "input_boolean": [(*c, {}, "") for c in _ONOFF],
    "media_player": [(*c, {}, "") for c in _ONOFF[:2]] + [
        ("volume_up", "volume_up", ["volume up", "louder"], {}, ""), ("volume_down", "volume_down", ["volume down", "quieter"], {}, ""),
        ("play_pause", "media_play_pause", ["play", "pause", "resume"], {}, ""), ("next", "media_next_track", ["next", "skip"], {}, ""),
        ("previous", "media_previous_track", ["previous"], {}, ""),
        ("set_volume", "volume_set", ["volume"], {"value": {"type": "integer", "min": 0, "max": 100}}, "volume_level"),
        ("select_source", "select_source", ["switch to", "change source", "input"], {"value": {"type": "string"}}, "source")],
    "climate": [(*c, {}, "") for c in _ONOFF[:2]] + [("set_temperature", "set_temperature", ["temperature", "set to"], {"value": {"type": "number", "min": 5, "max": 40}}, "temperature")],
    "cover": [("open", "open_cover", ["open"], {}, ""), ("close", "close_cover", ["close"], {}, ""), ("stop", "stop_cover", ["stop"], {}, "")],
    "lock": [("lock", "lock", ["lock"], {}, ""), ("unlock", "unlock", ["unlock"], {}, "")],
    "scene": [("activate", "turn_on", ["activate", "run", "start"], {}, "")],
    "script": [("run", "turn_on", ["run", "start"], {}, "")],
    "button": [("press", "press", ["press"], {}, "")],
    "vacuum": [("start", "start", ["start", "clean"], {}, ""), ("stop", "stop", ["stop"], {}, ""), ("return_home", "return_to_base", ["go home", "dock"], {}, "")],
}
KIND = {"light": "light", "switch": "switch", "fan": "fan", "media_player": "tv", "climate": "thermostat", "cover": "cover", "lock": "lock",
        "scene": "scene", "script": "script", "button": "button", "vacuum": "vacuum", "input_boolean": "switch"}


class HomeAssistantDriver(Driver):
    id = "homeassistant"

    def __init__(self, url: str | None = None, token: str | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.url = (url if url is not None else os.environ.get("HOME_ASSISTANT_URL", "")).rstrip("/")
        self.token = token if token is not None else os.environ.get("HOME_ASSISTANT_TOKEN", "")
        self._transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.url and self.token)

    def _client(self) -> httpx.AsyncClient:
        if not self.configured:
            raise DeviceError("Home Assistant isn't set up. Add HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN to .env.")
        host = httpx.URL(self.url).host
        if not is_lan_host(host):
            raise DeviceError("Home Assistant must be on your home network.")
        return httpx.AsyncClient(base_url=self.url, headers={"Authorization": f"Bearer {self.token}"}, timeout=10.0, transport=self._transport)

    async def entities(self) -> list[dict[str, Any]]:
        try:
            async with self._client() as client:
                resp = await client.get("/api/states")
            if resp.status_code == 401:
                raise DeviceError("Home Assistant refused the token. Make a new long-lived token and update .env.")
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise DeviceError(f"I couldn't reach Home Assistant: {type(exc).__name__}.") from exc
        return [{"entity": s["entity_id"], "name": (s.get("attributes") or {}).get("friendly_name") or s["entity_id"],
                 "domain": s["entity_id"].split(".", 1)[0], "state": s.get("state")}
                for s in resp.json() if s["entity_id"].split(".", 1)[0] in _DOMAINS]

    async def capabilities(self, device: DeviceRecord) -> list[Capability]:
        domain = str(device.config.get("entity", "")).split(".", 1)[0]
        return [Capability(name, name.replace("_", " "), phrases, params, risky=(name == "unlock"))
                for name, _svc, phrases, params, _key in _DOMAINS.get(domain, [])]

    async def execute(self, device: DeviceRecord, capability: str, args: dict[str, Any]) -> str:
        entity = str(device.config.get("entity", ""))
        domain = entity.split(".", 1)[0]
        row = next((r for r in _DOMAINS.get(domain, []) if r[0] == capability), None)
        if row is None:
            raise DeviceError(f"{device.name} can't “{capability.replace('_', ' ')}”.")
        _name, service, _phrases, params, key = row
        data: dict[str, Any] = {"entity_id": entity}
        for pname, spec in params.items():
            if args.get(pname) is None:
                raise DeviceError(f"I need {pname} for that.")
            value = coerce(args[pname], spec, pname)
            data[key] = value / 100 if key == "volume_level" else value
        try:
            async with self._client() as client:
                resp = await client.post(f"/api/services/{domain}/{service}", json=data)
            if resp.status_code == 401:
                raise DeviceError("Home Assistant refused the token.")
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise DeviceError(f"Home Assistant couldn't do that: {type(exc).__name__}.") from exc
        return f"Done: {capability.replace('_', ' ')} on {device.name}."

    async def state(self, device: DeviceRecord) -> dict[str, Any]:
        try:
            async with self._client() as client:
                resp = await client.get(f"/api/states/{device.config.get('entity')}")
            return {"online": resp.status_code == 200, "state": resp.json().get("state") if resp.status_code == 200 else None}
        except (httpx.HTTPError, DeviceError):
            return {"online": False}
