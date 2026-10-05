"""Raksha (रक्षा, protection): encryption at rest, security helpers and lockdown."""
from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import ipaddress
import json
import os
import threading
import secrets
import subprocess
import socket
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.x509.oid import NameOID

# ── raksha ────────────────────────────────────────────────────────────



# ── security ────────────────────────────────────────────────────────────
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


# ── Lockdown profile ────────────────────────────────────────────────────
# Moved from atulya/raksha.py; `ATULYA_LOCKDOWN=on` keeps Atulya
# reachable from this computer only.


def lockdown_on() -> bool:
    return os.environ.get("ATULYA_LOCKDOWN", "").strip().lower() in ("on", "1", "true", "yes")


def bind_host(default: str = "127.0.0.1") -> str:
    """Host to listen on: always localhost under lockdown, otherwise `ATULYA_HOST` or the default."""
    if lockdown_on():
        return "127.0.0.1"
    return os.environ.get("ATULYA_HOST", default)


def cors_origins() -> list[str] | None:
    """Explicit CORS origins, `[]` (none) under lockdown, or None to use the app's default."""
    listed = [o.strip() for o in os.environ.get("ATULYA_CORS_ORIGINS", "").split(",") if o.strip()]
    if listed:
        return listed
    return [] if lockdown_on() else None


# ── vault ────────────────────────────────────────────────────────────
MAGIC = b"ATV1"
_cache: dict[tuple[str, bytes], Fernet] = {}


class VaultLocked(Exception):
    """An encrypted file could not be opened: the passphrase is missing, wrong, or the file was altered."""


def _salt_path() -> Path:
    return Path(os.environ.get("ATULYA_VAULT_DIR", "kosh")) / "vault.salt"


def enabled() -> bool:
    return bool(os.environ.get("ATULYA_VAULT_PASSPHRASE", ""))


def _fernet() -> Fernet:
    passphrase = os.environ.get("ATULYA_VAULT_PASSPHRASE", "")
    if not passphrase:
        raise VaultLocked("This data is encrypted. Set ATULYA_VAULT_PASSPHRASE in .env to open it.")
    salt_file = _salt_path()
    if not salt_file.exists():
        salt_file.parent.mkdir(parents=True, exist_ok=True)
        salt_file.write_bytes(secrets.token_bytes(16))
    salt = salt_file.read_bytes()
    if (passphrase, salt) not in _cache:
        key = Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(passphrase.encode("utf-8"))
        _cache.clear()
        _cache[(passphrase, salt)] = Fernet(base64.urlsafe_b64encode(key))
    return _cache[(passphrase, salt)]


def is_encrypted(blob: bytes) -> bool:
    return blob.startswith(MAGIC)


def decrypt_bytes(blob: bytes) -> bytes:
    try:
        return _fernet().decrypt(blob[len(MAGIC):])
    except InvalidToken as exc:
        raise VaultLocked("Wrong passphrase, or the file was changed.") from exc


def read_text(path: Path, encoding: str = "utf-8") -> str:
    blob = Path(path).read_bytes()
    return (decrypt_bytes(blob) if is_encrypted(blob) else blob).decode(encoding)


def _secure_file(path: Path) -> None:
    """Restrict a sensitive file to the current user on POSIX and Windows."""
    if os.name == "nt":
        user = os.environ.get("USERNAME")
        if not user:
            raise OSError("Cannot identify the Windows account to secure a private file.")
        principal = os.environ.get("USERDOMAIN", ".") + "\\" + user
        result = subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"{principal}:(F)"],
                                capture_output=True, text=True, check=False)
        if result.returncode:
            raise OSError(result.stderr.strip() or "Could not restrict file permissions with icacls.")
    else:
        path.chmod(0o600)


def private_file_is_restricted(path: Path) -> bool:
    """Return whether group and other users are denied access to a private file."""
    if not path.exists():
        return False
    if os.name != "nt":
        return path.stat().st_mode & 0o077 == 0
    result = subprocess.run(["icacls", str(path)], capture_output=True, text=True, check=False)
    if result.returncode:
        return False
    output = result.stdout.casefold()
    return not any(identity in output for identity in ("everyone", "\\users:", "authenticated users"))


def write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write ``text`` (encrypted when the vault is on). Refuses to overwrite an encrypted file it cannot open."""
    path = Path(path)
    if path.exists():
        existing = path.read_bytes()
        if is_encrypted(existing):
            decrypt_bytes(existing)  # raises VaultLocked: never overwrite what we cannot read
    data = text.encode(encoding)
    if enabled():
        data = MAGIC + _fernet().encrypt(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    if enabled():
        _secure_file(tmp)
    tmp.replace(path)


def status(root: Path | str = "kosh") -> dict[str, object]:
    root = Path(root)
    enc = plain = 0
    for f in root.rglob("*.json") if root.exists() else []:
        try:
            if is_encrypted(f.read_bytes()[:4]):
                enc += 1
            else:
                plain += 1
        except OSError:
            continue
    return {"on": enabled(), "encrypted_files": enc, "plain_files": plain}


# Files that hold private data. Everything else (settings, caches, tokens meant to be read by tools) stays as is.
PRIVATE = ("money.json", "calendar.json", "reminders.json", "email_config.json", "tracking.json", "chat_history.json", "fabric.json", "contacts.json", "paired.json", "telegram_users.json")


def encrypt_tree(root: Path | str = "kosh") -> int:
    """Encrypt every private file under ``root`` now. Returns how many were converted."""
    if not enabled():
        raise VaultLocked("Set ATULYA_VAULT_PASSPHRASE in .env first.")
    done = 0
    for f in Path(root).rglob("*.json"):
        if f.name in PRIVATE or f.parent.name == "profiles":
            blob = f.read_bytes()
            if not is_encrypted(blob):
                write_text(f, blob.decode("utf-8"))
                done += 1
    return done


# ── lockdown ────────────────────────────────────────────────────────────



# ── https ────────────────────────────────────────────────────────────
RENEW_BEFORE = datetime.timedelta(days=30)


def certs_dir() -> Path:
    return Path(os.environ.get("ATULYA_CERTS_DIR", "kosh/certs"))


def https_enabled() -> bool:
    return os.environ.get("ATULYA_HTTPS", "").strip().lower() in ("1", "on", "true", "yes")


def local_names() -> tuple[list[str], list[str]]:
    """(host names, ip addresses) this computer answers to: localhost, its own name and its network addresses."""
    names = {"localhost"}
    ips = {"127.0.0.1"}
    host = socket.gethostname()
    if host:
        names.add(host)
    try:
        for info in socket.getaddrinfo(host, None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))   # picks the outgoing interface; sends nothing
            ips.add(s.getsockname()[0])
    except OSError:
        pass
    return sorted(names), sorted(ips)


def _covers(cert: x509.Certificate, names: list[str], ips: list[str]) -> bool:
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        return False
    have_names = set(san.get_values_for_type(x509.DNSName))
    have_ips = {str(i) for i in san.get_values_for_type(x509.IPAddress)}
    return set(names) <= have_names and set(ips) <= have_ips


def ensure_certs(directory: Path | None = None, names: list[str] | None = None, ips: list[str] | None = None) -> tuple[str, str]:
    """Return (cert_file, key_file), making a new pair when missing, nearly expired, or when this computer's
    address changed (a phone would otherwise get a name mismatch)."""
    directory = Path(directory) if directory else certs_dir()
    if names is None or ips is None:
        names, ips = local_names()
    cert_file, key_file = directory / "cert.pem", directory / "key.pem"
    now = datetime.datetime.now(datetime.timezone.utc)
    if cert_file.exists() and key_file.exists():
        try:
            cert = x509.load_pem_x509_certificate(cert_file.read_bytes())
            if cert.not_valid_after_utc - now > RENEW_BEFORE and _covers(cert, names, ips):
                return str(cert_file), str(key_file)
        except ValueError:
            pass  # unreadable: make a new one
    directory.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Atulya (this computer)")])
    san = x509.SubjectAlternativeName([*(x509.DNSName(n) for n in names), *(x509.IPAddress(ipaddress.ip_address(i)) for i in ips)])
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(days=365)).add_extension(san, critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    key_tmp = key_file.with_name(key_file.name + ".tmp")
    key_tmp.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                          serialization.NoEncryption()))
    try:
        _secure_file(key_tmp)
        key_tmp.replace(key_file)
    except OSError:
        key_tmp.unlink(missing_ok=True)
        raise
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return str(cert_file), str(key_file)


# ── paired devices ───────────────────────────────────────────────────────────
# Your phone, laptop or desktop joins with a short one-time code and then holds its own token. The token can be
# cut off on its own at any time, and it only ever carries the permission level it was paired with.

PERMISSIONS = ("read", "files", "full")  # what a paired device may be asked to do, least to most
_PAIR_CODE_SECONDS = 600
_PAIR_FAILS = 8  # wrong codes allowed per address per minute


class PairedDevices:
    def __init__(self, path: Path | str | None = None):
        base = Path(os.environ.get("ATULYA_AGENT_DATA_DIR", "kosh/agent"))
        self.path = Path(path) if path else base / "paired.json"
        self.telegram_path = self.path.with_name("telegram_users.json")
        self._lock = threading.Lock()
        self._codes: dict[str, tuple[float, str, str, str]] = {}  # expires, permission, owner username, display name
        self._telegram_codes: dict[str, tuple[float, str, str]] = {}  # expires, owner username, display name
        self._fails: dict[str, list[float]] = {}

    # storage: only a hash of each token is kept, so the file alone cannot be used to log in
    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            return json.loads(read_text(self.path))
        except (FileNotFoundError, ValueError):
            return {}

    def _save(self, devices: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_text(self.path, json.dumps(devices, indent=2))

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def new_code(self, permission: str = "files", owner: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a pairing code tied to the account that approved the pairing."""
        if permission not in PERMISSIONS:
            raise ValueError(f"permission must be one of {', '.join(PERMISSIONS)}")
        with self._lock:
            now = time.time()
            self._codes = {c: v for c, v in self._codes.items() if v[0] > now}
            while len(self._codes) >= 5:
                self._codes.pop(min(self._codes, key=lambda c: self._codes[c][0]))
            code = f"{secrets.randbelow(10**6):06d}"
            owner = owner or {}
            self._codes[code] = (now + _PAIR_CODE_SECONDS, permission,
                                 str(owner.get("username") or ""), str(owner.get("display_name") or ""))
        return {"code": code, "permission": permission, "expires_in": _PAIR_CODE_SECONDS}

    def _too_many_fails(self, who: str) -> bool:
        now = time.time()
        recent = [t for t in self._fails.get(who, []) if now - t < 60]
        self._fails[who] = recent
        return len(recent) >= _PAIR_FAILS

    def enroll(self, code: str, name: str, kind: str = "device", who: str = "") -> tuple[dict[str, Any], str]:
        """Swap a one-time code for a device token. Raises ValueError for a wrong, used or expired code."""
        with self._lock:
            if self._too_many_fails(who):
                raise ValueError("Too many wrong codes. Wait a minute and try again.")
            entry = self._codes.pop(str(code).strip(), None)
            if entry is None or entry[0] < time.time():
                self._fails.setdefault(who, []).append(time.time())
                raise ValueError("That pairing code is wrong or has expired.")
            _, permission, owner_username, owner_display_name = entry
            token = "dev_" + secrets.token_urlsafe(32)
            device = {"id": uuid.uuid4().hex[:10], "name": (name or "device").strip()[:60] or "device",
                      "kind": (kind or "device").strip()[:20], "permission": permission, "created": time.time(),
                      "last_seen": 0.0, "revoked": False}
            if owner_username:
                device["owner_username"] = owner_username
                device["owner_display_name"] = owner_display_name[:80]
            devices = self._load()
            devices[self._hash(token)] = device
            self._save(devices)
        return {k: v for k, v in device.items()}, token

    def authenticate(self, token: str | None) -> dict[str, Any] | None:
        if not token or not token.startswith("dev_"):
            return None
        with self._lock:
            devices = self._load()
            device = devices.get(self._hash(token))
            if not device or device.get("revoked"):
                return None
            if time.time() - device.get("last_seen", 0) > 60:  # note the visit, but do not rewrite the file every call
                device["last_seen"] = time.time()
                self._save(devices)
        return dict(device)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return sorted(self._load().values(), key=lambda d: d["created"])

    def revoke(self, device_id: str) -> bool:
        with self._lock:
            devices = self._load()
            for device in devices.values():
                if device["id"] == device_id and not device.get("revoked"):
                    device["revoked"] = True
                    self._save(devices)
                    return True
        return False

    def set_permission(self, device_id: str, permission: str) -> bool:
        if permission not in PERMISSIONS:
            raise ValueError(f"permission must be one of {', '.join(PERMISSIONS)}")
        with self._lock:
            devices = self._load()
            for device in devices.values():
                if device["id"] == device_id and not device.get("revoked"):
                    device["permission"] = permission
                    self._save(devices)
                    return True
        return False

    def new_telegram_code(self, owner: dict[str, Any]) -> dict[str, Any]:
        """Make a one-time code to link an allowlisted Telegram sender to an account."""
        username = str(owner.get("username") or "").strip()
        if not username:
            raise ValueError("The account has no username to link.")
        with self._lock:
            now = time.time()
            self._telegram_codes = {c: v for c, v in self._telegram_codes.items() if v[0] > now}
            while len(self._telegram_codes) >= 5:
                self._telegram_codes.pop(min(self._telegram_codes, key=lambda c: self._telegram_codes[c][0]))
            code = f"{secrets.randbelow(10**6):06d}"
            self._telegram_codes[code] = (now + _PAIR_CODE_SECONDS, username,
                                          str(owner.get("display_name") or "")[:80])
        return {"code": code, "expires_in": _PAIR_CODE_SECONDS}

    def link_telegram(self, code: str, sender_id: str) -> dict[str, Any]:
        """Consume a one-time link code and bind this Telegram sender to its owner account."""
        sender_id = str(sender_id).strip()
        limiter_key = f"telegram:{sender_id}"
        with self._lock:
            if self._too_many_fails(limiter_key):
                raise ValueError("Too many wrong codes. Wait a minute and try again.")
            entry = self._telegram_codes.pop(str(code).strip(), None)
            if entry is None or entry[0] < time.time():
                self._fails.setdefault(limiter_key, []).append(time.time())
                raise ValueError("That link code is wrong or has expired.")
            links = self._load_telegram_links()
            link = {"telegram_id": sender_id, "username": entry[1], "display_name": entry[2],
                    "created": time.time()}
            links[sender_id] = link
            self._save_telegram_links(links)
            return dict(link)

    def telegram_owner(self, sender_id: str) -> dict[str, Any] | None:
        """Return the account explicitly linked to a Telegram sender, if any."""
        with self._lock:
            return self._load_telegram_links().get(str(sender_id))

    def telegram_links(self) -> list[dict[str, Any]]:
        """List Telegram account links for the admin pairing screen."""
        with self._lock:
            return sorted(self._load_telegram_links().values(), key=lambda row: row.get("created", 0))

    def unlink_telegram(self, sender_id: str) -> bool:
        """Remove a Telegram-to-account link without deleting its separate chat history."""
        with self._lock:
            links = self._load_telegram_links()
            if str(sender_id) not in links:
                return False
            del links[str(sender_id)]
            self._save_telegram_links(links)
            return True

    def _load_telegram_links(self) -> dict[str, dict[str, Any]]:
        try:
            data = json.loads(read_text(self.telegram_path))
        except (FileNotFoundError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save_telegram_links(self, links: dict[str, dict[str, Any]]) -> None:
        self.telegram_path.parent.mkdir(parents=True, exist_ok=True)
        write_text(self.telegram_path, json.dumps(links, indent=2))


_paired: PairedDevices | None = None


def paired_devices() -> PairedDevices:
    global _paired
    if _paired is None or _paired.path.parent != Path(os.environ.get("ATULYA_AGENT_DATA_DIR", "kosh/agent")):
        _paired = PairedDevices()
    return _paired
