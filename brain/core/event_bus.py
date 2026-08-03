import logging
import queue
from typing import Callable, Any, Dict

class EventBus:
    """
    A lightweight, in-memory Event Bus for system observability.
    Decouples the Core Engine from the Dashboard.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance.subscribers = []
            cls._instance.history = [] # Optional: Verification/Replay
        return cls._instance

    def subscribe(self, callback: Callable[[str, Dict[str, Any]], None]):
        """
        Subscribe a callback function to receive events.
        Callback signature: (event_type: str, payload: dict)
        """
        self.subscribers.append(callback)

    def emit(self, event_type: str, payload: Dict[str, Any]):
        """
        Broadcast an event to all subscribers.
        Safe against subscriber errors to prevent crashing the Engine.
        """
        # Store verification history (capped)
        self.history.append((event_type, payload))
        if len(self.history) > 100:
            self.history.pop(0)

        for callback in self.subscribers:
            try:
                callback(event_type, payload)
            except Exception as e:
                # Do not let dashboard errors affect the brain
                print(f"[EventBus] Subscriber error: {e}")

# Global Accessor
bus = EventBus()
