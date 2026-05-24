"""Tests for Encoders — AudioEncoder and VisionEncoder."""



class TestAudioEncoder:
    """Tests for AudioEncoder — feature extraction from audio."""

    def test_encode_nonexistent_file(self):
        from tantra.npdna.encoders import AudioEncoder
        encoder = AudioEncoder(embedding_dim=128)
        result = encoder.encode("/nonexistent/file.wav")
        assert result.duration == 0
        assert len(result.embedding) == 128
        assert result.sample_rate == 16000

    def test_encode_creates_fixed_dim_embedding(self):
        from tantra.npdna.encoders import AudioEncoder
        encoder = AudioEncoder(embedding_dim=64)
        result = encoder.encode("/nonexistent/file.wav")
        assert len(result.embedding) == 64

    def test_audio_features_dataclass(self):
        from tantra.npdna.encoders import AudioFeatures
        f = AudioFeatures(embedding=[0.1, 0.2], duration=2.5, sample_rate=16000, channels=1)
        assert len(f.embedding) == 2
        assert f.duration == 2.5
        assert f.sample_rate == 16000

    def test_empty_audio_bytes_returns_zeros(self):
        from tantra.npdna.encoders import AudioEncoder
        encoder = AudioEncoder(embedding_dim=10)
        features = encoder._extract_features(b"", 10)
        assert features == [0.0] * 10


class TestVisionEncoder:
    """Tests for VisionEncoder — feature extraction from images."""

    def test_encode_nonexistent_file(self):
        from tantra.npdna.encoders import VisionEncoder
        encoder = VisionEncoder(embedding_dim=256)
        result = encoder.encode("/nonexistent/file.png")
        assert result.width == 224
        assert result.height == 224
        assert len(result.embedding) == 256

    def test_encode_creates_fixed_dim_embedding(self):
        from tantra.npdna.encoders import VisionEncoder
        encoder = VisionEncoder(embedding_dim=128)
        result = encoder.encode("/nonexistent/file.png")
        assert len(result.embedding) == 128

    def test_vision_features_dataclass(self):
        from tantra.npdna.encoders import VisionFeatures
        vf = VisionFeatures(embedding=[0.5] * 10, width=100, height=200, channels=3)
        assert len(vf.embedding) == 10
        assert vf.width == 100
        assert vf.height == 200
        assert vf.channels == 3
