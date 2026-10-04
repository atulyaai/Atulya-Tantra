"""Always-on ambient presence — Atulya listening in the background.

The web UI only hears you while its tab is open. This small app runs on your
computer (or a Raspberry Pi in the kitchen) all the time: it listens for the
wake word, sends what you say to your Atulya server, speaks the answer, and
speaks notifications such as reminders or "someone is at the door". A tray
icon shows its state and mutes the microphone.

    atulya listen --url http://localhost:8000 --login     # once
    atulya listen                                         # every time
    atulya listen --install-autostart                     # start at login

Everything important stays on the server: safety rules, confirmations ("should
I unlock the front door?" — just say yes or no) and what Atulya learns about
you are the same as in the web UI. Speech-to-text runs locally with
faster-whisper when installed (private), otherwise on the server.

Install the extras with ``pip install -e ".[ambient]"``.
"""
from __future__ import annotations

from atulya.shruti.listener import AmbientEngine, AmbientSession, AtulyaClient, Segmenter, WakeMatcher

__all__ = ["AmbientEngine", "AmbientSession", "AtulyaClient", "Segmenter", "WakeMatcher"]
