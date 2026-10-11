"""Detect host hardware so setup picks a runtime and model size that will actually run."""
from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Hardware:
    system: str  # windows | linux | macos
    arch: str  # x64 | arm64
    ram_gb: float
    cpu_count: int
    gpu: str  # nvidia | amd | apple | none

    @property
    def can_run_local_model(self) -> bool:
        """The bundled 2B Q4 model needs about 2.5 GB free; require 6 GB total RAM."""
        return self.ram_gb == 0 or self.ram_gb >= 6

    @property
    def llama_flavor(self) -> str:
        """Pick the llama.cpp release build; Vulkan covers NVIDIA and AMD without CUDA DLLs."""
        if self.system == "macos":
            return "metal"
        if self.gpu in {"nvidia", "amd"} and self.arch == "x64":
            return "vulkan"
        return "cpu"

    @property
    def threads(self) -> int:
        return max(2, min(self.cpu_count - 1, 8))

    def summary(self) -> str:
        return f"{self.system}-{self.arch}, {self.ram_gb:.1f} GB RAM, {self.cpu_count} CPUs, GPU: {self.gpu}"


def _ram_gb() -> float:
    try:
        if os.name == "nt":
            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                            ("total", ctypes.c_ulonglong), ("avail", ctypes.c_ulonglong),
                            ("total_page", ctypes.c_ulonglong), ("avail_page", ctypes.c_ulonglong),
                            ("total_virtual", ctypes.c_ulonglong), ("avail_virtual", ctypes.c_ulonglong),
                            ("avail_ext", ctypes.c_ulonglong)]
            status = MemoryStatus()
            status.length = ctypes.sizeof(MemoryStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return status.total / 1024 ** 3
        if platform.system() == "Darwin":
            out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5)
            return int(out.stdout.strip()) / 1024 ** 3
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3
    except (OSError, ValueError, AttributeError, subprocess.SubprocessError):
        return 0.0


def _gpu(system: str, arch: str) -> str:
    if system == "macos":
        return "apple" if arch == "arm64" else "none"
    if shutil.which("nvidia-smi"):
        return "nvidia"
    if system == "linux" and os.path.isdir("/sys/class/drm"):
        for card in os.listdir("/sys/class/drm"):
            try:
                with open(f"/sys/class/drm/{card}/device/vendor", encoding="ascii") as vendor:
                    if vendor.read().strip() == "0x1002":
                        return "amd"
            except OSError:
                continue
    return "none"


def detect() -> Hardware:
    system = {"Windows": "windows", "Darwin": "macos"}.get(platform.system(), "linux")
    machine = platform.machine().lower()
    arch = "arm64" if machine in {"arm64", "aarch64", "armv8l"} else "x64"
    return Hardware(system, arch, round(_ram_gb(), 1), os.cpu_count() or 2, _gpu(system, arch))
