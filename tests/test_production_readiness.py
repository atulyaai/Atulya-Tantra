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
