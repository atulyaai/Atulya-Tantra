"""Central, explicit configuration for the Atulya runtime."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables.

    Paths are absolute so running Atulya from a service manager does not write
    data into an arbitrary working directory.
    """

    data_dir: Path
    workspace_dir: Path
    database_path: Path
    host: str = "127.0.0.1"
    port: int = 8000
    max_message_chars: int = 12_000
    api_token: str | None = None
    model_base_url: str | None = None
    model_api_key: str | None = None
    model_name: str | None = None
    model_timeout_seconds: float = 30.0

    @classmethod
    def from_environment(cls) -> "Settings":
        project_root = Path(__file__).resolve().parents[1]
        data_dir = Path(os.getenv("ATULYA_DATA_DIR", project_root / "data")).expanduser().resolve()
        workspace_dir = Path(os.getenv("ATULYA_WORKSPACE_DIR", project_root.parent)).expanduser().resolve()
        database_path = Path(os.getenv("ATULYA_DATABASE_PATH", data_dir / "atulya.sqlite3")).expanduser().resolve()
        return cls(
            data_dir=data_dir,
            workspace_dir=workspace_dir,
            database_path=database_path,
            host=os.getenv("ATULYA_HOST", "127.0.0.1"),
            port=int(os.getenv("ATULYA_PORT", "8000")),
            max_message_chars=int(os.getenv("ATULYA_MAX_MESSAGE_CHARS", "12000")),
            api_token=os.getenv("ATULYA_API_TOKEN") or None,
            model_base_url=os.getenv("ATULYA_MODEL_BASE_URL") or None,
            model_api_key=os.getenv("ATULYA_MODEL_API_KEY") or None,
            model_name=os.getenv("ATULYA_MODEL_NAME") or None,
            model_timeout_seconds=float(os.getenv("ATULYA_MODEL_TIMEOUT_SECONDS", "30")),
        )
