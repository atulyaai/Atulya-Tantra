"""Production readiness checks for Jarvis/Atulya deployments."""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ReadinessCheck:
    name: str
    status: str
    detail: str
    required: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "required": self.required,
        }


def run_readiness_checks(root: str | Path = ".") -> dict[str, Any]:
    root_path = Path(root)
    checks = [
        _check_llm_bridge(root_path),
        _check_free_provider(),
        _check_telegram(),
        _check_mcp_config(root_path),
        _check_tantra_gate(root_path),
        _check_secret_hygiene(root_path),
        _check_key_rotation_ack(),
    ]
    required = [item for item in checks if item.required]
    passed_required = [item for item in required if item.status == "pass"]
    blocking = [item for item in required if item.status == "fail"]
    warnings = [item for item in checks if item.status == "warn"]
    grade = "production-ready" if not blocking else "production-candidate"
    return {
        "grade": grade,
        "passed_required": len(passed_required),
        "total_required": len(required),
        "blocking": [item.as_dict() for item in blocking],
        "warnings": [item.as_dict() for item in warnings],
        "checks": [item.as_dict() for item in checks],
    }


def _check_llm_bridge(root: Path) -> ReadinessCheck:
    return _file_check(root / "atulya" / "llm.py", "LLM bridge", "atulya/llm.py is present")


def _check_free_provider() -> ReadinessCheck:
    if _ollama_available():
        return ReadinessCheck("Free inference", "pass", "Ollama is reachable on localhost")
    configured = [
        key for key in ("GROQ_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY")
        if os.environ.get(key)
    ]
    if configured:
        return ReadinessCheck("Free inference", "pass", f"Configured: {', '.join(configured)}")
    return ReadinessCheck(
        "Free inference",
        "fail",
        "Configure Ollama locally or set one free-tier key: GROQ_API_KEY, OPENROUTER_API_KEY, or GEMINI_API_KEY",
    )


def _check_telegram() -> ReadinessCheck:
    token = bool(os.environ.get("ATULYA_TELEGRAM_BOT_TOKEN"))
    allowlist = bool(os.environ.get("ATULYA_TELEGRAM_ALLOWLIST"))
    if token and allowlist:
        return ReadinessCheck("Telegram", "pass", "Bot token and allowlist are configured")
    if token:
        return ReadinessCheck("Telegram", "fail", "Bot token exists, but ATULYA_TELEGRAM_ALLOWLIST is empty")
    return ReadinessCheck("Telegram", "warn", "Telegram token not configured; channel is disabled", required=False)


def _check_mcp_config(root: Path) -> ReadinessCheck:
    path = root / "config" / "mcp_servers.json"
    if not path.exists():
        return ReadinessCheck("MCP config", "fail", "config/mcp_servers.json is missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return ReadinessCheck("MCP config", "fail", f"Invalid MCP config: {exc}")
    servers = payload.get("servers", [])
    enabled = [item.get("name", "unknown") for item in servers if item.get("enabled")]
    oauth_errors = _google_mcp_oauth_errors(servers)
    if oauth_errors:
        return ReadinessCheck("MCP config", "fail", "; ".join(oauth_errors))
    google_servers = {item.get("name") for item in servers}
    if {"google_drive", "gmail"} & google_servers and not _google_mcp_env_ready():
        return ReadinessCheck(
            "MCP config",
            "warn",
            "Google/Gmail MCP entries are present; add Drive service-account and Gmail OAuth env before enabling them",
            required=False,
        )
    if enabled:
        return ReadinessCheck("MCP config", "pass", f"Enabled MCP servers have required local credentials: {', '.join(enabled)}")
    return ReadinessCheck("MCP config", "pass", "MCP servers are configured and disabled by default")


def _google_mcp_oauth_errors(servers: list[dict[str, Any]]) -> list[str]:
    enabled = {str(item.get("name")) for item in servers if item.get("enabled")}
    errors: list[str] = []
    if "google_drive" in enabled and not os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY"):
        errors.append("google_drive enabled but GOOGLE_SERVICE_ACCOUNT_KEY is missing")
    gmail_required = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN")
    missing_gmail = [key for key in gmail_required if not os.environ.get(key)]
    if "gmail" in enabled and missing_gmail:
        errors.append(f"gmail enabled but missing {', '.join(missing_gmail)}")
    return errors


def _google_mcp_env_ready() -> bool:
    drive_ready = bool(os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY"))
    gmail_ready = all(os.environ.get(key) for key in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"))
    return drive_ready and gmail_ready


def _check_tantra_gate(root: Path) -> ReadinessCheck:
    benchmark = root / "outputs" / "npdna" / "benchmark.json"
    if benchmark.exists():
        return ReadinessCheck("Tantra gate", "pass", "Benchmark file exists; Tantra remains gated by readiness policy")
    return ReadinessCheck("Tantra gate", "warn", "No Tantra benchmark file found; production will use external/free providers", required=False)


def _check_secret_hygiene(root: Path) -> ReadinessCheck:
    env_file = root / ".env"
    if env_file.exists():
        return ReadinessCheck("Secret hygiene", "fail", ".env exists in repo root; do not commit secrets")
    return ReadinessCheck("Secret hygiene", "pass", ".env is not present in the repository root")


def _check_key_rotation_ack() -> ReadinessCheck:
    if os.environ.get("ATULYA_KEYS_ROTATED", "").lower() in {"1", "true", "yes"}:
        return ReadinessCheck("Key rotation", "pass", "ATULYA_KEYS_ROTATED is acknowledged")
    return ReadinessCheck(
        "Key rotation",
        "warn",
        "Rotate any keys from old zips, then set ATULYA_KEYS_ROTATED=true for deployment checks",
        required=False,
    )


def _file_check(path: Path, name: str, detail: str) -> ReadinessCheck:
    if path.exists():
        return ReadinessCheck(name, "pass", detail)
    return ReadinessCheck(name, "fail", f"Missing {path}")


def _ollama_available() -> bool:
    host = os.environ.get("ATULYA_OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=1.0) as response:
            return response.status == 200
    except Exception:
        return False
