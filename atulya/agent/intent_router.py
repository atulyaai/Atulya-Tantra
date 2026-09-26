"""Deterministic intent router.

Maps a natural-language command directly to a concrete registered tool and
its arguments, without relying on the LLM's function-calling. This gives
reliable action-taking ("turn on the living room light", "remind me at 5pm",
"weather in Delhi") even with a small local model whose tool-calling is
unreliable.

``route_intent`` returns a ``RoutedIntent`` only for high-confidence, concrete
commands; it returns ``None`` for everything else so the normal LLM path
handles general conversation. The routed tool names and argument shapes match
the tools registered in ``atulya.agent.tools``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RoutedIntent:
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.9


# Spoken device name -> registered device_id (see tools.py _HOME_DEVICES).
_DEVICE_ALIASES = {
    "living room light": "living_room_light",
    "living room": "living_room_light",
    "kitchen light": "kitchen_light",
    "kitchen": "kitchen_light",
    "bedroom light": "bedroom_light",
    "bedroom": "bedroom_light",
    "thermostat": "thermostat",
    "front door": "front_door",
    "door": "front_door",
}


def _match_device(text: str) -> str | None:
    # Prefer the longest alias so "living room light" beats "living room".
    for alias in sorted(_DEVICE_ALIASES, key=len, reverse=True):
        if alias in text:
            return _DEVICE_ALIASES[alias]
    return None


def route_intent(text: str) -> RoutedIntent | None:
    """Return a concrete tool routing for a clear command, else None."""
    if not text or not text.strip():
        return None
    t = text.strip().lower()

    # --- Senses: "is anyone at the door?" ----------------------------------
    if not re.search(r"\b(?:lock|unlock|open|close|turn|switch)\b", t) and (
            re.match(r"(?:is|are|was|has|did|who|who's|whos|any|anyone|anybody|someone|somebody|check)\b", t)
            and re.search(r"\b(?:anyone|anybody|someone|somebody|who'?s|who is|who was)\b", t)
            and re.search(r"\b(?:door|outside|porch|gate|camera|cameras)\b", t)
            or re.search(r"\bwhat (?:do|can) (?:the |my )?cameras? see\b|\bany (?:motion|movement)\b", t)):
        return RoutedIntent("camera_status", {})

    # --- Home / device control ---------------------------------------------
    # Lock / unlock the door
    if re.search(r"\b(lock|unlock)\b", t) and ("door" in t or "lock" in t):
        device = _match_device(t) or "front_door"
        action = "unlock" if "unlock" in t else "lock"
        return RoutedIntent("home_control", {"device_id": device, "action": action})

    # Set thermostat to N degrees
    m = re.search(r"(?:thermostat|temperature|temp).*?(\d{1,2})", t)
    if m and ("thermostat" in t or "temperature" in t or "temp" in t) and re.search(r"\b(set|change|make)\b", t):
        return RoutedIntent(
            "home_control",
            {"device_id": "thermostat", "action": "set_temperature", "value": m.group(1)},
        )

    # Turn on/off a light or device
    m = re.search(r"\b(turn|switch)\s+(on|off)\b", t)
    if m:
        device = _match_device(t)
        if device:
            return RoutedIntent(
                "home_control",
                {"device_id": device, "action": m.group(2)},  # 'on' / 'off'
            )

    # --- Reminders ---------------------------------------------------------
    if re.search(r"\bremind me\b", t) or re.search(r"\bset a? reminder\b", t):
        # Split the time clause from the message where possible.
        time_str = "in 5 minutes"
        tm = re.search(r"\b(in\s+\d+\s+\w+|at\s+[\d: ]+\s*(?:am|pm)?|tomorrow[\w: ]*)", t)
        if tm:
            time_str = tm.group(1).strip()
        # Message = text after "remind me to" / "remind me", minus the time clause.
        msg = re.sub(r".*remind me\s*(to)?\s*", "", t, count=1)
        if tm:
            msg = msg.replace(tm.group(1), "")
        msg = re.sub(r"\bset a? reminder\b", "", msg).strip(" .,")
        return RoutedIntent(
            "set_reminder",
            {"message": msg or "reminder", "time_str": time_str},
            confidence=0.85,
        )

    # --- Weather / forecast ------------------------------------------------
    if "forecast" in t:
        loc = _extract_location(t)
        if loc:
            return RoutedIntent("get_forecast", {"location": loc})
    if "weather" in t:
        loc = _extract_location(t)
        if loc:
            return RoutedIntent("get_weather", {"location": loc})

    # --- Time --------------------------------------------------------------
    if re.search(r"\bwhat(?:'s| is)? the time\b", t) or re.search(r"\bwhat time is it\b", t) or t in ("time", "current time"):
        tz = ""
        mtz = re.search(r"\bin\s+([a-z /_]+)$", t)
        if mtz:
            tz = mtz.group(1).strip()
        return RoutedIntent("current_time", {"timezone": tz} if tz else {})

    # --- Email -------------------------------------------------------------
    if re.search(r"\b(check|any|new|fetch|read).{0,12}\b(email|emails|inbox|mail)\b", t):
        return RoutedIntent("fetch_emails", {})

    # --- Calendar ----------------------------------------------------------
    if re.search(r"\b(what'?s|whats|show|list).{0,20}\b(calendar|schedule|agenda)\b", t):
        return RoutedIntent("calendar_list", {})

    # --- Calculator --------------------------------------------------------
    m = re.search(r"\b(?:calculate|what(?:'s| is))\s+([-\d\s.+*/()x%]+)$", t)
    if m and re.search(r"\d", m.group(1)):
        expr = m.group(1).strip().replace("x", "*")
        return RoutedIntent("calculate", {"expression": expr}, confidence=0.8)

    return None


async def route_and_execute(text: str) -> str | None:
    """If the text is a clear command, execute the matched tool and return its
    result string. Return None when nothing matches (caller should fall back to
    the LLM). Used by both the interactive agent loop and scheduled automations
    so actions are reliable regardless of the model's tool-calling ability.
    """
    routed = route_intent(text)
    if routed is None:
        return None
    # Imported lazily to avoid a circular import (tools -> intent_router).
    from .tools import execute_tool

    return await execute_tool(routed.tool, **routed.arguments)


def _extract_location(t: str) -> str | None:
    """Pull a location out of 'weather in X' / 'forecast for X' phrasing."""
    m = re.search(r"\b(?:in|for|at)\s+([a-z][a-z .'-]+)$", t)
    if m:
        loc = m.group(1).strip(" .")
        # Trim trailing filler words.
        loc = re.sub(r"\b(today|tomorrow|now|please|right now)\b", "", loc).strip(" .")
        return loc or None
    return None
