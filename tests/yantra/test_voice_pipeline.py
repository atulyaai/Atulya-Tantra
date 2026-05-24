"""Tests for VoicePipeline, TextToSpeech, SpeechToText — TTS/STT infrastructure."""

import tempfile


class TestTextToSpeech:
    """Tests for TextToSpeech (no actual network calls)."""

    def test_initialization(self):
        from yantra.tools.voice_pipeline import TextToSpeech
        with tempfile.TemporaryDirectory() as tmp:
            tts = TextToSpeech(output_dir=tmp)
            assert tts.output_dir.exists()
            assert tts.get_history() == []

    def test_voices_defined(self):
        from yantra.tools.voice_pipeline import TextToSpeech
        assert "en_male" in TextToSpeech.VOICES
        assert "en_female" in TextToSpeech.VOICES
        assert "hi_male" in TextToSpeech.VOICES
        assert "hi_female" in TextToSpeech.VOICES
        assert "sa_male" in TextToSpeech.VOICES

    def test_voice_config(self):
        from yantra.tools.voice_pipeline import TextToSpeech
        voice = TextToSpeech.VOICES["hi_male"]
        assert voice["language"] == "hi"

    def test_get_stats_empty(self):
        from yantra.tools.voice_pipeline import TextToSpeech
        with tempfile.TemporaryDirectory() as tmp:
            tts = TextToSpeech(output_dir=tmp)
            stats = tts.get_stats()
            assert stats["total_synthesized"] == 0
            assert stats["total_cost"] == 0.0


class TestSpeechToText:
    """Tests for SpeechToText (no actual network calls)."""

    def test_initialization(self):
        from yantra.tools.voice_pipeline import SpeechToText
        with tempfile.TemporaryDirectory() as tmp:
            stt = SpeechToText(output_dir=tmp)
            assert stt.output_dir.exists()
            assert stt.get_stats()["total_transcribed"] == 0

    def test_transcribe_no_input_returns_error(self):
        """transcribe() with no input returns a structured STT error result."""
        from yantra.tools.voice_pipeline import SpeechToText
        import asyncio
        with tempfile.TemporaryDirectory() as tmp:
            stt = SpeechToText(output_dir=tmp)
            result = asyncio.run(stt.transcribe())
            assert result.id == "error"
            assert result.error == "No audio provided"


class TestVoicePipeline:
    """Tests for combined VoicePipeline."""

    def test_initialization(self):
        from yantra.tools.voice_pipeline import VoicePipeline
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = VoicePipeline(tts_dir=f"{tmp}/tts", stt_dir=f"{tmp}/stt")
            assert pipeline.tts is not None
            assert pipeline.stt is not None

    def test_get_stats_empty(self):
        from yantra.tools.voice_pipeline import VoicePipeline
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = VoicePipeline(tts_dir=f"{tmp}/tts", stt_dir=f"{tmp}/stt")
            stats = pipeline.get_stats()
            assert "tts" in stats
            assert "stt" in stats
            assert stats["turns"] == 0
