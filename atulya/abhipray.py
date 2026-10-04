"""Deterministic intent router.

Maps a natural-language command directly to a concrete registered tool and
its arguments, without relying on the LLM's function-calling. This gives
reliable action-taking ("turn on the living room light", "remind me at 5pm",
"weather in Delhi") even with a small local model whose tool-calling is
unreliable.

``route_intent`` returns a ``RoutedIntent`` only for high-confidence, concrete
commands; it returns ``None`` for everything else so the normal LLM path
handles general conversation. The routed tool names and argument shapes match
the tools registered in ``atulya.kriya``.
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


_AMT = r"(?:rs\.?|₹|inr)?\s*([\d,]+(?:\.\d+)?)\s*(?:rupees|rs|inr)?"


def _money_intent(t: str) -> RoutedIntent | None:
    m = re.search(r"\b(?:i |we )?(?:spent|paid|bought|used)\s+" + _AMT + r"\s+(?:on|for|at|in)\s+(.+)$", t)
    if m:
        note = m.group(2).strip(" .")
        when = "yesterday" if re.search(r"\byesterday\b", note) else ""
        note = re.sub(r"\b(?:today|yesterday)\b", "", note).strip(" .")
        return RoutedIntent("expense_add", {"amount": float(m.group(1).replace(",", "")), "note": note, **({"date": when} if when else {})})
    m = re.search(r"\bhow much (?:did|have|do) (?:i|we) (?:spend|spent)\b(.*)$", t)
    if m:
        tail = m.group(1)
        period = ("today" if "today" in tail else "last_month" if "last month" in tail else "week" if "week" in tail
                  else "year" if "year" in tail else "month")
        cat = re.search(r"\b(?:on|for)\s+([a-z ]+?)(?:\s+(?:this|last|today)\b.*)?$", tail)
        return RoutedIntent("expense_summary", {"period": period, **({"category": cat.group(1).strip()} if cat else {})})
    m = re.search(r"\b(?:set|make)\s+(?:a |my )?budget\s+(?:for|of)\s+([a-z ]+?)\s+(?:to|at|of)?\s*" + _AMT + r"$", t)
    if m:
        return RoutedIntent("budget_set", {"category": m.group(1).strip(), "amount": float(m.group(2).replace(",", ""))})
    m = re.search(r"\badd (?:a )?bill\s+(?:for\s+)?([a-z ]+?)\s+" + _AMT + r"\s+(?:due\s+)?(?:on\s+)?(?:the\s+)?(\d{1,2})", t)
    if m:
        return RoutedIntent("bill_add", {"name": m.group(1).strip(), "amount": float(m.group(2).replace(",", "")), "due_day": int(m.group(3))})
    if re.search(r"\bbills?\b.{0,20}\bdue\b|\bdue\b.{0,20}\bbills?\b|\bwhat bills\b", t):
        return RoutedIntent("bills_due", {})
    m = re.search(r"\b(?:i )?paid (?:the |my )?([a-z ]+?) bill\b", t)
    if m:
        return RoutedIntent("bill_paid", {"name": m.group(1).strip()})
    if re.search(r"\b(?:check|read|scan|import|update|add|pull|get)\b.{0,30}\b(?:email|emails|mail|inbox)\b.{0,30}\b(?:spend|spending|expenses?|bank|transactions?|alerts?)\b"
                 r"|\b(?:spend|spending|expenses?|transactions?|bank alerts?)\b.{0,30}\bfrom (?:my )?(?:email|emails|mail|inbox)\b", t):
        return RoutedIntent("expenses_from_email", {})
    if re.search(r"\bundo (?:the |that |my )?(?:last )?(?:expense|import|entry)\b", t):
        return RoutedIntent("expense_undo", {})
    return None


def _device_admin_intent(t: str) -> RoutedIntent | None:
    if re.search(r"\b(?:scan|search|look|discover|find)\b.{0,25}\b(?:devices?|tvs?|smart home|network)\b", t) and not re.search(r"\b(?:file|wifi password)\b", t):
        return RoutedIntent("device_discover", {})
    if re.search(r"\b(?:what|which|list|show)\b.{0,25}\bdevices?\b.{0,20}\b(?:do i have|have i|you control|can you control|are there|added)\b|^(?:list|show) (?:my )?devices$", t):
        return RoutedIntent("device_list", {})
    m = re.match(r"add (?:number |device |#)?(\d{1,2}|[0-9a-f]{8})(?: as (.+))?$", t)
    if m:
        return RoutedIntent("device_add", {"which": m.group(1), **({"name": m.group(2).strip()} if m.group(2) else {})})
    m = re.match(r"(?:forget|remove|delete) (?:the |my )?(.+?)(?: device)?$", t)
    if m:
        name = m.group(1).strip()
        known = False
        try:
            from atulya.upakaran_hub import get_hub

            known = get_hub().find(name) is not None
        except Exception:  # noqa: BLE001
            pass
        if known or re.search(r"\bdevice\b", t):      # "forget the kitchen tv" only when that really is one of your devices
            return RoutedIntent("device_remove", {"device": name})
    m = re.match(r"approve (?:the )?(?:device )?proposal ([0-9a-f]{6})$", t)
    if m:
        return RoutedIntent("device_profile_approve", {"proposal": m.group(1)})
    m = re.match(r"learn (?:this |the )?(?:device|tv|speaker|light|thing)(?: at| on)? (\d{1,3}(?:\.\d{1,3}){3}|[\w.-]+\.local)$", t)
    if m:
        return RoutedIntent("device_learn", {"host": m.group(1)})
    return None


def _device_intent(t: str) -> RoutedIntent | None:
    try:
        from atulya.upakaran_hub import get_hub

        hit = get_hub().resolve(t)
    except Exception:  # noqa: BLE001 - a broken device file must never break the assistant
        return None
    if hit is None:
        return None
    device, action, args = hit
    cap = device.cap(action)
    arguments: dict[str, Any] = {"device": device.name, "action": action}
    if cap and cap.params:
        pname = next(iter(cap.params))
        if pname in args:
            arguments["value"] = str(args[pname])
    if "times" in args:
        arguments["times"] = args["times"]
    return RoutedIntent("device_do", arguments, confidence=0.9)


def route_intent(text: str) -> RoutedIntent | None:
    """Return a concrete tool routing for a clear command, else None."""
    if not text or not text.strip():
        return None
    t = text.strip().lower()

    # --- Your devices (anything added through the device fabric), understood from their own capabilities ---
    device_hit = _device_intent(t)
    if device_hit is not None:
        return device_hit
    admin = _device_admin_intent(t)
    if admin is not None:
        return admin

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

    # --- Money: "I spent 500 on groceries", "how much did I spend this month", "bills due" ----
    money_intent = _money_intent(t)
    if money_intent is not None:
        return money_intent

    # --- Websites: "open youtube", "play lofi on youtube", "google cricket score"
    web = _website_intent(t)
    if web is not None:
        return web

    # --- Briefing, music and media keys ------------------------------------
    media = _media_intent(t)
    if media is not None:
        return media

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
    if re.search(r"\b(what'?s|whats|what is|show|list).{0,20}\b(calendar|schedule|agenda)\b", t):
        days = 1 if re.search(r"\btoday\b", t) else 2 if re.search(r"\btomorrow\b", t) else 7
        return RoutedIntent("calendar_list", {"days": days} if days != 7 else {})
    scheduled = _schedule_intent(text.strip(), t)
    if scheduled is not None:
        return scheduled

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
    from atulya.kriya import execute_tool

    return await execute_tool(routed.tool, **routed.arguments)


_WHEN_RE = re.compile(r"\b(?:today|tonight|tomorrow|next \w+day|on \w+day|(?:mon|tues|wednes|thurs|fri|satur|sun)day"
                      r"|at \d|in \d+ (?:minute|hour|day))")


def _schedule_intent(original: str, t: str) -> RoutedIntent | None:
    """ "schedule a call with Rahul tomorrow at 3pm" -> calendar_add(title, date)."""
    verb = re.search(r"\b(?:schedule|book)\b|\b(?:add|put|create)\b(?=.*\b(?:calendar|meeting|event|appointment)\b)", t)
    if not verb:
        return None
    when = _WHEN_RE.search(t, verb.end())
    if not when:
        return None  # no time given: let the brain ask
    same = len(original) == len(t)
    title = (original if same else t)[verb.end():when.start()]
    title = re.sub(r"^\s*(?:a|an|my|the|in)\s+", "", title.strip(), flags=re.I)
    title = re.sub(r"\s+(?:to|on|in)\s+(?:my\s+)?calendar\s*$", "", title, flags=re.I).strip(" ,.")
    date = t[when.start():]
    duration = 60
    d = re.search(r"\bfor (?:(\d+) (minute|min|hour)s?|an? (hour|half hour))\b", date)
    if d:
        duration = (int(d.group(1)) * (60 if d.group(2) == "hour" else 1)) if d.group(1) else (
            60 if d.group(3) == "hour" else 30)
        date = date[:d.start()] + date[d.end():]
    date = re.sub(r"\s+(?:to|on|in)\s+(?:my\s+)?calendar\b", "", date).strip(" ,.")
    if not title:
        return None
    args: dict[str, Any] = {"title": title[:1].upper() + title[1:], "date": date}
    if duration != 60:
        args["duration_minutes"] = duration
    return RoutedIntent("calendar_add", args, confidence=0.85)


_POLITE = r"(?:(?:hey |ok |okay )?atulya[, ]*)?(?:(?:can|could|would) you |please )?"


def _website_intent(t: str) -> RoutedIntent | None:
    from atulya.kriya import WEBSITES  # lazy: tools.py is heavier than this module

    t = t.strip(" .!?")
    sites = "|".join(re.escape(name) for name in sorted(WEBSITES, key=len, reverse=True))
    # "play X on youtube" / "search X on google" / "search for X on youtube"
    m = re.fullmatch(_POLITE + rf"(?:play|search(?: for)?|find|look up)\s+(.+?)\s+(?:on|in)\s+({sites})", t)
    if m:
        return RoutedIntent("open_website", {"site": m.group(2), "query": m.group(1)})
    # "search youtube for X"
    m = re.fullmatch(_POLITE + rf"search\s+({sites})\s+for\s+(.+)", t)
    if m:
        return RoutedIntent("open_website", {"site": m.group(1), "query": m.group(2)})
    # "google X"
    m = re.fullmatch(_POLITE + r"google\s+(.+)", t)
    if m and m.group(1) not in WEBSITES:
        return RoutedIntent("open_website", {"site": "google", "query": m.group(1)})
    # "open youtube" / "launch gmail" / "go to wikipedia"
    m = re.fullmatch(_POLITE + rf"(?:open|launch|start|go to|show me)\s+(?:the\s+)?({sites})(?:\s+(?:website|site|app))?(?:\s+please)?", t)
    if m:
        return RoutedIntent("open_website", {"site": m.group(1)})
    return None


_MEDIA_KEYS = (
    (r"(?:pause|resume|play|stop)(?: the)?(?: music| song| track| video)?", "play_pause"),
    (r"(?:next|skip)(?: the)?(?: song| track)?", "next"),
    (r"(?:previous|last|go back)(?: song| track)?", "previous"),
    (r"(?:turn )?(?:volume up|louder|turn it up|raise the volume)", "volume_up"),
    (r"(?:turn )?(?:volume down|quieter|softer|turn it down|lower the volume)", "volume_down"),
    (r"mute|unmute", "mute"),
)


def _media_intent(t: str) -> RoutedIntent | None:
    t = t.strip(" .!?")
    t = re.sub(r"^(?:(?:hey |ok |okay )?atulya[, ]*)?(?:(?:can|could|would) you |please )?", "", t).strip()
    if re.fullmatch(r"(?:good morning|morning briefing|brief me|(?:give me |what(?:'s| is) )?(?:my |the )?(?:morning )?(?:briefing|brief|day))", t):
        return RoutedIntent("morning_briefing", {})
    if re.fullmatch(r"(?:what (?:all )?(?:can|do) you (?:do|help (?:me )?with)(?: for me)?|what (?:are|is) your (?:abilities|capabilities|features|skills)|"
                    r"(?:tell me )?what (?:all )?you can do|help|what can i ask you|aap kya kar sakte ho|तुम क्या कर सकते हो|आप क्या कर सकते हैं)", t):
        return RoutedIntent("what_can_you_do", {})
    for pattern, action in _MEDIA_KEYS:
        if re.fullmatch(pattern + r"(?: please)?", t):
            return RoutedIntent("media_control", {"action": action})
    m = re.fullmatch(r"(?:play|put on)\s+(.+?)(?: please)?", t)
    if m and m.group(1) not in ("it", "that", "music", "something"):
        return RoutedIntent("play_music", {"query": m.group(1)})
    if t in ("play music", "play something"):
        return RoutedIntent("media_control", {"action": "play_pause"})
    return None


def _extract_location(t: str) -> str | None:
    """Pull a location out of 'weather in X' / 'forecast for X' phrasing."""
    m = re.search(r"\b(?:in|for|at)\s+([a-z][a-z .'-]+)$", t)
    if m:
        loc = m.group(1).strip(" .")
        # Trim trailing filler words.
        loc = re.sub(r"\b(today|tomorrow|now|please|right now)\b", "", loc).strip(" .")
        return loc or None
    return None
