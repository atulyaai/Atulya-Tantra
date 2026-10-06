"""Outbound, paired computer companion for remote use of the shared Sharir rules."""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

from atulya import queue as agent_queue
from atulya import raksha

_TTL = 180
_MAX_PENDING = 50

_commands = agent_queue.CommandQueue("dut_queue.json", ttl=_TTL, limit=_MAX_PENDING)


def enqueue(device_id: str, operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if operation not in {"diagnose", "list_dir", "find_files", "read_file", "run_command"}:
        raise ValueError("That remote computer operation is not supported.")
    if not isinstance(arguments, dict) or len(json.dumps(arguments, ensure_ascii=False)) > 8000:
        raise ValueError("Remote task arguments are invalid or too large.")
    command = _commands.enqueue(device_id, operation=operation, arguments=arguments)
    return {"id": command["id"], "operation": operation, "expires_at": command["expires_at"]}


def poll(device_id: str, permission: str = "read") -> list[dict[str, Any]]:
    ready = _commands.poll(device_id, ("id", "operation", "arguments", "expires_at"))
    for row in ready:
        row["permission"] = permission
    return ready


def result(device_id: str, command_id: str, value: dict[str, Any]) -> bool:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if len(encoded) > 20_000:
        value = {"ok": False, "error": "Remote result exceeded 20 KB."}
    def record(store: dict[str, list[dict[str, Any]]]) -> bool:
        row = next((item for item in store["commands"] if item.get("id") == command_id
                    and item.get("device_id") == device_id and item.get("status") == "sent"), None)
        if not row:
            return False
        row["status"] = "done"
        store.setdefault("results", []).append(
            {"id": command_id, "device_id": device_id, "result": value, "at": time.time()})
        store["results"] = store["results"][-100:]
        return True

    return _commands.update(record)


def recent_results(device_id: str, limit: int = 20) -> list[dict[str, Any]]:
    store = _commands.read()
    return [row for row in store.get("results", [])
            if row.get("device_id") == device_id][-max(1, min(limit, 50)):]


def execute(operation: str, arguments: dict[str, Any], permission: str = "read") -> dict[str, Any]:
    """Dispatch to shared, allowlisted Sharir operations under this device's permission."""
    from atulya import bhava, sharir

    calls = {
        "diagnose": sharir.diagnose,
        "list_dir": sharir.list_dir,
        "find_files": sharir.find_files,
        "read_file": sharir.read_file,
        "run_command": sharir.run_command,
    }
    if operation not in calls:
        return {"ok": False, "error": "Unsupported remote operation."}
    try:
        with bhava.acting_as("owner", {"role": "device", "permission": permission}):
            output = calls[operation](**arguments)
        return {"ok": True, "output": str(output)[:20_000]}
    except Exception as exc:  # noqa: BLE001 - result returns to the server, never to logs
        return {"ok": False, "error": str(exc)[:1000]}


def run(server: str, token: str, poll_seconds: int = 10) -> None:
    headers = {"X-Atulya-Token": token}
    base = server.rstrip("/")
    if not base.startswith("https://") and not base.startswith("http://localhost"):
        raise ValueError("Use an HTTPS Atulya server address.")
    while True:
        try:
            response = httpx.get(f"{base}/agent/commands", headers=headers, timeout=20)
            response.raise_for_status()
            for command in response.json().get("commands", []):
                output = execute(command["operation"], command.get("arguments", {}), command.get("permission", "read"))
                httpx.post(f"{base}/agent/results/{command['id']}", headers=headers,
                           json={"result": output}, timeout=20).raise_for_status()
        except Exception as exc:  # noqa: BLE001 - keep companion alive during network outages
            print(f"Atulya companion: {exc}", flush=True)
        time.sleep(max(3, min(int(poll_seconds), 60)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Paired Atulya computer companion")
    parser.add_argument("--server", default=os.environ.get("ATULYA_SERVER", ""))
    parser.add_argument("--poll", type=int, default=10)
    parser.add_argument("--name", default=os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "Computer")
    args = parser.parse_args()
    token = os.environ.get("ATULYA_DEVICE_TOKEN", "")
    token_path = Path.home() / ".config" / "atulya" / "device-token"
    if not token:
        try:
            token = token_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            token = ""
    if not token:
        import getpass

        code = getpass.getpass("One-time pairing code from Atulya: ").strip()
        if not args.server or not code:
            parser.error("provide --server and a valid pairing code")
        if not args.server.startswith("https://") and not args.server.startswith("http://localhost"):
            parser.error("Use an HTTPS Atulya server address.")
        response = httpx.post(f"{args.server.rstrip('/')}/api/pairing/enroll",
                              json={"code": code, "name": args.name, "kind": "computer"}, timeout=20)
        response.raise_for_status()
        token = response.json()["token"]
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(token, encoding="utf-8")
        try:
            raksha._secure_file(token_path)
        except Exception as exc:  # noqa: BLE001 - never leave an unprotected paired-device token behind
            token_path.unlink(missing_ok=True)
            raise RuntimeError("Could not restrict permissions on the paired device token file.") from exc
        print(f"Paired as {args.name}. Device token saved in the current user's private config folder.")
    if not args.server or not token:
        parser.error("provide --server and ATULYA_DEVICE_TOKEN")
    run(args.server, token, args.poll)


if __name__ == "__main__":
    main()
