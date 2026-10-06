"""Devices: device discovery, pairing, profiles and per-device actions."""
from __future__ import annotations

import json
import time
from typing import Any

from atulya import devices as learn

from atulya.devices import DeviceError, get_hub

from atulya import actions as _d

# ── devices_actions ────────────────────────────────────────────────────────────
def _first_param(device: Any, action: str) -> str | None:
    cap = device.cap(action) if device else None
    return next(iter(cap.params), None) if cap and cap.params else None


@_d.tool("device_do", "Control any device you've added (TV, phone, light, speaker, PC…): turn on/off, volume, open an app, brightness …", {
    "device": {"type": "string", "description": "The device's name, e.g. 'living room TV'"},
    "action": {"type": "string", "description": "What to do, as listed by device_list (e.g. power_off, volume_up, launch_app, set_brightness)"},
    "value": {"type": "string", "description": "Optional: the app, level, text or link the action needs", "default": ""},
    "times": {"type": "integer", "description": "Optional: repeat count, for volume", "default": 1},
})
async def device_do(device: str, action: str, value: str = "", times: int = 1) -> str:
    hub = get_hub()
    dev = hub.find(device)
    args: dict[str, Any] = {}
    pname = _first_param(dev, action)
    if pname and str(value).strip():
        args[pname] = value
    if int(times or 1) > 1:
        args["times"] = int(times)
    try:
        return await hub.act(device, action, args)
    except DeviceError as exc:
        return str(exc)


@_d.tool("device_list", "List the devices Atulya can control and what each one can do", {})
async def device_list() -> str:
    rows = get_hub().describe()
    if not rows:
        return "I don't control any devices yet. Say “scan for devices” and I'll look around your network."
    return "\n".join(f"{r['name']} ({r['kind']}{', ' + r['room'] if r['room'] else ''}): " + ", ".join(r["can"][:14]) + ("…" if len(r["can"]) > 14 else "")
                     for r in rows)


@_d.tool("phone_command", "Ring a paired phone or request its current location", {
    "action": {"type": "string", "description": "ring or locate"},
    "device": {"type": "string", "description": "Optional paired phone name", "default": ""},
})
async def phone_command(action: str, device: str = "") -> str:
    from atulya import phone as phone_store, security

    phones = [row for row in security.paired_devices().list()
              if str(row.get("kind", "")).lower() in {"phone", "termux", "android"}
              and row.get("permission") == "full" and not row.get("revoked")]
    if device:
        query = device.strip().lower()
        phones = [row for row in phones if query in str(row.get("name", "")).lower()]
    if not phones:
        return "No full-permission phone is paired. Pair the phone with full access, then try again."
    if len(phones) > 1:
        return "More than one phone is paired. Say the device name: " + ", ".join(str(row.get("name", "Phone")) for row in phones)
    try:
        phone_store.enqueue(phones[0]["id"], action.strip().lower())
    except ValueError as exc:
        return str(exc)
    return f"Queued {action} for {phones[0].get('name', 'your phone')}. It must be online with the Termux companion running."


@_d.tool("phone_inbox", "Read recent SMS, notifications, or location sent by your paired phone", {
    "kind": {"type": "string", "description": "all, sms, notifications, or location", "default": "all"},
    "limit": {"type": "integer", "description": "Maximum number of recent records", "default": 10},
})
async def phone_inbox(kind: str = "all", limit: int = 10) -> str:
    from atulya import phone as phone_store
    from atulya.persona import current_access

    caller = current_access.get() or {}
    if caller and caller.get("role") not in {"admin", "owner"}:
        return "Phone inbox data is only available to the owner."
    try:
        rows = phone_store.list_items(kind, limit)
    except ValueError as exc:
        return str(exc)
    if not rows:
        return "No phone data has arrived yet. Start the paired phone companion and enable the data types you want to share."
    return "\n".join(f"{row['kind']} · {time.strftime('%Y-%m-%d %H:%M', time.localtime(row.get('received_at', 0)))} · "
                     f"{json.dumps(row.get('item', {}), ensure_ascii=False)[:700]}" for row in rows)


@_d.tool("remote_computer", "Queue a check, read task, or a command on another paired computer (commands ask first)", {
    "device": {"type": "string", "description": "Name of a paired computer"},
    "operation": {"type": "string", "description": "results, diagnose, list_dir, find_files, read_file, or run_command"},
    "path": {"type": "string", "description": "Folder or file path for list_dir, find_files, or read_file", "default": ""},
    "query": {"type": "string", "description": "File search text for find_files", "default": ""},
    "command": {"type": "string", "description": "One safe command, only when the paired computer has full permission", "default": ""},
})
async def remote_computer(device: str, operation: str, path: str = "", query: str = "", command: str = "") -> str:
    from atulya import companion, security
    from atulya.persona import current_access

    caller = current_access.get() or {}
    if caller and caller.get("role") not in {"admin", "owner"}:
        return "Remote computer control is only available to the owner."
    computers = [row for row in security.paired_devices().list()
                 if str(row.get("kind", "")).lower() in {"computer", "laptop", "workstation"}
                 and not row.get("revoked")]
    query_name = device.strip().lower()
    computers = [row for row in computers if query_name in str(row.get("name", "")).lower()]
    if not computers:
        return "No paired computer matches that name. Pair the companion first."
    if len(computers) > 1:
        return "More than one computer matches. Name one of: " + ", ".join(str(row.get("name", "Computer")) for row in computers)
    selected = computers[0]
    if operation == "results":
        rows = companion.recent_results(selected["id"])
        if not rows:
            return f"No results have returned from {selected.get('name', 'the computer')} yet."
        return "\n".join(f"{row['result'].get('output') or row['result'].get('error', 'Finished')}" for row in rows[-5:])
    args: dict[str, Any] = {}
    if operation in {"list_dir", "read_file"}:
        args["path"] = path
    elif operation == "find_files":
        args.update(query=query, where=path)
    elif operation == "run_command":
        if selected.get("permission") != "full":
            return "That paired computer is not approved for full control."
        args["command"] = command
    try:
        companion.enqueue(selected["id"], operation, args)
    except ValueError as exc:
        return str(exc)
    return f"Queued {operation} on {selected.get('name', 'the computer')}. The companion must be running; request its result again after it checks in."


@_d.tool("device_discover", "Scan your home network for TVs, phones, lights, speakers and anything else Atulya can control", {})
async def device_discover() -> str:
    hub = get_hub()
    found = await _d.discover(profiles=hub.profiles)
    have = {(d.driver, d.address, str(sorted(d.config.items()))) for d in hub.devices.values()}
    fresh = [c for c in found if (c.driver, c.host, str(sorted(c.config.items()))) not in have]
    hub.last_candidates = {c.id: c for c in fresh}
    hub.last_order = [c.id for c in fresh]
    if not fresh:
        return "I didn't find anything new on your network." + (" (Everything I found is already added.)" if found else "")
    lines = [f"{i}. {c.label} at {c.host} — {c.evidence}" for i, c in enumerate(fresh[:40], 1)]
    return "I found:\n" + "\n".join(lines) + "\nSay “add number 1 as living room TV” to add one."


@_d.tool("device_add", "Add a device that device_discover found", {
    "which": {"type": "string", "description": "Its number from the scan, or its id"},
    "name": {"type": "string", "description": "What to call it, e.g. 'living room TV'", "default": ""},
    "room": {"type": "string", "description": "Optional room", "default": ""},
})
async def device_add(which: str, name: str = "", room: str = "") -> str:
    hub = get_hub()
    key = str(which).strip().lstrip("#")
    if key.isdigit():
        order = getattr(hub, "last_order", [])
        key = order[int(key) - 1] if 0 < int(key) <= len(order) else key
    try:
        dev = await hub.add_candidate(key, name, room)
    except DeviceError as exc:
        return str(exc)
    return f"Added {dev.name}. It can: {', '.join(c.name for c in dev.capabilities[:10])}."


@_d.tool("device_add_manual", "Add a device by hand when you know how to reach it (profile, adb, wol or homeassistant)", {
    "name": {"type": "string", "description": "What to call it"},
    "driver": {"type": "string", "description": "profile | adb | wol | homeassistant"},
    "address": {"type": "string", "description": "Its address on your network (not needed for homeassistant)", "default": ""},
    "profile": {"type": "string", "description": "For driver=profile: roku, tasmota, wled, shelly, kodi or one you taught me", "default": ""},
    "mac": {"type": "string", "description": "For driver=wol: its MAC address", "default": ""},
    "port": {"type": "integer", "description": "Optional port", "default": 0},
    "entity": {"type": "string", "description": "For driver=homeassistant: the entity id, e.g. light.kitchen", "default": ""},
    "room": {"type": "string", "description": "Optional room", "default": ""},
})
async def device_add_manual(name: str, driver: str, address: str = "", profile: str = "", mac: str = "", port: int = 0, entity: str = "", room: str = "") -> str:
    config = {k: v for k, v in {"profile": profile, "mac": mac, "port": port or None, "entity": entity}.items() if v}
    try:
        dev = await get_hub().add(name, driver.strip().lower(), address.strip(), config, room=room)
    except DeviceError as exc:
        return str(exc)
    return f"Added {dev.name}. It can: {', '.join(c.name for c in dev.capabilities[:10])}."


@_d.tool("device_remove", "Forget a device", {"device": {"type": "string", "description": "Its name"}})
async def device_remove(device: str) -> str:
    try:
        return f"Forgot {get_hub().remove(device)}."
    except DeviceError as exc:
        return str(exc)


@_d.tool("device_learn", "Teach Atulya a device it doesn't know: it looks at what the device says and drafts a control profile for you to approve", {
    "host": {"type": "string", "description": "The device's address on your network"},
    "notes": {"type": "string", "description": "Anything that helps: the model, or pasted API instructions", "default": ""},
})
async def device_learn(host: str, notes: str = "") -> str:
    hub = get_hub()
    try:
        draft = await learn.draft_profile(host.strip(), notes, hub.proposals_dir)
    except DeviceError as exc:
        return str(exc)
    return (f"I drafted a profile (proposal {draft['id']}) for {draft['profile'].get('label', host)}. It would let me send:\n"
            + "\n".join(draft["summary"][:12]) + f"\nNothing is used until you say “approve proposal {draft['id']}”.")


@_d.tool("device_profile_approve", "Approve a drafted device profile so Atulya may use it", {"proposal": {"type": "string", "description": "The proposal number"}})
async def device_profile_approve(proposal: str) -> str:
    hub = get_hub()
    try:
        profile = learn.approve(proposal.strip(), hub.proposals_dir, hub.profile_dir)
    except DeviceError as exc:
        return str(exc)
    hub.reload_profiles()
    return f"Approved “{profile.get('label', profile['id'])}”. Add the device with device_add_manual (driver profile, profile {profile['id']})."


