"""Connection evidence for the current principal, without exposing credentials."""
from pathlib import Path

from tools.plugins.information.google_api import connection_status
from tools.plugins.system.agents import AgentHub


def runtime_readiness(data_dir: Path, user_id: str) -> dict:
    google = connection_status(user_id, data_dir)
    devices = AgentHub(data_dir).devices(user_id)
    findings = []
    if not google.get("configured"):
        findings.append({"area": "google", "message": "Google OAuth client is not configured on the server", "next_step": "Configure the server Google OAuth client, then connect Gmail/Calendar in Connections."})
    elif not google.get("connected"):
        findings.append({"area": "google", "message": "Gmail and Calendar are not connected for this account", "next_step": "Open Connections and connect the Google services you need."})
    else:
        missing = [label for key, label in (("gmail_read", "Gmail read"), ("gmail_send", "Gmail send"), ("calendar_write", "Calendar events")) if not google.get(key)]
        if missing:
            findings.append({"area": "google", "message": "Missing Google scopes: " + ", ".join(missing), "next_step": "Reconnect the corresponding services in Connections."})
        if google.get("last_error"):
            findings.append({"area": "google", "message": "The last Google access attempt failed", "next_step": "Run Test Google access in Connections; reconnect if requested."})
    if not devices:
        findings.append({"area": "devices", "message": "No companion devices are paired", "next_step": "Pair this PC in Devices, start its companion, then run Test connection."})
    for device in devices:
        if device["status"] != "online":
            findings.append({"area": "devices", "message": f"Companion offline: {device['name']}", "next_step": "Start its companion and check connectivity. Inspect a ping receipt before sending actions."})
    return {"google": {key: google.get(key) for key in ("configured", "connected", "gmail_read", "gmail_send", "calendar_write", "scope_status")},
            "devices": devices, "findings": findings,
            "verification": "Configuration and recent heartbeat only. Google access and device actions require a successful test receipt."}
