"""Allowlisted Telegram polling channel for chat, status, and reminders."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

import httpx

from tools.plugins.brain import Brain, Message
from atulya.history import ConversationHistory
from tools.plugins.productivity.reminders import ReminderStore
from tools.plugins.registry import PluginContext, PluginExecutionError, PluginRegistry
from tools.plugins.productivity.briefing import briefing_city, briefing_prompt, briefing_time
from tools.plugins.toolkit import Toolbox

logger = logging.getLogger(__name__)

def _parse_due(value: str, now: datetime | None = None) -> datetime:
    """Parse `10m`, `2h`, `1d`, `in 20 minutes`, or an ISO date/time."""
    current = now or datetime.now(timezone.utc)
    compact = re.fullmatch(r"\s*(\d{1,4})\s*([mhd])\s*", value, re.I)
    natural = re.fullmatch(r"\s*in\s+(\d{1,4})\s+(minutes?|hours?|days?)\s*", value, re.I)
    if compact:
        amount, unit = int(compact.group(1)), compact.group(2).lower()
        delta = {"m": timedelta(minutes=amount), "h": timedelta(hours=amount), "d": timedelta(days=amount)}[unit]
    elif natural:
        amount, unit = int(natural.group(1)), natural.group(2).lower()[0]
        delta = {"m": timedelta(minutes=amount), "h": timedelta(hours=amount), "d": timedelta(days=amount)}[unit]
    else:
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Use 10m, 2h, 1d, 'in 20 minutes', or an ISO date/time.") from exc
        return parsed.astimezone() if parsed.tzinfo is None else parsed
    if amount < 1:
        raise ValueError("Reminder time must be in the future.")
    return current + delta


class TelegramChannel:
    """Long-poll Telegram only for explicitly allowlisted private user IDs."""

    def __init__(
        self,
        *,
        token: str,
        allowed_user_ids: set[str],
        brain: Brain | None,
        history: ConversationHistory,
        reminders: ReminderStore,
        status_summary,
        command_plugins: PluginRegistry | None = None,
        personal_memory=None,
        calendar=None,
        briefing_log=None,
        profiles=None,
        data_dir=None,
    ) -> None:
        self._token = token.strip()
        self._allowed = {value for value in allowed_user_ids if value.isdigit()}
        self._brain = brain
        self._history = history
        self._reminders = reminders
        self._status_summary = status_summary
        self._command_plugins = command_plugins
        self._personal_memory = personal_memory
        self._calendar = calendar
        self._briefing_log = briefing_log
        self._profiles = profiles
        self._members_path = (data_dir / "telegram_members.json") if data_dir else None
        self._briefing_task: asyncio.Task | None = None
        self._offset = 0
        self._poll_task: asyncio.Task | None = None
        self._reminder_task: asyncio.Task | None = None
        self._stopping = asyncio.Event()
        self._connected = False
        self._last_error = ""
        self._failures = 0
        self._guest_usage: dict[str, tuple[str, int]] = {}

    @property
    def configured(self) -> bool:
        return bool(self._token and self._allowed)

    @property
    def state(self) -> str:
        if not self._token:
            return "off"
        if not self._allowed:
            return "setup"
        return "ready" if self._connected else "setup"

    @property
    def status_label(self) -> str:
        if not self._token:
            return "Not configured"
        if not self._allowed:
            return "Access not paired"
        return "Connected" if self._connected else self._last_error or "Connecting"

    async def start(self) -> None:
        if not self.configured or self._poll_task is not None:
            return
        self._stopping.clear()
        self._poll_task = asyncio.create_task(self._poll(), name="atulya-telegram-poll")
        self._reminder_task = asyncio.create_task(self._deliver_reminders(), name="atulya-reminders")
        if self._briefing_log is not None and briefing_time() is not None:
            self._briefing_task = asyncio.create_task(self._deliver_briefings(), name="atulya-briefings")

    async def stop(self) -> None:
        self._stopping.set()
        tasks = [task for task in (self._poll_task, self._reminder_task, self._briefing_task) if task is not None]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._poll_task = None
        self._reminder_task = None
        self._briefing_task = None

    async def notify(self, text: str) -> int:
        """Send a message to every allowlisted owner; works even while polling is in conflict."""
        if not self._token or not self._allowed:
            return 0
        sent = 0
        async with httpx.AsyncClient(timeout=httpx.Timeout(10, connect=5)) as client:
            for user_id in sorted(self._allowed):
                try:
                    response = await client.post(self._url("sendMessage"), json={"chat_id": user_id, "text": text[:4000]})
                    response.raise_for_status()
                    sent += 1
                except httpx.HTTPError:
                    logger.warning("Telegram notification could not be delivered")
        return sent

    def _url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self._token}/{method}"

    async def _poll(self) -> None:
        timeout = httpx.Timeout(40, connect=10)
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Start after the latest queued update so an app restart does not
            # unexpectedly replay old messages or send stale bot replies.
            try:
                backlog = await client.get(self._url("getUpdates"), params={"timeout": 0})
                backlog.raise_for_status()
                body = backlog.json()
                if body.get("ok"):
                    self._offset = max(
                        (int(item.get("update_id", 0)) + 1 for item in body.get("result", [])),
                        default=0,
                    )
            except (httpx.HTTPError, ValueError, TypeError, KeyError):
                pass
            except Exception as exc:
                logger.error("Telegram backlog check failed (%s)", type(exc).__name__)
            while not self._stopping.is_set():
                try:
                    response = await client.get(
                        self._url("getUpdates"),
                        params={"timeout": 30, "offset": self._offset, "allowed_updates": '["message"]'},
                    )
                    response.raise_for_status()
                    body = response.json()
                    if not body.get("ok"):
                        await self._poll_failed(body.get("error_code"))
                        continue
                    self._connected = True
                    self._last_error = ""
                    self._failures = 0
                    for update in body.get("result", []):
                        self._offset = max(self._offset, int(update.get("update_id", 0)) + 1)
                        await self._handle_message(client, update.get("message", {}))
                except asyncio.CancelledError:
                    raise
                except httpx.HTTPStatusError as exc:
                    await self._poll_failed(exc.response.status_code)
                except (httpx.HTTPError, ValueError, TypeError, KeyError):
                    await self._poll_failed(None)
                except Exception as exc:
                    self._connected = False
                    self._last_error = "Telegram service recovering"
                    logger.error("Telegram polling recovered from an error (%s)", type(exc).__name__)
                    await asyncio.sleep(5)

    GUEST_DAILY_LIMIT = 30
    FREE_MESSAGES_BEFORE_REGISTER = 5
    MEMBER_DAILY_LIMIT = 100
    # All guests together; protects the cloud-model budget (ATULYA_GUEST_DAILY_TOTAL overrides).
    GUEST_DAILY_TOTAL = 200

    async def _guest_message(self, client: httpx.AsyncClient, user_id: str, chat_id: str, message_id: str,
                             text: str) -> None:
        """Strangers get a limited public assistant: info tools only, 30 messages a day, nothing private."""
        today = datetime.now().date().isoformat()
        day, used = self._guest_usage.get(user_id, (today, 0))
        if day != today:
            used = 0
        member = self._members().get(user_id, {})
        state = member.get("state")
        first_word = text.split(maxsplit=1)[0].split("@", 1)[0].lower()
        if first_word == "/register":
            name = " ".join(text.split()[1:])[:40].strip()
            if not name:
                reply = "Send /register followed by your name, e.g. /register Rahul."
            elif state == "approved":
                reply = "You're already registered."
            else:
                self._save_member(user_id, {"name": name, "state": "pending", "since": today})
                await self.notify(f"New Atulya registration: {name} (Telegram id {user_id}). "
                                  f"Reply /approve {user_id} or /deny {user_id}.")
                reply = "Thanks! Your registration is waiting for the owner's approval."
            await self._send(client, chat_id, reply)
            return
        if state == "denied":
            await self._send(client, chat_id, "Sorry, this assistant isn't available to you.")
            return
        daily_limit = self.MEMBER_DAILY_LIMIT if state == "approved" else self.GUEST_DAILY_LIMIT
        if state != "approved" and used >= self.FREE_MESSAGES_BEFORE_REGISTER:
            await self._send(client, chat_id, "To keep chatting, please register: send /register <your name>. "
                                              "The owner approves new users." if state != "pending"
                             else "Your registration is still waiting for approval.")
            return
        total_today = sum(count for day_seen, count in self._guest_usage.values() if day_seen == today)
        try:
            total_cap = int(os.environ.get("ATULYA_GUEST_DAILY_TOTAL", self.GUEST_DAILY_TOTAL))
        except ValueError:
            total_cap = self.GUEST_DAILY_TOTAL
        if used >= daily_limit or total_today >= total_cap:
            reply = "Guest access is at its limit for today. Try again tomorrow."
        elif text.split(maxsplit=1)[0].split("@", 1)[0].lower() in {"/start", "/help"}:
            reply = ("Hi, I'm Atulya. Ask me anything — weather, news, maths, quick facts. "
                     f"Guests get {self.GUEST_DAILY_LIMIT} messages a day.")
        elif self._brain is None:
            reply = "I'm not available right now."
        else:
            scoped = f"tgguest_{user_id}"
            try:
                saved = await asyncio.to_thread(self._history.read, f"tg{user_id}", 10, scoped)
                conversation = [Message(role=row["role"], content=row["content"]) for row in saved
                                if row["role"] in {"user", "assistant"}]
                conversation.append(Message(role="user", content=text[:1000]))
                toolbox = Toolbox.for_registry(self._command_plugins, None) if self._command_plugins else None
                guard = ("You are talking to a guest, not your owner. Never reveal anything about your owner, "
                         "their memory, calendar, devices or settings. Keep answers short.")
                reply = (await self._brain.respond_with_tools(conversation, toolbox, system_instructions=guard)).text \
                    if toolbox else (await self._brain.respond(conversation, system_instructions=guard)).text
                await asyncio.to_thread(self._history.append, f"tg{user_id}", f"u{message_id}", "user", text[:1000], scoped)
                await asyncio.to_thread(self._history.append, f"tg{user_id}", f"a{message_id}", "assistant", reply, scoped)
            except Exception:
                reply = "I couldn't answer that just now. Please try again."
        self._guest_usage[user_id] = (today, used + 1)
        try:
            response = await client.post(self._url("sendMessage"), json={"chat_id": chat_id, "text": reply[:4000]})
            response.raise_for_status()
        except httpx.HTTPError:
            return

    # --- registered Telegram members ---------------------------------------------
    def web_identity(self, telegram_id: str) -> str | None:
        """'owner' for allowlisted ids, 'member' for approved registrations, else None."""
        if telegram_id in self._allowed:
            return "owner"
        return "member" if self._members().get(telegram_id, {}).get("state") == "approved" else None

    def verify_webapp_data(self, init_data: str, max_age: int = 86400) -> dict | None:
        """Validate Telegram Mini App initData (HMAC with the bot token). Returns the user dict."""
        import hashlib
        import hmac
        import time as _time
        from urllib.parse import parse_qsl

        if not self._token or not init_data or len(init_data) > 4096:
            return None
        fields = dict(parse_qsl(init_data, keep_blank_values=True))
        received = fields.pop("hash", "")
        check = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
        secret = hmac.new(b"WebAppData", self._token.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not received or not hmac.compare_digest(expected, received):
            return None
        try:
            if _time.time() - int(fields.get("auth_date", "0")) > max_age:
                return None
            user = json.loads(fields.get("user", "{}"))
        except ValueError:
            return None
        return user if isinstance(user, dict) and str(user.get("id", "")).isdigit() else None

    async def set_menu_button(self, url: str) -> None:
        """Show an 'Open Atulya' button in the bot that launches the Mini App."""
        if not self._token or not url.startswith("https://"):
            return
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(self._url("setChatMenuButton"), json={
                    "menu_button": {"type": "web_app", "text": "Open Atulya", "web_app": {"url": url}}})
        except httpx.HTTPError:
            logger.info("Could not set the Telegram menu button")

    def _members(self) -> dict[str, dict]:
        if self._members_path is None or not self._members_path.is_file():
            return {}
        try:
            data = json.loads(self._members_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save_member(self, user_id: str, info: dict) -> None:
        if self._members_path is None:
            return
        members = self._members()
        members[user_id] = info
        self._members_path.write_text(json.dumps(members, indent=1), encoding="utf-8")

    def _decide_member(self, user_id: str, approve: bool) -> str:
        member = self._members().get(user_id)
        if not user_id.isdigit() or member is None:
            return "No registration with that id. Send /members to list them."
        member["state"] = "approved" if approve else "denied"
        self._save_member(user_id, member)
        return f"{member.get('name', user_id)} is now {member['state']}."

    async def _send(self, client: httpx.AsyncClient, chat_id: str, text: str) -> None:
        try:
            response = await client.post(self._url("sendMessage"), json={"chat_id": chat_id, "text": text[:4000]})
            response.raise_for_status()
        except httpx.HTTPError:
            pass

    async def _poll_failed(self, status_code: int | None) -> None:
        """Back off exponentially and log each distinct failure kind once, never per retry."""
        self._connected = False
        self._failures += 1
        if status_code == 409:
            error = "Polling conflict"
            hint = ("another program is polling this bot token (or a webhook is set); "
                    "stop the other copy or rotate the token in @BotFather")
        elif status_code in {401, 404}:
            error = "Bot access denied"
            hint = "the bot token was rejected; update ATULYA_TELEGRAM_BOT_TOKEN"
        else:
            error, hint = "Connection unavailable", "network or Telegram is unreachable"
        if error != self._last_error:
            logger.warning("Telegram polling paused: %s", hint)
        self._last_error = error
        delay = 300 if error == "Bot access denied" else min(60, 3 * 2 ** min(self._failures - 1, 5))
        try:
            await asyncio.wait_for(self._stopping.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass

    async def _handle_message(self, client: httpx.AsyncClient, message: dict) -> None:
        sender = message.get("from") or {}
        chat = message.get("chat") or {}
        user_id = str(sender.get("id", ""))
        chat_id = str(chat.get("id", ""))
        if chat.get("type") != "private" or not user_id.isdigit() or not chat_id.lstrip("-").isdigit():
            return
        text = str(message.get("text") or "").strip()
        if not text:
            return
        if user_id not in self._allowed:
            if os.environ.get("ATULYA_TELEGRAM_OPEN", "").strip() == "1":
                await self._guest_message(client, user_id, chat_id, str(message.get("message_id", "")), text)
            return
        message_id = str(message.get("message_id", ""))
        command_parts = text.split(maxsplit=1)
        command = command_parts[0].split("@", 1)[0].lower()
        command_args = command_parts[1] if len(command_parts) > 1 else ""
        if command in {"/start", "/help"}:
            reply = (
                "Atulya is connected. Send a message to chat. Commands: /status, /reminders, "
                "/remind 10m take a break. Use 10m, 2h, 1d, or an ISO date/time."
            )
        elif command == "/status":
            reply = self._status_summary()
        elif command == "/reminders":
            items = await asyncio.to_thread(self._reminders.list_for_user, user_id)
            reply = self._format_reminders(items)
        elif command == "/remind":
            reply = await self._create_reminder(user_id, chat_id, command_args.strip())
        elif command in {"/approve", "/deny"}:
            reply = self._decide_member(command_args.strip(), command == "/approve")
        elif command == "/members":
            members = self._members()
            reply = "\n".join(f"{uid}: {info.get('name', '?')} — {info.get('state')}" for uid, info in members.items()) \
                or "No registered Telegram users yet."
        else:
            reply = None
            if self._command_plugins is not None and self._personal_memory is not None and self._calendar is not None:
                try:
                    reply = await self._command_plugins.dispatch(
                        text, PluginContext(f"tg{user_id}", self._personal_memory, self._calendar, f"tg_{user_id}")
                    )
                except PluginExecutionError:
                    reply = "That feature is unavailable right now."
            if reply is None:
                reply = await self._answer(user_id, message_id, text)
        try:
            response = await client.post(self._url("sendMessage"), json={"chat_id": chat_id, "text": reply[:4000]})
            response.raise_for_status()
        except httpx.HTTPError:
            # Do not write bot URLs, tokens, or user chat IDs to logs.
            return

    async def _answer(self, user_id: str, message_id: str, text: str) -> str:
        if self._brain is None:
            return "Text chat is not available right now."
        conversation_id = f"tg{user_id}"
        try:
            scoped_user = f"tg_{user_id}"
            saved = await asyncio.to_thread(self._history.read, conversation_id, 30, scoped_user)
            conversation = [Message(role=row["role"], content=row["content"]) for row in saved if row["role"] in {"user", "assistant"}]
            conversation.append(Message(role="user", content=text))
            if self._command_plugins is not None and self._personal_memory is not None and self._calendar is not None:
                toolbox = Toolbox.for_registry(self._command_plugins, PluginContext(
                    conversation_id, self._personal_memory, self._calendar, scoped_user, history=self._history,
                    profile=self._profiles))
                reply = await self._brain.respond_with_tools(conversation, toolbox,
                                                             system_instructions=self._style(scoped_user))
            else:
                reply = await self._brain.respond(conversation)
        except Exception:
            return "I couldn't complete that reply. Please try again in a moment."
        try:
            await asyncio.to_thread(self._history.append, conversation_id, f"u{message_id}", "user", text, scoped_user)
            await asyncio.to_thread(self._history.append, conversation_id, f"a{message_id}", "assistant", reply.text, scoped_user)
        except ValueError:
            pass
        return reply.text

    def _style(self, user_id: str) -> str:
        if self._profiles is None:
            return ""
        from atulya.profiles import profile_instructions

        return profile_instructions(self._profiles.get(user_id))

    async def _deliver_briefings(self) -> None:
        """Send each allowlisted user one morning briefing per day at ATULYA_BRIEFING_TIME."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=10)) as client:
            while not self._stopping.is_set():
                try:
                    hour, minute = briefing_time() or (25, 0)
                    now = datetime.now().astimezone()
                    if (now.hour, now.minute) >= (hour, minute) and self._brain is not None:
                        for user_id in sorted(self._allowed):
                            recipient = f"tg_{user_id}"
                            if await asyncio.to_thread(self._briefing_log.sent_today, recipient):
                                continue
                            toolbox = Toolbox.for_registry(self._command_plugins, PluginContext(
                                f"tg{user_id}", self._personal_memory, self._calendar, recipient,
                                history=self._history)) if self._command_plugins is not None else None
                            city = (self._profiles.get(recipient).get("city") if self._profiles else "") or briefing_city()
                            prompt = [Message(role="user", content=briefing_prompt(city))]
                            reply = (await self._brain.respond_with_tools(prompt, toolbox,
                                                                          system_instructions=self._style(recipient)) if toolbox
                                     else await self._brain.respond(prompt))
                            response = await client.post(self._url("sendMessage"),
                                                         json={"chat_id": user_id, "text": reply.text[:4000]})
                            response.raise_for_status()
                            await asyncio.to_thread(self._briefing_log.mark, recipient)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning("Morning briefing delivery failed (%s)", type(exc).__name__)
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=60)
                except asyncio.TimeoutError:
                    pass

    async def _create_reminder(self, user_id: str, chat_id: str, payload: str) -> str:
        natural = re.fullmatch(r"(in\s+\d{1,4}\s+(?:minutes?|hours?|days?))\s+(.+)", payload, re.I)
        parts = [natural.group(1), natural.group(2)] if natural else payload.split(maxsplit=1)
        if len(parts) != 2:
            return "Use /remind 10m take a break, /remind 2h call home, or an ISO date/time."
        try:
            due_at = _parse_due(parts[0])
            if due_at <= datetime.now(timezone.utc):
                return "That time has already passed. Choose a future time."
            await asyncio.to_thread(self._reminders.add, user_id, chat_id, parts[1], due_at)
        except ValueError as exc:
            return str(exc)
        local_time = due_at.astimezone().strftime("%b %d at %I:%M %p %Z")
        return f"Reminder saved for {local_time}: {parts[1].strip()}"

    @staticmethod
    def _format_reminders(items: list[dict]) -> str:
        if not items:
            return "No upcoming reminders. Add one with /remind 10m take a break."
        rows = ["Upcoming reminders:"]
        for item in items:
            due = datetime.fromisoformat(str(item["due_at"])).astimezone().strftime("%b %d, %I:%M %p %Z")
            rows.append(f"• {due} — {item['message']}")
        return "\n".join(rows)

    async def _deliver_reminders(self) -> None:
        timeout = httpx.Timeout(15, connect=10)
        async with httpx.AsyncClient(timeout=timeout) as client:
            while not self._stopping.is_set():
                try:
                    due = await asyncio.to_thread(self._reminders.claim_due)
                    for reminder in due:
                        reminder_id = int(reminder["id"])
                        if str(reminder["user_id"]) not in self._allowed:
                            await asyncio.to_thread(self._reminders.mark_failed, reminder_id)
                            continue
                        try:
                            text = f"Reminder: {reminder['message']}"
                            response = await client.post(
                                self._url("sendMessage"),
                                json={"chat_id": reminder["chat_id"], "text": text[:4000]},
                            )
                            response.raise_for_status()
                            await asyncio.to_thread(self._reminders.mark_delivered, reminder_id)
                        except asyncio.CancelledError:
                            raise
                        except Exception as exc:
                            await asyncio.to_thread(self._reminders.retry_failed, reminder_id)
                            logger.error("Telegram reminder delivery failed (%s)", type(exc).__name__)
                except asyncio.CancelledError:
                    raise
                except (httpx.HTTPError, ValueError, TypeError):
                    pass
                except Exception as exc:
                    logger.error("Telegram reminder loop recovered from an error (%s)", type(exc).__name__)
                await asyncio.sleep(10)
