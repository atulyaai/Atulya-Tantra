"""Action safety policy.

Decides whether an action may run immediately or needs the user's explicit
confirmation first. One policy is shared by every path that can act — the
deterministic intent router, the model's native tool calls, and triggers — so
"unlock the front door" can never fire on a misheard word.

An action needs confirmation when it:
  * affects physical security (unlocking a door),
  * speaks for the user to other people (sending email),
  * irreversibly deletes the user's data (calendar events, reminders), or
  * runs code or modifies files.

Power users can pre-approve specific actions with ``ATULYA_AUTO_APPROVE``, a
comma-separated list of ``tool`` or ``tool:action`` entries
(e.g. ``send_email,home_control:unlock``).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

ALLOW = "allow"
CONFIRM = "confirm"

# Code execution / file mutation / automation of external systems.
RISKY_TOOLS = {
    "exec",
    "file_write",
    "file_edit",
    "code_execute",
    "sap_gui_automation",
}

# Tools that always need confirmation, with the reason shown to the user.
_CONFIRM_TOOLS = {
    **{name: "runs code or changes files" for name in RISKY_TOOLS},
    "send_email": "sends a message on your behalf",
    "calendar_remove": "permanently deletes a calendar event",
    "cancel_reminder": "deletes a reminder",
    "configure_email": "stores email credentials",
    "download_vision_model": "downloads a large model",
}

# Specific (tool, action) pairs that need confirmation.
_CONFIRM_ACTIONS = {
    ("home_control", "unlock"): "unlocks a door",
}


@dataclass
class Assessment:
    level: str
    reason: str = ""

    @property
    def needs_confirmation(self) -> bool:
        return self.level == CONFIRM


def _auto_approved() -> set[str]:
    raw = os.environ.get("ATULYA_AUTO_APPROVE", "")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def assess(tool: str, arguments: dict[str, Any] | None = None) -> Assessment:
    """Classify an action as ALLOW or CONFIRM."""
    tool = (tool or "").strip()
    action = str((arguments or {}).get("action") or "").strip().lower()
    approved = _auto_approved()

    reason = _CONFIRM_ACTIONS.get((tool, action))
    if reason and f"{tool}:{action}".lower() not in approved and tool.lower() not in approved:
        return Assessment(CONFIRM, reason)

    reason = _CONFIRM_TOOLS.get(tool)
    if reason and tool.lower() not in approved:
        return Assessment(CONFIRM, reason)

    return Assessment(ALLOW)


def needs_confirmation(tool: str, arguments: dict[str, Any] | None = None) -> bool:
    return assess(tool, arguments).needs_confirmation


def describe_action(tool: str, arguments: dict[str, Any] | None = None) -> str:
    """A short human phrase for a pending action, used in confirmation prompts."""
    args = arguments or {}
    if tool == "home_control":
        device = str(args.get("device_id", "the device")).replace("_", " ")
        action = str(args.get("action", "control"))
        if action == "set_temperature":
            return f"set the {device} to {args.get('value')}°"
        if action in ("on", "off"):
            return f"turn {action} the {device}"
        return f"{action} the {device}"
    if tool == "send_email":
        return f"send an email to {args.get('to', 'someone')} about \"{args.get('subject', '')}\""
    if tool == "calendar_remove":
        return f"delete calendar event {args.get('event_id', '')}".strip()
    if tool == "cancel_reminder":
        return f"cancel reminder {args.get('reminder_id', '')}".strip()
    return f"run {tool}"
