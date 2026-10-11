"""Clock and safe-calculator command plugin."""
from __future__ import annotations

import re

from tools.plugins.registry import PluginContext
from .calculator import calculate
from .clock import current_time


async def handle(command: str, _context: PluginContext) -> str | None:
    if re.fullmatch(r"(?:what(?:'s| is)?\s+(?:the\s+)?time(?:\s+now|\s+is\s+it)?|time(?:\s+now)?)\??", command, re.I):
        return current_time()
    calculation = re.fullmatch(r"(?:calculate|compute|what is)\s+([0-9().+*/%\-\s]+)\??", command, re.I)
    if calculation:
        try:
            return calculate(calculation.group(1).strip())
        except ValueError as exc:
            return str(exc)
    return None
