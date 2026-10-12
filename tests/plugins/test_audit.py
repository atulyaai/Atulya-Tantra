"""Audit log tests: every tool run recorded, secrets scrubbed, API readable."""
from __future__ import annotations

import json
from pathlib import Path

from tools.plugins.audit import AuditLog, init_audit_log, get_audit_log, record_tool_run


def test_audit_log_records_tool_run(tmp_path: Path) -> None:
    log = AuditLog(tmp_path)
    entry = log.record(
        user_id="admin",
        channel="telegram",
        tool="get_weather",
        args={"place": "Pune", "when": "today"},
        outcome="ok",
        duration_ms=150,
    )
    assert entry.tool == "get_weather"
    assert entry.outcome == "ok"
    assert entry.channel == "telegram"
    recent = log.recent()
    assert len(recent) == 1
    assert recent[0]["tool"] == "get_weather"
    assert recent[0]["channel"] == "telegram"


def test_audit_log_scrubs_secrets(tmp_path: Path) -> None:
    log = AuditLog(tmp_path)
    log.record(
        user_id="admin",
        channel="web",
        tool="open_url",
        args={"url": "https://example.com", "api_key": "sk-abc123secret", "token": "Bearer xyz789"},
        outcome="ok",
    )
    recent = log.recent()
    args_summary = recent[0]["args_summary"]
    assert "sk-abc123secret" not in args_summary
    assert "xyz789" not in args_summary
    assert "[REDACTED]" in args_summary


def test_audit_log_persists_to_disk(tmp_path: Path) -> None:
    log = AuditLog(tmp_path)
    log.record(user_id="admin", channel="web", tool="calculate", args={"expression": "2+2"}, outcome="ok")

    # Re-create from disk
    log2 = AuditLog(tmp_path)
    recent = log2.recent()
    assert len(recent) == 1
    assert recent[0]["tool"] == "calculate"
    assert recent[0]["expression" if False else "args_summary"] == "expression=2+2"


def test_audit_log_ring_buffer_limit(tmp_path: Path) -> None:
    log = AuditLog(tmp_path)
    for i in range(600):
        log.record(user_id="admin", channel="web", tool=f"tool_{i}", args={}, outcome="ok")
    recent = log.recent(limit=600)
    assert len(recent) == 500  # capped at MAX_ENTRIES


def test_audit_log_clear(tmp_path: Path) -> None:
    log = AuditLog(tmp_path)
    log.record(user_id="admin", channel="web", tool="test", args={}, outcome="ok")
    assert len(log.recent()) == 1
    log.clear()
    assert len(log.recent()) == 0


def test_global_audit_log_singleton(tmp_path: Path) -> None:
    log = init_audit_log(tmp_path)
    assert get_audit_log() is log
    record_tool_run(user_id="admin", channel="mcp", tool="get_time", args={}, outcome="ok")
    recent = log.recent()
    assert len(recent) == 1
    assert recent[0]["tool"] == "get_time"


def test_audit_log_jsonl_format(tmp_path: Path) -> None:
    log = AuditLog(tmp_path)
    log.record(user_id="admin", channel="web", tool="get_news", args={"limit": 5}, outcome="ok")
    lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["tool"] == "get_news"
    assert data["user_id"] == "admin"
    assert data["channel"] == "web"
    assert "at" in data
