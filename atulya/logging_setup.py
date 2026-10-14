"""Process logging: rotating files and secret redaction for every handler."""
from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Telegram bot tokens appear inside request URLs; API keys appear in headers or query strings.
_SECRET_PATTERNS = (
    (re.compile(r"/bot\d{5,}:[A-Za-z0-9_-]{20,}"), "/bot<redacted>"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{12,}"), r"\1<redacted>"),
    (re.compile(r"(?i)([?&](?:key|api_key|token|access_token|id_token|refresh_token|code|handoff|verifier)=)[^&\s\"']+"), r"\1<redacted>"),
    (re.compile(r"\b(?:sk|nvapi|AIza)[A-Za-z0-9_-]{16,}"), "<redacted>"),
)


def redact(text: str) -> str:
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RedactingFilter(logging.Filter):
    """Rewrite each record's final message so no handler can emit a secret."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True
        cleaned = redact(message)
        if cleaned != message:
            record.msg, record.args = cleaned, None
        return True


def configure_logging(log_path: Path | None = None, *, level: int = logging.INFO) -> None:
    """Install redaction on the root handlers and quiet per-request HTTP client logs."""
    root = logging.getLogger()
    root.setLevel(level)
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(log_path, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root.addHandler(handler)
    elif not root.handlers:
        logging.basicConfig(level=level, format="%(levelname)s %(name)s %(message)s")
    for handler in root.handlers:
        if not any(isinstance(item, RedactingFilter) for item in handler.filters):
            handler.addFilter(RedactingFilter())
    # httpx logs every request URL at INFO, which includes the Telegram token.
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def scrub_log_file(path: Path) -> bool:
    """Redact secrets already written to an existing log file; returns True when it changed."""
    try:
        original = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    cleaned = redact(original)
    if cleaned == original:
        return False
    path.write_text(cleaned, encoding="utf-8")
    return True
