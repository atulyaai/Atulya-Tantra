"""Report anything in tracked files that belongs to one person, not to the project.

The project is meant for everyone. Keys, bot tokens, addresses and the domain it
is published on are the operator's own business, and they live in .env, which is
gitignored — nobody else should ever have to edit them out of a commit.

Two kinds of thing still slip in:

  * credentials — looked for by shape, because a key looks the same whoever owns
    it. These patterns are generic and safe to keep in a public repo.
  * the maintainer's own values — listed one per line in tools/.personal-values,
    which is gitignored, so that this script never publishes them either.

Run it with:  python tools/audit_personal_values.py
Exit status 0 means clean.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BLOCKLIST = HERE / ".personal-values"

# Credentials, recognised by shape. A Telegram bot token, for instance, is
# digits, a colon, then 35 URL-safe characters — that form says nothing about
# whose it is.
CREDENTIAL_PATTERNS = {
    "Telegram bot token": re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{35}\b"),
    "OpenRouter key": re.compile(r"\bsk-or-[A-Za-z0-9_-]{10,}"),
    "Anthropic key": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{10,}"),
    "Groq key": re.compile(r"\bgsk_[A-Za-z0-9_-]{10,}"),
    "Google API key": re.compile(r"\bAIza[A-Za-z0-9_-]{30,}"),
    "Cloudflare key": re.compile(r"\bcfk_[A-Za-z0-9_-]{10,}"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "credential on an assignment": re.compile(
        r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD))\s*=\s*(\S+)"
    ),
}

# What a value is allowed to look like before we call it a real credential.
# Deliberately generous: anything that announces itself as fake, a placeholder,
# or a documented example is not worth a maintainer's attention.
FAKE_MARKERS = (
    "secret", "test", "fake", "dummy", "example", "sample", "placeholder",
    "your-", "your_", "change", "changeme", "redacted", "not-a-real", "do-not-use",
    # An ellipsis means the writer deliberately left the value out.
    "...", "…",
)


def is_placeholder(value: str) -> bool:
    value = value.strip().strip("\"'")
    if not value:
        return True
    low = value.lower()
    if low in {"none", "null", "false", "true", "xxx", "x", "set-me"}:
        return True
    if value.startswith(("<", "${", "$", "%", "'", '"')):
        return True
    return any(marker in low for marker in FAKE_MARKERS)


def mask(value: str) -> str:
    """Show enough to act on, never enough to reuse."""
    value = value.strip().strip("\"'")
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:3]}…({len(value)} chars)"


def tracked_files() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files"], capture_output=True, text=True, check=True, cwd=ROOT
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"cannot list tracked files: {exc}")
    return out.splitlines()


def readable_text(name: str) -> str | None:
    path = ROOT / name
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\0" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def blocklist_values() -> list[str]:
    """The maintainer's own values. Absent by design in a fresh clone."""
    if not BLOCKLIST.exists():
        return []
    values = []
    for line in BLOCKLIST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            values.append(line)
    return values


def scan_credential(label: str, pattern: re.Pattern[str], name: str, line: str, lineno: int) -> int:
    if label == "credential on an assignment":
        match = pattern.search(line)
        if not match or is_placeholder(match.group(2)):
            return 0
        print(f"  LEAK  {name}:{lineno}  {match.group(1)}={mask(match.group(2))}")
        return 1
    match = pattern.search(line)
    if not match or is_placeholder(match.group(0)):
        return 0
    print(f"  LEAK  {name}:{lineno}  {label}: {mask(match.group(0))}")
    return 1


def main() -> int:
    files = tracked_files()
    mine = blocklist_values()
    findings = 0

    for name in files:
        if name.endswith(
            (".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".bin", ".pdf", ".woff",
             ".woff2", ".mp3", ".mp4", ".gguf", ".safetensors", ".onnx")
        ):
            continue
        text = readable_text(name)
        if text is None:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for label, pattern in CREDENTIAL_PATTERNS.items():
                findings += scan_credential(label, pattern, name, line, lineno)
            for value in mine:
                if value in line:
                    findings += 1
                    print(f"  LEAK  {name}:{lineno}  your own value present: {mask(value)}")

    # .env holds everything personal by design, so it must never be tracked.
    if ".env" in files:
        findings += 1
        print("  LEAK  .env is tracked — the whole credential set would be published")

    print()
    if findings:
        print(f"  {findings} thing(s) in tracked files do not belong to the project.")
        return 1
    scope = f"{len(mine)} of your own values, " if mine else ""
    print(f"  clean — {len(files)} tracked files checked ({scope}nothing personal in them).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
