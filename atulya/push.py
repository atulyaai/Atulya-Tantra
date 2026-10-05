"""Optional Web Push delivery backed by the existing browser subscriptions."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from atulya import raksha as vault

_LOCK = threading.RLock()
_MAX_SUBSCRIPTIONS = 8
_MAX_USERS = 200


def public_key() -> str:
    return os.environ.get("ATULYA_VAPID_PUBLIC_KEY", "").strip()


def configured() -> bool:
    return bool(public_key() and os.environ.get("ATULYA_VAPID_PRIVATE_KEY") and os.environ.get("ATULYA_VAPID_SUBJECT"))


def _path() -> Path:
    return Path(os.environ.get("ATULYA_AGENT_DATA_DIR", "kosh/agent")) / "push_subscriptions.json"


def _legacy_path() -> Path:
    return Path(__file__).resolve().parents[1] / "kosh" / "push_subs.json"


def _read() -> dict[str, list[dict[str, Any]]]:
    try:
        value = json.loads(vault.read_text(_path()))
    except FileNotFoundError:
        try:
            value = json.loads(vault.read_text(_legacy_path()))
        except FileNotFoundError:
            return {}
    if not isinstance(value, dict):
        return {}
    return {str(user): [s for s in rows if isinstance(s, dict) and isinstance(s.get("endpoint"), str)]
            for user, rows in value.items() if isinstance(rows, list)}


def _write(data: dict[str, list[dict[str, Any]]]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    vault.write_text(path, json.dumps(data, separators=(",", ":")))
    _legacy_path().unlink(missing_ok=True)


def subscribe(username: str, subscription: Any) -> None:
    if not isinstance(subscription, dict):
        raise ValueError("A push subscription object is required.")
    endpoint = subscription.get("endpoint")
    keys = subscription.get("keys")
    if not isinstance(endpoint, str) or not endpoint.startswith("https://") or not isinstance(keys, dict):
        raise ValueError("The push subscription is missing its secure endpoint or keys.")
    clean = {"endpoint": endpoint[:2048], "keys": {key: str(keys.get(key, ""))[:512] for key in ("p256dh", "auth")}}
    if not all(clean["keys"].values()):
        raise ValueError("The push subscription is missing encryption keys.")
    with _LOCK:
        data = _read()
        rows = [row for row in data.get(username, []) if row.get("endpoint") != endpoint]
        rows.append(clean)
        data[username] = rows[-_MAX_SUBSCRIPTIONS:]
        data = dict(list(data.items())[-_MAX_USERS:])
        _write(data)


def unsubscribe(username: str, endpoint: str = "") -> None:
    with _LOCK:
        data = _read()
        if endpoint:
            data[username] = [row for row in data.get(username, []) if row.get("endpoint") != endpoint]
            if not data[username]:
                data.pop(username, None)
        else:
            data.pop(username, None)
        if data:
            _write(data)
        else:
            _path().unlink(missing_ok=True)
            _legacy_path().unlink(missing_ok=True)


def send(username: str, payload: dict[str, Any]) -> int:
    """Send one notification; stale endpoints are removed and delivery stays best effort."""
    if not configured():
        return 0
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        return 0
    encoded = json.dumps({key: str(payload.get(key, ""))[:240] for key in ("title", "body", "type")})
    sent = 0
    stale: set[str] = set()
    data = _read()
    for subscription in data.get(username, []):
        try:
            webpush(subscription_info=subscription, data=encoded,
                    vapid_private_key=os.environ["ATULYA_VAPID_PRIVATE_KEY"],
                    vapid_claims={"sub": os.environ["ATULYA_VAPID_SUBJECT"]}, timeout=8)
            sent += 1
        except WebPushException as exc:
            response = getattr(exc, "response", None)
            if response is not None and getattr(response, "status_code", 0) in (404, 410):
                stale.add(subscription["endpoint"])
        except Exception:  # noqa: BLE001 - a push outage must not interrupt Atulya
            continue
    if stale:
        with _LOCK:
            data = _read()
            data[username] = [row for row in data.get(username, []) if row.get("endpoint") not in stale]
            _write(data)
    return sent

