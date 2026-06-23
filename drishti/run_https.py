"""HTTPS launcher for Atulya Tantra Dashboard with self-signed cert generation."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CERTS_DIR = Path(__file__).resolve().parent / "certs"


def _ensure_certs() -> tuple[str, str]:
    CERTS_DIR.mkdir(parents=True, exist_ok=True)
    cert_file = CERTS_DIR / "cert.pem"
    key_file = CERTS_DIR / "key.pem"

    if not cert_file.exists() or not key_file.exists():
        logger.info("Generating self-signed SSL certificate...")
        subprocess.run([
            sys.executable, "-c", f"""
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import datetime

key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, u"localhost")])
cert = x509.CertificateBuilder().subject_name(subject).issuer_name(issuer).public_key(key.public_key()).serial_number(1000).not_valid_before(datetime.datetime.utcnow()).not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365)).sign(key, hashes.SHA256(), default_backend())
with open(r'{key_file}', 'wb') as f: f.write(key.private_bytes(encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.TraditionalOpenSSL, encryption_algorithm=serialization.NoEncryption()))
with open(r'{cert_file}', 'wb') as f: f.write(cert.public_bytes(serialization.Encoding.PEM))
"""], check=True)
        logger.info("SSL certs generated at %s", CERTS_DIR)

    return str(cert_file), str(key_file)


def main():
    import uvicorn

    host = os.environ.get("ATULYA_HOST", "0.0.0.0")
    port = int(os.environ.get("ATULYA_HTTPS_PORT", "4433"))

    try:
        cert_file, key_file = _ensure_certs()
        logger.info("Starting HTTPS on %s:%s", host, port)
        uvicorn.run(
            "drishti.dashboard.app:app",
            host=host,
            port=port,
            ssl_certfile=cert_file,
            ssl_keyfile=key_file,
            log_level="info",
        )
    except ImportError:
        logger.warning("cryptography not installed, falling back to HTTP")
        port = int(os.environ.get("ATULYA_PORT", "3001"))
        uvicorn.run("drishti.dashboard.app:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
