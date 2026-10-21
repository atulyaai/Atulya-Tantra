"""bootstrap installs from requirements.lock.txt; it must exist and cover the voice stack (AUDIT N2)."""
import re

from tools import bootstrap


def test_bootstrap_lock_file_exists_and_pins_voice_stack():
    lock = bootstrap.PROJECT_ROOT / "requirements.lock.txt"
    assert lock.is_file()
    pins = {}
    for line in lock.read_text(encoding="utf-8").splitlines():
        match = re.match(r"([a-z0-9-]+)==([^;\s]+)", line)
        if match:
            pins[match.group(1)] = match.group(2)
    for package in ("fastapi", "uvicorn", "faster-whisper", "sherpa-onnx", "onnxruntime",
                    "openwakeword", "sounddevice", "pypdf", "psutil", "mcp"):
        assert package in pins, package
    assert int(pins["av"].split(".")[0]) < 19


def test_lock_lines_are_pinned_and_client_only_packages_skip_linux():
    lines = [line for line in (bootstrap.PROJECT_ROOT / "requirements.lock.txt").read_text(encoding="utf-8").splitlines()
             if line and not line.startswith("#")]
    assert all("==" in line for line in lines), [line for line in lines if "==" not in line]
    assert not any("tflite" in line for line in lines)
    for package in ("openwakeword", "sounddevice"):
        line = next(line for line in lines if line.startswith(package + "=="))
        assert line.endswith('; sys_platform == "win32"')
