"""Runtime settings for the Atulya application."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip()
    path = Path(raw).expanduser() if raw else default
    return path if path.is_absolute() else PROJECT_ROOT / path


def _default_model_provider() -> str:
    """Prefer one configured cloud provider, falling back to local offline chat."""
    configured = os.environ.get("ATULYA_MODEL_PROVIDER", "").strip().lower()
    if configured and configured != "auto":
        return configured
    for provider, key_name, model_name in (
        ("openrouter", "OPENROUTER_API_KEY", "ATULYA_OPENROUTER_MODEL"),
        ("nvidia", "NVIDIA_API_KEY", "ATULYA_NVIDIA_MODEL"),
        ("gemini", "GEMINI_API_KEY", "ATULYA_GEMINI_MODEL"),
        ("deepseek", "DEEPSEEK_API_KEY", "ATULYA_DEEPSEEK_MODEL"),
    ):
        if os.environ.get(key_name, "").strip() and os.environ.get(model_name, "").strip():
            return provider
    return "local"


@dataclass(frozen=True, slots=True)
class Settings:
    """Process configuration; secrets are never included in repr output."""

    assistant_name: str
    host: str
    port: int
    data_dir: Path
    models_dir: Path
    model_provider: str
    model_name: str
    model_base_url: str
    model_api_key: str = field(repr=False)
    model_provider_auto: bool = False
    public_origin: str = ""
    trusted_proxy_ips: str = "127.0.0.1,::1"
    admin_setup_token: str = field(default="", repr=False)

    @classmethod
    def from_environment(cls) -> "Settings":
        try:
            port = int(os.environ.get("ATULYA_PORT", "8501"))
        except ValueError as exc:
            raise ValueError("ATULYA_PORT must be a number") from exc
        if not 1 <= port <= 65535:
            raise ValueError("ATULYA_PORT must be between 1 and 65535")
        host = os.environ.get("ATULYA_HOST", "127.0.0.1").strip() or "127.0.0.1"
        # Inside a container the port is published by the runtime (bind it to the host's
        # loopback, e.g. `-p 127.0.0.1:8501:8501`), so listening on all container interfaces is safe.
        in_container = os.environ.get("ATULYA_CONTAINER", "").strip() == "1"
        if host.lower() not in {"127.0.0.1", "localhost", "::1"} and not (in_container and host == "0.0.0.0"):
            raise ValueError("ATULYA_HOST must stay loopback; put a TLS reverse proxy in front of Atulya")
        public_origin = os.environ.get("ATULYA_PUBLIC_ORIGIN", "").strip().rstrip("/")
        if public_origin:
            parsed = urlsplit(public_origin)
            try:
                parsed_port = parsed.port
            except ValueError as exc:
                raise ValueError("ATULYA_PUBLIC_ORIGIN contains an invalid port") from exc
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or (parsed_port is not None and not 1 <= parsed_port <= 65535)
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
                or (parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"})
            ):
                raise ValueError("ATULYA_PUBLIC_ORIGIN must be an HTTPS origin (HTTP is allowed only for localhost)")
            public_origin = f"{parsed.scheme}://{parsed.netloc}"
        trusted_proxy_ips = os.environ.get("ATULYA_TRUSTED_PROXY_IPS", "127.0.0.1,::1").strip()
        if not trusted_proxy_ips or trusted_proxy_ips == "*":
            raise ValueError("ATULYA_TRUSTED_PROXY_IPS must name trusted proxy IPs; wildcard trust is not allowed")
        admin_setup_token = os.environ.get("ATULYA_ADMIN_SETUP_TOKEN", "").strip()
        if admin_setup_token and (len(admin_setup_token) < 32 or not admin_setup_token.isascii()):
            raise ValueError("ATULYA_ADMIN_SETUP_TOKEN must contain at least 32 characters")
        configured_provider = os.environ.get("ATULYA_MODEL_PROVIDER", "").strip().lower()
        return cls(
            assistant_name=os.environ.get("ATULYA_ASSISTANT_NAME", "Atulya").strip() or "Atulya",
            host=host,
            port=port,
            data_dir=_env_path("ATULYA_DATA_DIR", PROJECT_ROOT / "data"),
            # Model weights are app-owned assets and always stay in the project.
            models_dir=PROJECT_ROOT / "models",
            # Use one explicitly configured cloud provider; keep an offline local fallback.
            model_provider=_default_model_provider(),
            model_name=os.environ.get("ATULYA_MODEL_NAME", "").strip(),
            model_base_url=os.environ.get("ATULYA_MODEL_BASE_URL", "").strip(),
            model_api_key=os.environ.get("ATULYA_MODEL_API_KEY", ""),
            model_provider_auto=configured_provider in {"", "auto"},
            public_origin=public_origin,
            trusted_proxy_ips=trusted_proxy_ips,
            admin_setup_token=admin_setup_token,
        )

    @property
    def trusted_hosts(self) -> list[str]:
        """Hostnames accepted by the app; port numbers are not part of Host validation."""
        hosts = ["127.0.0.1", "localhost", "::1"]
        if self.public_origin:
            hostname = urlsplit(self.public_origin).hostname
            if hostname and hostname not in hosts:
                hosts.append(hostname)
        return hosts

