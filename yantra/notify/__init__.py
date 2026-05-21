"""Notification System — Telegram, Email, Webhook, Discord, Slack."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class NotifyChannel(Enum):
    TELEGRAM = "telegram"
    EMAIL = "email"
    WEBHOOK = "webhook"
    DISCORD = "discord"
    SLACK = "slack"
    CONSOLE = "console"


@dataclass
class Notification:
    id: str
    channel: NotifyChannel
    message: str
    title: str = ""
    priority: str = "normal"
    sent: bool = False
    timestamp: float = field(default_factory=time.time)


class NotificationSystem:
    """Multi-channel notification system."""

    def __init__(self, data_dir: str | Path = "data/notify"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._notifications: list[Notification] = []
        self._configs: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self):
        config_file = self.data_dir / "notify_config.json"
        if config_file.exists():
            self._configs = json.loads(config_file.read_text())

    def _save_config(self):
        config_file = self.data_dir / "notify_config.json"
        config_file.write_text(json.dumps(self._configs, indent=2))

    def configure(self, channel: str, config: dict[str, Any]):
        """Configure a notification channel."""
        self._configs[channel] = config
        self._save_config()

    async def send(self, message: str, channel: str = "console", title: str = "", priority: str = "normal") -> Notification:
        """Send a notification."""
        import uuid
        notif = Notification(
            id=str(uuid.uuid4())[:8],
            channel=NotifyChannel(channel),
            message=message, title=title, priority=priority,
        )

        try:
            if channel == "console":
                print(f"[{priority.upper()}] {title}: {message}")
            elif channel == "telegram":
                await self._send_telegram(message)
            elif channel == "email":
                await self._send_email(message, title)
            elif channel == "webhook":
                await self._send_webhook(message)
            elif channel == "discord":
                await self._send_discord(message)
            elif channel == "slack":
                await self._send_slack(message)
            notif.sent = True
        except Exception as e:
            logger.error(f"Notification failed ({channel}): {e}")

        self._notifications.append(notif)
        return notif

    async def _send_telegram(self, message: str):
        config = self._configs.get("telegram", {})
        token = config.get("bot_token", "")
        chat_id = config.get("chat_id", "")
        if not token or not chat_id:
            logger.warning("Telegram not configured")
            return
        try:
            import aiohttp
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            async with aiohttp.ClientSession() as session:
                await session.post(url, json={"chat_id": chat_id, "text": message})
        except ImportError:
            pass

    async def _send_email(self, message: str, title: str = ""):
        config = self._configs.get("email", {})
        smtp_host = config.get("smtp_host", "smtp.gmail.com")
        smtp_port = config.get("smtp_port", 587)
        username = config.get("username", "")
        password = config.get("password", "")
        to_email = config.get("to_email", "")
        if not all([username, password, to_email]):
            logger.warning("Email not configured")
            return
        try:
            import smtplib
            from email.mime.text import MIMEText
            msg = MIMEText(message)
            msg["Subject"] = title or "Atulya Notification"
            msg["From"] = username
            msg["To"] = to_email
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(username, password)
                server.send_message(msg)
        except Exception as e:
            logger.error(f"Email send failed: {e}")

    async def _send_webhook(self, message: str):
        config = self._configs.get("webhook", {})
        url = config.get("url", "")
        if not url:
            logger.warning("Webhook not configured")
            return
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                await session.post(url, json={"message": message, "timestamp": time.time()})
        except ImportError:
            pass

    async def _send_discord(self, message: str):
        config = self._configs.get("discord", {})
        webhook_url = config.get("webhook_url", "")
        if not webhook_url:
            logger.warning("Discord not configured")
            return
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                await session.post(webhook_url, json={"content": message})
        except ImportError:
            pass

    async def _send_slack(self, message: str):
        config = self._configs.get("slack", {})
        webhook_url = config.get("webhook_url", "")
        if not webhook_url:
            logger.warning("Slack not configured")
            return
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                await session.post(webhook_url, json={"text": message})
        except ImportError:
            pass

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        return [vars(n) for n in self._notifications[-limit:]]

    def get_stats(self) -> dict[str, Any]:
        by_channel = {}
        for n in self._notifications:
            by_channel[n.channel.value] = by_channel.get(n.channel.value, 0) + 1
        return {"total_sent": len(self._notifications), "by_channel": by_channel}
