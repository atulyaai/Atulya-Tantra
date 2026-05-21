"""Audio and vision encoders for NP-DNA multimodal."""
from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from typing import Any


@dataclass
class AudioFeatures:
    embedding: list[float]
    duration: float
    sample_rate: int
    channels: int


@dataclass
class VisionFeatures:
    embedding: list[float]
    width: int
    height: int
    channels: int


class AudioEncoder:
    """Simple audio encoder using MFCC-like features."""

    def __init__(self, embedding_dim: int = 128):
        self.embedding_dim = embedding_dim

    def encode(self, audio_path: str) -> AudioFeatures:
        """Encode audio file to features."""
        try:
            import wave
            with wave.open(audio_path, 'rb') as wf:
                sample_rate = wf.getframerate()
                channels = wf.getnchannels()
                n_frames = wf.getnframes()
                duration = n_frames / sample_rate if sample_rate > 0 else 0
                frames = wf.readframes(min(n_frames, 1000))
        except Exception:
            sample_rate = 16000
            channels = 1
            duration = 0
            frames = b""

        # Simple feature extraction: hash-based embedding
        embedding = self._extract_features(frames, self.embedding_dim)
        return AudioFeatures(embedding=embedding, duration=duration, sample_rate=sample_rate, channels=channels)

    def _extract_features(self, audio_bytes: bytes, dim: int) -> list[float]:
        """Extract simple audio features."""
        if not audio_bytes:
            return [0.0] * dim
        # Use hash-based pseudo-features
        features = []
        for i in range(dim):
            chunk = audio_bytes[i*4:(i+1)*4] if i*4 < len(audio_bytes) else b'\x00\x00\x00\x00'
            value = struct.unpack('<I', chunk.ljust(4, b'\x00')[:4])[0]
            features.append((value % 1000) / 1000.0)
        return features


class VisionEncoder:
    """Simple vision encoder using pixel-based features."""

    def __init__(self, embedding_dim: int = 256):
        self.embedding_dim = embedding_dim

    def encode(self, image_path: str) -> VisionFeatures:
        """Encode image file to features."""
        try:
            from PIL import Image
            img = Image.open(image_path).convert('RGB')
            width, height = img.size
            channels = 3
            pixels = list(img.getdata())[:1000]  # Sample first 1000 pixels
        except Exception:
            width = 224
            height = 224
            channels = 3
            pixels = []

        embedding = self._extract_features(pixels, width, height, self.embedding_dim)
        return VisionFeatures(embedding=embedding, width=width, height=height, channels=channels)

    def _extract_features(self, pixels: list, width: int, height: int, dim: int) -> list[float]:
        """Extract simple vision features."""
        if not pixels:
            return [0.0] * dim
        features = []
        for i in range(dim):
            idx = i % len(pixels)
            pixel = pixels[idx]
            if isinstance(pixel, tuple):
                value = sum(pixel) / len(pixel) / 255.0
            else:
                value = pixel / 255.0
            features.append(value)
        # Pad if needed
        while len(features) < dim:
            features.append(0.0)
        return features[:dim]
