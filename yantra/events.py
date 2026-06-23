"""Lightweight async event bus for decoupled system events."""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

_MAX_HISTORY = 1000


@dataclass
class Event:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


EventHandler = Callable[[Event], Awaitable[None] | None]


class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._history: list[Event] = []
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._subscribers[event_type].append(handler)

    async def emit(self, event_type: str, payload: dict[str, Any] | None = None) -> Event:
        event = Event(event_type, payload or {})
        with self._lock:
            self._history.append(event)
            if len(self._history) > _MAX_HISTORY:
                self._history = self._history[-_MAX_HISTORY:]
        handlers = [*self._subscribers.get(event_type, []), *self._subscribers.get("*", [])]
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.warning("Handler %s failed for event %s: %s", handler, event_type, e)
        return event

    def history(self, limit: int = 100) -> list[Event]:
        with self._lock:
            return list(self._history[-limit:])


default_bus = EventBus()
