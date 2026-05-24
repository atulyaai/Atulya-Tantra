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
