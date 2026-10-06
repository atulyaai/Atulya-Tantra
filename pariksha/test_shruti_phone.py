"""Regression tests for the Termux listener's API and wake/VAD handoff."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from atulya import shruti_phone
from atulya.shruti import AtulyaClient, Segmenter, WakeGate


class _Api:
    def __init__(self, transcript="हे अतुल्य समय क्या है?", reply="समय दोपहर का है"):
        self.transcript = transcript
        self.reply = reply
        self.transcribed = []
        self.chatted = []

    async def transcribe(self, audio):
        self.transcribed.append(audio)
        return self.transcript

    async def chat(self, text):
        self.chatted.append(text)
        return {"response_text": self.reply}


class _Speaker:
    def __init__(self):
        self.spoken = []

    def say(self, text):
        self.spoken.append(text)


class _Wake:
    def __init__(self, fired):
        self.fired = iter(fired)

    def feed(self, _frame):
        return next(self.fired, False)


class _Segmenter:
    def __init__(self, utterances):
        self.utterances = iter(utterances)

    def feed(self, _frame):
        return next(self.utterances, None)


def test_termux_listener_reuses_shared_shruti_audio_and_server_clients():
    assert shruti_phone.WakeGate is WakeGate
    assert shruti_phone.Segmenter is Segmenter
    client = shruti_phone.ShrutiPhoneClient("https://server", "device-token", model_path="wake.onnx",
                                          api=_Api(), speaker=_Speaker())
    assert isinstance(client.api, _Api)
    assert isinstance(client.speaker, _Speaker)


def test_model_configuration_is_required_unless_a_gate_is_injected():
    with pytest.raises(ValueError, match="ATULYA_WAKE_MODEL"):
        shruti_phone.ShrutiPhoneClient("https://server", "token")
    with pytest.raises(ValueError, match="threshold"):
        shruti_phone.ShrutiPhoneClient("https://server", "token", model_path="wake.onnx", threshold=0)


def test_first_utterance_survives_until_vad_finishes_after_wake():
    api, speaker = _Api(), _Speaker()
    client = shruti_phone.ShrutiPhoneClient(
        "https://server", "token", model_path="wake.onnx", api=api, speaker=speaker,
        matcher=_Wake([True, False]), segmenter=_Segmenter([None, b"audio"]),
    )

    async def run():
        await client.process_frame(b"wake frame")
        await client.process_frame(b"end of spoken command")

    asyncio.run(run())
    assert api.transcribed == [b"audio"]
    assert api.chatted == ["हे अतुल्य समय क्या है?"]
    assert speaker.spoken == ["समय दोपहर का है"]


def test_stop_command_cancels_followup_without_chatting():
    api, speaker = _Api(transcript="रुको अतुल्य"), _Speaker()
    client = shruti_phone.ShrutiPhoneClient("https://server", "token", model_path="wake.onnx", api=api,
                                          speaker=speaker)
    client.follow_up_until = 100
    asyncio.run(client.process_utterance(b"audio"))
    assert api.chatted == []
    assert client.follow_up_until == 0
    assert speaker.spoken == []


def test_shared_atulya_client_uses_expected_device_token_and_automatic_language(monkeypatch):
    """The shared client owns the server protocol; the phone must not add Bearer auth."""
    import httpx

    requests = []

    async def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"text": "नमस्ते"})

    transport = httpx.MockTransport(handler)
    shared = AtulyaClient("https://server", "device-token", transport=transport)

    async def run():
        return await shared.transcribe(b"wav")

    assert asyncio.run(run()) == "नमस्ते"
    assert requests[0].headers["X-Atulya-Token"] == "device-token"
    assert requests[0].headers.get("Authorization") is None
    assert b"wav" in requests[0].read()
    assert requests[0].url.path == "/api/voice/stt"



def test_hindi_named_phone_extra_and_cli_are_declared():
    project = (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    assert 'atulya-shruti-phone = "atulya.shruti_phone:main"' in project
    assert "shruti_phone = [" in project
    assert '"numpy>=1.24"' in project
    assert '"sounddevice>=0.4"' in project
