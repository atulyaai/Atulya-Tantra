"""MQTT: connection config and the watcher that turns messages into events."""
from __future__ import annotations

import asyncio
from typing import Any



from atulya import kriya as _d

# ── Watch: MQTT messages arrive as events ────────────────────────────────────

_MQTT_CONFIG_FILE = "mqtt_config.json"
_MQTT_STATE_FILE = "mqtt_state.json"


def _mqtt_config() -> dict:
    data = _d._load_json(_MQTT_CONFIG_FILE)
    return data if isinstance(data, dict) else {}


def _save_mqtt_config(cfg: dict) -> None:
    _d._save_json(_MQTT_CONFIG_FILE, cfg)


def _mqtt_state() -> dict:
    data = _d._load_json(_MQTT_STATE_FILE)
    return data if isinstance(data, dict) else {}


def _save_mqtt_state(state: dict) -> None:
    _d._save_json(_MQTT_STATE_FILE, state)


async def watch_mqtt(events: Any, host: str = "", port: int = 1883, subscribe: str = "atulya/#",
                     username: str = "", password: str = "") -> None:
    """Connect to an MQTT broker and republish messages as `mqtt.<topic>` events.

    Configuration is read from `mqtt_config.json` (created by `mqtt_configure`)
    and can be overridden by arguments. If no host is configured the watcher
    idles instead of failing, so a machine without a broker pays nothing.
    """
    cfg = _mqtt_config()
    host = host or cfg.get("host", "")
    port = port or int(cfg.get("port", 1883))
    subscribe = subscribe or cfg.get("subscribe", "atulya/#")
    username = username or cfg.get("username", "")
    password = password or cfg.get("password", "")

    if not host:
        _d.logger.debug("MQTT watcher: no host configured, idling")
        while True:
            await asyncio.sleep(3600)

    import paho.mqtt.client as mqtt

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if username:
        client.username_pw_set(username, password)

    connected = asyncio.Event()

    def on_connect(c, u, flags, rc, props):
        if rc == 0:
            c.subscribe(subscribe)
            connected.set()
        else:
            _d.logger.warning("MQTT connect failed: %s", rc)

    def on_message(c, u, msg):
        try:
            payload = msg.payload.decode("utf-8", "replace")
        except Exception:
            payload = str(msg.payload)
        asyncio.run_coroutine_threadsafe(
            events.emit(f"mqtt.{msg.topic}", {"topic": msg.topic, "payload": payload}),
            asyncio.get_event_loop(),
        )

    client.on_connect = on_connect
    client.on_message = on_message

    backoff = 1
    while True:
        try:
            client.connect(host, port, keepalive=30)
            client.loop_start()
            await connected.wait()
            _d.logger.info("MQTT connected to %s:%s, subscribed to %s", host, port, subscribe)
            backoff = 1
            while True:
                await asyncio.sleep(1)
                if not client.is_connected():
                    raise ConnectionError("disconnected")
        except asyncio.CancelledError:
            client.loop_stop()
            client.disconnect()
            raise
        except Exception as exc:  # noqa: BLE001 - reconnect loop
            client.loop_stop()
            try:
                client.disconnect()
            except Exception:
                pass
            _d.logger.warning("MQTT error: %s; reconnecting in %ss", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)


@_d.tool("mqtt_configure", "Configure MQTT broker connection", {
    "host": {"type": "string", "description": "Broker host, e.g. 192.168.1.50 or test.mosquitto.org"},
    "port": {"type": "integer", "description": "Broker port (default 1883)", "default": 1883},
    "subscribe": {"type": "string", "description": "Topic pattern to subscribe (default atulya/#)", "default": "atulya/#"},
    "username": {"type": "string", "description": "Username (optional)", "default": ""},
    "password": {"type": "string", "description": "Password (optional)", "default": ""},
})
async def mqtt_configure(host: str = "", port: int = 1883, subscribe: str = "atulya/#",
                          username: str = "", password: str = "") -> str:
    host = str(host).strip()
    if not host:
        return "A broker host is required."
    subscribe = str(subscribe).strip() or "atulya/#"
    _save_mqtt_config({
        "host": host, "port": int(port), "subscribe": subscribe,
        "username": str(username).strip(), "password": str(password).strip()
    })
    return f"MQTT configured: {host}:{port} -> {subscribe}"


@_d.tool("mqtt_status", "Show MQTT configuration and connection status", {})
async def mqtt_status() -> str:
    cfg = _mqtt_config()
    if not cfg.get("host"):
        return "MQTT not configured. Use mqtt_configure to set a broker."
    return (f"Host: {cfg.get('host')}:{cfg.get('port', 1883)}\n"
            f"Subscribe: {cfg.get('subscribe', 'atulya/#')}\n"
            f"User: {cfg.get('username') or '(none)'}")


