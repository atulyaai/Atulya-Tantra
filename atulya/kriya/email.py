"""Email: IMAP/SMTP/Gmail send and fetch, plus the inbox watcher."""
from __future__ import annotations

import asyncio
import re
from typing import Any



from atulya import kriya as _d

# ── Tool: Email Skills ─────────────────────────────────────────────────────
# With Google connected (Settings → Accounts) email and calendar use the
# requesting user's Gmail and Google Calendar; otherwise IMAP/SMTP and the
# built-in calendar.

_EMAIL_CFG: dict[str, Any] = {}


def _google():
    """The current user's connected Google account, or None."""
    try:
        from atulya.jaal import GoogleAccount

        account = GoogleAccount.for_current_user()
        return account if account.connected else None
    except Exception:  # noqa: BLE001 - never let an integration break the basics
        return None


def _sender_name(value: str) -> str:
    name = value.split("<", 1)[0].strip().strip('"')
    return name or value


def _load_email_config():
    global _EMAIL_CFG
    cfg = _d._load_json("email_config.json")
    if cfg:
        _d._EMAIL_CFG = cfg


@_d.tool("configure_email", "Configure email account (IMAP/SMTP)", {
    "imap_server": {"type": "string", "description": "IMAP server address"},
    "imap_port": {"type": "integer", "description": "IMAP port (default 993)", "default": 993},
    "smtp_server": {"type": "string", "description": "SMTP server address"},
    "smtp_port": {"type": "integer", "description": "SMTP port (default 587)", "default": 587},
    "username": {"type": "string", "description": "Email username"},
    "password": {"type": "string", "description": "Email password (stored locally)"},
})
async def configure_email(imap_server: str, imap_port: int = 993, smtp_server: str = "", smtp_port: int = 587, username: str = "", password: str = "") -> str:
    cfg = {"imap_server": imap_server, "imap_port": imap_port, "smtp_server": smtp_server or imap_server, "smtp_port": smtp_port, "username": username, "password": password}
    _d._EMAIL_CFG.update(cfg)
    _d._save_json("email_config.json", _d._EMAIL_CFG)
    return f"Email configured for {username}."


@_d.tool("send_email", "Send an email", {
    "to": {"type": "string", "description": "Recipient email address"},
    "subject": {"type": "string", "description": "Email subject"},
    "body": {"type": "string", "description": "Email body text"},
})
async def send_email(to: str, subject: str, body: str) -> str:
    google = _d._google()
    if google is not None:
        from atulya.jaal import GoogleError

        try:
            await google.send_message(to, subject, body)
        except GoogleError as exc:
            return f"Couldn't send with Gmail: {exc}"
        return f"Email sent to {to}: '{subject}' (Gmail)"
    if not _d._EMAIL_CFG.get("smtp_server"):
        return "Email not configured. Use configure_email first."
    try:
        from email.message import EmailMessage

        import aiosmtplib
        msg = EmailMessage()
        msg["From"] = _d._EMAIL_CFG["username"]
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        await aiosmtplib.send(msg, hostname=_d._EMAIL_CFG["smtp_server"], port=_d._EMAIL_CFG["smtp_port"], username=_d._EMAIL_CFG["username"], password=_d._EMAIL_CFG["password"], use_tls=_d._EMAIL_CFG["smtp_port"] == 587)
        return f"Email sent to {to}: '{subject}'"
    except ImportError:
        return "aiosmtplib not installed. Install with: pip install aiosmtplib"
    except Exception as e:
        return f"Failed to send email: {e}"


@_d.tool("fetch_emails", "Fetch recent emails from inbox", {
    "limit": {"type": "integer", "description": "Number of emails to fetch (default 5)", "default": 5},
    "query": {"type": "string", "description": "Optional Gmail search, e.g. 'is:unread' or 'from:rahul'",
              "default": ""},
})
async def fetch_emails(limit: int = 5, query: str = "") -> str:
    google = _d._google()
    if google is not None:
        from atulya.jaal import GoogleError

        try:
            messages = await google.list_messages(query or "in:inbox", limit)
        except GoogleError as exc:
            return f"Couldn't read Gmail: {exc}"
        if not messages:
            return "No emails found." if query else "Your inbox is empty."
        lines = [f"{i}. {_sender_name(m['from'])} — {m['subject'] or '(no subject)'}"
                 + (" (unread)" if m["unread"] else "") for i, m in enumerate(messages, 1)]
        return "Latest emails:\n" + "\n".join(lines)
    if not _d._EMAIL_CFG.get("imap_server"):
        return "Email not configured. Use configure_email first."
    try:
        import email

        import aioimaplib
        client = aioimaplib.IMAP4_SSL(_d._EMAIL_CFG["imap_server"], _d._EMAIL_CFG["imap_port"])
        await client.wait_hello_from_server()
        await client.login(_d._EMAIL_CFG["username"], _d._EMAIL_CFG["password"])
        await client.select("INBOX")
        _, data = await client.search("ALL")
        ids = data[0].split()[-limit:]
        lines = []
        for mid in ids:
            _, msg_data = await client.fetch(mid, "(RFC822)")
            for part in msg_data:
                if isinstance(part, tuple):
                    msg = email.message_from_bytes(part[1])
                    subj = msg["Subject"] or "(no subject)"
                    frm = msg["From"] or "unknown"
                    lines.append(f"From: {frm} | Subject: {subj}")
        await client.logout()
        return "\n".join(lines) if lines else "No emails found."
    except ImportError:
        return "aioimaplib not installed. Install with: pip install aioimaplib"
    except Exception as e:
        return f"Failed to fetch emails: {e}"


# ── Watch: the inbox announces itself ──────────────────────────────────────

_EMAIL_STATE_FILE = "email_state.json"
_EMAIL_WINDOW = 20  # Gmail's list_messages caps maxResults at 20
_SEEN_KEEP = 500  # comfortably more than the window on either backend


def _email_state() -> dict:
    data = _d._load_json(_EMAIL_STATE_FILE)
    return data if isinstance(data, dict) else {}


def _save_email_state(state: dict) -> None:
    _d._save_json(_EMAIL_STATE_FILE, state)


async def _new_imap(limit: int) -> list[dict]:
    """Mail newer than the saved UID watermark, then move that watermark.

    UIDs are what make this safe. Sequence numbers shift every time a message
    is deleted, so a watermark on them eventually stops seeing new mail at all,
    while UIDs are never reused. UIDVALIDITY rides along for the same reason:
    a rebuilt mailbox restarts the numbering, and without that check the choice
    is between announcing the whole backlog again and going quiet for good.
    """
    if not _d._EMAIL_CFG.get("imap_server"):
        return []
    import email

    import aioimaplib

    client = aioimaplib.IMAP4_SSL(_d._EMAIL_CFG["imap_server"], int(_d._EMAIL_CFG.get("imap_port") or 993))
    await client.wait_hello_from_server()
    try:
        await client.login(_d._EMAIL_CFG["username"], _d._EMAIL_CFG["password"])
        await client.select("INBOX")
        _, status = await client.status("INBOX", "(UIDVALIDITY)")
        hit = re.search(rb"UIDVALIDITY\s+(\d+)", status[0] if status else b"")
        uidvalidity = hit.group(1).decode() if hit else ""
        _, data = await client.uid_search("ALL")
        uids = sorted(int(u) for u in (data[0].split() if data else []))
        if not uids:
            return []
        state = _email_state()
        if state.get("backend") != "imap" or state.get("uidvalidity") != uidvalidity:
            _save_email_state({"backend": "imap", "uidvalidity": uidvalidity, "watermark": uids[-1]})
            return []  # first poll, or a rebuilt mailbox: baseline, never read the backlog aloud
        fresh = [u for u in uids if u > int(state.get("watermark") or 0)][:limit]
        if not fresh:
            return []
        messages = []
        for uid in fresh:
            _, parts = await client.uid("FETCH", str(uid), "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
            for part in parts:
                if isinstance(part, tuple):
                    header = email.message_from_bytes(part[1])
                    messages.append({"id": str(uid), "from": header["From"] or "",
                                     "subject": header["Subject"] or ""})
        _save_email_state({"backend": "imap", "uidvalidity": uidvalidity, "watermark": fresh[-1]})
        return messages
    finally:
        try:
            await client.logout()
        except Exception:  # noqa: BLE001 - a dead connection must not hide the real error
            pass


async def _new_gmail(google: Any, limit: int) -> list[dict]:
    """Inbox mail that has not been announced yet, oldest first.

    Gmail ids are opaque and carry no order, so there is no watermark to move;
    this remembers what it has already said out loud instead, bounded to the
    last ``_SEEN_KEEP`` so the state file does not grow with the mailbox.
    """
    messages = await google.list_messages("in:inbox", _EMAIL_WINDOW)
    state = _email_state()
    if state.get("backend") != "gmail":
        _save_email_state({"backend": "gmail", "seen": [m["id"] for m in messages]})
        return []  # first poll: mail that was already here is history, not news
    seen = [i for i in (state.get("seen") or [])]
    known = set(seen)
    fresh = [m for m in reversed(messages) if m["id"] not in known][:limit]
    if fresh:
        _save_email_state({"backend": "gmail", "seen": (seen + [m["id"] for m in fresh])[-_SEEN_KEEP:]})
    return fresh


async def _new_emails(limit: int = 20) -> list[dict]:
    """Mail Atulya has not announced yet, oldest first.

    Returns an empty list when nothing is configured, so a machine with no
    mailbox gets a watcher costing one branch per tick rather than a stack
    trace every two minutes.
    """
    google = _d._google()
    if google is not None:
        return await _new_gmail(google, limit)
    return await _new_imap(limit)


async def watch_email(events: Any, interval: float = 120.0, limit: int = 20) -> None:
    """Emit ``email.new`` once per message that arrived after we started watching.

    ``fetch_emails`` only answers when somebody asks, and an assistant that has
    to be asked is a mailbox rather than a secretary.
    """
    failed: str | None = None
    while True:
        try:
            for message in await _d._new_emails(limit):
                await events.emit("email.new", {
                    "from": _sender_name(message.get("from", "") or "someone"),
                    "subject": message.get("subject") or "(no subject)",
                })
            failed = None
        except Exception as exc:  # noqa: BLE001 - the watcher must never die
            text = f"{type(exc).__name__}: {exc}"
            if text == failed:  # the same fault, hundreds of times a day, is noise
                _d.logger.debug("email watch failed: %s", text)
            else:
                _d.logger.warning("email watch failed: %s", text)
                failed = text
        await asyncio.sleep(interval)


