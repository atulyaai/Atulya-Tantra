"""Run the hands-free voice loop on this PC.

  python -m tools.voice_loop --pair "Desk PC"        # once: create this PC's voice token (stored in data/)
  python -m tools.voice_loop --wake-test             # print WAKE scores; nothing is sent anywhere
  python -m tools.voice_loop [--url http://127.0.0.1:8000] [--language en]

Per-turn timings go to logs/voice_loop.log.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _token_file() -> Path:
    from atulya.settings import Settings

    return Settings.from_environment().data_dir / "voice-loop.token"


def pair(name: str, owner: str) -> int:
    """Pair this PC for the voice loop. Local file access to data/ already means control of this server."""
    from atulya.settings import Settings
    from tools.plugins.system.agents import AgentHub

    from atulya.auth import AuthStore

    data_dir = Settings.from_environment().data_dir
    if not AuthStore(data_dir).is_admin(owner):
        print(f"'{owner}' is not an administrator; only admins can pair a voice-loop device.", file=sys.stderr)
        return 2
    device = AgentHub(data_dir).pair(owner, name, ["voice_loop"])
    path = _token_file()
    path.write_text(device["token"], encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    print(f"Paired '{name}' for {owner}; token saved to {path}. Revoke it in Devices to stop the loop.")
    return 0


def wake_test(seconds: float, device) -> int:
    from .audio_io import Mic
    from .wake import WakeDetector

    detector = WakeDetector()
    print(f"Listening for the wake word with {Path(detector.model_path).name} for {seconds:.0f} s...")
    mic = Mic(device).start()
    hits = 0
    deadline = time.monotonic() + seconds
    try:
        while time.monotonic() < deadline:
            frame = mic.read()
            if frame is None:
                continue
            score = detector.feed(frame)
            if score is not None:
                hits += 1
                print(f"WAKE {score:.2f} at {time.strftime('%H:%M:%S')}", flush=True)
                detector.reset()
    finally:
        mic.stop()
    print(f"{hits} wake detections")
    return 0


async def run_loop(args) -> int:
    from .audio_io import Mic, Player
    from .client import ServerClient
    from .loop import VoiceLoop
    from .vad import Endpointer, SileroVAD
    from .wake import WakeDetector

    token = os.environ.get("ATULYA_VOICE_TOKEN", "").strip()
    if not token and _token_file().is_file():
        token = _token_file().read_text(encoding="utf-8").strip()
    if not token:
        print("No voice token. Run: python -m tools.voice_loop --pair \"Desk PC\"", file=sys.stderr)
        return 2
    client = ServerClient(args.url, token)
    mic = Mic(args.device).start()
    player = Player(args.output_device)
    loop = VoiceLoop(mic, WakeDetector(threshold=args.threshold), Endpointer(SileroVAD()), client, player,
                     language=args.language, log_path=ROOT / "logs" / "voice_loop.log")
    print("Voice loop ready: say the wake word.", flush=True)
    try:
        while True:
            try:
                await loop.run(turns=1)
            except Exception as exc:  # keep listening; report what failed instead of going silent forever
                logging.getLogger(__name__).warning("Voice turn failed: %s", exc)
                loop._write_log({"error": type(exc).__name__})
                player.stop()
    finally:
        mic.stop()
        player.close()
        await client.aclose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Atulya hands-free voice loop")
    parser.add_argument("--url", default=os.environ.get("ATULYA_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--language", default=os.environ.get("ATULYA_VOICE_LANGUAGE", ""))
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--device", default=None, help="Input device index or name (python -m sounddevice lists them)")
    parser.add_argument("--output-device", default=None)
    parser.add_argument("--wake-test", action="store_true")
    parser.add_argument("--seconds", type=float, default=60)
    parser.add_argument("--pair", metavar="NAME")
    parser.add_argument("--owner", default="admin")
    args = parser.parse_args()
    for name in ("device", "output_device"):
        value = getattr(args, name)
        if isinstance(value, str) and value.isdigit():
            setattr(args, name, int(value))
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.pair:
        return pair(args.pair, args.owner)
    if args.wake_test:
        return wake_test(args.seconds, args.device)
    try:
        return asyncio.run(run_loop(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
