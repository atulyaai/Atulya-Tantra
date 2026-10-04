"""Event-driven proactivity — the assistant's reflexes.

Rules react to events on the bus, so Atulya acts on what *happens*, not only on
what it is told or on a clock.

Events available (wired by ``connect_sensors`` and the kernel):
  reminder.due                            a reminder's time arrived
  health.<status>                         a heartbeat check changed state
                                          (warning / error / ok / info)
  automation.completed / automation.failed
  action.executed / action.pending / action.cancelled   (from the kernel)

A rule (JSON list in ATULYA_TRIGGERS_FILE, default data/agent/triggers.json):
    {
      "id": "trg_...", "name": "Lights on when I'm reminded to read",
      "event": "reminder.due",              # type, glob ("health.*") or list of them
      "match": {"message": "read"},         # optional: payload field equals/contains
      "notify": "Reminder: {message}",      # optional: text; {field} from the payload
      "command": "turn on the living room light",  # optional: run via the kernel
      "allow_risky": false,                 # needed for unlock / email / deletes…
      "cooldown_seconds": 60, "enabled": true
    }

Safety:
  * Event payloads are never interpolated into commands — a command is exactly
    what the rule's author wrote, so an event (e.g. an email subject) can't
    smuggle in an instruction.
  * Risky commands are refused unless the rule sets ``allow_risky``.
  * Events caused by trigger-run actions don't fire further triggers, so rules
    can't loop.
"""
from __future__ import annotations

import asyncio
import fnmatch
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from atulya.cognition import safety
from atulya.cognition.planner import expand_command
from atulya.events import Event, EventBus, default_bus

logger = logging.getLogger(__name__)

TRIGGER_SOURCE = "trigger"
_DEFAULT_RULES_FILE = "data/agent/triggers.json"

# Built-in reflexes, seeded on first run (users can edit, disable or delete them).
DEFAULT_RULES: list[dict[str, Any]] = [
    {
        "id": "trg_reminder_alert",
        "name": "Reminder alerts",
        "event": "reminder.due",
        "notify": "Reminder: {message}",
        "enabled": True,
        "cooldown_seconds": 0,
    },
    {
        "id": "trg_health_alert",
        "name": "System health alerts",
        "event": ["health.warning", "health.error"],
        "notify": "System check '{check}' needs attention: {message}",
        "enabled": True,
        "cooldown_seconds": 900,
    },
    {
        "id": "trg_automation_failed",
        "name": "Automation failure alerts",
        "event": "automation.failed",
        "notify": "Automation '{job}' failed: {error}",
        "enabled": True,
        "cooldown_seconds": 300,
    },
    {
        "id": "trg_habit_nudge",
        "name": "Habit nudges",
        "event": "habit.due",
        "notify": "You usually {label} {when} — just say the word.",
        "enabled": True,
        "cooldown_seconds": 0,
    },
    {
        "id": "trg_someone_at_door",
        "name": "Someone at the door",
        "event": ["vision.person", "doorbell.pressed"],
        "match": {"camera": "door"},
        "notify": "Someone is at the {camera}.",
        "enabled": True,
        "cooldown_seconds": 60,
    },
]
# Rules shipped before new defaults were added; used to top up older rule files
# without bringing back a default the user deleted.
_ORIGINAL_DEFAULTS = {"trg_reminder_alert", "trg_health_alert", "trg_automation_failed"}

_FIELD_RE = re.compile(r"\{(\w+)\}")


def render(template: str, payload: dict[str, Any]) -> str:
    """Fill ``{field}`` placeholders from the payload (plain names only)."""
    return _FIELD_RE.sub(lambda m: str(payload.get(m.group(1), ""))[:300], template)


def _event_matches(pattern: Any, event_type: str) -> bool:
    patterns = pattern if isinstance(pattern, list) else [pattern]
    return any(isinstance(p, str) and fnmatch.fnmatchcase(event_type, p) for p in patterns)


def _payload_matches(match: dict[str, Any] | None, payload: dict[str, Any]) -> bool:
    for field, expected in (match or {}).items():
        actual = payload.get(field)
        if isinstance(actual, str) and isinstance(expected, str):
            if expected.lower() not in actual.lower():
                return False
        elif actual != expected:
            return False
    return True


class TriggerEngine:
    def __init__(
        self,
        rules_file: str | Path | None = None,
        kernel: Any = None,
        events: EventBus | None = None,
        seed_defaults: bool = True,
    ):
        self.rules_file = Path(rules_file or os.environ.get("ATULYA_TRIGGERS_FILE", _DEFAULT_RULES_FILE))
        self._kernel = kernel
        self.events = events or default_bus
        self._started = False
        self._last_fired: dict[str, float] = {}
        self._tasks: set[asyncio.Task] = set()
        if seed_defaults:
            self._seed_defaults()

    @property
    def kernel(self) -> Any:
        if self._kernel is None:
            from atulya.cognition.kernel import get_kernel

            self._kernel = get_kernel()
        return self._kernel

    def start(self) -> None:
        """Subscribe to every event on the bus (idempotent)."""
        if not self._started:
            self.events.subscribe("*", self._on_event)
            self._started = True

    def stop(self) -> None:
        if self._started:
            self.events.unsubscribe("*", self._on_event)
            self._started = False

    def _seed_defaults(self) -> None:
        """First run: every built-in rule. Later: only built-ins added since, once."""
        seeded_file = self.rules_file.with_name(self.rules_file.stem + ".seeded.json")
        if not self.rules_file.exists():
            self._save([dict(rule) for rule in DEFAULT_RULES])
        else:
            try:
                seeded = set(json.loads(seeded_file.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, TypeError):
                seeded = set(_ORIGINAL_DEFAULTS)
            rules = self.list_rules()
            have = {r.get("id") for r in rules}
            new = [dict(r) for r in DEFAULT_RULES if r["id"] not in seeded and r["id"] not in have]
            if new:
                self._save(rules + new)
        try:
            seeded_file.write_text(json.dumps(sorted(r["id"] for r in DEFAULT_RULES)), encoding="utf-8")
        except OSError:
            pass

    # ── rules ──────────────────────────────────────────────────────────────
    def list_rules(self) -> list[dict[str, Any]]:
        if not self.rules_file.exists():
            return []
        try:
            data = json.loads(self.rules_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return [rule for rule in data if isinstance(rule, dict)] if isinstance(data, list) else []

    def add_rule(self, rule: dict[str, Any]) -> dict[str, Any]:
        event = rule.get("event")
        if not event or not (isinstance(event, str) or isinstance(event, list)):
            raise ValueError("rule needs an 'event' (type, glob, or list)")
        if not (rule.get("notify") or rule.get("command")):
            raise ValueError("rule needs 'notify' and/or 'command'")
        clean = {
            "id": str(rule.get("id") or f"trg_{uuid.uuid4().hex[:10]}"),
            "name": str(rule.get("name") or rule.get("command") or rule.get("notify"))[:120],
            "event": event,
            "match": rule.get("match") if isinstance(rule.get("match"), dict) else {},
            "notify": str(rule.get("notify") or ""),
            "command": str(rule.get("command") or ""),
            "allow_risky": bool(rule.get("allow_risky", False)),
            "cooldown_seconds": max(0, int(rule.get("cooldown_seconds", 60))),
            "enabled": bool(rule.get("enabled", True)),
        }
        rules = self.list_rules()
        previous = next((r for r in rules if r.get("id") == clean["id"]), None)
        if previous:  # editing (e.g. pause/resume) keeps the rule's history
            for key in ("fire_count", "last_fired", "last_result"):
                if key in previous:
                    clean[key] = previous[key]
        rules = [r for r in rules if r.get("id") != clean["id"]]
        rules.append(clean)
        self._save(rules)
        return clean

    def remove_rule(self, rule_id: str) -> bool:
        rules = self.list_rules()
        kept = [r for r in rules if r.get("id") != rule_id]
        if len(kept) == len(rules):
            return False
        self._save(kept)
        return True

    def matching_rules(self, event: Event) -> list[dict[str, Any]]:
        # Loop guard: never react to what a trigger itself caused.
        if event.payload.get("source") == TRIGGER_SOURCE or event.type in ("trigger.fired", "notification"):
            return []
        return [
            rule for rule in self.list_rules()
            if rule.get("enabled", True)
            and _event_matches(rule.get("event"), event.type)
            and _payload_matches(rule.get("match"), event.payload)
        ]

    # ── firing ─────────────────────────────────────────────────────────────
    async def _on_event(self, event: Event) -> None:
        now = time.monotonic()
        for rule in self.matching_rules(event):
            rid = str(rule.get("id"))
            cooldown = float(rule.get("cooldown_seconds", 60) or 0)
            if cooldown and now - self._last_fired.get(rid, -1e18) < cooldown:
                continue
            self._last_fired[rid] = now
            # Run in the background: the emitter (e.g. a chat request) must not wait.
            task = asyncio.create_task(self.fire(rule, event))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def fire(self, rule: dict[str, Any], event: Event) -> dict[str, Any]:
        name = str(rule.get("name") or rule.get("id"))
        result: dict[str, Any] = {"rule": rule.get("id"), "name": name, "event": event.type,
                                  "source": TRIGGER_SOURCE}
        if rule.get("notify"):
            text = render(str(rule["notify"]), event.payload)
            await self._notify(name, text)
            result["notified"] = text

        command = str(rule.get("command") or "").strip()
        if command:
            # A command may be a routine or several commands: check every step.
            planner = getattr(self.kernel, "planner", None)
            steps = expand_command(command, getattr(planner, "routines", None))
            risky = [s for s in steps if safety.needs_confirmation(s.tool, s.arguments)]
            if risky and not rule.get("allow_risky"):
                blocked = (f"Trigger '{name}' wanted to {safety.describe_action(risky[0].tool, risky[0].arguments)}, "
                           "but risky actions need allow_risky on the rule.")
                await self._notify(name, blocked)
                result["blocked"] = blocked
            else:
                try:
                    response = await self.kernel.handle(command, user=TRIGGER_SOURCE, source=TRIGGER_SOURCE)
                    result["response"] = response.text
                except Exception as exc:  # noqa: BLE001 - a failing rule must not break the bus
                    result["error"] = str(exc)
                    logger.warning("trigger %s failed: %s", name, exc)

        self._record(str(rule.get("id")), result)
        try:
            await self.events.emit("trigger.fired", result)
        except Exception:  # noqa: BLE001
            pass
        return result

    async def drain(self) -> None:
        """Wait for in-flight trigger tasks (used by tests and shutdown)."""
        if self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def _notify(self, title: str, message: str) -> None:
        # Published on the bus; the web layer relays "notification" events to
        # connected clients, so the core never depends on the UI.
        try:
            await self.events.emit("notification", {"title": title, "message": message, "source": TRIGGER_SOURCE})
        except Exception:  # noqa: BLE001
            pass

    def _record(self, rule_id: str, result: dict[str, Any]) -> None:
        rules = self.list_rules()
        for rule in rules:
            if rule.get("id") == rule_id:
                rule["fire_count"] = int(rule.get("fire_count") or 0) + 1
                rule["last_fired"] = time.time()
                rule["last_result"] = {k: v for k, v in result.items() if k in ("notified", "response", "blocked", "error")}
        self._save(rules)

    def _save(self, rules: list[dict[str, Any]]) -> None:
        self.rules_file.parent.mkdir(parents=True, exist_ok=True)
        self.rules_file.write_text(json.dumps(rules, indent=2, ensure_ascii=False), encoding="utf-8")


_SENSORS_CONNECTED = False


def connect_sensors(events: EventBus | None = None) -> None:
    """Publish reminder firings on the event bus (idempotent).

    Reminders previously fired into callbacks nobody registered, so a due
    reminder reached no one; now it becomes a ``reminder.due`` event.
    """
    global _SENSORS_CONNECTED
    if _SENSORS_CONNECTED:
        return
    bus = events or default_bus
    from atulya.agent.tools import register_reminder_callback

    async def _reminder_due(event_type: str, entry: dict[str, Any]) -> None:
        await bus.emit("reminder.due", {
            "id": entry.get("id"),
            "message": entry.get("message", ""),
            "scheduled_time": entry.get("scheduled_time"),
        })

    register_reminder_callback(_reminder_due)
    _SENSORS_CONNECTED = True
