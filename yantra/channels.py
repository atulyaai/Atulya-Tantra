"""Unified inbound/outbound channel system."""
from __future__ import annotations

import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


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

    async def send(self, message: str, chat_id: str = "", **kwargs: Any) -> bool:
        token = self.config.get("bot_token") or self.config.get("token")
        target = chat_id or self.config.get("chat_id", "")
        if not token or not target:
            logger.warning("Telegram not configured")
            return False
        try:
            import aiohttp
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            async with aiohttp.ClientSession() as session:
                response = await session.post(url, json={"chat_id": target, "text": message})
                return response.status < 400
        except ImportError:
            logger.warning("aiohttp not installed; Telegram send unavailable")
            return False

    async def receive(self) -> list[ChannelMessage]:
        token = self.config.get("bot_token") or self.config.get("token")
        if not token:
            return []
        offset = self.config.get("offset", 0)
        try:
            import aiohttp
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            async with aiohttp.ClientSession() as session:
                response = await session.get(url, params={"offset": offset, "timeout": 0})
                if response.status >= 400:
                    return []
                payload = await response.json()
        except ImportError:
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


class WebhookChannel(ChannelBase):
    type = ChannelType.WEBHOOK
    name = "Webhook"

    async def send(self, message: str, chat_id: str = "", **kwargs: Any) -> bool:
        url = chat_id or self.config.get("url", "")
        if not url:
            logger.warning("Webhook not configured")
            return False
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                response = await session.post(url, json={"message": message, "timestamp": time.time(), **kwargs})
                return response.status < 400
        except ImportError:
            logger.warning("aiohttp not installed; webhook send unavailable")
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
        config = self.config
        username = config.get("username", "")
        password = config.get("password", "")
        to_email = chat_id or config.get("to_email", "")
        if not all([username, password, to_email]):
            logger.warning("Email not configured")
            return False
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

    def __init__(self, data_dir: str | Path = "assets/notify"):
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
