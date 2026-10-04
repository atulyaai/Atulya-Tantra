"""Eyes: decoding shared pictures safely, and phrasing what was seen for the brain."""
from __future__ import annotations

import base64

import pytest

from atulya import indriya as eyes

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def test_accepts_data_urls_and_bare_base64():
    b64 = base64.b64encode(PNG).decode()
    assert eyes.decode_image(f"data:image/png;base64,{b64}") == PNG
    assert eyes.decode_image(b64) == PNG


@pytest.mark.parametrize("bad", ["", "not base64!!", base64.b64encode(b"hello").decode()])
def test_rejects_non_images(bad):
    with pytest.raises(ValueError):
        eyes.decode_image(bad)


def test_rejects_huge_images(monkeypatch):
    monkeypatch.setattr(eyes, "MAX_IMAGE_BYTES", 10)
    with pytest.raises(ValueError):
        eyes.decode_image(base64.b64encode(PNG).decode())


def test_no_cloud_vision_without_a_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert eyes.cloud_describe(PNG, "what is this?") == ""


def test_context_is_honest_when_nothing_was_seen():
    ctx = eyes.as_context({"text": "", "description": "", "can_describe": False})
    assert "no text was readable" in ctx and "GEMINI_API_KEY" in ctx
    ctx = eyes.as_context({"text": "Milk expires 12 Oct", "description": "", "can_describe": False})
    assert "Milk expires 12 Oct" in ctx
