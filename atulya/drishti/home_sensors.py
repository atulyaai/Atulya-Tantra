"""Home Assistant sensors as senses — doorbells, people, motion, doors.

Most smart doorbells and cameras (Ring, Nest, Reolink, UniFi, Frigate…) already
detect people and presses and expose them to Home Assistant. This watcher polls
Home Assistant's states and turns *changes* into Atulya events:

  doorbell.pressed  a doorbell entity changed (button pressed / "ding")
  vision.person     a person/occupancy/presence sensor turned on
  vision.motion     a motion sensor turned on
  home.sensor       any watched sensor changed (door opened, smoke, leak…)

The payload's "camera" is the place, taken from the entity's name
("Front Door Doorbell" -> "front door"), so the built-in "Someone at the door"
rule works for real doorbells as well as Atulya's own cameras.

Watched entities: ``HOME_ASSISTANT_WATCH`` (comma-separated entity ids), or by
default every doorbell and every binary sensor whose device class is one of
motion, occupancy, presence, door, opening, window, smoke, gas or moisture.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import Any

logger = logging.getLogger(__name__)

_WATCHED_CLASSES = {"motion", "occupancy", "presence", "door", "opening", "window", "garage_door",
                    "smoke", "gas", "moisture", "carbon_monoxide", "sound", "vibration"}
_PERSON_CLASSES = {"occupancy", "presence"}
_NOISE_WORDS = {"doorbell", "person", "people", "motion", "occupancy", "presence", "sensor", "detected", "detection",
                "ding", "ring", "button", "pressed", "press", "camera", "cam", "event", "binary", "visitor"}


def place_name(entity_id: str, friendly_name: str = "") -> str:
    """'Front Door Doorbell' / binary_sensor.front_door_person -> 'front door'."""
    base = friendly_name or entity_id.split(".", 1)[-1]
    words = [w for w in re.split(r"[\s_\-]+", base.lower()) if w and w not in _NOISE_WORDS]
    return " ".join(words) or "home"


def is_doorbell(entity_id: str, attributes: dict[str, Any]) -> bool:
    text = f"{entity_id} {attributes.get('friendly_name', '')}".lower()
    return attributes.get("device_class") == "doorbell" or "doorbell" in text or re.search(r"\bding\b|_ding\b", text) is not None


def classify(entity_id: str, state: str, previous: str, attributes: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Events for one state change (empty if it's not interesting)."""
    if state == previous or state in ("unavailable", "unknown"):
        return []
    name = str(attributes.get("friendly_name") or entity_id)
    place = place_name(entity_id, str(attributes.get("friendly_name") or ""))
    device_class = str(attributes.get("device_class") or "")
    base = {"camera": place, "entity": entity_id, "name": name, "source": "home_assistant"}
    events: list[tuple[str, dict[str, Any]]] = [
        ("home.sensor", {**base, "state": state, "previous": previous, "device_class": device_class})]
    domain = entity_id.split(".", 1)[0]
    turned_on = state == "on"
    if is_doorbell(entity_id, attributes) and (turned_on or domain == "event"):
        events.append(("doorbell.pressed", base))
    elif turned_on and (device_class in _PERSON_CLASSES or re.search(r"person|people|visitor", entity_id)):
        events.append(("vision.person", {**base, "count": 1}))
    elif turned_on and device_class == "motion":
        events.append(("vision.motion", base))
    return events


def _watched(entity: dict[str, Any], explicit: set[str]) -> bool:
    entity_id = str(entity.get("entity_id", ""))
    if explicit:
        return entity_id in explicit
    attrs = entity.get("attributes") or {}
    if is_doorbell(entity_id, attrs):
        return True
    return entity_id.startswith("binary_sensor.") and attrs.get("device_class") in _WATCHED_CLASSES


class HomeSensorWatcher:
    def __init__(self, bridge: Any, events: Any, interval: float = 5.0, watch: set[str] | None = None):
        self.bridge = bridge
        self.events = events
        self.interval = interval
        env = os.environ.get("HOME_ASSISTANT_WATCH", "")
        self.explicit = watch if watch is not None else {e.strip() for e in env.split(",") if e.strip()}
        self._states: dict[str, str] = {}
        self._task: asyncio.Task | None = None
        self.error = ""
        self.watching = 0
        self.recent: list[dict[str, Any]] = []

    async def poll(self) -> list[tuple[str, dict[str, Any]]]:
        """One poll; returns the events raised. The first poll only learns states."""
        try:
            states = await self.bridge.states()
        except Exception as exc:  # noqa: BLE001 - Home Assistant restarting etc.
            self.error = str(exc)[:200]
            return []
        self.error = ""
        first = not self._states
        raised: list[tuple[str, dict[str, Any]]] = []
        watched = [s for s in states if _watched(s, self.explicit)]
        self.watching = len(watched)
        for entity in watched:
            entity_id = str(entity.get("entity_id"))
            state = str(entity.get("state", ""))
            previous = self._states.get(entity_id)
            self._states[entity_id] = state
            if first or previous is None:
                continue
            for event_type, payload in classify(entity_id, state, previous, entity.get("attributes") or {}):
                raised.append((event_type, payload))
                try:
                    await self.events.emit(event_type, payload)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("sensor event failed: %s", exc)
        if raised:
            now = time.time()
            self.recent = ([{"type": t, **p, "at": now} for t, p in raised] + self.recent)[:20]
        return raised

    async def run(self) -> None:
        while True:
            await self.poll()
            await asyncio.sleep(self.interval)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._task = None

    def status(self) -> dict[str, Any]:
        return {"running": self._task is not None and not self._task.done(), "watching": self.watching,
                "explicit": sorted(self.explicit), "error": self.error, "recent": self.recent[:10]}
