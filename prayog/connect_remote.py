"""Connect Atulya to a bigger model running somewhere else (Colab, a GPU server, LM Studio on another PC ...).

    python prayog/connect_remote.py --url https://abc.trycloudflare.com/v1 --key SECRET
    python prayog/connect_remote.py --url http://192.168.1.50:1234/v1 --model qwen3-8b
    python prayog/connect_remote.py --remove           # go back to the other brains

It tests the server first, then saves ATULYA_CUSTOM_URL / ATULYA_CUSTOM_KEY / ATULYA_CUSTOM_MODEL in .env (the same
settings as Menu > Brains & keys > "Your own"). Restart start.bat afterwards. Atulya tries the fastest working brain first,
so this one leads when it is quicker than the others.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from atulya.adhar import set_env_value  # noqa: E402


def normalize_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if not urllib.parse.urlparse(url).scheme:
        url = "https://" + url
    return url if urllib.parse.urlparse(url).path.rstrip("/").endswith("/v1") else url + "/v1"


def is_private_host(host: str) -> bool:
    if host in ("localhost",) or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback


def check_transport(url: str, key: str) -> None:
    """A secret key must not cross the internet in plain text."""
    parts = urllib.parse.urlparse(url)
    if key and parts.scheme != "https" and not is_private_host(parts.hostname or ""):
        raise SystemExit("Refusing to send a key over plain http to the internet. Use an https:// address.")


def _call(url: str, key: str, path: str, payload: dict | None = None, timeout: float = 60.0) -> dict:
    req = urllib.request.Request(url + path, data=json.dumps(payload).encode() if payload else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - the address you gave
        return json.loads(resp.read().decode())


def detect_model(url: str, key: str) -> str:
    models = _call(url, key, "/models").get("data") or []
    if not models:
        raise SystemExit("The server answered but lists no models.")
    return str(models[0]["id"])


def test_chat(url: str, key: str, model: str) -> dict:
    started = time.perf_counter()
    reply = _call(url, key, "/chat/completions", {"model": model, "max_tokens": 48,
                  "messages": [{"role": "user", "content": "Reply with the single word: ready"}]})
    return {"seconds": round(time.perf_counter() - started, 2), "text": reply["choices"][0]["message"]["content"].strip()[:60]}


def connect(url: str, key: str, model: str = "", env_file: Path | None = None) -> dict:
    url = normalize_url(url)
    check_transport(url, key)
    try:
        model = model or detect_model(url, key)
        result = test_chat(url, key, model)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"The server refused: {exc.code}. " + ("Check the key." if exc.code in (401, 403) else "Check the address.")) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SystemExit(f"I couldn't reach {url}: {exc}") from exc
    env = env_file or HERE.parent / ".env"
    set_env_value("ATULYA_CUSTOM_URL", url, env)
    set_env_value("ATULYA_CUSTOM_KEY", key, env)
    set_env_value("ATULYA_CUSTOM_MODEL", model, env)
    return {"url": url, "model": model, **result}


def remove(env_file: Path | None = None) -> None:
    env = env_file or HERE.parent / ".env"
    for name in ("ATULYA_CUSTOM_URL", "ATULYA_CUSTOM_KEY", "ATULYA_CUSTOM_MODEL"):
        set_env_value(name, "", env)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", help="the server address, e.g. https://abc.trycloudflare.com/v1")
    ap.add_argument("--key", default="", help="the server's API key (if it has one)")
    ap.add_argument("--model", default="", help="model name (detected automatically if left out)")
    ap.add_argument("--remove", action="store_true", help="forget the remote brain")
    args = ap.parse_args(argv)
    if args.remove:
        remove()
        print("Removed. Restart start.bat.")
        return 0
    if not args.url:
        ap.error("--url is required")
    info = connect(args.url, args.key, args.model)
    print(f"Works: {info['model']} answered “{info['text']}” in {info['seconds']} s.\n"
          f"Saved to .env ({info['url']}). Restart start.bat; Atulya will use it whenever it is the fastest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
