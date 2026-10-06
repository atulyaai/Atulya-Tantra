"""Policy: policy -- what may run unattended, what asks first, what is refused."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any




# ── policy ────────────────────────────────────────────────────────────
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
    "message_send": "sends a message to someone on your behalf",
    "twilio_sms": "sends an SMS using your phone service",
    "twilio_call": "places a phone call using your phone service",
    "ha_call_service": "runs a Home Assistant service that may change your home",
    "contact_remove": "forgets a contact",
    "calendar_remove": "permanently deletes a calendar event",
    "cancel_reminder": "deletes a reminder",
    "configure_email": "stores email credentials",
    "download_vision_model": "downloads a large model",
    "pc_open_app": "opens an app on your computer",
    "pc_type": "types on your keyboard",
    "pc_hotkey": "presses keyboard shortcuts",
    "pc_screenshot": "captures your screen",
    "phone_command": "rings your phone or requests its location",
    "remote_computer": "runs a task on another paired computer",
    "run_command": "runs a command on your computer",
    "install_software": "installs software on your computer",
    "web_task": "drives a web browser to do a task for you",
    "device_remove": "forgets a device",
    "device_profile_approve": "lets me send a new kind of command to a device",
}

# Specific (tool, action) pairs that need confirmation.
_CONFIRM_ACTIONS = {
    ("home_control", "unlock"): "unlocks a door",
    **{("files", a): "changes or opens your files" for a in ("move", "delete", "write", "edit", "open", "print")},
    ("clipboard", "set"): "changes your clipboard",
    ("screen", "read"): "reads what is on your screen",
    **{("screen", a): "controls your screen" for a in ("focus", "click", "click_text", "double_click", "right_click", "move", "scroll")},
}

# Outside MCP servers name their own tools, and `assess` matches on the exact
# name -- so `mcp_filesystem_write_file` sailed straight past the gate that
# stops the native `file_write`, because neither name equals the other. The
# full name to bare name mapping is recorded when a server is adapted, and
# only the tools listed here are allowed to run without asking: an outside
# server is somebody else's code acting on this machine, so anything not
# positively known to merely look around has to be confirmed first.
MCP_BARE_NAMES: dict[str, str] = {}

_MCP_READONLY = {
    # filesystem
    "read_file", "read_text_file", "read_media_file", "read_multiple_files",
    "list_directory", "list_directory_with_sizes", "directory_tree",
    "search_files", "get_file_info", "list_allowed_directories",
    # git
    "git_status", "git_diff", "git_diff_unstaged", "git_diff_staged",
    "git_log", "git_show",
    # playwright
    "browser_snapshot", "browser_console_messages", "browser_network_requests",
    "browser_network_request", "browser_wait_for", "browser_find",
    "browser_take_screenshot",
}


def _mcp_readonly(tool: str) -> bool:
    """Whether an outside server's tool only looks, and so may run freely."""
    bare = MCP_BARE_NAMES.get(tool, "")
    if bare:
        return bare in _MCP_READONLY
    # The registry was not built in this process, or the name is not one we
    # discovered. Judge it by its tail instead of assuming it is harmless:
    # only a name we positively recognise passes, everything else confirms.
    return any(tool.endswith("_" + name) for name in _MCP_READONLY)


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

    if tool == "device_do":  # the device's own profile says which actions need a yes (unlock, restart, typing …)
        from atulya.devices import get_hub

        if get_hub().is_risky(str((arguments or {}).get("device", "")), str((arguments or {}).get("action", ""))) and "device_do" not in approved:
            return Assessment(CONFIRM, "could change or restart a device")
    if tool == "files" and action == "copy" and (arguments or {}).get("overwrite") and "files" not in approved:
        return Assessment(CONFIRM, "replaces an existing file")

    if tool.startswith("mcp_"):  # an outside server: read-only work is free, the rest is not
        if tool.lower() in approved or "mcp" in approved:
            return Assessment(ALLOW)
        if _mcp_readonly(tool):
            return Assessment(ALLOW)
        return Assessment(CONFIRM, "an outside tool would make a change")

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
    if tool == "run_plan":
        return f"run “{args.get('title') or 'the plan'}” ({len(args.get('steps') or [])} steps)"
    if tool == "trust_action":
        return f"stop asking before I {args.get('label') or 'do that'}"
    if tool == "forget_profile":
        return "forget everything I've learned about you"
    if tool in ("get_weather", "get_forecast"):
        return f"check the weather in {args.get('location', 'your city')}"
    if tool == "open_website":
        return f"open {args.get('site', 'a website')}"
    if tool == "device_do":
        return f"{str(args.get('action', 'do something')).replace('_', ' ')} on {args.get('device', 'a device')}"
    if tool == "device_remove":
        return f"forget the device {args.get('device', '')}".strip()
    if tool == "device_profile_approve":
        return f"approve device profile {args.get('proposal', '')}".strip()
    if tool == "web_task":
        return f"do this on the web: {str(args.get('goal', 'a task'))[:80]}"
    if tool == "message_send":
        via = f" on {args['via']}" if args.get("via") else ""
        return f"send “{str(args.get('text', ''))[:80]}” to {args.get('to', 'them')}{via}"
    if tool == "contact_remove":
        return f"forget the contact {args.get('name', '')}".strip()
    if tool == "pc_open_app":
        return f"open {args.get('app', 'an app')}"
    if tool == "pc_type":
        return "type that on your keyboard"
    if tool == "pc_hotkey":
        return f"press {args.get('keys', 'a shortcut')}"
    if tool == "files":
        what, where = str(args.get("path", "a file")), str(args.get("to", ""))
        verbs = {"list": f"look in {what}", "find": f"look for {what}", "read": f"read {what}",
                 "copy": f"copy {what} to {where}", "move": f"move {what} to {where}",
                 "delete": f"move {what} to the trash", "folder": f"make the folder {what}",
                 "write": f"write the file {what}", "edit": f"change the file {what}",
                 "open": f"open {what}", "print": f"print {what}"}
        return verbs.get(str(args.get("action", "")).lower(), "work with your files")
    if tool == "clipboard":
        return "put that on your clipboard" if args.get("action") == "set" else "read your clipboard"
    if tool == "screen":
        act = str(args.get("action", "")).lower()
        return {"read": "read what is on your screen", "windows": "list your open windows",
                "focus": f"switch to the {args.get('title', '')} window",
                "click_text": f"click the {args.get('text', 'labeled')} text on your screen"}.get(act, f"{act.replace('_', ' ')} on your screen")
    if tool == "run_command":
        return f"run this on your computer: {str(args.get('command', ''))[:80]}"
    if tool == "install_software":
        return f"install {args.get('package', 'a program')}"
    if tool == "check_computer":
        return "check your computer's health"
    if tool == "pc_screenshot":
        return "take a screenshot of your screen"
    if tool == "file_write":
        return f"write the file {args.get('path', 'a file')}"
    if tool == "file_edit":
        return f"change the file {args.get('path', 'a file')}"
    if tool in ("exec", "code_execute"):
        return f"run this on your computer: {str(args.get('command') or args.get('code') or 'a command')[:80]}"
    if tool in _CHECKS:
        return _CHECKS[tool]
    return f"run {tool}"


_CHECKS = {"calendar_list": "check your calendar", "fetch_emails": "check your email", "current_time": "check the time",
           "phone_inbox": "check your paired phone inbox",
           "list_reminders": "check your reminders", "home_list_devices": "check your devices"}


