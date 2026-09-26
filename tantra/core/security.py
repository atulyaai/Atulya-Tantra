"""Security - approval system, sandbox, SSRF protection, injection guard, encryption."""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os
import re
import time
import uuid
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
    requested_by: str = ""
    approved_by: str = ""
    notes: str = ""


class ApprovalSystem:
    def __init__(self, allow_no_password: bool = False):
        self._requests: dict[str, ApprovalRequest] = {}
        self._sudo_mode: bool = False
        self._sudo_expires: float = 0
        self._sudo_password_hash: str | None = None
        self._allow_no_password = allow_no_password

    def set_sudo_password(self, password: str) -> None:
        """Set the sudo password (salted SHA-256, never stored in plaintext)."""
        salt = os.urandom(16).hex()
        self._sudo_password_hash = f"{salt}:{hashlib.sha256((salt + password).encode()).hexdigest()}"

    def _verify_sudo_password(self, password: str) -> bool:
        if self._sudo_password_hash is None:
            return self._allow_no_password
        try:
            salt, hash_val = self._sudo_password_hash.split(":")
            computed = hashlib.sha256((salt + password).encode()).hexdigest()
            return hmac.compare_digest(computed, hash_val)
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
        req = ApprovalRequest(
            id=uuid.uuid4().hex[:12],
            action=action,
            risk=self.assess_risk(action),
            requested_by=user,
        )
        self._requests[req.id] = req
        return req

    def approve(self, request_id: str | ApprovalRequest, approver: str = "admin") -> bool:
        if isinstance(request_id, ApprovalRequest):
            request_id = request_id.id
        req = self._requests.get(request_id)
        if req:
            req.status = ApprovalStatus.APPROVED
            req.approved_by = approver
            return True
        return False

    def deny(self, request_id: str | ApprovalRequest) -> bool:
        if isinstance(request_id, ApprovalRequest):
            request_id = request_id.id
        req = self._requests.get(request_id)
        if req:
            req.status = ApprovalStatus.DENIED
            return True
        return False

    def get_request(self, request_id: str | ApprovalRequest) -> dict[str, Any] | None:
        if isinstance(request_id, ApprovalRequest):
            request_id = request_id.id
        req = self._requests.get(request_id)
        if not req:
            return None
        return {
            "id": req.id,
            "action": req.action,
            "risk": req.risk.value,
            "requested_at": req.requested_at,
            "status": req.status.value,
            "requested_by": req.requested_by,
            "approved_by": req.approved_by,
            "notes": req.notes,
        }

    def enter_sudo(self, password: str, ttl: float = 300) -> bool:
        """Enter sudo mode. Returns True only when password policy allows it."""
        if not self._verify_sudo_password(password):
            return False
        self._sudo_mode = True
        self._sudo_expires = time.time() + ttl
        return True

    def enable_sudo(self, password: str, ttl: float = 300) -> bool:
        """Alias for enter_sudo for backward compatibility."""
        return self.enter_sudo(password, ttl=ttl)

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


_EXTRA_BLOCKED = [ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("0.0.0.0/8")]


def is_public_ip(value: str) -> bool:
    """False for loopback, private, link-local (cloud metadata), CGNAT, multicast, reserved…"""
    try:
        ip = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped:  # ::ffff:127.0.0.1
        ip = ip.ipv4_mapped
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved
                or ip.is_unspecified or any(ip in net for net in _EXTRA_BLOCKED if net.version == ip.version))


def _resolve(host: str) -> set[str]:
    import socket

    return {info[4][0] for info in socket.getaddrinfo(host, None)}


class SSRFProtection:
    """Is this URL safe to fetch from the server? Only public http(s) destinations.

    Hostnames are resolved and *every* address must be public, so names that
    point inside the network (localhost, localtest.me, internal DNS) are
    refused; a name that doesn't resolve is refused too (fail closed).
    """

    def __init__(self, resolver=None):
        self._resolve = resolver

    def check_url(self, url: str) -> bool:
        try:
            import urllib.parse
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False  # file://, ftp://, gopher://… never
            host = (parsed.hostname or "").strip("[]").lower()
            if not host:
                return False
            try:
                ipaddress.ip_address(host.split("%", 1)[0])
                return is_public_ip(host)
            except ValueError:
                pass
            if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".lan", ".home.arpa")):
                return False
            addresses = (self._resolve or _resolve)(host)
            return bool(addresses) and all(is_public_ip(a) for a in addresses)
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
        resolved = key or os.environ.get("ATULYA_ENCRYPTION_KEY")
        if not resolved:
            raise ValueError(
                "EncryptionManager requires a key via constructor argument or "
                "ATULYA_ENCRYPTION_KEY environment variable"
            )
        self._key = resolved

    def hash_password(self, password: str) -> str:
        salt = os.urandom(16)
        hash_val = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000).hex()
        return f"{salt.hex()}:{hash_val}"

    def verify_password(self, password: str, stored: str) -> bool:
        salt_hex, hash_val = stored.split(":")
        salt = bytes.fromhex(salt_hex)
        return hmac.compare_digest(
            hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000).hex(),
            hash_val,
        )

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
        self.encryption = (
            EncryptionManager()
            if os.environ.get("ATULYA_ENCRYPTION_KEY")
            else None
        )
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
