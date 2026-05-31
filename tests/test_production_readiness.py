import json


def test_readiness_reports_candidate_without_provider(tmp_path, monkeypatch):
    from atulya.production_readiness import run_readiness_checks

    (tmp_path / "atulya").mkdir()
    (tmp_path / "atulya" / "llm.py").write_text("", encoding="utf-8")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "mcp_servers.json").write_text(json.dumps({"servers": []}), encoding="utf-8")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ATULYA_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("ATULYA_TELEGRAM_ALLOWLIST", raising=False)

    report = run_readiness_checks(tmp_path)

    assert report["grade"] == "production-candidate"
    assert any(item["name"] == "Free inference" for item in report["blocking"])


def test_readiness_passes_required_checks_with_free_key(tmp_path, monkeypatch):
    from atulya.production_readiness import run_readiness_checks

    (tmp_path / "atulya").mkdir()
    (tmp_path / "atulya" / "llm.py").write_text("", encoding="utf-8")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "mcp_servers.json").write_text(json.dumps({"servers": []}), encoding="utf-8")
    monkeypatch.setenv("GROQ_API_KEY", "demo")
    monkeypatch.delenv("ATULYA_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("ATULYA_TELEGRAM_ALLOWLIST", raising=False)

    report = run_readiness_checks(tmp_path)

    assert report["grade"] == "production-ready"
    assert report["passed_required"] == report["total_required"]


def test_readiness_blocks_enabled_google_drive_without_key(tmp_path, monkeypatch):
    from atulya.production_readiness import run_readiness_checks

    (tmp_path / "atulya").mkdir()
    (tmp_path / "atulya" / "llm.py").write_text("", encoding="utf-8")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "mcp_servers.json").write_text(
        json.dumps({"servers": [{"name": "google_drive", "enabled": True}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENROUTER_API_KEY", "demo")
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_KEY", raising=False)

    report = run_readiness_checks(tmp_path)

    assert report["grade"] == "production-candidate"
    assert any("GOOGLE_SERVICE_ACCOUNT_KEY" in item["detail"] for item in report["blocking"])


def test_readiness_blocks_enabled_gmail_without_oauth(tmp_path, monkeypatch):
    from atulya.production_readiness import run_readiness_checks

    (tmp_path / "atulya").mkdir()
    (tmp_path / "atulya" / "llm.py").write_text("", encoding="utf-8")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "mcp_servers.json").write_text(
        json.dumps({"servers": [{"name": "gmail", "enabled": True}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENROUTER_API_KEY", "demo")
    for key in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"):
        monkeypatch.delenv(key, raising=False)

    report = run_readiness_checks(tmp_path)

    assert report["grade"] == "production-candidate"
    assert any("GMAIL_REFRESH_TOKEN" in item["detail"] for item in report["blocking"])
