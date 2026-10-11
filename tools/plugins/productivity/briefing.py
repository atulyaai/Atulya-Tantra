"""Morning briefing: weather, headlines, and today's meetings, written by the model with tools.

Configured with ATULYA_BRIEFING_CITY and ATULYA_BRIEFING_TIME (HH:MM, local time;
empty disables the scheduled Telegram delivery). The WebUI asks for it on the
first visit of the day.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path


def briefing_city() -> str:
    return os.environ.get("ATULYA_BRIEFING_CITY", "").strip()


def briefing_time() -> tuple[int, int] | None:
    match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", os.environ.get("ATULYA_BRIEFING_TIME", "").strip())
    return (int(match.group(1)), int(match.group(2))) if match else None


def briefing_prompt(city: str) -> str:
    today = datetime.now().astimezone().strftime("%A %d %B")
    where = f"for {city}" if city else "(ask which city if weather is needed and none is saved)"
    return (
        f"Give me my morning briefing for {today} {where}. Use your tools: current weather, the top five "
        "headlines, and my meetings today (say if there are none). Start with a one-line greeting, keep it under "
        "120 words, plain text, no markdown tables. Report any part that fails as unavailable."
    )


class BriefingLog:
    """Remembers which day each recipient last got a briefing, so restarts don't resend."""

    def __init__(self, data_dir: Path) -> None:
        self._path = data_dir / "briefings.json"

    def _load(self) -> dict:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def sent_today(self, recipient: str) -> bool:
        return self._load().get(recipient) == datetime.now().astimezone().date().isoformat()

    def mark(self, recipient: str) -> None:
        data = self._load()
        data[recipient] = datetime.now().astimezone().date().isoformat()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data), encoding="utf-8")
