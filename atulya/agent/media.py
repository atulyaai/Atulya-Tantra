"""Music and media: play songs, and control whatever is playing."""
from __future__ import annotations

import asyncio
import platform

from atulya.agent.tools import open_website, tool

# Windows virtual-key codes for the media keys.
_VK = {"play_pause": 0xB3, "next": 0xB0, "previous": 0xB1, "stop": 0xB2,
       "volume_up": 0xAF, "volume_down": 0xAE, "mute": 0xAD}


def _press(vk: int, times: int = 1) -> None:
    import ctypes

    for _ in range(times):
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)  # type: ignore[attr-defined]
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)  # type: ignore[attr-defined]


@tool("play_music", "Play a song, artist or playlist by searching a music site in the browser", {
    "query": {"type": "string", "description": "Song, artist or mood, e.g. 'arijit singh' or 'lofi beats'"},
    "service": {"type": "string", "description": "'youtube' or 'spotify'", "default": "youtube"},
})
async def play_music(query: str, service: str = "youtube") -> str:
    service = service.strip().lower()
    if service not in ("youtube", "spotify"):
        service = "youtube"
    if not query.strip():
        return "Tell me what to play."
    return await open_website(service, query)


@tool("media_control", "Control playback on this computer: play_pause, next, previous, stop, volume_up, volume_down, mute", {
    "action": {"type": "string", "description": "play_pause | next | previous | stop | volume_up | volume_down | mute"},
    "amount": {"type": "integer", "description": "Repeat count, for volume steps", "default": 1},
})
async def media_control(action: str, amount: int = 1) -> str:
    action = action.strip().lower().replace(" ", "_")
    if action not in _VK:
        return f"I can do: {', '.join(_VK)}."
    if platform.system() != "Windows":
        return "Media keys are only wired up on Windows so far."
    await asyncio.to_thread(_press, _VK[action], max(1, min(int(amount or 1), 20)))
    return f"Done: {action.replace('_', ' ')}."
