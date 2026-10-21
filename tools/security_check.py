"""Free security checks for every change (GOAL M13): known-vulnerable packages, high-severity code issues and hard-coded secrets.

Run: .venv\Scripts\python -m tools.security_check   (needs the dev extra: pip-audit, bandit)
Exits non-zero if either check finds a problem.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRET = re.compile(
    r"AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|xox[bap]-[A-Za-z0-9-]{10,}"
    r"|[0-9]{8,10}:AA[0-9A-Za-z_-]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
SCANNED = ("atulya", "tools", "webui", "android", "docs")
SKIP = {"renderer.js"}


def find_secrets() -> list[str]:
    """Hard-coded keys and tokens in shipped code and docs (tests use obvious fakes and are skipped)."""
    hits = []
    for folder in SCANNED:
        for path in (ROOT / folder).rglob("*"):
            if not path.is_file() or path.name in SKIP or path.suffix in {".png", ".jpg", ".gif", ".onnx", ".wav", ".exe"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            hits += [f"{path.relative_to(ROOT)}:{n}" for n, line in enumerate(text.splitlines(), 1) if SECRET.search(line)]
    return hits


def main() -> int:
    checks = [
        ("dependencies (pip-audit)", [sys.executable, "-m", "pip_audit", "-r", "requirements.lock.txt",
                                      "--progress-spinner", "off"]),
        ("code (bandit, high severity)", [sys.executable, "-m", "bandit", "-q", "-r", "atulya", "tools", "-lll"]),
    ]
    failed = 0
    for name, command in checks:
        result = subprocess.run(command, cwd=ROOT)
        print(f"{'PASS' if result.returncode == 0 else 'FAIL'}  {name}")
        failed += result.returncode != 0
    secrets = find_secrets()
    for hit in secrets:
        print(f"  possible secret: {hit}")
    print(f"{'FAIL' if secrets else 'PASS'}  secrets in code (pattern scan)")
    return 1 if failed or secrets else 0


if __name__ == "__main__":
    raise SystemExit(main())
