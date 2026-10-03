"""``atulya listen`` / ``python -m atulya.ambient`` — the always-listening app.

First time (signs this device in and remembers it):
    atulya listen --url http://atulya.local:8000 --login

Then just:
    atulya listen                      # tray icon; say "Hey Atulya, …"
    atulya listen --install-autostart  # start at every login
    atulya listen --text               # type instead of talk (no microphone needed)
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import logging
import os
import platform
import socket
import sys
import threading
from pathlib import Path
from typing import Any

from .listener import DEFAULT_WAKE_WORDS, AmbientEngine, AmbientSession, AtulyaClient, AuthError, WakeMatcher

logger = logging.getLogger("atulya.ambient")


def config_path() -> Path:
    if os.environ.get("ATULYA_AMBIENT_CONFIG"):
        return Path(os.environ["ATULYA_AMBIENT_CONFIG"])
    if platform.system() == "Windows" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "Atulya" / "ambient.json"
    return Path.home() / ".config" / "atulya" / "ambient.json"


def load_config(path: Path | None = None) -> dict[str, Any]:
    try:
        return json.loads((path or config_path()).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(cfg: dict[str, Any], path: Path | None = None) -> Path:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)  # it holds this device's sign-in token
    except OSError:
        pass
    return path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="atulya listen", description="Always-listening Atulya (wake word, tray icon).")
    p.add_argument("--url", help="Atulya server, e.g. http://localhost:8000")
    p.add_argument("--token", help="Sign-in token (normally saved by --login)")
    p.add_argument("--login", action="store_true", help="Sign this device in and remember it")
    p.add_argument("--user", help="Username for --login")
    p.add_argument("--device", help="Name shown in Atulya (default: this computer's name)")
    p.add_argument("--wake", help="Wake phrases, comma-separated (default: hey atulya, atulya)")
    p.add_argument("--stt", choices=["auto", "local", "server"], help="Speech-to-text: local whisper or the server")
    p.add_argument("--model", help="Local whisper model (default base.en; tiny.en for small devices)")
    p.add_argument("--follow-up", type=float, help="Seconds to keep listening without the wake word after a reply")
    p.add_argument("--mic", help="Microphone device name or number")
    p.add_argument("--no-tray", action="store_true", help="Run without a tray icon (headless)")
    p.add_argument("--text", action="store_true", help="Type instead of talk (testing without a microphone)")
    p.add_argument("--install-autostart", nargs="?", const="desktop", choices=["desktop", "systemd"],
                   help="Start at login (desktop) or at boot on headless Linux (systemd)")
    p.add_argument("--remove-autostart", nargs="?", const="desktop", choices=["desktop", "systemd"])
    p.add_argument("--save", action="store_true", help="Save these options as the defaults")
    return p


def resolve(args: argparse.Namespace, cfg: dict[str, Any]) -> dict[str, Any]:
    """Options from flags, then environment, then the saved config, then defaults."""
    def pick(flag: Any, env: str, key: str, default: Any) -> Any:
        if flag not in (None, ""):
            return flag
        if os.environ.get(env):
            return os.environ[env]
        return cfg.get(key, default)

    return {
        "url": pick(args.url, "ATULYA_URL", "url", "http://localhost:8000"),
        "token": pick(args.token, "ATULYA_TOKEN", "token", ""),
        "device": pick(args.device, "ATULYA_DEVICE", "device", socket.gethostname() or "listener"),
        "wake": pick(args.wake, "ATULYA_WAKE_WORDS", "wake", ",".join(DEFAULT_WAKE_WORDS)),
        "stt": pick(args.stt, "ATULYA_AMBIENT_STT", "stt", "auto"),
        "model": pick(args.model, "ATULYA_WHISPER_MODEL", "model", "base.en"),
        "follow_up": float(pick(args.follow_up, "ATULYA_FOLLOW_UP", "follow_up", 0.0)),
        "mic": pick(args.mic, "ATULYA_MIC", "mic", None),
    }


async def _text_loop(engine: AmbientEngine) -> None:
    tasks = [asyncio.create_task(engine.heartbeat_loop()),
             asyncio.create_task(engine.client.notifications(engine.on_notification))]
    print('Type what you would say (e.g. "hey atulya, turn on the kitchen light"). Ctrl+C to stop.')
    try:
        while True:
            line = await asyncio.to_thread(input, "> ")
            await engine.handle_text(line)
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        for task in tasks:
            task.cancel()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    args = build_parser().parse_args(argv)
    cfg = load_config()
    opts = resolve(args, cfg)

    if args.install_autostart or args.remove_autostart:
        from . import autostart

        if args.remove_autostart:
            removed = autostart.uninstall(mode=args.remove_autostart)
            print("Autostart removed." if removed else "Autostart wasn't installed.")
        else:
            path, hint = autostart.install(mode=args.install_autostart)
            print(f"Autostart installed: {path}\n{hint}")
        return 0

    if args.login:
        username = args.user or input("Atulya username: ")
        password = getpass.getpass("Password: ")
        try:
            opts["token"] = asyncio.run(AtulyaClient.device_token(opts["url"], username, password, opts["device"]))
        except AuthError as exc:
            print(f"Sign-in failed: {exc}")
            return 1
        args.save = True
        print(f"Signed in as {username} on {opts['device']}.")

    if args.save:
        path = save_config({**cfg, **{k: v for k, v in opts.items() if v not in (None, "")}})
        print(f"Saved settings to {path}")

    if not opts["token"]:
        print("This device isn't signed in yet. Run: atulya listen --url <server> --login")
        return 1

    from .audio import Microphone, Speaker, WakeGate, make_stt

    client = AtulyaClient(opts["url"], opts["token"], opts["device"])
    wake_words = [w.strip() for w in str(opts["wake"]).split(",") if w.strip()]
    session = AmbientSession(WakeMatcher(wake_words), follow_up=opts["follow_up"])
    speaker = Speaker()

    if args.text:
        engine = AmbientEngine(client, stt=None, speaker=speaker, session=session, wake_label=wake_words[0])
        asyncio.run(_text_loop(engine))
        return 0

    stt = make_stt(opts["stt"], client, opts["model"])
    engine = AmbientEngine(client, stt=stt, speaker=speaker, session=session, wake_label=wake_words[0],
                           stt_label=getattr(stt, "label", ""),
                           briefing_at=os.environ.get("ATULYA_BRIEFING_AT", ""),
                           briefing_location=os.environ.get("ATULYA_BRIEFING_LOCATION", ""))
    mic_device = int(opts["mic"]) if str(opts["mic"] or "").isdigit() else opts["mic"]
    wake_model = os.environ.get("ATULYA_WAKE_MODEL", "")
    gate = WakeGate(wake_model) if wake_model else None
    mic = Microphone(device=mic_device, enabled=engine.accepts_audio, gate=gate,
                     active=lambda: engine.session.state != engine.session.IDLE)
    print(f'Listening for "{wake_words[0]}" on {opts["device"]} (speech-to-text: {engine.stt_label}).')

    from .tray import TrayApp, tray_available

    if args.no_tray or not tray_available():
        try:
            asyncio.run(engine.run(mic.utterances()))
        except KeyboardInterrupt:
            pass
        return 0

    # The tray needs the main thread; listening runs alongside it.
    loop = asyncio.new_event_loop()
    runner = threading.Thread(target=lambda: loop.run_until_complete(engine.run(mic.utterances())), daemon=True)
    runner.start()

    def stop() -> None:
        loop.call_soon_threadsafe(loop.stop)

    TrayApp(engine, opts["url"], on_quit=stop).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
