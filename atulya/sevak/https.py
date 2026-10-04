"""HTTPS for the local server: a self-signed certificate made for this computer.

Browsers only allow the camera and microphone on https:// pages or on http://localhost. To use them from a phone
or another computer, set ``ATULYA_HTTPS=on`` in ``.env``. Atulya then serves https on the same port, with a
certificate valid for ``localhost``, this computer's name and its network addresses. The browser warns once because
the certificate is not from a public authority; choose "Advanced > Continue". Nothing leaves your network.
"""
from __future__ import annotations

import datetime
import ipaddress
import os
import socket
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

RENEW_BEFORE = datetime.timedelta(days=30)


def certs_dir() -> Path:
    return Path(os.environ.get("ATULYA_CERTS_DIR", "data/certs"))


def enabled() -> bool:
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
    key_file.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                           serialization.NoEncryption()))
    try:
        key_file.chmod(0o600)   # the private key: readable by you only (no effect on Windows)
    except OSError:
        pass
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return str(cert_file), str(key_file)
