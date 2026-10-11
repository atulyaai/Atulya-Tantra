"""Clock and safe-calculator command plugin."""
from __future__ import annotations

import re

from tools.plugins.registry import PluginContext
from .calculator import calculate
from .clock import current_time


_TIME = re.compile(r"(?:hey |ok )?(?:atulya[, ]+)?(?:what(?:'s| is)?|tell me)\s+(?:the\s+)?(?:current\s+)?time"
                   r"(?:\s+(?:is it|now|right now|please))*(?:\s+in one (?:short )?sentence)?\s*[?.!]*", re.I)
_DATE = re.compile(r"(?:hey |ok )?(?:atulya[, ]+)?(?:what(?:'s| is)?|tell me)\s+(?:the\s+|today'?s\s+)?"
                   r"(?:date|day)(?:\s+(?:is it|today|now|please))*\s*[?.!]*|what day is (?:it|today)\s*[?.!]*", re.I)
_THANKS = re.compile(r"(?:thanks|thank you|thx|shukriya|dhanyavad)(?:\s+(?:atulya|so much|a lot))*\s*[!.]*", re.I)


async def handle(command: str, _context: PluginContext) -> str | None:
    from datetime import datetime

    if _TIME.fullmatch(command):
        return datetime.now().astimezone().strftime("It's %I:%M %p.").replace(" 0", " ")
    if _DATE.fullmatch(command):
        return datetime.now().astimezone().strftime("Today is %A, %d %B %Y.").replace(" 0", " ")
    if _THANKS.fullmatch(command):
        return "You're welcome."
    if re.fullmatch(r"(?:what(?:'s| is)?\s+(?:the\s+)?time(?:\s+now|\s+is\s+it)?|time(?:\s+now)?)\??", command, re.I):
        return current_time()
    calculation = re.fullmatch(r"(?:calculate|compute|what is)\s+([0-9().+*/%\-\s]+)\??", command, re.I)
    if calculation:
        try:
            return calculate(calculation.group(1).strip())
        except ValueError as exc:
            return str(exc)
    return None
