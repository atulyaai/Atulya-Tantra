"""Tests for multimodal encoders — VoiceEncoder and VisionEncoder (torch nn.Modules)."""

import torch


class TestVoiceEncoder:
    """Tests for VoiceEncoder — audio to hidden space projection."""

    def test_forward_with_spectrogram(self):
        from tantra.core.npdna.multimodal import VoiceEncoder
        encoder = VoiceEncoder(hidden_size=64, input_freq_bins=80)
        # Simulate pre-computed spectrogram: (B, T, freq_bins)
        x = torch.randn(2, 10, 80)
        out = encoder.forward(x)
        # Output: (B, T_downsampled, hidden_size)
        assert out.dim() == 3
        assert out.size(0) == 2
        assert out.size(2) == 64

    def test_forward_with_raw_audio(self):
        from tantra.core.npdna.multimodal import VoiceEncoder
        encoder = VoiceEncoder(hidden_size=32, input_freq_bins=80)
        # Raw audio waveform: (B, sample_len)
        x = torch.randn(1, 16000)  # 1 second at 16kHz
        out = encoder.forward(x)
        assert out.dim() == 3
        assert out.size(0) == 1
        assert out.size(2) == 32

    def test_forward_preserves_batch_dimension(self):
        from tantra.core.npdna.multimodal import VoiceEncoder
        encoder = VoiceEncoder(hidden_size=128, input_freq_bins=80)
        x = torch.randn(4, 20, 80)
        out = encoder.forward(x)
        assert out.size(0) == 4

    def test_norm_applied(self):
        from tantra.core.npdna.multimodal import VoiceEncoder
        encoder = VoiceEncoder(hidden_size=64)
        x = torch.randn(1, 5, 80)
        out = encoder.forward(x)
        # Layer norm produces output with stable values
        assert not torch.isnan(out).any()
        assert not torch.isinf(out).any()


class TestVisionEncoder:
    """Tests for VisionEncoder — image patches to hidden space projection."""

    def test_forward_standard_image(self):
        from tantra.core.npdna.multimodal import VisionEncoder
        encoder = VisionEncoder(hidden_size=64, patch_size=16)
        # Standard image: (B, C, H, W)
        x = torch.randn(1, 3, 224, 224)
        out = encoder.forward(x)
        # 224/16 = 14 patches per side → 196 patches total
        assert out.dim() == 3
        assert out.size(0) == 1
        assert out.size(2) == 64
        assert out.size(1) == 196  # (224/16)^2

    def test_forward_multiple_batches(self):
        from tantra.core.npdna.multimodal import VisionEncoder
        encoder = VisionEncoder(hidden_size=128, patch_size=32)
        x = torch.randn(3, 3, 256, 256)
        out = encoder.forward(x)
        # 256/32 = 8 patches per side → 64 patches
        assert out.size(0) == 3
        assert out.size(1) == 64
        assert out.size(2) == 128

    def test_forward_small_image(self):
        from tantra.core.npdna.multimodal import VisionEncoder
        encoder = VisionEncoder(hidden_size=32, patch_size=16, max_patches=64)
        # Small image: (B, C, 64, 64) → 4*4 = 16 patches
        x = torch.randn(1, 3, 64, 64)
        out = encoder.forward(x)
        assert out.size(1) == 16

    def test_forward_large_image_interpolates_pos_embed(self):
        from tantra.core.npdna.multimodal import VisionEncoder
        encoder = VisionEncoder(hidden_size=64, patch_size=16, max_patches=100)
        # Larger image: more patches than max_patches, triggers interpolation
        x = torch.randn(1, 3, 512, 512)
        out = encoder.forward(x)
        # 512/16 = 32 patches per side → 1024 patches (exceeds max_patches=100)
        assert out.size(1) == 1024
        assert out.size(2) == 64

    def test_no_nan_or_inf(self):
        from tantra.core.npdna.multimodal import VisionEncoder
        encoder = VisionEncoder(hidden_size=64, patch_size=16)
        x = torch.randn(2, 3, 224, 224)
        out = encoder.forward(x)
        assert not torch.isnan(out).any()
        assert not torch.isinf(out).any()
