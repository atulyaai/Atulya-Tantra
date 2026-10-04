import os

from atulya.parivesh import load_env, parse_env


def test_parses_what_notepad_and_humans_write():
    text = '﻿OPENROUTER_API_KEY = sk-or-1  \n# comment\nexport A="b c" # note\nB=\'q\'\nC=plain # trailing\nEMPTY=\nnoequals\n'
    assert parse_env(text) == {"OPENROUTER_API_KEY": "sk-or-1", "A": "b c", "B": "q", "C": "plain", "EMPTY": ""}


def test_load_env_sets_missing_keys_and_never_overrides(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_bytes("﻿OPENCODE_API_KEY=abc\nGROQ_API_KEY=from-file\n".encode("utf-8"))
    monkeypatch.setenv("OPENCODE_API_KEY", "placeholder")  # registers the restore, so the load below cannot leak
    monkeypatch.delenv("OPENCODE_API_KEY")
    monkeypatch.setenv("GROQ_API_KEY", "already-set")
    assert load_env([f, tmp_path / "missing.env"]) == [f]
    assert os.environ["OPENCODE_API_KEY"] == "abc" and os.environ["GROQ_API_KEY"] == "already-set"


def test_opencode_go_is_a_real_brain(monkeypatch):
    from atulya.vahak import OpenCodeGoProvider, OpenRouterProvider, ProviderRouter

    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    monkeypatch.delenv("OPENCODE_GO_API_KEY", raising=False)
    assert not OpenCodeGoProvider().is_available()
    monkeypatch.setenv("OPENCODE_API_KEY", "k")
    p = OpenCodeGoProvider()
    assert p.is_available() and p.name() == "OpenCode Go" and p.URL == "https://opencode.ai/zen/go/v1/chat/completions"
    assert OpenRouterProvider.URL.startswith("https://openrouter.ai")  # parent unchanged
    monkeypatch.setenv("ATULYA_OPENCODE_URL", "https://x.test/v1/")
    assert p.URL == "https://x.test/v1/chat/completions"
    assert any(isinstance(x, OpenCodeGoProvider) for x in ProviderRouter().providers)
