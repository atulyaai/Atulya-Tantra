"""Tests for atulya/adhar.py."""

import os

from atulya import adhar as kosh
from atulya.adhar import load_env, parse_env


# ── test_kosh ────────────────────────────────────────────────────────────
def test_old_data_folder_is_moved_once_with_its_files(tmp_path):
    (tmp_path / "data" / "agent").mkdir(parents=True)
    (tmp_path / "data" / "agent" / "money.json").write_text('{"a": 1}')
    assert kosh.migrate(tmp_path) == "moved data to kosh"
    assert (tmp_path / "kosh" / "agent" / "money.json").read_text() == '{"a": 1}'
    assert not (tmp_path / "data").exists()
    assert kosh.migrate(tmp_path) == "nothing to do"


def test_existing_kosh_is_never_overwritten(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "old.txt").write_text("old")
    (tmp_path / "kosh").mkdir()
    (tmp_path / "kosh" / "new.txt").write_text("new")
    assert kosh.migrate(tmp_path) == "nothing to do"
    assert (tmp_path / "kosh" / "new.txt").read_text() == "new" and (tmp_path / "data" / "old.txt").exists()


def test_no_data_folder_is_fine(tmp_path):
    assert kosh.migrate(tmp_path) == "nothing to do"


# ── test_envfile ────────────────────────────────────────────────────────────
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
    from atulya.mastishk import OpenCodeGoProvider, OpenRouterProvider, ProviderRouter

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

