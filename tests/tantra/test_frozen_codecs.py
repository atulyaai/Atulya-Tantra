"""Tests for frozen tokenizer-like codec references."""

import pytest

from tantra.npdna import FrozenCodecRegistry
from tantra.npdna.config import CodecConfig


def test_default_codec_refs_are_frozen_and_unavailable():
    registry = FrozenCodecRegistry.default()
    refs = registry.describe()

    assert sorted(refs) == ["audio", "image", "video"]
    assert all(ref["frozen"] for ref in refs.values())
    assert not any(ref["trainable"] for ref in refs.values())
    assert not any(ref["available"] for ref in refs.values())


def test_configured_codec_refs_are_referenced_not_trained():
    registry = FrozenCodecRegistry.from_config(
        CodecConfig(
            audio_codec="frozen://encodec/tokenizer",
            image_codec="frozen://vqgan/tokenizer",
            video_codec="frozen://video-tokenizer",
        )
    )

    refs = registry.describe()
    assert all(ref["available"] for ref in refs.values())
    assert not any(ref["trainable"] for ref in refs.values())


def test_missing_codec_fails_clearly():
    registry = FrozenCodecRegistry.default()

    with pytest.raises(NotImplementedError, match="No frozen audio codec"):
        registry.encode("audio", b"")

