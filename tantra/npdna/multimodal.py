"""NP-DNA Multimodal Encoders.

Provides VoiceEncoder (Mel spectrogram & raw audio) and VisionEncoder (patch embedding)
projecting multimodal signals into the shared model hidden space.
"""
from __future__ import annotations
import torch
import torch.nn as nn
import torch.nn.functional as F

class VoiceEncoder(nn.Module):
    """Processes raw audio waveforms or precomputed magnitude spectrograms

    and projects them into the model's hidden dimension.
    """
    def __init__(self, hidden_size: int, input_freq_bins: int = 80):
        super().__init__()
        self.hidden_size = hidden_size
        self.input_freq_bins = input_freq_bins
        
        # Project frequency dimension to hidden size
        self.proj = nn.Linear(input_freq_bins, hidden_size)
        
        # 1D Convolutional downsampling over the temporal sequence
        self.conv = nn.Sequential(
            nn.Conv1d(hidden_size, hidden_size, kernel_size=3, stride=2, padding=1),
            nn.GELU(),
            nn.Conv1d(hidden_size, hidden_size, kernel_size=3, stride=2, padding=1),
        )
        self.norm = nn.LayerNorm(hidden_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Tensor of shape (B, T, freq) or raw audio (B, sample_len).

        Returns:
            Projected voice features of shape (B, T_downsampled, hidden_size).
        """
        # If input is 2D, assume it is raw waveform: convert to magnitude spectrogram
        if x.dim() == 2:
            B, L = x.shape
            # Compute Short-time Fourier Transform (STFT) with custom Hann window
            window = torch.hann_window(512, device=x.device)
            stft_res = torch.stft(
                x,
                n_fft=512,
                hop_length=160,
                win_length=512,
                window=window,
                return_complex=True,
                center=True
            )
            # Take magnitude
            x = torch.abs(stft_res)  # (B, freq_bins, time_frames)
            x = x.transpose(1, 2)    # (B, time_frames, freq_bins)
            
            # Interpolate frequency dimension to self.input_freq_bins if different
            if x.size(-1) != self.input_freq_bins:
                x = F.interpolate(
                    x, 
                    size=self.input_freq_bins, 
                    mode='linear', 
                    align_corners=False
                )

        # 1. Project frequency bins to hidden dimension
        h = self.proj(x)  # (B, T, hidden_size)
        
        # 2. Downsample temporal sequence via Conv1d
        h = h.transpose(1, 2)  # (B, hidden_size, T)
        h = self.conv(h)       # (B, hidden_size, T_downsampled)
        h = h.transpose(1, 2)  # (B, T_downsampled, hidden_size)
        
        # 3. Layer normalization
        return self.norm(h)


class VisionEncoder(nn.Module):
    """ViT-style patch projection mapping image frames to sequence tokens."""
    def __init__(self, hidden_size: int, patch_size: int = 16, in_channels: int = 3, max_patches: int = 256):
        super().__init__()
        self.hidden_size = hidden_size
        self.patch_size = patch_size
        
        # Project patches to hidden size
        self.proj = nn.Conv2d(
            in_channels,
            hidden_size,
            kernel_size=patch_size,
            stride=patch_size
        )
        
        # Positional embedding
        self.pos_embed = nn.Parameter(torch.zeros(1, max_patches, hidden_size))
        nn.init.trunc_normal_(self.pos_embed, std=0.02)
        
        self.norm = nn.LayerNorm(hidden_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Tensor of shape (B, C, H, W).

        Returns:
            Projected vision features of shape (B, num_patches, hidden_size).
        """
        B, C, H, W = x.shape
        
        # Project patches
        x = self.proj(x)                  # (B, hidden_size, H_patches, W_patches)
        x = x.flatten(2).transpose(1, 2)  # (B, num_patches, hidden_size)
        
        # Dynamic positional embedding interpolation to handle varying image sizes
        num_patches = x.size(1)
        max_patches = self.pos_embed.size(1)
        
        if num_patches <= max_patches:
            pos = self.pos_embed[:, :num_patches, :]
        else:
            # Interpolate pos_embed along temporal dimension
            pos_trans = self.pos_embed.transpose(1, 2)  # (1, hidden_size, max_patches)
            pos_interp = F.interpolate(
                pos_trans,
                size=num_patches,
                mode='linear',
                align_corners=False
            )
            pos = pos_interp.transpose(1, 2)            # (1, num_patches, hidden_size)
            
        x = x + pos
        return self.norm(x)
