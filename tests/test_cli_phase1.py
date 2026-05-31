from pathlib import Path


def test_session_round_trip_uses_safe_name(tmp_path, monkeypatch):
    from atulya import cli

    monkeypatch.setenv("ATULYA_CLI_SESSION_DIR", str(tmp_path))
    history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "namaste"},
        {"role": "user", "content": "trim"},
    ]

    path = cli._save_session("demo/session", history, limit=2)

    assert path == tmp_path / "sessions" / "demo_session.json"
    assert cli._load_session("demo/session") == history[-2:]


def test_load_session_ignores_invalid_payload(tmp_path, monkeypatch):
    from atulya import cli

    monkeypatch.setenv("ATULYA_CLI_SESSION_DIR", str(tmp_path))
    path = tmp_path / "sessions" / "bad.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"not":"a list"}', encoding="utf-8")

    assert cli._load_session("bad") == []


def test_merge_env_defaults_preserves_existing_values(tmp_path):
    from atulya import cli

    env_path = Path(tmp_path) / ".env"
    env_path.write_text("ATULYA_OLLAMA_MODEL=custom\n", encoding="utf-8")

    changed = cli._merge_env_defaults(
        env_path,
        {
            "ATULYA_OLLAMA_MODEL": "llama3",
            "ATULYA_GROQ_MODEL": "llama-3.3-70b-versatile",
        },
    )
    content = env_path.read_text(encoding="utf-8")

    assert changed == {"ATULYA_GROQ_MODEL": "llama-3.3-70b-versatile"}
    assert "ATULYA_OLLAMA_MODEL=custom" in content
    assert "ATULYA_GROQ_MODEL=llama-3.3-70b-versatile" in content
