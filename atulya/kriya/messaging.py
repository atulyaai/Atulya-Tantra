"""Contacts and messages: sending, voice, Twilio calls/SMS and Home Assistant."""
from __future__ import annotations

import os
import re
import httpx
from typing import Any



from atulya import kriya as _d

# ── contacts and messages ────────────────────────────────────────────────────
# "tell Mum I'm late": a small contact book plus one send tool. Sending always asks first (see mastishk.py), and
# only reaches a person you saved: Atulya never guesses a recipient or looks one up.
_CHANNEL_WORDS = {"telegram": "telegram", "whatsapp": "whatsapp", "email": "email", "mail": "email", "slack": "slack",
                  "discord": "discord", "signal": "signal", "sms": "sms"}
MESSAGE_LIMIT = 500


def _contacts() -> list[dict[str, Any]]:
    data = _d._load_json("contacts.json")
    rows = data.get("contacts") if isinstance(data, dict) else None
    return rows if isinstance(rows, list) else []


def _save_contacts(rows: list[dict[str, Any]]) -> None:
    _d._save_json("contacts.json", {"contacts": rows})


def find_contact(who: str) -> dict[str, Any] | None:
    """A saved contact by name or nickname ("Mum", "mom", "Priya"), exact match only."""
    w = " ".join(str(who or "").lower().split())
    if not w:
        return None
    return next((c for c in _contacts() if w == c["name"].lower() or w in [a.lower() for a in c.get("aliases", [])]), None)


def contact_names() -> list[str]:
    """Every name and nickname that means a saved contact, longest first (the intent router matches on these)."""
    names = [n for c in _contacts() for n in [c["name"], *c.get("aliases", [])]]
    return sorted({n.lower() for n in names}, key=len, reverse=True)


@_d.tool("contact_add", "Save or update a person you can message, e.g. Mum on Telegram", {
    "name": {"type": "string", "description": "Name, e.g. Mum"},
    "channel": {"type": "string", "description": "telegram, whatsapp, email, slack, discord or signal"},
    "address": {"type": "string", "description": "Telegram chat id, phone number or email address"},
    "nicknames": {"type": "string", "description": "Other names for them, comma separated, e.g. Mom, Mummy", "default": ""},
})
async def contact_add(name: str, channel: str, address: str, nicknames: str = "") -> str:
    name = " ".join(str(name).split())[:40]
    chan = _CHANNEL_WORDS.get(str(channel).strip().lower())
    address = str(address).strip()[:120]
    if not name or not chan or not address:
        return "I need a name, a channel (telegram, whatsapp, email, slack, discord, signal) and an address."
    rows = _contacts()
    row = next((c for c in rows if c["name"].lower() == name.lower()), None)
    if row is None:
        row = {"name": name, "aliases": [], "channels": {}}
        rows.append(row)
    row["channels"][chan] = address
    row.setdefault("preferred", chan)
    row["aliases"] = sorted({*row.get("aliases", []), *[a.strip() for a in str(nicknames).split(",") if a.strip()]})
    _save_contacts(rows)
    return f"Saved {name} on {chan}."


@_d.tool("contact_list", "List the people you can message", {})
async def contact_list() -> str:
    rows = _contacts()
    if not rows:
        return "No contacts yet. Say, for example: add Mum on Telegram with chat id 12345."
    return "\n".join(f"{c['name']}: {', '.join(c.get('channels', {}))}" + (f" (also: {', '.join(c['aliases'])})" if c.get("aliases") else "")
                     for c in rows)


@_d.tool("contact_remove", "Forget a saved contact", {"name": {"type": "string", "description": "Name or nickname"}})
async def contact_remove(name: str) -> str:
    c = find_contact(name)
    if c is None:
        return f"I don't have a contact called {name}."
    _save_contacts([x for x in _contacts() if x["name"] != c["name"]])
    return f"Forgot {c['name']}."


@_d.tool("message_send", "Send a message to a saved contact (asks you first)", {
    "to": {"type": "string", "description": "A saved contact's name or nickname"},
    "text": {"type": "string", "description": "What to say"},
    "via": {"type": "string", "description": "telegram, whatsapp, email ... (default: their usual one)", "default": ""},
})
async def message_send(to: str, text: str, via: str = "") -> str:
    contact = find_contact(to)
    if contact is None:
        return f"I don't have a contact called {to}. Save them first: add {to} on Telegram with their chat id."
    text = " ".join(str(text).split())
    if not text:
        return "What should I say?"
    if len(text) > MESSAGE_LIMIT:
        return f"That is too long to send by voice ({len(text)} characters; the limit is {MESSAGE_LIMIT})."
    channels = contact.get("channels", {})
    chan = _CHANNEL_WORDS.get(str(via).strip().lower()) if via else contact.get("preferred")
    if chan not in channels:
        return f"I don't have {contact['name']} on {via or 'any channel'}. I have: {', '.join(channels) or 'nothing'}."
    address = channels[chan]
    if chan == "email":
        return await _d.send_email(address, "Message from Atulya", text)
    from atulya.sandesh import create_default_registry

    registry = create_default_registry(os.environ.get("ATULYA_CHANNELS_DIR", "kosh/channels"))
    try:
        sent = await registry.send(chan, text, chat_id=address)
    except Exception as exc:  # noqa: BLE001 - say what went wrong instead of pretending
        return f"I couldn't send to {contact['name']} on {chan}: {exc}"
    if not sent:
        return f"I couldn't send to {contact['name']} on {chan}. {chan.title()} isn't set up yet (see the Channels section of the README)."
    return f"Sent to {contact['name']} on {chan}."


# ─ Voice Identity ────────────────────────────
@_d.tool("voice_enroll", "Enroll your voice for speaker recognition", {
    "name": {"type": "string", "description": "Your name (e.g. 'Ananya')"},
    "wav_path": {"type": "string", "description": "Path to a WAV file of you speaking (16kHz, mono)"},
})
async def voice_enroll(name: str, wav_path: str) -> str:
    name = str(name).strip()
    if not name:
        return "A name is required."
    if not os.path.exists(wav_path):
        return f"File not found: {wav_path}"
    from atulya.smriti import MemoryManager
    mm = MemoryManager()
    await mm.initialize()
    ok = mm.voice_identity.enroll(name, wav_path)
    await mm.close()
    return f"Enrolled voice for {name}" if ok else "Enrollment failed (model unavailable or bad audio)."


@_d.tool("voice_identify", "Identify who is speaking from a WAV file", {
    "wav_path": {"type": "string", "description": "Path to a WAV file (16kHz, mono)"},
})
async def voice_identify(wav_path: str) -> str:
    if not os.path.exists(wav_path):
        return f"File not found: {wav_path}"
    from atulya.smriti import MemoryManager
    mm = MemoryManager()
    await mm.initialize()
    result = mm.voice_identity.identify(wav_path)
    await mm.close()
    if result:
        return f"Recognized: {result[0]} (similarity {result[1]:.2f})"
    return "Unknown speaker (or model unavailable)."


@_d.tool("voice_list", "List enrolled voice identities", {})
async def voice_list() -> str:
    from atulya.smriti import MemoryManager
    mm = MemoryManager()
    await mm.initialize()
    names = list(mm.voice_identity._embeddings.keys())
    await mm.close()
    return f"Enrolled voices: {', '.join(names) if names else '(none)'}"


# ── Twilio Calls/SMS ────────────────────────────────────────────────────────
@_d.tool("twilio_sms", "Send an SMS via Twilio", {
    "to": {"type": "string", "description": "Destination phone number in E.164 format (+15551234567)"},
    "body": {"type": "string", "description": "Message text"},
})
async def twilio_sms(to: str, body: str) -> str:
    if not to.startswith("+"):
        return "Phone number must be in E.164 format (e.g. +15551234567)."
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_number = os.environ.get("TWILIO_FROM_NUMBER", "")
    if not all([account_sid, auth_token, from_number]):
        return "Twilio not configured (set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER)."
    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        msg = client.messages.create(body=body, from_=from_number, to=to)
        return f"SMS sent to {to} (SID: {msg.sid})"
    except Exception as exc:  # noqa: BLE001
        return f"SMS failed: {exc}"


def _twilio_say_twiml(text: str) -> str:
    """Build a TwiML Say response without allowing text to inject XML verbs."""
    from xml.sax.saxutils import escape as xml_escape

    return f"<Response><Say>{xml_escape(text)}</Say></Response>"


@_d.tool("twilio_call", "Make a voice call via Twilio (TTS or recorded)", {
    "to": {"type": "string", "description": "Destination phone number in E.164 format"},
    "text": {"type": "string", "description": "Text to speak (TTS)", "default": ""},
    "url": {"type": "string", "description": "Twilio TwiML URL for custom call flow", "default": ""},
})
async def twilio_call(to: str, text: str = "", url: str = "") -> str:
    if not to.startswith("+"):
        return "Phone number must be in E.164 format (e.g. +15551234567)."
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_number = os.environ.get("TWILIO_FROM_NUMBER", "")
    if not all([account_sid, auth_token, from_number]):
        return "Twilio not configured."
    if not text and not url:
        return "Provide either 'text' (for TTS) or 'url' (TwiML)."
    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        call = client.calls.create(
            to=to, from_=from_number,
            twiml=_twilio_say_twiml(text) if text else None,
            url=url if url else None,
        )
        return f"Call started to {to} (SID: {call.sid})"
    except Exception as exc:  # noqa: BLE001
        return f"Call failed: {exc}"


# ── Home Assistant ───────────────────────────────────────────────────────────
_HA_ENTITY_ID_RE = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")
_HA_SERVICE_PART_RE = re.compile(r"^[a-z0-9_]+$")


@_d.tool("ha_state", "Get the state of a Home Assistant entity", {
    "entity_id": {"type": "string", "description": "Entity ID (e.g. binary_sensor.front_door)"},
})
async def ha_state(entity_id: str) -> str:
    entity_id = str(entity_id).strip()
    if not _HA_ENTITY_ID_RE.fullmatch(entity_id):
        return "Entity ID must look like domain.object (for example light.kitchen)."
    url = os.environ.get("HOME_ASSISTANT_URL", "").rstrip("/")
    token = os.environ.get("HOME_ASSISTANT_TOKEN", "")
    if not url or not token:
        return "Home Assistant not configured (set HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN)."
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{url}/api/states/{entity_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code == 404:
            return f"Entity not found: {entity_id}"
        resp.raise_for_status()
        data = resp.json()
        state = data.get("state", "unknown")
        attrs = data.get("attributes", {})
        friendly = attrs.get("friendly_name", entity_id)
        return f"{friendly}: {state}"
    except Exception as exc:  # noqa: BLE001
        return f"HA request failed: {exc}"


@_d.tool("ha_call_service", "Call a Home Assistant service", {
    "domain": {"type": "string", "description": "Service domain (e.g. light, switch, climate)"},
    "service": {"type": "string", "description": "Service name (e.g. turn_on, set_temperature)"},
    "entity_id": {"type": "string", "description": "Target entity ID"},
    "data": {"type": "object", "description": "Service data (JSON)", "default": {}},
})
async def ha_call_service(domain: str, service: str, entity_id: str, data: dict = None) -> str:
    domain, service, entity_id = (str(value).strip() for value in (domain, service, entity_id))
    if not _HA_SERVICE_PART_RE.fullmatch(domain) or not _HA_SERVICE_PART_RE.fullmatch(service):
        return "Home Assistant domain and service must contain only letters, numbers, and underscores."
    if not _HA_ENTITY_ID_RE.fullmatch(entity_id):
        return "Entity ID must look like domain.object (for example light.kitchen)."
    if data is not None and not isinstance(data, dict):
        return "Service data must be an object."
    url = os.environ.get("HOME_ASSISTANT_URL", "").rstrip("/")
    token = os.environ.get("HOME_ASSISTANT_TOKEN", "")
    if not url or not token:
        return "Home Assistant not configured."
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{url}/api/services/{domain}/{service}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={**(data or {}), "entity_id": entity_id},
            )
        resp.raise_for_status()
        return f"Service {domain}.{service} called on {entity_id}"
    except Exception as exc:  # noqa: BLE001
        return f"HA service call failed: {exc}"


@_d.tool("ha_entities", "List Home Assistant entities (optionally filtered)", {
    "domain": {"type": "string", "description": "Filter by domain (e.g. binary_sensor, sensor)", "default": ""},
})
async def ha_entities(domain: str = "") -> str:
    domain = str(domain).strip()
    if domain and not _HA_SERVICE_PART_RE.fullmatch(domain):
        return "Domain must contain only letters, numbers, and underscores."
    url = os.environ.get("HOME_ASSISTANT_URL", "").rstrip("/")
    token = os.environ.get("HOME_ASSISTANT_TOKEN", "")
    if not url or not token:
        return "Home Assistant not configured."
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{url}/api/states",
                headers={"Authorization": f"Bearer {token}"},
            )
        resp.raise_for_status()
        entities = resp.json()
        if domain:
            entities = [e for e in entities if e["entity_id"].startswith(f"{domain}.")]
        lines = [f"{e['entity_id']}: {e['state']}" for e in entities[:50]]
        return "\n".join(lines) if lines else "No entities found."
    except Exception as exc:  # noqa: BLE001
        return f"HA request failed: {exc}"


from atulya import jaal  # noqa: E402,F401  (registers the web tools; jaal needs the tool registry above)
