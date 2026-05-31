"""Unified inbound/outbound channel system."""
from __future__ import annotations

import html
import json
import logging
import os
import time
import urllib.parse
import urllib.request
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


async def _post_json(url: str, payload: dict[str, Any], timeout: float = 10.0) -> tuple[int, dict[str, Any]]:
    import asyncio

    def request() -> tuple[int, dict[str, Any]]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8") or "{}"
            return response.status, json.loads(body)

    return await asyncio.to_thread(request)


async def _get_json(url: str, params: dict[str, Any], timeout: float = 10.0) -> tuple[int, dict[str, Any]]:
    import asyncio

    def request() -> tuple[int, dict[str, Any]]:
        query = urllib.parse.urlencode(params)
        with urllib.request.urlopen(f"{url}?{query}", timeout=timeout) as response:
            body = response.read().decode("utf-8") or "{}"
            return response.status, json.loads(body)

    return await asyncio.to_thread(request)


class ChannelType(Enum):
    DISCORD = "discord"
    WHATSAPP = "whatsapp"
    SLACK = "slack"
    SIGNAL = "signal"
    MATRIX = "matrix"
    WEBCHAT = "webchat"
    TELEGRAM = "telegram"
    EMAIL = "email"
    WEBHOOK = "webhook"
    IMESSAGE = "imessage"
    TEAMS = "teams"
    IRC = "irc"
    FEISHU = "feishu"
    LINE = "line"
    QQ = "qq"
    CONSOLE = "console"


@dataclass
class ChannelMessage:
    id: str
    channel: str
    sender: str
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Notification:
    id: str
    channel: ChannelType
    message: str
    title: str = ""
    priority: str = "normal"
    sent: bool = False
    timestamp: float = field(default_factory=time.time)


class ChannelBase(ABC):
    type: ChannelType
    name: str = ""

    def __init__(self):
        self.config: dict[str, Any] = {}
        self.connected = False

    async def connect(self, config: dict[str, Any]) -> bool:
        self.config = dict(config)
        self.connected = True
        return True

    async def disconnect(self):
        self.connected = False

    @abstractmethod
    async def send(self, message: str, chat_id: str = "", **kwargs: Any) -> bool:
        pass

    async def receive(self) -> list[ChannelMessage]:
        return []


class WebChatChannel(ChannelBase):
    type = ChannelType.WEBCHAT
    name = "WebChat"

    def __init__(self):
        super().__init__()
        self._messages: list[ChannelMessage] = []

    async def send(self, message: str, chat_id: str = "", **kwargs: Any) -> bool:
        self._messages.append(ChannelMessage(id=str(len(self._messages) + 1), channel=self.type.value, sender="bot", content=message))
        return True

    async def receive(self) -> list[ChannelMessage]:
        messages = self._messages[:]
        self._messages.clear()
        return messages


class ConsoleChannel(ChannelBase):
    type = ChannelType.CONSOLE
    name = "Console"

    async def send(self, message: str, chat_id: str = "", **kwargs: Any) -> bool:
        title = kwargs.get("title", "")
        priority = kwargs.get("priority", "normal").upper()
        print(f"[{priority}] {title}: {message}" if title else f"[{priority}] {message}")
        return True


class TelegramChannel(ChannelBase):
    type = ChannelType.TELEGRAM
    name = "Telegram"

    def __init__(self):
        super().__init__()
        self._histories: dict[str, list[dict[str, str]]] = {}

    async def send(self, message: str, chat_id: str = "", **kwargs: Any) -> bool:
        token = self.config.get("bot_token") or self.config.get("token") or os.environ.get("ATULYA_TELEGRAM_BOT_TOKEN")
        target = chat_id or self.config.get("chat_id", "") or os.environ.get("ATULYA_TELEGRAM_CHAT_ID", "")
        if not token or not target:
            logger.warning("Telegram not configured")
            return False
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {"chat_id": target, "text": message}
            parse_mode = kwargs.get("parse_mode") or self.config.get("parse_mode")
            if parse_mode:
                payload["parse_mode"] = parse_mode
            if kwargs.get("reply_markup"):
                payload["reply_markup"] = kwargs["reply_markup"]
            status, _ = await _post_json(url, payload)
            return status < 400
        except Exception as exc:
            logger.warning("Telegram send failed: %s", exc)
            return False

    async def send_photo(self, photo_url: str, caption: str = "", chat_id: str = "", **kwargs: Any) -> bool:
        token = self.config.get("bot_token") or self.config.get("token") or os.environ.get("ATULYA_TELEGRAM_BOT_TOKEN")
        target = chat_id or self.config.get("chat_id", "") or os.environ.get("ATULYA_TELEGRAM_CHAT_ID", "")
        if not token or not target:
            logger.warning("Telegram not configured")
            return False
        try:
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            payload: dict[str, Any] = {"chat_id": target, "photo": photo_url, "caption": caption}
            parse_mode = kwargs.get("parse_mode") or self.config.get("parse_mode")
            if parse_mode:
                payload["parse_mode"] = parse_mode
            if kwargs.get("reply_markup"):
                payload["reply_markup"] = kwargs["reply_markup"]
            status, _ = await _post_json(url, payload)
            return status < 400
        except Exception as exc:
            logger.warning("Telegram sendPhoto failed: %s", exc)
            return False

    async def receive(self) -> list[ChannelMessage]:
        token = self.config.get("bot_token") or self.config.get("token") or os.environ.get("ATULYA_TELEGRAM_BOT_TOKEN")
        if not token:
            return []
        offset = self.config.get("offset", 0)
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            status, payload = await _get_json(url, {"offset": offset, "timeout": 30})
            if status >= 400:
                return []
        except Exception as exc:
            logger.warning("Telegram receive failed: %s", exc)
            return []
        messages: list[ChannelMessage] = []
        for update in payload.get("result", []):
            self.config["offset"] = max(self.config.get("offset", 0), update.get("update_id", 0) + 1)
            msg = update.get("message") or {}
            text = msg.get("text", "")
            if not text:
                continue
            chat = msg.get("chat", {})
            sender = msg.get("from", {})
            messages.append(ChannelMessage(
                id=str(update.get("update_id")),
                channel=self.type.value,
                sender=str(sender.get("id", chat.get("id", ""))),
                content=text,
                metadata={"chat_id": chat.get("id"), "raw": update},
            ))
        return messages

    def is_allowed(self, sender_id: str) -> bool:
        allowlist = self.config.get("allowlist") or self.config.get("allowed_users") or os.environ.get("ATULYA_TELEGRAM_ALLOWLIST", "")
        if isinstance(allowlist, str):
            allowed = {item.strip() for item in allowlist.split(",") if item.strip()}
        else:
            allowed = {str(item).strip() for item in allowlist if str(item).strip()}
        return allowed and str(sender_id) in allowed

    async def handle_message(self, message: ChannelMessage, llm: Any | None = None) -> str:
        text = message.content.strip()
        chat_id = str(message.metadata.get("chat_id") or "")
        if not self.is_allowed(message.sender):
            await self.send("Access denied. Ask the owner to add your Telegram user id to ATULYA_TELEGRAM_ALLOWLIST.", chat_id)
            return "denied"
        if text in {"/start", "/help"}:
            await self.send("Atulya is online. Use /ask <question>, /status, or /help.", chat_id)
            return "help"
        if text == "/status":
            await self.send("Atulya Telegram bridge is running. LLM fallback is free-first.", chat_id)
            return "status"
        if text.startswith("/ask"):
            prompt = text[4:].strip()
        else:
            prompt = text
        if not prompt:
            await self.send("Send /ask followed by a question.", chat_id)
            return "empty"
        if llm is None:
            from atulya.llm import AtulyaLLM
            llm = AtulyaLLM()
        history = self._histories.setdefault(str(message.sender), [])
        response = await llm.ask(prompt, history=history)
        history.extend([
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": response.text},
        ])
        del history[:-20]
        outgoing = html.escape(response.text)
        show_provider = self.config.get("show_provider") or os.environ.get("ATULYA_TELEGRAM_SHOW_PROVIDER", "").lower() in {"1", "true", "yes"}
        if show_provider and getattr(response, "provider", ""):
            outgoing = f"{outgoing}\n\nvia {response.provider}"
        await self.send(outgoing[:3900], chat_id, parse_mode=self.config.get("parse_mode", "HTML"))
        return "answered"

    async def poll_and_reply(self, llm: Any | None = None) -> int:
        count = 0
        for message in await self.receive():
            await self.handle_message(message, llm=llm)
            count += 1
        return count

    async def handle_webhook(self, update: dict[str, Any], llm: Any | None = None) -> str:
        msg = update.get("message") or {}
        chat = msg.get("chat", {})
        sender = msg.get("from", {})
        text = msg.get("text", "")
        if not text:
            return "ignored"
        message = ChannelMessage(
            id=str(update.get("update_id", "")),
            channel=self.type.value,
            sender=str(sender.get("id", chat.get("id", ""))),
            content=text,
            metadata={"chat_id": chat.get("id"), "raw": update},
        )
        return await self.handle_message(message, llm=llm)


class WebhookChannel(ChannelBase):
    type = ChannelType.WEBHOOK
    name = "Webhook"

    async def send(self, message: str, chat_id: str = "", **kwargs: Any) -> bool:
        url = chat_id or self.config.get("url", "")
        if not url:
            logger.warning("Webhook not configured")
            return False
        try:
            status, _ = await _post_json(url, {"message": message, "timestamp": time.time(), **kwargs})
            return status < 400
        except Exception as exc:
            logger.warning("Webhook send failed: %s", exc)
            return False


class SlackChannel(WebhookChannel):
    type = ChannelType.SLACK
    name = "Slack"

    async def send(self, message: str, chat_id: str = "", **kwargs: Any) -> bool:
        self.config.setdefault("url", self.config.get("webhook_url", ""))
        return await super().send(message, chat_id, text=message, **kwargs)


class DiscordChannel(WebhookChannel):
    type = ChannelType.DISCORD
    name = "Discord"

    async def send(self, message: str, chat_id: str = "", **kwargs: Any) -> bool:
        self.config.setdefault("url", self.config.get("webhook_url", ""))
        return await super().send(message, chat_id, content=message, **kwargs)


class EmailChannel(ChannelBase):
    type = ChannelType.EMAIL
    name = "Email"

    async def send(self, message: str, chat_id: str = "", **kwargs: Any) -> bool:
        import asyncio
        config = self.config
        username = config.get("username", "")
        password = config.get("password", "")
        to_email = chat_id or config.get("to_email", "")
        if not all([username, password, to_email]):
            logger.warning("Email not configured")
            return False

        def _send_email():
            import smtplib
            from email.mime.text import MIMEText
            msg = MIMEText(message)
            msg["Subject"] = kwargs.get("title") or "Atulya Notification"
            msg["From"] = username
            msg["To"] = to_email
            with smtplib.SMTP(config.get("smtp_host", "smtp.gmail.com"), int(config.get("smtp_port", 587))) as server:
                server.starttls()
                server.login(username, password)
                server.send_message(msg)

        await asyncio.to_thread(_send_email)
        return True


class WhatsAppChannel(WebhookChannel):
    type = ChannelType.WHATSAPP
    name = "WhatsApp"

    async def send(self, message: str, chat_id: str = "", **kwargs: Any) -> bool:
        url = chat_id or self.config.get("webhook_url") or self.config.get("url", "")
        if not url:
            logger.warning("WhatsApp not configured (set webhook_url)")
            return False
        return await super().send(message, url, **kwargs)


class SignalChannel(WebhookChannel):
    type = ChannelType.SIGNAL
    name = "Signal"

    async def send(self, message: str, chat_id: str = "", **kwargs: Any) -> bool:
        url = chat_id or self.config.get("webhook_url") or self.config.get("url", "")
        if not url:
            logger.warning("Signal not configured (set webhook_url)")
            return False
        return await super().send(message, url, **kwargs)


class MatrixChannel(WebhookChannel):
    type = ChannelType.MATRIX
    name = "Matrix"

    async def send(self, message: str, chat_id: str = "", **kwargs: Any) -> bool:
        url = chat_id or self.config.get("webhook_url") or self.config.get("url", "")
        if not url:
            logger.warning("Matrix not configured (set webhook_url)")
            return False
        return await super().send(message, url, **kwargs)


class TeamsChannel(WebhookChannel):
    type = ChannelType.TEAMS
    name = "Microsoft Teams"

    async def send(self, message: str, chat_id: str = "", **kwargs: Any) -> bool:
        url = chat_id or self.config.get("webhook_url") or self.config.get("url", "")
        if not url:
            logger.warning("Teams not configured (set webhook_url)")
            return False
        return await super().send(message, url, **kwargs)


class IRCChannel(WebhookChannel):
    type = ChannelType.IRC
    name = "IRC"

    async def send(self, message: str, chat_id: str = "", **kwargs: Any) -> bool:
        url = chat_id or self.config.get("webhook_url") or self.config.get("url", "")
        if not url:
            logger.warning("IRC not configured (set webhook_url)")
            return False
        return await super().send(message, url, **kwargs)


class ChannelRegistry:
    def __init__(self, data_dir: str | Path = "config/channels"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._channels: dict[str, ChannelBase] = {}
        self._configs = self._load_configs()

    def _load_configs(self) -> dict[str, dict[str, Any]]:
        config_file = self.data_dir / "channels.json"
        if not config_file.exists():
            return {}
        return json.loads(config_file.read_text(encoding="utf-8"))

    def _save_configs(self) -> None:
        (self.data_dir / "channels.json").write_text(json.dumps(self._configs, indent=2), encoding="utf-8")

    def register(self, channel: ChannelBase):
        self._channels[channel.type.value] = channel

    async def configure(self, channel_type: str, config: dict[str, Any]) -> bool:
        self._configs[channel_type] = dict(config)
        self._save_configs()
        channel = self._channels.get(channel_type)
        return await channel.connect(config) if channel else False

    async def send(self, channel_type: str, message: str, chat_id: str = "", **kwargs: Any) -> bool:
        channel = self._channels.get(channel_type)
        if not channel:
            return False
        if not channel.connected:
            await channel.connect(self._configs.get(channel_type, {}))
        return await channel.send(message, chat_id, **kwargs)

    async def receive(self, channel_type: str | None = None) -> list[ChannelMessage]:
        channels = [self._channels[channel_type]] if channel_type else list(self._channels.values())
        messages: list[ChannelMessage] = []
        for channel in channels:
            if not channel.connected:
                await channel.connect(self._configs.get(channel.type.value, {}))
            messages.extend(await channel.receive())
        return messages

    def get_status(self) -> dict[str, dict[str, Any]]:
        return {
            name: {"type": ch.type.value, "name": ch.name, "connected": ch.connected}
            for name, ch in self._channels.items()
        }


class NotificationSystem:
    """Notification facade backed by the unified channel registry."""

    def __init__(self, data_dir: str | Path = "config/channels"):
        self.registry = create_default_registry(data_dir)
        self._notifications: list[Notification] = []

    def configure(self, channel: str, config: dict[str, Any]):
        self.registry._configs[channel] = dict(config)
        self.registry._save_configs()

    async def send(self, message: str, channel: str = "console", title: str = "", priority: str = "normal") -> Notification:
        sent = await self.registry.send(channel, message, title=title, priority=priority)
        notification = Notification(
            id=str(uuid.uuid4())[:8],
            channel=ChannelType(channel),
            message=message,
            title=title,
            priority=priority,
            sent=sent,
        )
        self._notifications.append(notification)
        return notification

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        return [vars(n) for n in self._notifications[-limit:]]

    def get_stats(self) -> dict[str, Any]:
        by_channel: dict[str, int] = {}
        for item in self._notifications:
            by_channel[item.channel.value] = by_channel.get(item.channel.value, 0) + 1
        return {"total_sent": len(self._notifications), "by_channel": by_channel}


def create_default_registry(data_dir: str | Path = "config/channels") -> ChannelRegistry:
    registry = ChannelRegistry(data_dir)
    for channel in [
        ConsoleChannel(),
        WebChatChannel(),
        TelegramChannel(),
        EmailChannel(),
        WebhookChannel(),
        SlackChannel(),
        DiscordChannel(),
        WhatsAppChannel(),
        SignalChannel(),
        MatrixChannel(),
        TeamsChannel(),
        IRCChannel(),
    ]:
        registry.register(channel)
    return registry


NotifyChannel = ChannelType
