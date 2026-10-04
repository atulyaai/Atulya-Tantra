"""Tools that let the brain (and voice) use the device fabric: find, add, control and teach devices."""
from __future__ import annotations

from typing import Any

from atulya.yantra.tools import tool
from atulya.upakaran import learn
from atulya.upakaran.base import DeviceError
from atulya.upakaran.discovery import discover
from atulya.upakaran.hub import get_hub


def _first_param(device: Any, action: str) -> str | None:
    cap = device.cap(action) if device else None
    return next(iter(cap.params), None) if cap and cap.params else None


@tool("device_do", "Control any device you've added (TV, phone, light, speaker, PC…): turn on/off, volume, open an app, brightness …", {
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


@tool("device_list", "List the devices Atulya can control and what each one can do", {})
async def device_list() -> str:
    rows = get_hub().describe()
    if not rows:
        return "I don't control any devices yet. Say “scan for devices” and I'll look around your network."
    return "\n".join(f"{r['name']} ({r['kind']}{', ' + r['room'] if r['room'] else ''}): " + ", ".join(r["can"][:14]) + ("…" if len(r["can"]) > 14 else "")
                     for r in rows)


@tool("device_discover", "Scan your home network for TVs, phones, lights, speakers and anything else Atulya can control", {})
async def device_discover() -> str:
    hub = get_hub()
    found = await discover(profiles=hub.profiles)
    have = {(d.driver, d.address, str(sorted(d.config.items()))) for d in hub.devices.values()}
    fresh = [c for c in found if (c.driver, c.host, str(sorted(c.config.items()))) not in have]
    hub.last_candidates = {c.id: c for c in fresh}
    hub.last_order = [c.id for c in fresh]
    if not fresh:
        return "I didn't find anything new on your network." + (" (Everything I found is already added.)" if found else "")
    lines = [f"{i}. {c.label} at {c.host} — {c.evidence}" for i, c in enumerate(fresh[:40], 1)]
    return "I found:\n" + "\n".join(lines) + "\nSay “add number 1 as living room TV” to add one."


@tool("device_add", "Add a device that device_discover found", {
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


@tool("device_add_manual", "Add a device by hand when you know how to reach it (profile, adb, wol or homeassistant)", {
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


@tool("device_remove", "Forget a device", {"device": {"type": "string", "description": "Its name"}})
async def device_remove(device: str) -> str:
    try:
        return f"Forgot {get_hub().remove(device)}."
    except DeviceError as exc:
        return str(exc)


@tool("device_learn", "Teach Atulya a device it doesn't know: it looks at what the device says and drafts a control profile for you to approve", {
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


@tool("device_profile_approve", "Approve a drafted device profile so Atulya may use it", {"proposal": {"type": "string", "description": "The proposal number"}})
async def device_profile_approve(proposal: str) -> str:
    hub = get_hub()
    try:
        profile = learn.approve(proposal.strip(), hub.proposals_dir, hub.profile_dir)
    except DeviceError as exc:
        return str(exc)
    hub.reload_profiles()
    return f"Approved “{profile.get('label', profile['id'])}”. Add the device with device_add_manual (driver profile, profile {profile['id']})."
