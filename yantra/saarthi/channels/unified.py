"""Unified channel system."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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


@dataclass
class ChannelMessage:
    id: str
    channel: str
    sender: str
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class ChannelBase(ABC):
    type: ChannelType
    name: str = ""

    @abstractmethod
    async def connect(self, config: dict[str, Any]) -> bool:
        pass

    @abstractmethod
    async def disconnect(self):
        pass

    @abstractmethod
    async def send(self, message: str, chat_id: str, **kwargs: Any) -> bool:
        pass

    @abstractmethod
    async def receive(self) -> list[ChannelMessage]:
        pass


class DiscordChannel(ChannelBase):
    type = ChannelType.DISCORD
    name = "Discord"
    async def connect(self, config: dict[str, Any]) -> bool: return True
    async def disconnect(self): pass
    async def send(self, message: str, chat_id: str, **kwargs: Any) -> bool: return True
    async def receive(self) -> list[ChannelMessage]: return []


class WhatsAppChannel(ChannelBase):
    type = ChannelType.WHATSAPP
    name = "WhatsApp"
    async def connect(self, config: dict[str, Any]) -> bool: return True
    async def disconnect(self): pass
    async def send(self, message: str, chat_id: str, **kwargs: Any) -> bool: return True
    async def receive(self) -> list[ChannelMessage]: return []


class SlackChannel(ChannelBase):
    type = ChannelType.SLACK
    name = "Slack"
    async def connect(self, config: dict[str, Any]) -> bool: return True
    async def disconnect(self): pass
    async def send(self, message: str, chat_id: str, **kwargs: Any) -> bool: return True
    async def receive(self) -> list[ChannelMessage]: return []


class SignalChannel(ChannelBase):
    type = ChannelType.SIGNAL
    name = "Signal"
    async def connect(self, config: dict[str, Any]) -> bool: return True
    async def disconnect(self): pass
    async def send(self, message: str, chat_id: str, **kwargs: Any) -> bool: return True
    async def receive(self) -> list[ChannelMessage]: return []


class MatrixChannel(ChannelBase):
    type = ChannelType.MATRIX
    name = "Matrix"
    async def connect(self, config: dict[str, Any]) -> bool: return True
    async def disconnect(self): pass
    async def send(self, message: str, chat_id: str, **kwargs: Any) -> bool: return True
    async def receive(self) -> list[ChannelMessage]: return []


class WebChatChannel(ChannelBase):
    type = ChannelType.WEBCHAT
    name = "WebChat"
    def __init__(self):
        self._messages: list[ChannelMessage] = []
    async def connect(self, config: dict[str, Any]) -> bool: return True
    async def disconnect(self): pass
    async def send(self, message: str, chat_id: str, **kwargs: Any) -> bool:
        self._messages.append(ChannelMessage(id=str(len(self._messages)+1), channel="webchat", sender="bot", content=message))
        return True
    async def receive(self) -> list[ChannelMessage]:
        msgs = self._messages[:]
        self._messages.clear()
        return msgs


class TelegramChannel(ChannelBase):
    type = ChannelType.TELEGRAM
    name = "Telegram"
    async def connect(self, config: dict[str, Any]) -> bool: return True
    async def disconnect(self): pass
    async def send(self, message: str, chat_id: str, **kwargs: Any) -> bool: return True
    async def receive(self) -> list[ChannelMessage]: return []


class EmailChannel(ChannelBase):
    type = ChannelType.EMAIL
    name = "Email"
    async def connect(self, config: dict[str, Any]) -> bool: return True
    async def disconnect(self): pass
    async def send(self, message: str, chat_id: str, **kwargs: Any) -> bool: return True
    async def receive(self) -> list[ChannelMessage]: return []


class WebhookChannel(ChannelBase):
    type = ChannelType.WEBHOOK
    name = "Webhook"
    async def connect(self, config: dict[str, Any]) -> bool: return True
    async def disconnect(self): pass
    async def send(self, message: str, chat_id: str, **kwargs: Any) -> bool: return True
    async def receive(self) -> list[ChannelMessage]: return []


class TeamsChannel(ChannelBase):
    type = ChannelType.TEAMS
    name = "Teams"
    async def connect(self, config: dict[str, Any]) -> bool: return True
    async def disconnect(self): pass
    async def send(self, message: str, chat_id: str, **kwargs: Any) -> bool: return True
    async def receive(self) -> list[ChannelMessage]: return []


class IRCChannel(ChannelBase):
    type = ChannelType.IRC
    name = "IRC"
    async def connect(self, config: dict[str, Any]) -> bool: return True
    async def disconnect(self): pass
    async def send(self, message: str, chat_id: str, **kwargs: Any) -> bool: return True
    async def receive(self) -> list[ChannelMessage]: return []


class ChannelRegistry:
    def __init__(self):
        self._channels: dict[str, ChannelBase] = {}

    def register(self, channel: ChannelBase):
        self._channels[channel.type.value] = channel

    async def send(self, channel_type: str, message: str, chat_id: str, **kwargs: Any) -> bool:
        channel = self._channels.get(channel_type)
        if not channel:
            return False
        return await channel.send(message, chat_id, **kwargs)

    def get_status(self) -> dict[str, dict[str, str]]:
        return {name: {"type": ch.type.value, "name": ch.name} for name, ch in self._channels.items()}


def create_default_registry() -> ChannelRegistry:
    registry = ChannelRegistry()
    for ch_class in [DiscordChannel, WhatsAppChannel, SlackChannel, SignalChannel,
                     MatrixChannel, WebChatChannel, TelegramChannel, EmailChannel,
                     WebhookChannel, TeamsChannel, IRCChannel]:
        registry.register(ch_class())
    return registry
