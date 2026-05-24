"""Security — approval system, sandbox, SSRF protection, injection guard, encryption."""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


@dataclass
class ApprovalRequest:
    id: str
    action: str
    risk: RiskLevel
    requested_at: float = field(default_factory=time.time)
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: str = ""
    notes: str = ""


class ApprovalSystem:
    def __init__(self):
        self._requests: dict[str, ApprovalRequest] = {}
        self._sudo_mode: bool = False
        self._sudo_expires: float = 0
        self._sudo_password_hash: str | None = None

    def set_sudo_password(self, password: str) -> None:
        """Set the sudo password (salted SHA-256, never stored in plaintext)."""
        salt = os.urandom(16).hex()
        self._sudo_password_hash = f"{salt}:{hashlib.sha256((salt + password).encode()).hexdigest()}"

    def _verify_sudo_password(self, password: str) -> bool:
        if self._sudo_password_hash is None:
            return True  # No password set — backward-compatible
        try:
            salt, hash_val = self._sudo_password_hash.split(":")
            return hashlib.sha256((salt + password).encode()).hexdigest() == hash_val
        except (ValueError, AttributeError):
            return False

    def assess_risk(self, action: str) -> RiskLevel:
        risky_patterns = ["rm -rf", "sudo", "DROP TABLE", "DELETE FROM", "format(", "shutdown"]
        for pattern in risky_patterns:
            if pattern.lower() in action.lower():
                return RiskLevel.CRITICAL
        if any(p in action.lower() for p in ["write", "edit", "create"]):
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def request_approval(self, action: str, user: str = "") -> ApprovalRequest:
        req = ApprovalRequest(id=str(int(time.time())), action=action, risk=self.assess_risk(action))
        if user:
            req.approved_by = user
        self._requests[req.id] = req
        return req

    def approve(self, request_id: str, approver: str = "admin"):
        req = self._requests.get(request_id)
        if req:
            req.status = ApprovalStatus.APPROVED
            req.approved_by = approver

    def deny(self, request_id: str):
        req = self._requests.get(request_id)
        if req:
            req.status = ApprovalStatus.DENIED

    def enter_sudo(self, password: str, ttl: float = 300) -> bool:
        """Enter sudo mode. Returns True if password is correct or no password set."""
        if not self._verify_sudo_password(password):
            return False
        self._sudo_mode = True
        self._sudo_expires = time.time() + ttl
        return True

    def enable_sudo(self, password: str, ttl: float = 300):
        """Alias for enter_sudo for backward compatibility."""
        self.enter_sudo(password, ttl=ttl)

    def exit_sudo(self):
        self._sudo_mode = False


class SandboxManager:
    def __init__(self):
        self._sandboxes: dict[str, dict[str, Any]] = {}

    def create_sandbox(self, name: str, sandbox_type: str = "local") -> dict[str, Any]:
        sandbox = {"name": name, "type": sandbox_type, "created": time.time(), "active": True}
        self._sandboxes[name] = sandbox
        return sandbox

    def destroy_sandbox(self, name: str):
        if name in self._sandboxes:
            self._sandboxes[name]["active"] = False

    def status(self) -> dict[str, Any]:
        return self._sandboxes


class SSRFProtection:
    def __init__(self):
        self._blocked_ranges = [
            ipaddress.ip_network("10.0.0.0/8"),
            ipaddress.ip_network("172.16.0.0/12"),
            ipaddress.ip_network("192.168.0.0/16"),
            ipaddress.ip_network("127.0.0.0/8"),
            ipaddress.ip_network("169.254.0.0/16"),
        ]

    def check_url(self, url: str) -> bool:
        try:
            import urllib.parse
            parsed = urllib.parse.urlparse(url)
            host = parsed.hostname
            if not host:
                return False
            # If host is a hostname (not an IP), allow it (assume external)
            try:
                ip = ipaddress.ip_address(host)
            except ValueError:
                # Not an IP address — it's a hostname, so it's external
                return True
            return not any(ip in net for net in self._blocked_ranges)
        except Exception:
            return False


class PromptInjectionGuard:
    def __init__(self):
        self._injection_patterns = [
            r"ignore previous instructions",
            r"system prompt",
            r"you are now",
            r"disregard",
            r"override",
            r"new instructions",
        ]

    def detect(self, content: str) -> bool:
        for pattern in self._injection_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False

    def sanitize(self, content: str) -> str:
        for pattern in self._injection_patterns:
            content = re.sub(pattern, "[REDACTED]", content, flags=re.IGNORECASE)
        return content


class EncryptionManager:
    def __init__(self, key: str | None = None):
        self._key = key or os.environ.get("ATULYA_ENCRYPTION_KEY", "default-key-change-in-production")

    def hash_password(self, password: str) -> str:
        salt = os.urandom(16).hex()
        hash_val = hashlib.sha256((salt + password).encode()).hexdigest()
        return f"{salt}:{hash_val}"

    def verify_password(self, password: str, stored: str) -> bool:
        salt, hash_val = stored.split(":")
        return hashlib.sha256((salt + password).encode()).hexdigest() == hash_val

    def redact_secrets(self, text: str) -> str:
        patterns = [
            (r'["\']?api[_-]?key["\']?\s*[:=]\s*["\']([A-Za-z0-9_\-]{16,})["\']', "[REDACTED_API_KEY]"),
            (r'["\']?password["\']?\s*[:=]\s*["\']([^"\']{4,})["\']', "[REDACTED_PASSWORD]"),
            (r'["\']?token["\']?\s*[:=]\s*["\']([A-Za-z0-9_\-]{16,})["\']', "[REDACTED_TOKEN]"),
        ]
        for pattern, replacement in patterns:
            text = re.sub(pattern, replacement, text)
        return text


class SecurityManager:
    def __init__(self, data_dir: str | Path = "."):
        self.data_dir = Path(data_dir)
        self.approval = ApprovalSystem()
        self.sandbox = SandboxManager()
        self.ssrf = SSRFProtection()
        self.injection = PromptInjectionGuard()
        self.encryption = EncryptionManager()
        self._audit_log: list[dict[str, Any]] = []

    def check_url(self, url: str) -> bool:
        return self.ssrf.check_url(url)

    def sanitize_input(self, content: str) -> str:
        if self.injection.detect(content):
            return self.injection.sanitize(content)
        return content

    def log_action(self, action: str, details: dict[str, Any]):
        self._audit_log.append({"action": action, "details": details, "timestamp": time.time()})

    def status(self) -> dict[str, Any]:
        return {
            "approval_requests": len(self.approval._requests),
            "active_sandboxes": sum(1 for s in self.sandbox._sandboxes.values() if s.get("active")),
            "audit_entries": len(self._audit_log),
        }
