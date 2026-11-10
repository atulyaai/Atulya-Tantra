"""Proactive alerts the owner did not ask for, with quiet hours, per-kind switches and a reason.

Every alert carries the fact that caused it, so "why did you tell me this?" can be answered from
the record instead of from the model's memory. Nothing here invents a fact: each alert is built
from a measurement (disk, battery), a calendar row, or a stored goal.

Delivery is the caller's job (the routine loop sends to the phone inbox and Telegram); this module
only decides what is due, respects the owner's switches, and dedupes so a retry cannot repeat a
notice.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, time as clock_time
from pathlib import Path

KINDS = ("disk", "battery", "rain", "calendar_soon", "goal_followup")
KIND_LABELS = {
    "disk": "Disk almost full",
    "battery": "Battery low",
    "rain": "Rain coming",
    "calendar_soon": "Event starting soon",
    "goal_followup": "Unfinished goal",
}
DISK_WARN = 90.0
BATTERY_LOW = 15.0
CALENDAR_WINDOW = 15 * 60
GOAL_QUIET_HOURS = 6
GOAL_MAX_AGE = 3 * 24 * 3600
RAIN_ALERT_PROBABILITY = 40.0
UNFINISHED = frozenset({"planning", "running", "waiting_approval", "interrupted"})

DEFAULT_SETTINGS = {
    "enabled": True,
    # Quiet hours wrap past midnight: nothing is sent between 22:30 and 07:00.
    "quiet_hours": {"start": "22:30", "end": "07:00"},
    "kinds": {kind: True for kind in KINDS},
}


@dataclass(frozen=True)
class Alert:
    kind: str
    title: str
    body: str
    reason: str
    dedupe: str

    def as_dict(self) -> dict:
        return asdict(self)


def _settings_path(data_dir) -> Path:
    return Path(data_dir) / "proactive.json"


def _parse_clock(value: str) -> clock_time | None:
    if not isinstance(value, str):
        return None
    parts = value.strip().split(":")
    if len(parts) != 2:
        return None
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return clock_time(hour, minute)


def normalize_settings(raw: dict | None) -> dict:
    """Merge whatever is stored over the defaults, dropping anything that is not valid."""
    settings = {
        "enabled": DEFAULT_SETTINGS["enabled"],
        "quiet_hours": dict(DEFAULT_SETTINGS["quiet_hours"]),
        "kinds": dict(DEFAULT_SETTINGS["kinds"]),
    }
    if not isinstance(raw, dict):
        return settings
    if isinstance(raw.get("enabled"), bool):
        settings["enabled"] = raw["enabled"]
    quiet = raw.get("quiet_hours")
    if isinstance(quiet, dict):
        for edge in ("start", "end"):
            parsed = _parse_clock(quiet.get(edge))
            if parsed is not None:
                settings["quiet_hours"][edge] = parsed.strftime("%H:%M")
    kinds = raw.get("kinds")
    if isinstance(kinds, dict):
        for kind in KINDS:
            if isinstance(kinds.get(kind), bool):
                settings["kinds"][kind] = kinds[kind]
    return settings


def load_settings(data_dir) -> dict:
    try:
        raw = json.loads(_settings_path(data_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = None
    return normalize_settings(raw)


def save_settings(data_dir, changes: dict) -> dict:
    """Apply a partial change and persist it. Unknown keys are ignored, bad clocks rejected."""
    if not isinstance(changes, dict):
        raise ValueError("settings must be an object")
    current = load_settings(data_dir)
    for key in ("enabled",):
        if key in changes:
            if not isinstance(changes[key], bool):
                raise ValueError(f"{key} must be true or false")
            current[key] = changes[key]
    if "quiet_start" in changes or "quiet_end" in changes:
        for edge, key in (("start", "quiet_start"), ("end", "quiet_end")):
            if key in changes:
                parsed = _parse_clock(changes[key])
                if parsed is None:
                    raise ValueError(f"{key} must be HH:MM")
                current["quiet_hours"][edge] = parsed.strftime("%H:%M")
    for kind in KINDS:
        if kind in changes:
            if not isinstance(changes[kind], bool):
                raise ValueError(f"{kind} must be true or false")
            current["kinds"][kind] = changes[kind]
    path = _settings_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2), encoding="utf-8")
    return current


def in_quiet_hours(now: datetime, quiet: dict) -> bool:
    start = _parse_clock(quiet.get("start") if isinstance(quiet, dict) else None)
    end = _parse_clock(quiet.get("end") if isinstance(quiet, dict) else None)
    if start is None or end is None or start == end:
        return False
    current = now.time()
    if start < end:
        return start <= current < end
    return current >= start or current < end


def _event_start(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.astimezone()


def build_alerts(
    now: datetime,
    *,
    disk_percent: float | None = None,
    battery_percent: float | None = None,
    battery_charging: bool | None = None,
    rain: dict | None = None,
    events=(),
    goals=(),
) -> list[Alert]:
    """Every alert that is due right now, before the owner's switches are applied."""
    today = now.date().isoformat()
    alerts: list[Alert] = []

    if disk_percent is not None and disk_percent >= DISK_WARN:
        used = float(disk_percent)
        alerts.append(Alert(
            "disk", "Disk almost full",
            f"The server disk is {used:.0f}% full. Free space or move old backups.",
            f"Disk usage is {used:.0f}%, which is at or above the {DISK_WARN:.0f}% threshold.",
            f"disk:{today}"))

    if battery_percent is not None and battery_percent <= BATTERY_LOW and not battery_charging:
        level = float(battery_percent)
        alerts.append(Alert(
            "battery", "Battery low",
            f"Battery is at {level:.0f}% and not charging. Plug in soon.",
            f"The battery reported {level:.0f}%, at or below the {BATTERY_LOW:.0f}% threshold, "
            "and the device is not charging.",
            f"battery:{today}"))

    if isinstance(rain, dict):
        try:
            probability = float(rain.get("probability"))
            minutes = float(rain.get("minutes"))
        except (TypeError, ValueError):
            probability = minutes = None
        at = str(rain.get("at") or "")[:5]
        city = str(rain.get("city") or "your area")[:80]
        if probability is not None and minutes is not None and probability >= RAIN_ALERT_PROBABILITY:
            at = at or f"{int(max(0, minutes) // 60):02d}:{int(max(0, minutes) % 60):02d}"
            when = now.astimezone().replace(hour=int(at[:2]), minute=int(at[3:5])) if at else now
            alerts.append(Alert(
                "rain", f"Rain in {max(0, round(minutes))} minutes" if minutes > 0 else "Rain is likely now",
                f"{round(probability)}% chance of rain in {city}{f' around {at}.' if at else '.'}",
                f"Open-Meteo forecasts {round(probability)}% chance of rain in {city}"
                + (f", expected around {when.strftime('%H:%M')}." if at else "."),
                f"rain:{str(rain.get('key') or str(today) + ':' + at)}"))

    for index, event in enumerate(events or ()):
        start = _event_start(event.get("starts_at") if isinstance(event, dict) else None)
        if start is None:
            continue
        ahead = (start - now).total_seconds()
        if not 0 <= ahead <= CALENDAR_WINDOW:
            continue
        title = str(event.get("title") or "Event")[:120]
        minutes = max(0, round(ahead / 60))
        key = str(event.get("id") or start.isoformat())
        alerts.append(Alert(
            "calendar_soon", f"In {minutes} minutes: {title}",
            f"{title} starts at {start.astimezone().strftime('%H:%M')}.",
            f"Your calendar has \"{title}\" starting at {start.astimezone().strftime('%H:%M')}, "
            f"{minutes} minutes from now.",
            f"calendar:{key}:{today}"))

    for goal in goals or ():
        if not isinstance(goal, dict):
            continue
        status = str(goal.get("status") or "")
        if status not in UNFINISHED:
            continue
        updated = goal.get("updated")
        try:
            updated = float(updated)
        except (TypeError, ValueError):
            continue
        idle = now.timestamp() - updated
        if idle < GOAL_QUIET_HOURS * 3600 or idle > GOAL_MAX_AGE:
            continue
        text = str(goal.get("goal") or "goal")[:160]
        hours = int(idle // 3600)
        alerts.append(Alert(
            "goal_followup", f"Still open: {text}",
            f"This goal has been {status.replace('_', ' ')} for {hours} hours. "
            "Open Atulya to continue it or drop it.",
            f"The goal \"{text}\" has been {status.replace('_', ' ')} for {hours} hours, "
            "so it is due for a follow-up.",
            f"goal:{goal.get('id') or text}:{today}"))

    return alerts


def explain(data_dir, user_id: str = "admin", limit: int = 5) -> list[dict]:
    """Recent proactive notices with the fact that caused each one."""
    from atulya.inbox import Inbox

    rows = Inbox(data_dir).recent(user_id, limit)
    return [row for row in rows if row.get("reason")]


def tick(data_dir, now: datetime | None = None, *, user_id: str = "admin", deliver=None, **snapshot) -> list[dict]:
    """Send what is due: quiet hours and the owner's switches are applied, duplicates skipped."""
    now = now or datetime.now().astimezone()
    settings = load_settings(data_dir)
    if not settings["enabled"]:
        return []
    if in_quiet_hours(now, settings["quiet_hours"]):
        return []
    from atulya.inbox import Inbox

    inbox = Inbox(data_dir)
    sent: list[dict] = []
    for alert in build_alerts(now, **snapshot):
        if not settings["kinds"].get(alert.kind, True):
            continue
        notice_id = inbox.add_new(user_id, alert.title, alert.body, alert.kind,
                                  dedupe=alert.dedupe, reason=alert.reason)
        if notice_id is None:
            continue
        if deliver is not None:
            try:
                deliver(alert)
            except Exception:  # noqa: BLE001 - a failed channel must not drop the recorded alert
                pass
        sent.append(alert.as_dict())
    return sent


def snapshot_providers(data_dir) -> dict:
    """Real measurements for tick(); each provider degrades to None instead of raising."""
    values: dict = {"disk_percent": None, "battery_percent": None,
                    "battery_charging": None, "rain": None, "events": (), "goals": ()}
    try:
        import shutil

        usage = shutil.disk_usage("/")
        values["disk_percent"] = usage.used / usage.total * 100 if usage.total else None
    except OSError:
        pass
    try:
        import psutil

        battery = psutil.sensors_battery()
        if battery is not None:
            values["battery_percent"] = float(battery.percent)
            values["battery_charging"] = bool(battery.power_plugged)
    except Exception:  # noqa: BLE001 - no battery sensor is normal on a server
        pass
    try:
        from atulya.goal_runner import GoalStore

        values["goals"] = GoalStore(data_dir).list_for("admin", 20)
    except Exception:  # noqa: BLE001 - a missing goal store means no follow-ups yet
        pass
    return values


def seconds_since(epoch, now: float | None = None) -> float:
    return (now if now is not None else time.time()) - float(epoch)
