import asyncio
import time

from atulya import sahayak as calendar_watch, kriya as tools


class _Bus:
    def __init__(self):
        self.events = []

    async def emit(self, kind, payload):
        self.events.append((kind, payload))


def test_announces_soon_event_once(monkeypatch):
    monkeypatch.setattr(tools, "_google", lambda: None)
    monkeypatch.setattr(tools, "_CALENDAR", {
        "a": {"id": "a", "title": "Standup", "time": time.time() + 300},
        "b": {"id": "b", "title": "Later", "time": time.time() + 7200},
    })
    bus = _Bus()

    async def run():
        task = asyncio.create_task(calendar_watch.watch_calendar(bus, interval=0.05, lead_minutes=10))
        await asyncio.sleep(0.2)
        task.cancel()

    asyncio.run(run())
    assert [e[0] for e in bus.events] == ["calendar.soon"]
    assert bus.events[0][1]["title"] == "Standup"
