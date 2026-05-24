"""Tests for HeartbeatSystem — health checks and status persistence."""

import tempfile
import json


class TestHeartbeatSystem:
    """Tests for HeartbeatSystem (non-async parts)."""

    def test_initialization(self):
        from atulya.heartbeat import HeartbeatSystem
        with tempfile.TemporaryDirectory() as tmp:
            hb = HeartbeatSystem(data_dir=tmp)
            assert hb.data_dir.exists()
            assert hb._checks == []
            assert hb._running is False

    def test_memory_check_import_fallback(self):
        """_memory_check should handle missing psutil gracefully."""
        from atulya.heartbeat import HeartbeatSystem
        import asyncio
        with tempfile.TemporaryDirectory() as tmp:
            hb = HeartbeatSystem(data_dir=tmp)
            result = asyncio.run(hb._memory_check())
            assert result.name == "memory"
            assert result.status == "ok"

    def test_disk_check(self):
        from atulya.heartbeat import HeartbeatSystem
        import asyncio
        with tempfile.TemporaryDirectory() as tmp:
            hb = HeartbeatSystem(data_dir=tmp)
            result = asyncio.run(hb._disk_check())
            assert result.name == "disk"
            assert result.status in ("ok", "warning", "error")

    def test_maintenance_check(self):
        from atulya.heartbeat import HeartbeatSystem
        import asyncio
        with tempfile.TemporaryDirectory() as tmp:
            hb = HeartbeatSystem(data_dir=tmp)
            result = asyncio.run(hb._maintenance_check())
            assert result.name == "maintenance"
            assert result.status in ("ok", "warning", "info", "error")

    def test_save_status_creates_file(self):
        from atulya.heartbeat import HeartbeatSystem
        import asyncio
        with tempfile.TemporaryDirectory() as tmp:
            hb = HeartbeatSystem(data_dir=tmp)
            asyncio.run(hb._run_checks())
            # File is heartbeat_status.json, not heartbeat.json
            status_file = hb.data_dir / "heartbeat_status.json"
            assert status_file.exists()
            data = json.loads(status_file.read_text())
            assert "last_check" in data
            assert "checks" in data

    def test_healthcheck_dataclass(self):
        from atulya.heartbeat import HealthCheck
        hc = HealthCheck(name="test", status="ok", message="all good")
        assert hc.name == "test"
        assert hc.status == "ok"
        assert hc.message == "all good"
        assert hc.timestamp > 0

    def test_get_status_empty(self):
        """get_status returns default when no file exists."""
        from atulya.heartbeat import HeartbeatSystem
        with tempfile.TemporaryDirectory() as tmp:
            hb = HeartbeatSystem(data_dir=tmp)
            status = hb.get_status()
            assert status["last_check"] == 0
            assert status["checks"] == []

    def test_task_check_no_crash(self):
        """_task_check should handle missing kanban directory."""
        from atulya.heartbeat import HeartbeatSystem
        import asyncio
        with tempfile.TemporaryDirectory() as tmp:
            hb = HeartbeatSystem(data_dir=tmp)
            result = asyncio.run(hb._task_check())
            assert result.name == "tasks"

    def test_start_stop(self):
        from atulya.heartbeat import HeartbeatSystem
        import asyncio
        with tempfile.TemporaryDirectory() as tmp:
            hb = HeartbeatSystem(data_dir=tmp)
            hb._interval = 0.1
            # Quick start/stop to ensure it doesn't crash
            async def quick_test():
                task = asyncio.create_task(hb.start())
                await asyncio.sleep(0.05)
                await hb.stop()
                await task
            asyncio.run(quick_test())
            status_file = hb.data_dir / "heartbeat_status.json"
            assert status_file.exists()


"""Tests for Identity — personality config loading and privacy system."""

import os
import tempfile
import json


class TestIdentity:
    """Tests for Identity class — config loading, personality, privacy."""

    def test_default_config(self):
        """When no config file exists, Identity uses sensible defaults."""
        from atulya.persona import Persona
        with tempfile.TemporaryDirectory() as tmp:
            ident = Persona(os.path.join(tmp, "identity.json"))
            assert ident.name == "Atulya"
            assert ident.personality == {"tone": "warm and helpful"}
            assert "what_i_am" in ident.self_knowledge

    def test_load_from_config(self):
        from atulya.persona import Persona
        cfg = {
            "name": "TestBot",
            "personality": {"tone": "cheerful"},
            "self_knowledge": {"what_i_am": "A test bot.", "how_i_work": "Testing",
                               "languages": ["en", "fr"]},
            "privacy": {
                "default_role": "user",
                "roles": {
                    "user": {"can_see": ["name"]},
                    "superuser": {"can_see": ["everything"]},
                },
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "identity.json")
            with open(cfg_path, "w") as f:
                json.dump(cfg, f)
            ident = Persona(cfg_path)
            assert ident.name == "TestBot"
            assert ident.personality == {"tone": "cheerful"}
            assert ident.self_knowledge["what_i_am"] == "A test bot."

    def test_get_profile_user(self):
        from atulya.persona import Persona
        with tempfile.TemporaryDirectory() as tmp:
            ident = Persona(os.path.join(tmp, "identity.json"))
            # get_system_prompt generates a role-appropriate identity string
            prompt = ident.get_system_prompt(role="user")
            assert isinstance(prompt, str)
            assert "Atulya" in prompt or "You are" in prompt

    def test_get_profile_superuser(self):
        from atulya.persona import Persona
        with tempfile.TemporaryDirectory() as tmp:
            ident = Persona(os.path.join(tmp, "identity.json"))
            prompt = ident.get_system_prompt(role="superuser")
            assert isinstance(prompt, str)
            # Superuser sees everything
            assert "NP-DNA" in prompt or "Architecture" in prompt

    def test_privacy_rules_property(self):
        from atulya.persona import Persona
        with tempfile.TemporaryDirectory() as tmp:
            ident = Persona(os.path.join(tmp, "identity.json"))
            rules = ident.privacy_rules
            assert isinstance(rules, list)

    def test_format_for_training(self):
        from atulya.persona import Persona
        with tempfile.TemporaryDirectory() as tmp:
            ident = Persona(os.path.join(tmp, "identity.json"))
            samples = ident.format_for_training()
            assert isinstance(samples, list)
            assert len(samples) > 0
            assert "instruction" in samples[0]
            assert "output" in samples[0]

    def test_self_knowledge_languages(self):
        from atulya.persona import Persona
        with tempfile.TemporaryDirectory() as tmp:
            ident = Persona(os.path.join(tmp, "identity.json"))
            sk = ident.self_knowledge
            # Self-knowledge should include languages
            assert "languages" in sk

    def test_name_from_config(self):
        from atulya.persona import Persona
        cfg = {"name": "CustomAI", "personality": {}, "self_knowledge": {}}
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "identity.json")
            json.dump(cfg, open(cfg_path, "w"))
            ident = Persona(cfg_path)
            assert ident.name == "CustomAI"

    def test_markdown_fallback(self):
        from atulya.persona import Persona
        with tempfile.TemporaryDirectory() as tmp:
            soul = os.path.join(tmp, "SOUL.md")
            with open(soul, "w") as f:
                f.write("# MarkdownBot\n\n- personality: curious\n- tone: calm\n")
            persona = Persona(os.path.join(tmp, "missing.json"), data_dir=tmp)
            assert persona.name == "MarkdownBot"
            assert "curious" in persona.build_system_prompt()
