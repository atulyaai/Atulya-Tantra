"""llama-server arguments for the CPU voice loop (PLAN M1-B2)."""
from pathlib import Path

from tools.plugins.brain.local_llm import VISION_FILENAME, LocalLlamaRuntime
from tools.plugins.brain.providers import OpenAICompatibleProvider


def _command(tmp_path: Path, monkeypatch, vision: str | None):
    (tmp_path / "vision").mkdir()
    (tmp_path / "vision" / VISION_FILENAME).write_bytes(b"x")
    if vision is None:
        monkeypatch.delenv("ATULYA_VISION", raising=False)
    else:
        monkeypatch.setenv("ATULYA_VISION", vision)
    monkeypatch.delenv("ATULYA_LLAMA_LOG", raising=False)
    runtime = LocalLlamaRuntime(tmp_path)
    return runtime, runtime.command(Path("llama-server"), tmp_path / "model.gguf")


def test_cache_flags_and_no_projector_by_default(tmp_path, monkeypatch):
    runtime, command = _command(tmp_path, monkeypatch, None)
    assert command[command.index("--cache-reuse") + 1] == "256"
    assert command[command.index("--slot-save-path") + 1] == str(runtime.slot_dir)
    assert runtime.slot_dir.is_dir()
    assert command[command.index("--threads") + 1] == command[command.index("--threads-batch") + 1]
    assert "--mmproj" not in command
    assert "--reasoning-budget" in command and "--jinja" in command


def test_projector_only_when_vision_enabled(tmp_path, monkeypatch):
    _runtime, command = _command(tmp_path, monkeypatch, "1")
    assert "--mmproj" in command


def test_slot_action_rejects_bad_names():
    import pytest
    for action, name in (("delete", "a.bin"), ("save", "../x"), ("restore", "")):
        with pytest.raises(ValueError):
            LocalLlamaRuntime.slot_action(action, name)


def test_cache_prompt_only_for_local_server():
    local = OpenAICompatibleProvider(name="l", model="m", base_url="http://127.0.0.1:11435/v1")
    cloud = OpenAICompatibleProvider(name="c", model="m", base_url="https://api.example.com/v1", api_key="k")
    from tools.plugins.brain import Message
    messages = [Message(role="user", content="hi")]
    assert local._payload(messages, stream=True)["cache_prompt"] is True
    assert "cache_prompt" not in cloud._payload(messages, stream=True)
